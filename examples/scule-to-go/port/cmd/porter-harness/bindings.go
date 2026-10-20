package main

import (
	"encoding/json"

	"github.com/agentporter-examples/scule"
)

var bindings = map[string]Call{
	"./src/index.ts:isUppercase": func(in Input) (any, error) {
		upper, ok := scule.IsUppercase(str(in, 0))
		if !ok {
			return Undefined, nil
		}
		return upper, nil
	},
	"./src/index.ts:splitByCase": func(in Input) (any, error) {
		if in.IsUndefined(1) {
			return scule.SplitByCase(str(in, 0)), nil
		}
		return scule.SplitByCaseWith(str(in, 0), in.Strs(1)), nil
	},
	"./src/index.ts:upperFirst": func(in Input) (any, error) {
		return scule.UpperFirst(str(in, 0)), nil
	},
	"./src/index.ts:lowerFirst": func(in Input) (any, error) {
		return scule.LowerFirst(str(in, 0)), nil
	},
	"./src/index.ts:pascalCase": withOpts(scule.PascalCase[string], scule.PascalCase[[]string]),
	"./src/index.ts:camelCase":  withOpts(scule.CamelCase[string], scule.CamelCase[[]string]),
	"./src/index.ts:trainCase":  withOpts(scule.TrainCase[string], scule.TrainCase[[]string]),
	"./src/index.ts:titleCase":  withOpts(scule.TitleCase[string], scule.TitleCase[[]string]),
	"./src/index.ts:kebabCase": func(in Input) (any, error) {
		var joiner []string
		if !in.IsUndefined(1) && in.Arg(1) != nil {
			joiner = []string{in.Str(1)}
		}
		if words, ok := strs(in, 0); ok {
			return scule.KebabCase(words, joiner...), nil
		}
		return scule.KebabCase(str(in, 0), joiner...), nil
	},
	"./src/index.ts:snakeCase": plain(scule.SnakeCase[string], scule.SnakeCase[[]string]),
	"./src/index.ts:flatCase":  plain(scule.FlatCase[string], scule.FlatCase[[]string]),
}

// strs reads argument i when it is a JSON array.
func strs(in Input, i int) ([]string, bool) {
	if i < in.Len() {
		if _, ok := in.Arg(i).([]any); ok {
			return in.Strs(i), true
		}
	}
	return nil, false
}

// withOpts binds a converter taking a string or []string and optional
// CaseOptions; {normalize: x} becomes CaseOptions{Normalize: truthy(x)}.
func withOpts(s func(string, ...scule.CaseOptions) string, a func([]string, ...scule.CaseOptions) string) Call {
	return func(in Input) (any, error) {
		var opts []scule.CaseOptions
		if !in.IsUndefined(1) {
			if m, ok := in.Arg(1).(map[string]any); ok {
				opts = []scule.CaseOptions{{Normalize: truthy(m["normalize"])}}
			}
		}
		if words, ok := strs(in, 0); ok {
			return a(words, opts...), nil
		}
		return s(str(in, 0), opts...), nil
	}
}

func plain(s func(string) string, a func([]string) string) Call {
	return func(in Input) (any, error) {
		if words, ok := strs(in, 0); ok {
			return a(words), nil
		}
		return s(str(in, 0)), nil
	}
}

// truthy is JavaScript truthiness for the values a fixture can hold.
func truthy(v any) bool {
	switch x := v.(type) {
	case nil:
		return false
	case bool:
		return x
	case string:
		return x != ""
	case json.Number:
		f, err := x.Float64()
		return err == nil && f != 0
	case map[string]any:
		return x["$undefined"] != true
	}
	return true
}

// str reads string argument i; a missing or undefined argument is "".
func str(in Input, i int) string {
	if in.IsUndefined(i) {
		return ""
	}
	return in.Str(i)
}
