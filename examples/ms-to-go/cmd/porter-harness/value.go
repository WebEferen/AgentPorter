package main

// Shared by the AgentPorter Go oracle and Go harness: input accessors and contract value serialization
// (knowledge/oracles/CONTRACT.md). Keep both copies identical.

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"math/big"
	"reflect"
	"sort"
	"strconv"
	"time"
)

const safeInt = 1 << 53

// Input is one case input: {"args": [...], "kwargs": {...}, "init": {"args": [...], "kwargs": {...}}}.
type Input struct {
	Args   []any          `json:"args"`
	Kwargs map[string]any `json:"kwargs"`
	Init   *Input         `json:"init"`
}

// ArgError means a case input does not fit the Go signature: a case authoring problem, not an outcome.
type ArgError struct{ msg string }

func (e ArgError) Error() string { return e.msg }

func argFail(format string, a ...any) { panic(ArgError{fmt.Sprintf(format, a...)}) }

func (in Input) Len() int { return len(in.Args) }

func (in Input) Arg(i int) any {
	if i >= len(in.Args) {
		argFail("argument %d missing (have %d)", i, len(in.Args))
	}
	return in.Args[i]
}

func (in Input) Has(name string) bool { _, ok := in.Kwargs[name]; return ok }

func (in Input) Kw(name string) any { return in.Kwargs[name] }

func (in Input) Str(i int) string { return asString(in.Arg(i), i) }

func (in Input) Int(i int) int { return int(asInt64(in.Arg(i), i)) }

func (in Input) Int64(i int) int64 { return asInt64(in.Arg(i), i) }

func (in Input) Float(i int) float64 { return asFloat(in.Arg(i), i) }

func (in Input) Bool(i int) bool {
	b, ok := in.Arg(i).(bool)
	if !ok {
		argFail("argument %d: want bool, got %T", i, in.Arg(i))
	}
	return b
}

func (in Input) Bytes(i int) []byte {
	m, ok := in.Arg(i).(map[string]any)
	if s, isStr := m["$bytes"].(string); ok && isStr {
		b, err := base64.StdEncoding.DecodeString(s)
		if err == nil {
			return b
		}
	}
	if s, isStr := in.Arg(i).(string); isStr {
		return []byte(s)
	}
	argFail("argument %d: want {\"$bytes\": ...} or string, got %T", i, in.Arg(i))
	return nil
}

func (in Input) Strs(i int) []string {
	raw, ok := in.Arg(i).([]any)
	if !ok {
		argFail("argument %d: want array, got %T", i, in.Arg(i))
	}
	out := make([]string, len(raw))
	for j, v := range raw {
		out[j] = asString(v, i)
	}
	return out
}

func (in Input) Time(i int) time.Time {
	m, _ := in.Arg(i).(map[string]any)
	s, ok := m["$datetime"].(string)
	if !ok {
		argFail("argument %d: want {\"$datetime\": ...}", i)
	}
	t, err := time.Parse(time.RFC3339Nano, s)
	if err != nil {
		argFail("argument %d: %v", i, err)
	}
	return t
}

func asString(v any, i int) string {
	s, ok := v.(string)
	if !ok {
		argFail("argument %d: want string, got %T", i, v)
	}
	return s
}

func asInt64(v any, i int) int64 {
	switch x := v.(type) {
	case json.Number:
		n, err := x.Int64()
		if err != nil {
			argFail("argument %d: want integer, got %s", i, x)
		}
		return n
	case map[string]any:
		if s, ok := x["$int"].(string); ok {
			n, err := strconv.ParseInt(s, 10, 64)
			if err != nil {
				argFail("argument %d: %v", i, err)
			}
			return n
		}
	}
	argFail("argument %d: want integer, got %T", i, v)
	return 0
}

func asFloat(v any, i int) float64 {
	switch x := v.(type) {
	case json.Number:
		f, err := x.Float64()
		if err != nil {
			argFail("argument %d: %v", i, err)
		}
		return f
	case map[string]any:
		switch x["$float"] {
		case "nan":
			return math.NaN()
		case "inf":
			return math.Inf(1)
		case "-inf":
			return math.Inf(-1)
		case "-0":
			return math.Copysign(0, -1)
		}
	}
	argFail("argument %d: want number, got %T", i, v)
	return 0
}

// DecodeJSON parses JSON keeping numbers as json.Number.
func DecodeJSON(data []byte, out any) error {
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.UseNumber()
	return dec.Decode(out)
}

// EncodeJSON writes indented JSON without HTML escaping.
func EncodeJSON(v any) ([]byte, error) {
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	enc.SetIndent("", "  ")
	if err := enc.Encode(v); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}

// Undefined marks "no value" for ports of APIs that return undefined.
type undefined struct{}

var Undefined = undefined{}

var (
	timeType   = reflect.TypeOf(time.Time{})
	bigIntType = reflect.TypeOf(big.Int{})
	errorIface = reflect.TypeOf((*error)(nil)).Elem()
)

func canonical(v any) string {
	b, _ := json.Marshal(v)
	return string(b)
}

