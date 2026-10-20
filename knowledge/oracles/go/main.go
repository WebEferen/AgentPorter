// AgentPorter oracle driver for Go sources (see knowledge/oracles/CONTRACT.md).
// Go cannot call functions by name, so every call id is listed in dispatch.go.
package main

import (
	"errors"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
	"time"
)

const driver = "agentporter/knowledge/oracles/go"

// Call runs one case. Return the value, or the error the source returned.
type Call func(in Input) (any, error)

type unitFile struct {
	Unit  string           `json:"unit"`
	Kind  string           `json:"kind"`
	Cases []map[string]any `json:"cases"`
}

type multiFlag []string

func (m *multiFlag) String() string     { return strings.Join(*m, ",") }
func (m *multiFlag) Set(s string) error { *m = append(*m, s); return nil }

func runCase(fn Call, in Input, timeout time.Duration) (outcome map[string]any, elapsed time.Duration, argErr error) {
	type result struct {
		value any
		err   error
		panic any
	}
	done := make(chan result, 1)
	start := time.Now()
	go func() {
		defer func() {
			if r := recover(); r != nil {
				done <- result{panic: r}
			}
		}()
		v, err := fn(in)
		done <- result{value: v, err: err}
	}()
	select {
	case r := <-done:
		elapsed = time.Since(start)
		if r.panic != nil {
			if ae, ok := r.panic.(ArgError); ok {
				return nil, elapsed, ae
			}
			return map[string]any{"kind": "error", "category": "panic", "message": fmt.Sprint(r.panic)}, elapsed, nil
		}
		if r.err != nil {
			return map[string]any{"kind": "error", "category": ErrorCategory(r.err), "message": r.err.Error()}, elapsed, nil
		}
		return map[string]any{"kind": "value", "value": Serialize(r.value)}, elapsed, nil
	case <-time.After(timeout):
		return map[string]any{"kind": "error", "category": "timeout", "message": fmt.Sprintf("timed out after %s", timeout)}, timeout, nil
	}
}

func readJSON(path string, out any) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return DecodeJSON(data, out)
}

func writeJSON(path string, v any) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	data, err := EncodeJSON(v)
	if err != nil {
		return err
	}
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, data, 0o644); err != nil {
		return err
	}
	return os.Rename(tmp, path)
}

func fail(format string, a ...any) {
	fmt.Fprintf(os.Stderr, "oracle: "+format+"\n", a...)
	os.Exit(2)
}

func main() {
	workspace := flag.String("workspace", ".porter", "path to the .porter workspace")
	version := flag.String("package-version", "", "upstream version (default: config.json)")
	commit := flag.String("commit", "", "upstream commit (default: config.json)")
	timeout := flag.Float64("timeout", 10, "seconds per case")
	var units multiFlag
	flag.Var(&units, "unit", "unit to record (repeatable; default: every expanded unit)")
	flag.Parse()

	var config struct {
		Source struct {
			Commit  *string `json:"commit"`
			Package *struct {
				Name    *string `json:"name"`
				Version *string `json:"version"`
			} `json:"package"`
		} `json:"source"`
	}
	if err := readJSON(filepath.Join(*workspace, "config.json"), &config); err != nil {
		fail("cannot read config.json: %v", err)
	}
	name, ver, sha := "", *version, *commit
	if p := config.Source.Package; p != nil {
		if p.Name != nil {
			name = *p.Name
		}
		if ver == "" && p.Version != nil {
			ver = *p.Version
		}
	}
	if sha == "" && config.Source.Commit != nil {
		sha = *config.Source.Commit
	}
	if ver == "" {
		ver = "unknown"
	}
	expandedDir := filepath.Join(*workspace, "oracle", "expanded")
	if len(units) == 0 {
		matches, _ := filepath.Glob(filepath.Join(expandedDir, "*.json"))
		for _, m := range matches {
			units = append(units, strings.TrimSuffix(filepath.Base(m), ".json"))
		}
		sort.Strings(units)
	}
	if len(units) == 0 {
		fail("no expanded cases in %s; run porter.py fixtures expand", expandedDir)
	}
	if name == "" {
		name = units[0]
	}
	for _, unit := range units {
		var spec unitFile
		if err := readJSON(filepath.Join(expandedDir, unit+".json"), &spec); err != nil {
			fail("cannot read expanded cases for %s: %v", unit, err)
		}
		if spec.Kind == "cli" {
			fail("unit %s is a CLI unit; record it with porter.py cli record", unit)
		}
		cases := make([]map[string]any, 0, len(spec.Cases))
		timings := map[string]float64{}
		errCount := 0
		for _, raw := range spec.Cases {
			id, _ := raw["case"].(string)
			call, _ := raw["call"].(string)
			fn, ok := dispatch[call]
			if !ok {
				fail("case %s: no dispatch entry for %q; add it to dispatch.go", id, call)
			}
			in, err := toInput(raw["input"])
			if err != nil {
				fail("case %s: %v", id, err)
			}
			outcome, elapsed, argErr := runCase(fn, in, time.Duration(*timeout*float64(time.Second)))
			if argErr != nil {
				fail("case %s (%s): %v", id, call, argErr)
			}
			if outcome["kind"] == "error" {
				errCount++
				if mp, ok := raw["messagePattern"].(string); ok && mp != "" {
					outcome["messagePattern"] = mp
				}
			}
			out := map[string]any{}
			for k, v := range raw {
				if k != "messagePattern" {
					out[k] = v
				}
			}
			out["expect"] = outcome
			cases = append(cases, out)
			timings[id] = float64(elapsed.Microseconds()) / 1000
		}
		fixture := map[string]any{
			"schema": 1,
			"unit":   unit,
			"oracle": map[string]any{
				"language":   "go",
				"package":    name,
				"version":    ver,
				"commit":     nullable(sha),
				"runtime":    runtime.Version(),
				"driver":     driver,
				"recordedAt": time.Now().UTC().Format("2006-01-02T15:04:05Z"),
			},
			"cases": cases,
		}
		if err := writeJSON(filepath.Join(*workspace, "fixtures", unit, "oracle.json"), fixture); err != nil {
			fail("%v", err)
		}
		if err := writeJSON(filepath.Join(*workspace, "oracle", "timings", unit+".json"), map[string]any{"unit": unit, "cases": timings}); err != nil {
			fail("%v", err)
		}
		fmt.Printf("%s: recorded %d cases (%d errors) -> fixtures/%s/oracle.json\n", unit, len(cases), errCount, unit)
	}
}

func nullable(s string) any {
	if s == "" {
		return nil
	}
	return s
}

func toInput(raw any) (Input, error) {
	var in Input
	data, err := EncodeJSON(raw)
	if err != nil {
		return in, err
	}
	if err := DecodeJSON(data, &in); err != nil {
		return in, errors.New("input does not match {args, kwargs, init}: " + err.Error())
	}
	return in, nil
}
