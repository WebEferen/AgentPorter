# Unit report: index

Status: DONE. Parity: DIVERGENT. Attempts: 1.

## Checklist

| Task | Done at |
| --- | --- |
| read-contract | 2026-10-20T16:53:00Z |
| scaffold | 2026-10-20T16:55:51Z |
| implement | 2026-10-20T16:56:29Z |
| mark-divergences | 2026-10-20T16:56:48Z |
| port-tests | 2026-10-20T16:58:55Z |
| wire-fixtures | 2026-10-20T16:59:38Z |
| green | 2026-10-20T16:59:54Z |
| review | 2026-10-20T17:09:00Z (reviewer agent; no task event, the implement skill never records `review`) |
| apply-findings | 2026-10-20T17:09:42Z |
| verify | 2026-10-20T17:17:52Z |
| report | 2026-10-20 (this file) |
| commit | per-unit policy, `port(index): ...` |

## What was ported

- `ms.go`: `Parse(s string) (float64, bool)`, `Format(float64) (string, error)`,
  `FormatLong(float64) (string, error)`, `*InvalidValueError`. Parsing is an ASCII-only scanner (no
  `(?i)`, no Unicode case folding) with the 100-byte limit.
- `number.go`: `jsRound` (Math.round, ties toward +infinity, exact near 2^52) and `formatNumber`
  (ECMAScript Number::toString on top of `strconv.FormatFloat(x, 'e', -1, 64)`).
- `doc.go`, `example_test.go` (readme examples), `ms_test.go` (all 49 tests.js tests plus leak-list
  tests, coverage 96.1%), `go.mod` (`go 1.22`), `LICENSE`, `README.md`, `.github/workflows/ci.yml`.
- `cmd/porter-harness/`: plugin `harness.go` and `value.go` unchanged, `bindings.go` with one entry,
  `ms:default`.

## Decisions and divergences

- DIVERGENCE(typed-input): 20 fixtures with a non-string, non-number `val` or non-boolean `long` / non-object
  `options` cannot be expressed in the typed API and surface as BindingError. Rationale in
  `divergences.json`.
- DIVERGENCE(empty-string): `Parse("")` reports "not a duration" where `ms("")` throws (2 fixtures).
- Both were planned in `strategy.md` and logged as an unattended agent decision in `decisions.md`;
  `approvedBy` is null.

## Reference tests

PASS 44, OUT-OF-SCOPE 4, DIVERGENCE 1, FAIL 0.

## Review findings

- Applied: reftests.json ids rewritten from the `go test` underscore form to the canonical tests.js ids;
  binding treats the `{"$undefined": true}` marker as absent for `options` and `options.long`; the
  `ms_test.go` comment about the ref tag corrected.
- Logged, not applied: `approvedBy` on both divergences (needs a human, not the agent); add `"1m\n"` and
  `"1m\r\n"` to the Go grammar test (style, fixtures already pin it); simplify the nested `if` headers in
  `Parse` and note that the unreachable `ParseFloat` error branch depends on `maxParseLen` (style).

## Open questions

- Should a human approve the two divergences (`approvedBy`)?
- CI runs Go 1.22.x, but only Go 1.26.0 was run locally.
- A BigInt input has no Go counterpart and no fixture; out of scope by the contract.
