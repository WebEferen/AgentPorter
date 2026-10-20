# Contract: ms 2.1.3

The port must preserve what the single exported function `ms(val, options)` returns or throws for every
input, observed at the function boundary: the parsed millisecond value (a double, `-0` included) or
`undefined` for strings, the formatted text for finite numbers, and the error category and exact message for
everything else. There is no I/O, state or nondeterminism. Confidence is high for the behavior the 49
reference tests cover (unit conversion, both output formats, the throwing inputs) and for the edges recorded
from the pinned source at commit `1c6264b7` on Node 24.18.0 (rounding, pluralisation, Number-to-string,
grammar, the 100-character limit). It is lower for the error message text and the JavaScript-only dynamic
typing (options truthiness, non-string non-number values), which no test asserts and which an idiomatic Go
API may not be able to express. Those are recorded exactly and tagged `dynamic-type` so the strategy phase
can decide on them.

## Public surface

| Symbol | Kind | Signature | Unit | In scope | Notes |
| --- | --- | --- | --- | --- | --- |
| `index:default` (fixture call `ms:default`) | function | `ms(val: string \| number, options?: { long?: any }): number \| string \| undefined` | index | yes | Pure, no side effects. Returns `undefined` for a non-matching or over-long string; throws `Error` for anything that is not a non-empty string or a finite number. |
| `index:default.long` | config-key | `options.long: any` | index | yes | Truthiness selects the long format; read only for numbers. `options` defaults through `options \|\| {}`. |

Private helpers `parse`, `fmtShort`, `fmtLong`, `plural` and the constants `s`, `m`, `h`, `d`, `w`, `y` belong to
unit `index` in `plan.json` and are not public. Nothing is out of scope.

## Semantics the tests promise and the docs omit

- Units are case-insensitive (`"1.5H"` is 5400000).
- Any number of spaces may separate number and unit (`"1   s"` is 1000).
- Numbers may start with `.` and results may be fractional (`".5ms"` is 0.5, `"-.5h"` is -1800000).
- Long unit spellings: `milliseconds`, `msecs`, `sec`, `min`, `hr`, `hours`, `days`.
- An invalid string gives a value for which `isNaN` is true. The recorded value is `undefined`, not NaN.
- Rounding to the nearest unit: `234234234` is `"3d"` and `"3 days"`; `1200` is `"1 second"`.
- Negative values keep the singular below 1.5 units: `-1200` is `"-1 second"`.
- `""`, `undefined`, `null`, `[]`, `{}`, `NaN`, `Infinity` and `-Infinity` throw. Tests do not check the
  error type or message.

The docs add `"1y"` (31557600000, a 365.25-day year), `"2.5 hrs"` and the round trip `ms(ms('10 hours'))`
(`"10h"`), which the tests omit. Neither tests nor docs state any item in the leak list below.

## Error model

| Source error | When | Target category (error-map.json) |
| --- | --- | --- |
| `Error`, message `val is not a non-empty string or a valid number. val=<JSON.stringify(val)>` | `val` is `""`, `undefined`, `null`, a boolean, an array, an object, `NaN`, `Infinity` or `-Infinity` (19 fixtures) | `InvalidValueError` (proposed; the strategy may rename it and update the map) |
| `TypeError`, message `Do not know how to serialize a BigInt` | `val` is a BigInt (JavaScript only, no fixture) | not mapped |

The string branch never throws (a bad string gives `undefined`), and the number branch never returns
`undefined`. In a typed Go API, `null`, booleans, arrays, objects and `undefined` cannot be passed to a
`string` or `float64` parameter. The strategy decides whether the port offers a dynamic entry point that
reproduces these errors, or whether the 12 `dynamic-type` error fixtures (and the 10 `options-truthiness`
value fixtures) become documented divergences.

## Leak list

Internals that leak into observable behavior and must be preserved or consciously diverged from. Each is in
`api.json.leaks` with its fixture patterns.

- `round-half-up`: `Math.round` rounds halves toward +infinity, so `ms(-1500)` is `"-1s"`. Go `math.Round`
  rounds away from zero, and `math.Floor(x+0.5)` is wrong for odd integers in [2^52, 2^53)
  (`ms(3.891110078048109e+23)` is `"4503599627370497d"`). Trap T14.
- `plural-sign`: the plural uses `|ms| >= 1.5 * unit` but the count uses the signed rounding, so
  `ms(-1500, {long: true})` is `"-1 seconds"` and `ms(-90000, {long: true})` is `"-1 minutes"`.
