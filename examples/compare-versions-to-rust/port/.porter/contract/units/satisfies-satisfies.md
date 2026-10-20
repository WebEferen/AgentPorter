# Unit contract: satisfies-satisfies

Layer: core. Wave: 1. Depends on: utils-utils.

Holds src/compareVersions.ts, src/compare.ts and src/satisfies.ts (90 LOC). Fixtures call the package entry:
`compare-versions:compareVersions`, `compare-versions:compare`, `compare-versions:satisfies`.

## Symbols

| Symbol | Signature | Semantics |
| --- | --- | --- |
| src/compareVersions:compareVersions | `compareVersions(v1: string, v2: string): number` | Parses both with the semver regex (v1 first), compares the four numeric segments with compareSegments, then the pre-release: both present compares their dot-split identifiers, only one present makes that side smaller. Returns -1, 0 or 1. Build metadata is ignored. |
| src/compare:compare | `compare(v1, v2, operator): boolean` | Validates the operator (type, then membership in `> >= = <= < !=`), then maps compareVersions' result through the operator's result set. |
| src/satisfies:satisfies | `satisfies(version: string, range: string): boolean` | Strips whitespace after runs of `> < =`; then `\|\|` (some, left to right), else ` - ` (`>=A <=B` from `split(' - ', 2)`), else ASCII space (trim, collapse 2+ whitespace, every); else the leading `[<>=~^]+` run is the operator (`=` when absent). `^`/`~` compare the first three segments: a range pre-release requires the version to have one, the same three numbers and a pre-release not below it; then segments before the pointer (`~`: 2; `^`: index of the first non-`0` segment + 1, at least 1, with missing segments as `x`) must be equal and the rest not lower. Any other operator run goes to compare(), which throws for unknown runs. |

## Errors

- v1/v2/version or a comparator does not match the semver regex -> `Error` (`Invalid argument not valid semver ('<input>' received)`, the input verbatim; for satisfies the comparator text including its operator, for example `'^foo'`, `'<='`, `''`).
- compare operator, or a satisfies operator run other than `^`, `~`, `>`, `>=`, `=`, `<=`, `<`, `!=` -> `Error` (`Invalid operator, expected one of >|>=|=|<=|<|!=`). `!=` is not recognized as a satisfies prefix (`!` is not in `[<>=~^]`), so `!=1.0.0` fails as an invalid version.
- non-string version argument -> `TypeError` (`Invalid argument expected string`); non-string compare operator -> `TypeError` (`Invalid operator type, expected string but got <typeof>`), checked before anything else.
- non-string satisfies range -> `TypeError` with a V8 message (4 cases, `ignore-message`).
- Precedence: operator type, operator value, v1, v2. In satisfies, comparators are evaluated left to right and evaluation stops once the result is decided, so later malformed comparators raise nothing.

## Fixtures

- `fixtures/satisfies-satisfies/oracle.json`: 3041 cases (336 harvested, 255 hand-written, 2450 generated); 2397 values, 644 errors.
  - compareVersions 1563 (208 harvested incl. 90 sort pairs, 105 hand-written, 1250 generated)
  - compare 374 (30 harvested, 44 hand-written, 300 generated)
  - satisfies 1104 (98 harvested, 106 hand-written, 900 generated)
- Case names: `ref-<file>-L<line>` (harvested), `edge-cv-*`, `edge-cmp-*`, `edge-sat-*` (hand-written), `gen-*-NNNN` (generated). 32 cases have `nonstring` in their name (non-string arguments).
- Normalization: `ignore-message` on `edge-sat-nonstring-range-number`, `-null`, `-undefined`, `-array`. Reason: the message is V8's (`range.replace is not a function`, `Cannot read properties of null (reading 'replace')`), produced by the runtime, not the library. Nothing else is normalized.

## Reference tests mapped here

- test/compare.ts::L24-L27, L32-L34, L40-L44, L50-L60, L66-L71, L77-L88, L94-L102, L108-L111, L117-L123, L129-L150, L175-L204 (112 compareVersions rows) -> PASS
- test/compare.ts::L161-L163 (invalid semver) -> PASS
- test/compare.ts::L157-L159 (42, {}, [] as versions) -> DIVERGENCE if the strategy keeps a `&str` API (non-string arguments cannot be passed), else PASS through Value-taking bindings
- test/compare.ts::L160 (function as version) -> OUT-OF-SCOPE (not representable in JSON fixtures or in Rust)
- test/compare.ts::L233, L234, L240, L246, L252 (null, undefined, true, 1, {foo} as operator) -> DIVERGENCE or PASS, same strategy decision
- test/compare.ts::L258 (function as operator) -> OUT-OF-SCOPE (not representable)
- test/compare.ts::L264-L266 ('', 'foo', '> ' as operator) -> PASS
- test/compare.ts::L269 (one `it`, 7 rows): rows 276-278 PASS, rows 272-274 follow the non-string decision, row 275 is a function (OUT-OF-SCOPE) -> resolves with the non-string decision
- test/compare.ts::L288-L303 (16 compare rows) -> PASS
- test/satisfies.ts::L15-L29 (tilde), L35-L46 (caret), L51-L83, L88-L96 (pre-release), L102-L123 (comparator sets), L129-L135 (malformed) (98 rows) -> PASS
- test/sort.ts::L5, L31, L37 -> PASS (a stable sort over compare_versions)

## Risk tags and traps to read

- error-model: T32, T35 (exact messages; the operator TypeError embeds JS `typeof` names)
- numeric: T11 (2^53), T15 (Number to String in mixed comparisons), T17 (`parseInt` prefix parsing, negatives)
- ordering: T7 (code-unit order; ASCII here, so byte order agrees), T26 (sort stability)
- regex: T20 (`\d` and `\s` are ASCII-only or ECMAScript-specific; the Rust `regex` crate is Unicode-aware), T21 (`$` before a trailing newline), T5 (case folding of K, long s, dotless i under `/i`), T45 (U+FEFF is `\s` and trimmed in JS)
- nullability: T43 (`a[i] || '0'` and `p1 && p2` truthiness; regex groups are `undefined` when absent)
- reflection: `typeof` checks on every argument (non-string fixtures)
