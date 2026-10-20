package main

// AgentPorter parity harness for Go ports, see knowledge/oracles/CONTRACT.md. Copy harness.go, value.go and
// bindings.go into one directory of the port (for example cmd/porter-harness), then:
//   go run ./cmd/porter-harness --workspace .porter --run <run> [--unit <unit>]

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
	"time"
)

const driver = "agentporter/knowledge/harnesses/go"

// Call is one binding: it unpacks the case input, calls the port, and returns its result or error.
type Call func(in Input) (any, error)

type fixtureCase struct {
	Case   string          `json:"case"`
	Call   string          `json:"call"`
	Input  json.RawMessage `json:"input"`
	Expect struct {
		Kind string `json:"kind"`
	} `json:"expect"`
}

type multiFlag []string

func (m *multiFlag) String() string     { return strings.Join(*m, ",") }
func (m *multiFlag) Set(v string) error { *m = append(*m, v); return nil }

func runCase(call Call, in Input, timeout time.Duration) (outcome map[string]any) {
	done := make(chan map[string]any, 1)
	go func() {
		defer func() {
			if r := recover(); r != nil {
				if ae, ok := r.(ArgError); ok {
					done <- errorOutcome("BindingError", ae.Error())
					return
				}
				done <- errorOutcome("panic", fmt.Sprint(r))
			}
		}()
		v, err := call(in)
		if err != nil {
			done <- errorOutcome(ErrorCategory(err), err.Error())
			return
		}
		done <- map[string]any{"kind": "value", "value": Serialize(v)}
	}()
	select {
	case out := <-done:
		return out
	case <-time.After(timeout):
		return errorOutcome("timeout", fmt.Sprintf("timed out after %s", timeout))
	}
}

func errorOutcome(category, message string) map[string]any {
	return map[string]any{"kind": "error", "category": category, "message": message}
}

func writeJSON(path string, v any) error {
	data, err := EncodeJSON(v)
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	if err := os.WriteFile(path+".tmp", data, 0o644); err != nil {
		return err
	}
	return os.Rename(path+".tmp", path)
}

func fail(format string, a ...any) {
	fmt.Fprintf(os.Stderr, "harness: "+format+"\n", a...)
	os.Exit(2)
}

func main() {
	workspace := flag.String("workspace", ".porter", "workspace directory")
	run := flag.String("run", time.Now().UTC().Format("20060102T150405Z"), "run id under .porter/runs")
	timeout := flag.Float64("timeout", 10, "seconds per case")
	var units multiFlag
	flag.Var(&units, "unit", "unit to run (repeatable; default: every fixture unit)")
	flag.Parse()

	fixtures := filepath.Join(*workspace, "fixtures")
	if len(units) == 0 {
		entries, err := os.ReadDir(fixtures)
		if err != nil {
			fail("no fixtures under %s: %v", fixtures, err)
		}
		for _, e := range entries {
			if e.IsDir() {
				units = append(units, e.Name())
			}
		}
		sort.Strings(units)
	}
	if len(units) == 0 {
		fail("no fixtures under %s", fixtures)
	}
	missing := 0
	for _, unit := range units {
		files, _ := filepath.Glob(filepath.Join(fixtures, unit, "*.json"))
		if len(files) == 0 {
			fail("no fixtures for unit %s", unit)
		}
		sort.Strings(files)
		startedAt := time.Now().UTC().Format(time.RFC3339)
		results := []any{}
		errors := 0
		for _, f := range files {
			raw, err := os.ReadFile(f)
			if err != nil {
				fail("%v", err)
			}
			var fixture struct {
				Cases []fixtureCase `json:"cases"`
			}
			if err := json.Unmarshal(raw, &fixture); err != nil {
				fail("%s: %v", f, err)
			}
			for _, c := range fixture.Cases {
				if c.Expect.Kind == "cli" {
					continue
				}
				var in Input
				if len(c.Input) > 0 {
					if err := DecodeJSON(c.Input, &in); err != nil {
						fail("case %s: bad input: %v", c.Case, err)
					}
				}
				started := time.Now()
				var actual map[string]any
				if call, ok := bindings[c.Call]; ok {
					actual = runCase(call, in, time.Duration(*timeout*float64(time.Second)))
				} else {
					missing++
					actual = errorOutcome("MissingBinding", "no binding for "+c.Call)
				}
				if actual["kind"] == "error" {
					errors++
				}
				ms := float64(time.Since(started).Nanoseconds()) / 1e6
				results = append(results, map[string]any{"case": c.Case, "actual": actual, "durationMs": ms})
			}
		}
		out := map[string]any{
			"schema":    1,
			"unit":      unit,
			"runner":    map[string]any{"language": "go", "driver": driver, "runtime": runtime.Version()},
			"startedAt": startedAt,
			"results":   results,
		}
		if err := writeJSON(filepath.Join(*workspace, "runs", *run, unit+".json"), out); err != nil {
			fail("%v", err)
		}
		fmt.Printf("%s: ran %d cases (%d errors) -> runs/%s/%s.json\n", unit, len(results), errors, *run, unit)
	}
	if missing > 0 {
		fmt.Fprintf(os.Stderr, "harness: %d case(s) have no binding (recorded as MissingBinding)\n", missing)
	}
}
