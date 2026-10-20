# Strategy: ms -> go (github.com/agentporter-examples/ms)

ms is one pure 111-line function, so the port is a single unit, `index`, which is also the tracer bullet. It
is a contract port: the Go package reimplements the behavior in `contract/units/index.md` with an idiomatic
typed API rather than translating the JavaScript `typeof` dispatch. The fixture call id stays `ms:default`;
the harness binding in `cmd/porter-harness/bindings.go` dispatches a string argument to `Parse` and a number
to `Format` or `FormatLong`. Inputs that only exist in JavaScript's dynamic typing become two documented
divergences. At the gate the user approves the one-unit plan, the API below, those divergences, and the
budgets.

## Per-unit strategy

| Unit | Layer | Strategy | Why |
| --- | --- | --- | --- |
| index | core | contract port | Pure data in, data out, fully pinned by 1432 fixtures; the risk is JavaScript number semantics, which needs native Go code written against the leak list, not a line-by-line translation of the `typeof` dispatch. |

Public Go API (package `ms`, module `github.com/agentporter-examples/ms`):

```go
func Parse(s string) (float64, bool)          // ms("2 days"); ok is false where ms returns undefined
func Format(ms float64) (string, error)       // ms(60000)                -> "1m"
func FormatLong(ms float64) (string, error)   // ms(60000, {long: true})  -> "1 minute"
type InvalidValueError struct{ ... }          // NaN, +Inf, -Inf passed to Format or FormatLong
```

`Parse` has no failure cause worth reporting (the source returns `undefined` with no message), so it uses
the comma-ok form. `Format` rejects NaN and infinities the way the source throws, so it returns an error;
`*InvalidValueError` carries the source message (`error-map.json`: `Error` -> `InvalidValueError`).

## Idiom map

Seeded from `knowledge/pairs/GENERIC.md` (no javascript-to-go pair file exists) and specialized to this
codebase.

| Concern | Source idiom | Target idiom | Rule for this port |
| --- | --- | --- | --- |
| Errors | `throw new Error('val is not a non-empty string or a valid number. val=' + JSON.stringify(val))` | `return "", &InvalidValueError{Value: v}` | Only `Format` and `FormatLong` return errors, only for NaN and infinities. `Error()` returns the exact source text; non-finite numbers render as `val=null` (JSON.stringify of NaN). No panics. |
| Absence | `undefined` from the string branch | `(0, false)` from `Parse` | The binding turns `ok == false` into the harness `Undefined` marker. Never NaN. |
| Dynamic dispatch | `typeof val` string / number / other | separate `Parse` and `Format` functions | The type system replaces the `typeof` check; other types cannot be passed (divergence `typed-input`). |
| Options | `options = options \|\| {}; if (options.long)` | `FormatLong` function | No options struct. The binding decodes `options` the way `encoding/json` would into `struct{ Long bool }`: object or null, `long` true, false, null or absent. Anything else is a binding error (divergence `typed-input`). |
| Async | none | none | Pure synchronous functions, safe for concurrent use. |
| Numbers | IEEE-754 doubles, `Math.round`, `Math.abs`, `parseFloat` | `float64`, `math.Floor`, `math.Abs`, `strconv.ParseFloat` | `Math.round` is `r := math.Floor(x); if x-r >= 0.5 { r++ }` (ties toward +infinity, exact around 2^52). Never `math.Round` and never `math.Floor(x+0.5)`. `-0` results print as `0`. Parse returns `-0` for `"-0"`. |
| Number to text | `Number#toString` via string concatenation | internal `formatNumber(float64) string` | Implements ECMAScript Number::toString on top of `strconv.FormatFloat(x, 'e', -1, 64)` shortest digits: plain decimal for exponents -7 < e < 21, otherwise `d.ddde+N` / `de-N` with no zero padding. Never `%v`, `'g'` or `'f'` directly. |
| Strings and bytes | UTF-16 `length > 100` | `len(s) > 100` | Only ASCII can match, so byte length gives the same observable result (leak `length-limit`). |
| Regex | `/^(-?(?:\d+)?\.?\d+) *(units)?$/i`, non-Unicode case folding | hand-written ASCII scanner, or `regexp` with explicit ASCII classes | No `(?i)`, no `strings.ToLower`/`EqualFold` on the unit: both fold `ſ` to `s` and the Kelvin sign to `k`. Lower-case the unit with an ASCII-only loop. Only U+0020 between number and unit; `$` is end of input. |
| Dates | none | none | Durations stay `float64` milliseconds; no `time.Duration` (it would truncate fractions and overflow past ~292 years). |
| Module layout and naming | CommonJS default export `ms` | package `ms` at the module root | Exported names `Parse`, `Format`, `FormatLong`, `InvalidValueError`; helpers unexported. Package doc in `doc.go` with the MIT notice kept in `LICENSE`. |