func serializeFloat(f float64) any {
	switch {
	case math.IsNaN(f):
		return map[string]any{"$float": "nan"}
	case math.IsInf(f, 1):
		return map[string]any{"$float": "inf"}
	case math.IsInf(f, -1):
		return map[string]any{"$float": "-inf"}
	case f == 0 && math.Signbit(f):
		return map[string]any{"$float": "-0"}
	}
	return f
}

// Serialize converts a Go value to the contract's JSON form.
func Serialize(v any) any { return serialize(reflect.ValueOf(v), 0) }

func serialize(v reflect.Value, depth int) any {
	if !v.IsValid() {
		return nil
	}
	if depth > 64 {
		return map[string]any{"$type": v.Type().String(), "truncated": true}
	}
	if v.Type() == reflect.TypeOf(Undefined) {
		return map[string]any{"$undefined": true}
	}
	if v.Kind() == reflect.Interface || v.Kind() == reflect.Pointer {
		if v.IsNil() {
			return nil
		}
		if v.Kind() == reflect.Pointer && v.Type().Elem() == bigIntType {
			return map[string]any{"$int": v.Interface().(*big.Int).String()}
		}
		if v.Type().Implements(errorIface) {
			return map[string]any{"$type": shortType(v.Type()), "message": v.Interface().(error).Error()}
		}
		return serialize(v.Elem(), depth+1)
	}
	if v.Type().Implements(errorIface) {
		return map[string]any{"$type": shortType(v.Type()), "message": v.Interface().(error).Error()}
	}
	switch v.Kind() {
	case reflect.Bool:
		return v.Bool()
	case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
		n := v.Int()
		if n > safeInt || n < -safeInt {
			return map[string]any{"$int": strconv.FormatInt(n, 10)}
		}
		return n
	case reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64, reflect.Uintptr:
		n := v.Uint()
		if n > safeInt {
			return map[string]any{"$int": strconv.FormatUint(n, 10)}
		}
		return n
	case reflect.Float32:
		f, _ := strconv.ParseFloat(strconv.FormatFloat(v.Float(), 'g', -1, 32), 64)
		return serializeFloat(f)
	case reflect.Float64:
		return serializeFloat(v.Float())
	case reflect.String:
		return v.String()
	case reflect.Slice, reflect.Array:
		if v.Type().Elem().Kind() == reflect.Uint8 {
			b := make([]byte, v.Len())
			reflect.Copy(reflect.ValueOf(b), v)
			return map[string]any{"$bytes": base64.StdEncoding.EncodeToString(b)}
		}
		out := make([]any, v.Len())
		for i := range out {
			out[i] = serialize(v.Index(i), depth+1)
		}
		return out
	case reflect.Map:
		if v.Type().Key().Kind() == reflect.String {
			out := map[string]any{}
			for _, k := range v.MapKeys() {
				out[k.String()] = serialize(v.MapIndex(k), depth+1)
			}
			return out
		}
		entries := make([][]any, 0, v.Len())
		for _, k := range v.MapKeys() {
			entries = append(entries, []any{serialize(k, depth+1), serialize(v.MapIndex(k), depth+1)})
		}
		sort.Slice(entries, func(a, b int) bool { return canonical(entries[a][0]) < canonical(entries[b][0]) })
		return map[string]any{"$map": entries}
	case reflect.Struct:
		if v.Type() == timeType {
			return map[string]any{"$datetime": v.Interface().(time.Time).Format(time.RFC3339Nano)}
		}
		if v.Type() == bigIntType {
			n := v.Interface().(big.Int)
			return map[string]any{"$int": n.String()}
		}
		out := map[string]any{"$type": shortType(v.Type())}
		for i := 0; i < v.NumField(); i++ {
			f := v.Type().Field(i)
			if !f.IsExported() {
				continue
			}
			name := f.Name
			if tag := f.Tag.Get("json"); tag != "" && tag != "-" {
				if comma := bytes.IndexByte([]byte(tag), ','); comma >= 0 {
					tag = tag[:comma]
				}
				if tag != "" {
					name = tag
				}
			}
			out[name] = serialize(v.Field(i), depth+1)
		}
		return out
	case reflect.Func:
		return map[string]any{"$type": "func"}
	case reflect.Chan:
		return map[string]any{"$type": "chan"}
	}
	return map[string]any{"$type": v.Type().String(), "repr": fmt.Sprint(v.Interface())}
}

func shortType(t reflect.Type) string {
	for t.Kind() == reflect.Pointer {
		t = t.Elem()
	}
	if t.Name() != "" {
		return t.Name()
	}
	return t.String()
}

// Sentinels names sentinel errors so they get a stable category, for example {io.EOF: "EOF"}.
var Sentinels = map[error]string{}

// ErrorCategory is the contract category for an error: a named sentinel, or the error's type name.
func ErrorCategory(err error) string {
	for s, name := range Sentinels {
		if errors.Is(err, s) {
			return name
		}
	}
	return shortType(reflect.TypeOf(err))
}
