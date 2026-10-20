# Parity report

Upstream: ms 2.1.3 (javascript, commit 1c6264b79549).
Port: github.com/agentporter-examples/ms in go. Evidence date: 2026-10-20. Harness run: final.
Fixtures: 1490 cases, 1458 exact, 8 normalized, 24 divergent, 0 failed, 0 missing.

| Unit | Level | Fixtures (exact / normalized / divergent / failed of total) | Reference tests (pass / total) | Divergences | Perf (median ratio) |
| --- | --- | --- | --- | --- | --- |
| index | DIVERGENT | 1458 / 8 / 24 / 0 of 1490 | 44 / 49 | empty-string, typed-input | 0.022x |

Levels: EXACT means every fixture matched byte for byte. EQUIVALENT means every fixture matched under
the normalization declared on the fixture. DIVERGENT means some cases differ on purpose (listed below).
ASSERTED means no oracle fixtures exist and ported reference tests carry the evidence. GAP means a known
mismatch remains.

## Intentional divergences

- **typed-input** (index): Inputs that exist only through JavaScript's dynamic typing cannot be passed to the Go API: a val that is undefined, null, a boolean, an array or an object (the source throws Error), and an options value other than an object or null, or an options.long other than true, false, null or absent (the source applies JavaScript truthiness). The harness reports these cases as BindingError. Why: Planned in strategy.md (scope gauntlet, idiom map rows Dynamic dispatch and Options) and logged in decisions.md on 2026-10-20. The idiomatic Go API is Parse(string), Format(float64) and FormatLong(float64); the compiler rules out the other value types, so the typeof check and the truthiness rules have nothing to act on. options null, {}, {long: true/false/null} and an undefined options stay in scope through the binding and are not covered here.
- **empty-string** (index): Parse("") returns (0, false), reported as undefined, where the JavaScript ms("") throws Error "val is not a non-empty string or a valid number. val=\"\"". Why: Planned in strategy.md (scope gauntlet) and logged in decisions.md on 2026-10-20. The source throws for "" to catch type confusion at a dynamic entry point; with a typed Parse(string) the empty string is just another string that is not a duration, and the comma-ok form has no error to return.