- `unit-rollup`: the unit is chosen before rounding, so `ms(59999)` is `"60s"`, `ms(3599999)` is `"60m"`,
  `ms(86399999)` is `"24h"`. Days is the largest output unit (`ms(31557600000)` is `"365d"`).
- `number-to-string`: JavaScript `Number#toString` prints the sub-second input and the rounded count:
  `"0.30000000000000004ms"`, `"0.000001ms"`, `"9.99e-7ms"`, `"5e-324ms"`, `"999999999999999900000d"`,
  `"1.0000000000000001e+21d"`, `"1.1574074074074075e+292d"`. Go `strconv` 'g' writes `1e-07` and changes to
  exponent form at other thresholds. Trap T15.
- `negative-zero`: `ms(-0)` is `"0ms"` (Go prints `-0`); `ms("-0")` returns -0.
- `undefined-result`: a non-matching or over-long string returns `undefined`, recorded as
  `{"$undefined": true}`. Trap T42.
- `double-results`: parsing returns `parseFloat(n) * unit` as a double (`"1.15h"` is 4139999.9999999995,
  `"1.1d"` is 95040000.00000001; a year is 365.25 days). Traps T11, T17.
- `grammar`: the regex is the whole grammar (ASCII digits, optional `-`, leading `.` allowed, U+0020 only,
  trailing spaces only without a unit, `$` at end of input). Case folding is ASCII-only: `"1ſ"` and `"1 weeK"`
  (Kelvin sign) are `undefined`, but Go `(?i)` accepts both (probed with Go 1.26). Traps T5, T17, T20, T21.
- `length-limit`: more than 100 UTF-16 code units gives `undefined`; only ASCII can match, so the counting
  unit is not observable. Trap T1.
- `typeof-dispatch`: strings parse (options ignored), finite numbers format, everything else throws.
- `options-truthiness`: `options.long` uses JavaScript truthiness (`{long: "false"}` is long, `{long: 0}` is
  short); `null` options mean `{}`. Trap T43.
- `error-message`: the message embeds `JSON.stringify(val)`, so `NaN` and `Infinity` print as `null`.
  Traps T19, T35.

Free to differ:

- Helper names and boundaries (`parse`, `fmtShort`, `fmtLong`, `plural`) and the unit constant names.
- The Go API shape (separate parse and format functions, an options struct, `(float64, bool)` or error
  returns), as long as the `ms:default` binding only translates calling conventions.
- The Go error type name, through `error-map.json`.
- Regex engine or hand-written scanner, as long as the `grammar` leak holds.
- The unreachable `default` branch of `parse` (index.js:100-101) and the `String(str)` coercion in `parse`.
- The unit used to count input length.
- Performance: the source makes no timing promises.

## Observation boundary per unit

| Unit | Observed | Normalization |
| --- | --- | --- |
| index | return values (number, string, `{"$undefined": true}`, `{"$float": "-0"}`) and errors (category and exact message) | none |

No case carries a `normalize` list or a `messagePattern`: every output is deterministic and is compared
exactly.

## Fixtures

```
| Unit | Files | Cases | Kinds | Origins |
| --- | --- | --- | --- | --- |
| index | 1 | 1432 | error 19, value 1413 | docs 20, generated 1020, hand-written 305, reference-test 87 |
```

Sources of the 1432 cases in `fixtures/index/oracle.json` (spec `oracle/cases/index.json`, call `ms:default`):

- 87 harvested from every assertion in `tests.js` (49 tests), origin `reference-test:tests.js::<describe>::<it>`.
- 20 from the readme examples, origin `docs:readme.md:<line>`.
- 305 hand-written edge cases: every unit alias, case variants, numeric forms, `-0`, whitespace,
  malformed input, Unicode case-folding traps, the 100-character boundary, sub-second and huge numbers,
  the half-way and 1.5x plural boundaries for each unit, unit roll-ups, options truthiness and invalid
  values.
- 1020 from seeded generators: `gen.parse.valid` (seed 1001, 200), `gen.parse.near-grammar` (1002, 150),
  `gen.parse.fuzz-ascii` (1003, 80), `gen.parse.fuzz-unicode` (1004, 40), `gen.format.int` (2001, 200),
  `gen.format-long.int` (2002, 200), `gen.format.float` (2003, 150).

Recorded with `.porter/oracle/driver/oracle.mjs` (copied from the plugin) on Node 24.18.0 against the
source checkout at `1c6264b795492e8fdecbc82cb8802fcfbfc08d26`. `npm ci` was not run: `index.js` has no
runtime dependencies, and installing would write `node_modules` into the pinned checkout.
