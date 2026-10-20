# Unit contract: index

Layer: core. Wave: 0. Depends on: none. Tracer unit. Sources: `index.js` 5-10, 26-38, 48-103, 113-128, 138-153,
159-162 (111 LOC). Private symbols owned here: `parse`, `fmtShort`, `fmtLong`, `plural`, `s`, `m`, `h`, `d`,
`w`, `y`.

## Symbols

| Symbol | Signature | Semantics |
| --- | --- | --- |
| `index:default` (call `ms:default`) | `ms(val: string \| number, options?: { long?: any }): number \| string \| undefined` | Non-empty string: parse to milliseconds (double) or `undefined`; options ignored. Finite number: format as `"<n><unit>"` or, with truthy `options.long`, `"<n> <unit name>[s]"`. Anything else: throw. |
| `index:default.long` | `options.long: any` | JavaScript truthiness picks the long format. `null` or missing options mean `{}`. |

Parse, in order:

1. More than 100 UTF-16 code units: `undefined`.
2. Match `/^(-?(?:\d+)?\.?\d+) *(milliseconds?|msecs?|ms|seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h|days?|d|weeks?|w|years?|yrs?|y)?$/i`
   with JavaScript non-Unicode case folding (ASCII only). No match: `undefined`.
3. `parseFloat(number) * unit`, unit defaulting to ms. Units: s 1000, m 60000, h 3600000, d 86400000,
   w 604800000, y 31557600000.

Format (`fmtShort` / `fmtLong`), with `a = |ms|`:

1. `a >= d`: days; else `a >= h`: hours; else `a >= m`: minutes; else `a >= s`: seconds.
2. Count is `Math.round(ms / unit)` (ties toward +infinity), printed with `Number#toString`.
3. Short: count + `d`/`h`/`m`/`s`. Long: count + ` day`/` hour`/` minute`/` second`, plus `s` when
   `a >= 1.5 * unit`.
4. Below one second: `ms + "ms"` (short) or `ms + " ms"` (long), the input printed with `Number#toString`
   (`-0` prints as `0`).

## Errors

- `val` is `""`, `undefined`, `null`, a boolean, an array, an object, `NaN`, `Infinity` or `-Infinity` ->
  `Error` (target `InvalidValueError` via `error-map.json`), exact message
  `val is not a non-empty string or a valid number. val=<JSON.stringify(val)>`. `NaN` and `Infinity` give
  `val=null`; `undefined` gives `val=undefined`; `""` gives `val=""`.
- `val` is a BigInt -> `TypeError` `Do not know how to serialize a BigInt`. JavaScript only, no fixture, no Go
  counterpart.

## Fixtures

- `fixtures/index/oracle.json`: 1432 cases (87 harvested from `tests.js`, 20 from the readme, 305 hand-written,
  1020 generated with seeds 1001-1004 and 2001-2003). 1413 values, 19 errors.
- Tags to filter on: `parse`, `format`, `long`, `options`, `invalid`, `dynamic-type` (22 cases a typed Go API
  cannot express without a dynamic entry point), `options-truthiness` (10), and trap ids (`T14`, `T15`, `T5`,
  ...).
- Normalization: none. Every outcome is deterministic and compared exactly, error messages included.
- Value encodings the binding must produce: `{"$undefined": true}` for "no value" from the string branch
  (the Go harness `Undefined` marker), `{"$float": "-0"}` for a parsed negative zero (a Go `float64` -0
  serializes this way on its own).

## Reference tests mapped here

All 49 tests in `tests.js` exercise this unit. Ref ids are `tests.js::<describe>::<it>`.

`ms(string)`, 16 tests -> PASS:
should not throw an error; should preserve ms; should convert from m to ms; should convert from h to ms;
should convert d to ms; should convert w to ms; should convert s to ms; should convert ms to ms; should work
with decimals; should work with multiple spaces; should return NaN if invalid (the port returns "no value",
pinned as `undefined`; a Go test asserts that, not NaN); should be case-insensitive; should work with numbers
starting with .; should work with negative integers; should work with negative decimals; should work with
negative decimals starting with ".".

`ms(long string)`, 11 tests -> PASS:
should not throw an error; should convert milliseconds to ms; should convert msecs to ms; should convert sec
to ms; should convert from min to ms; should convert from hr to ms; should convert days to ms; should work
with decimals; should work with negative integers; should work with negative decimals; should work with
negative decimals starting with ".".

`ms(number, { long: true })`, 7 tests -> PASS:
should not throw an error; should support milliseconds; should support seconds; should support minutes;
should support hours; should support days; should round.

`ms(number)`, 7 tests -> PASS:
should not throw an error; should support milliseconds; should support seconds; should support minutes;
should support hours; should support days; should round.

`ms(invalid inputs)`, 8 tests:

- `should throw an error, when ms("")`, `ms(NaN)`, `ms(Infinity)`, `ms(-Infinity)` -> PASS.
- `should throw an error, when ms(undefined)`, `ms(null)`, `ms([])`, `ms({})` -> PASS if the port keeps a
  dynamic entry point (`any` argument); otherwise OUT-OF-SCOPE (the Go type system rejects the argument at
  compile time) with matching divergences for fixtures `ref.invalid.undefined`, `ref.invalid.null`,
  `ref.invalid.array`, `ref.invalid.object`. The strategy decides.

## Risk tags and traps to read

No `javascript-to-go` pair file exists; traps are from `knowledge/pairs/GENERIC.md`.

- numeric: T14 (rounding mode: JS ties to +infinity, Go `math.Round` away from zero), T11 (doubles above
  2^53), T17 (lenient parsing: validate with the grammar before `strconv.ParseFloat`).
- float-format: T15 (Number-to-string: exponent form below 1e-6 and from 1e21, `e-7` not `e-07`, `-0` as `0`),
  T9 (text built from numbers).
- regex: T5 (case folding: Go `(?i)` folds `ſ` and the Kelvin sign; probe confirmed on Go 1.26), T20 (ASCII
  `\d`), T21 (`$` is end of input in both JS and Go; keep it that way), T22 does not apply (no lookaround).
- nullability: T42 (`undefined` result for bad strings), T43 (options truthiness).
- error-model: T32 (error identity: callers test the type), T35 (the message is recorded exactly).
- reflection: `typeof` dispatch on `val`; see the `dynamic-type` tag.
