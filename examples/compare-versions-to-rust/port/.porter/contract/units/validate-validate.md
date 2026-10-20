# Unit contract: validate-validate

Layer: core. Wave: 1. Depends on: utils-utils (the shared `semver` regex). Tracer bullet.

Holds src/validate.ts (7 LOC). Fixtures call `compare-versions:validate` and `compare-versions:validateStrict`.

## Symbols

| Symbol | Signature | Semantics |
| --- | --- | --- |
| src/validate:validate | `validate(version: string): boolean` | `typeof version === 'string' && /^[v\d]/.test(version) && semver.test(version)`: the first character is a lowercase `v` or an ASCII digit, and the whole string matches the shared semver regex (case-insensitive, prefix runs of `v^~<>=`, 1 to 4 segments, `x`/`X`/`*` after the first, pre-release and build only after 3 segments, ASCII identifiers). |
| src/validate:validateStrict | `validateStrict(version: string): boolean` | `typeof version === 'string'` and the semver.org 2.0.0 regex (case-sensitive, ASCII): exactly three segments without leading zeros, numeric pre-release identifiers without leading zeros, build identifiers may have them. |

## Errors

- None. Both functions return false for every non-string (undefined, null, numbers, NaN, objects, arrays, booleans) and never throw.

## Fixtures

- `fixtures/validate-validate/oracle.json`: 1174 cases (92 harvested, 82 hand-written, 1000 generated), all values.
  - validate 569 (20 harvested, 49 hand-written, 500 generated)
  - validateStrict 605 (72 harvested, 33 hand-written, 500 generated)
- 16 cases have `nonstring` in their name.
- Probes for the regex dialect: `edge-val-fullwidth-digits`, `edge-val-arabic-indic-digits`, `edge-val-mixed-unicode-digit`, `edge-val-kelvin-sign`, `edge-val-long-s`, `edge-val-trailing-newline`, `edge-strict-unicode-digit-in-major` (`1١.2.3`), `edge-strict-unicode-digit-in-prerelease` (`1.2.3-1١`), plus `gen-validate-unicode-*` and `gen-strict-unicode-*`. All are false in JS; a Unicode-aware `\d` makes several of them true.
- Normalization: none.

## Reference tests mapped here

- test/validate.ts::L13-L27 (string rows of the validate table) -> PASS
- test/validate.ts::L7-L11 (undefined, null, 42, {}, []) -> DIVERGENCE if the strategy keeps a `&str` API, else PASS through Value-taking bindings
- test/validate.ts::L12 (function) -> OUT-OF-SCOPE (not representable in JSON fixtures or in Rust)
- test/validate.ts::L39-L69 (31 valid validateStrict rows) -> PASS
- test/validate.ts::L79-L119 (41 invalid validateStrict rows) -> PASS

## Risk tags and traps to read

- regex: T20 (ASCII `\d`; the Rust `regex` crate needs `(?-u:\d)` or `[0-9]`), T21 (`$` before a trailing newline), T5 (`/i` case folding is ASCII-only in non-unicode JS regexes), T22 (the regexes use no lookaround or backreferences, so a linear-time engine can express them)
- reflection: `typeof version === 'string'` guard (non-string fixtures)