## Dropped workarounds and new substrate

- Dropped: the `typeof` dispatch and `options || {}` defaulting; Go's types and two functions replace them.
- Dropped: `isFinite` on strings and boxed objects; only `float64` reaches `Format`.
- New substrate: `formatNumber`, an ECMAScript-exact Number-to-string, built inside unit `index`.
- New substrate: `jsRound`, `Math.round` semantics, built inside unit `index`.

## Scope gauntlet

| Item | Decision | Reason |
| --- | --- | --- |
| `index:default` string branch | now | `Parse`. |
| `index:default` number branch | now | `Format`, `FormatLong`. |
| `index:default.long` | now | Becomes the choice between `Format` and `FormatLong`. |
| Non-string, non-number `val` (`undefined`, `null`, booleans, arrays, objects): 12 fixtures tagged `dynamic-type` with kind error | out of scope, divergence `typed-input` | Go's type system rules these calls out; there is nothing to pass them to. |
| `options.long` truthiness for non-boolean values and non-object `options`: fixtures tagged `options-truthiness` | out of scope, divergence `typed-input` | Same reason. `long: true/false/null` and `options: null` stay in scope through the binding. |
| `ms("")` throws (`ref.invalid.empty-string`, `edge.invalid.empty-string-long`) | divergence `empty-string` | In Go an empty string is just another string that is not a duration: `Parse("")` returns `(0, false)`. The type-confusion check the error exists for cannot happen. |
| BigInt `TypeError` | out of scope | JavaScript only, no fixture. |
| A dynamic `ms(any)` entry point | seam for later | Not built; it would only exist to replay JavaScript typing. |

## Risk register

| Risk | Mitigation | Signal that it is happening |
| --- | --- | --- |
| Number-to-string differs from JavaScript (exponent thresholds, `e-7` vs `e-07`, digit count) | `formatNumber` from shortest digits plus the ECMAScript rule; table test over the `number-to-string` leak values | `edge.format.subsecond.*`, `edge.format.large.*` or `gen.format.float-*` fail |
| Rounding differs (`math.Round` away from zero, `Floor(x+0.5)` off by one near 2^52) | `jsRound` as above; negative half cases in Go tests | `edge.format.half.*` or `edge.format.large.round-2p52-*` fail |
| Unicode case folding accepts `"1ſ"` or `"1 weeK"` | ASCII-only unit matching | `edge.parse.unicode.*` or `gen.parse.near-grammar-*` return a value instead of `$undefined` |
| `-0` printed as `"-0ms"` | normalize zero before formatting | `edge.format.negative-zero` fails |
| Plural chosen from the rounded or signed value | plural from `abs(ms) >= 1.5*unit`, count from the signed value | `edge.format-long.half.*` fail |

## Scaffold

- Package layout:

  ```text
  go.mod                      module github.com/agentporter-examples/ms, go 1.22
  LICENSE                     MIT, original Vercel notice kept
  README.md
  doc.go                      package comment
  ms.go                       Parse, Format, FormatLong, InvalidValueError
  number.go                   formatNumber, jsRound (unexported)
  ms_test.go                  ported tests.js, table-driven
  example_test.go             runnable examples from readme.md
  cmd/porter-harness/         harness.go, value.go, bindings.go
  .github/workflows/ci.yml    gofmt, go vet, go test on Go 1.22.x and 1.26.x
  ```

- Toolchain: build `go build ./...`, test `go test ./... -count=1`, lint `go vet ./...` (staticcheck is not
  installed here; optional in CI), format `gofmt -l .` (must print nothing), typecheck: the compiler.
  The `go` line is 1.22 because the user asked for "Go 1.22 or newer"; the ecosystem file's default of 1.26
  would force that minimum on every consumer.
- Harness: `knowledge/harnesses/go/{harness.go,value.go}` copied to `cmd/porter-harness/`; bindings in
  `cmd/porter-harness/bindings.go` with one entry, `ms:default`. Run with
  `go run ./cmd/porter-harness --workspace .porter --run <run> --unit index`.
- Reference tests: `tests.js` ported to `ms_test.go`, test names mirroring `describe`/`it`; results imported
  with `porter parity reftests gotest <go test -json report>`.
- CI: `.github/workflows/ci.yml` with one job, matrix Go 1.22.x and 1.26.x: `gofmt -l .`, `go vet ./...`,
  `go test ./... -count=1`.

## Budgets

Attempts per unit: 3. Discovered units before returning to the user: 5. PORT depth and LOC: 1, 2000 (no PORT
decisions in this port).
