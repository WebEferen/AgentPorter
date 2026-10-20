# Unit contract: utils-utils

Layer: foundation. Wave: 0. Depends on: none.

Holds src/utils.ts (40 LOC): the comparison core every other unit uses. Its exports are module-internal
(`src/index.ts` re-exports only the `CompareOperator` type), so it has no call id and no fixtures of its own.

## Symbols

| Symbol | Signature | Semantics |
| --- | --- | --- |
| src/utils:CompareOperator | `type CompareOperator = '>' \| '>=' \| '=' \| '<' \| '<=' \| '!='` | Public type. In Rust either `&str` validated at run time or an enum; the invalid-operator fixtures in satisfies-satisfies must still resolve (pass or recorded divergence). |
| src/utils:semver | `/^[v^~<>=]*?(\d+)(?:\.([x*]\|\d+)(?:\.([x*]\|\d+)(?:\.([x*]\|\d+))?(?:-([\da-z\-]+(?:\.[\da-z\-]+)*))?(?:\+[\da-z\-]+(?:\.[\da-z\-]+)*)?)?)?$/i` | Internal. Prefix run of `v^~<>=` (lazy), a digit run, up to three more segments of digits or `x`/`*` (`X` through `/i`), pre-release and build only after the third segment, ASCII identifiers, case-insensitive. Groups: major, minor, patch, fourth, pre-release. |
| src/utils:validateAndParse | `validateAndParse(version: string): RegExpMatchArray` | Internal. TypeError for non-strings, Error with the raw input for no match; returns the five groups (absent ones `undefined`). |
| src/utils:compareSegments | `compareSegments(a, b): number` | Internal. For i up to the longer length: `x = a[i] \|\| '0'`, `y = b[i] \|\| '0'`; wildcard on either side is equal; else `parseInt(_, 10)` each side (NaN keeps the string); if one is a number and the other a string, compare `String(number)` with the string; return 1/-1 at the first difference, else 0. |

## Errors

- `validateAndParse`: non-string -> `TypeError` (`Invalid argument expected string`); no match -> `Error` (`Invalid argument not valid semver ('<input>' received)`). Observed through satisfies-satisfies.

## Fixtures

- None (`noFixturesReason` in plan.json and on each symbol in api.json). The behavior is recorded through the
  public functions:
  - semver acceptance: `edge-cv-prefix-*`, `edge-cv-five-segments`, `edge-cv-prerelease-needs-three-segments`, `edge-cv-unicode-*`, `edge-val-*`, `gen-cv-junk-*`, `gen-validate-*`
  - compareSegments ordering: `edge-cv-parseint-*`, `edge-cv-negative-*`, `edge-cv-tostring-*`, `edge-cv-2pow53-*`, `edge-cv-infinity-*`, `edge-cv-wildcard-*`, `edge-cv-nontransitive-*`, `edge-cv-missing-*`, `gen-cv-*`
  - validateAndParse errors: `ref-compare-L15[7-9]*`, `ref-compare-L16[0-3]*`, `edge-cv-message-*`
- Normalization: n/a.

Behavioral assertion plan (since the unit cannot be graded by fixtures on its own):

1. Port it crate-private and test it through the public API: the fixtures above fail if any rule is wrong.
2. Add Rust unit tests for the helpers that a public-API fixture can only reach indirectly, tagged with the
   fixture they mirror, for example `[ref: test/compare.ts::L129]` for wildcard equality: parseInt-style
   prefix parsing (`"10a"` -> 10, `"-5"` -> -5, `"0x10"` -> 0, `"abc"` -> string), f64 rounding above 2^53,
   overflow to infinity at about 309 digits, and JS `String()` of -0 and infinities.
3. Or merge this unit into a unit with fixtures at the strategy phase (see decomposition.md), so parity grades
   it through those fixtures. Without one of these, `parity collect` grades it GAP.

## Reference tests mapped here

- None directly. Every test goes through `src/index.ts` and is mapped to satisfies-satisfies or validate-validate.

## Risk tags and traps to read

- numeric: T11 (2^53), T15 (Number to String), T17 (lenient `parseInt`)
- error-model: T35 (exact messages)
- reflection: `typeof` guards; T43 (truthiness of `undefined` groups and empty strings)
- regex: T20, T21, T5 (the semver regex dialect, see validate-validate)
