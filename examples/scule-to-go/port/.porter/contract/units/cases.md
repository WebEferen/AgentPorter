# Unit contract: cases

Layer: core. Wave: 1. Depends on: split (splitByCase, upperFirst, lowerFirst). Re-filed during the contract
rerun from the draft units src-titlecase (flatCase, titleCase), src-isuppercase (pascalCase, camelCase,
kebabCase, snakeCase, trainCase) and types-types (CaseOptions). Calls inside the unit: camelCase calls
pascalCase; snakeCase and flatCase call kebabCase.

## Symbols

| Symbol | Signature | Semantics |
| --- | --- | --- |
| src/types:CaseOptions | `interface CaseOptions { normalize?: boolean }` | Options for pascalCase, camelCase, trainCase and titleCase. `normalize` truthy: each part is lowercased (full Unicode `toLowerCase`) before `upperFirst`. Missing opts, `{}` and `{normalize: false}` are identical. Go: an options struct with `Normalize bool`. No fixtures of its own (`noFixturesReason` in api.json). |
| src/index:pascalCase | `pascalCase(): ""`, `pascalCase(str: string \| readonly string[], opts?: CaseOptions): string` | Parts through `upperFirst` (after `toLowerCase` when `normalize`), joined with `""`. Falsy `str` gives `""`. |
| src/index:camelCase | `camelCase(): ""`, `camelCase(str: string \| readonly string[], opts?: CaseOptions): string` | `lowerFirst(pascalCase(str \|\| "", opts))`, so `"FOO"` -> `"fOO"` and `"ßfoo"` -> `"sSfoo"`. |
| src/index:kebabCase | `kebabCase(): ""`, `kebabCase(str: string \| readonly string[], joiner?: string): string` | Parts lowercased (whole-part `toLowerCase`, final sigma applies), joined with `joiner ?? "-"`; `""` is a real joiner; empty parts kept. |
| src/index:snakeCase | `snakeCase(): ""`, `snakeCase(str: string \| readonly string[]): string` | `kebabCase(str \|\| "", "_")`. |
| src/index:flatCase | `flatCase(): ""`, `flatCase(str: string \| readonly string[]): string` | `kebabCase(str \|\| "", "")`: parts lowercased and concatenated. |
| src/index:trainCase | `trainCase(): ""`, `trainCase(str: string \| readonly string[], opts?: CaseOptions): string` | Non-empty parts through `upperFirst` (after `toLowerCase` when `normalize`), joined with `"-"`. `FooBARb` -> `Foo-BA-Rb` (README says `Foo-Ba-Rb`; the code wins). |
| src/index:titleCase | `titleCase(): ""`, `titleCase(str: string \| readonly string[], opts?: CaseOptions): string` | Non-empty parts joined with a space. Parts matching the 18 minor words (ASCII-only, case-insensitive) are lowercased; others go through `upperFirst`, after `toLowerCase` when `normalize`. |

Arrays are taken as parts without re-splitting in every string-or-array function.

## Errors

- None. No input inside the TypeScript signatures throws; all 1982 outcomes are values.

## Fixtures

- `fixtures/cases/oracle.json`: 1982 cases. pascalCase 314 (7 harvested, 3 README, 134 hand-written, 170
  generated), camelCase 312 (2, 1, 139, 170), kebabCase 334 (8, 1, 75, 250), snakeCase 168 (2, 1, 65, 100),
  flatCase 196 (7, 1, 68, 120), trainCase 324 (13, 3, 138, 170), titleCase 334 (5, 1, 158, 170).
- CaseOptions is observed through the 288 cases tagged `normalize`, including `{}`, `{normalize: false}` and
  `undefined` options.
- Generators: `gen.pascalCase.{words,chars-unicode,array}` (seeds 205, 206, 207: 80, 60, 30),
  `gen.camelCase.*` (208, 209, 210), `gen.kebabCase.{chars-ascii,chars-unicode,words,joiner,array}` (211-215:
  60, 60, 60, 40, 30), `gen.snakeCase.{words,chars-unicode}` (216, 217: 60, 40), `gen.trainCase.*` (218, 219,
  220: 80, 60, 30), `gen.flatCase.{chars-unicode,words,array}` (105, 106, 107: 60, 40, 20),
  `gen.titleCase.{words,chars-unicode,array}` (108, 109, 110: 80, 60, 30).
- Normalization: none.
- The astral cases whose outputs are valid UTF-8 stay in the fixtures and must pass (`flatCase("𐐀a")` =
  `"𐐀a"`, `pascalCase("𐐀a")` = `"𐐀a"`, `camelCase("𐐀oo")` = `"𐐀oo"`, `kebabCase("a𐐀")` = `"a-𐐨"`).

## Removed cases: documented divergence

These 18 inputs were recorded from the original and then removed from the fixtures. Their outputs contain
lone UTF-16 surrogates, and fixture strings must be UTF-8 (`knowledge/oracles/CONTRACT.md`: "Strings stay
strings (UTF-8)"). A Go string cannot carry these values, so the port's result for them is a documented
divergence (leaks `utf16-falling-edge-split` and `lone-surrogate-encoding` in `api.json`). The outputs below
are the original's return values as JSON text; `\udXXX` is a lone surrogate.

| Removed case | Call | Original output |
| --- | --- | --- |
| kebabCase.astral-upper-then-lower | `kebabCase("𐐀a")` | `"\ud801-\udc00a"` |
| kebabCase.astral-upper-mid | `kebabCase("A𐐀a")` | `"a\ud801-\udc00a"` |
| kebabCase.astral-upper-then-astral-lower | `kebabCase("𐐀𐐨")` | `"\ud801-\udc00𐐨"` |
| snakeCase.astral-upper-then-lower | `snakeCase("𐐀a")` | `"\ud801_\udc00a"` |
| snakeCase.astral-upper-mid | `snakeCase("A𐐀a")` | `"a\ud801_\udc00a"` |
| snakeCase.astral-upper-then-astral-lower | `snakeCase("𐐀𐐨")` | `"\ud801_\udc00𐐨"` |
| trainCase.astral-upper-then-lower | `trainCase("𐐀a")` | `"\ud801-\udc00a"` |
| trainCase.astral-upper-mid | `trainCase("A𐐀a")` | `"A\ud801-\udc00a"` |
| trainCase.astral-upper-then-astral-lower | `trainCase("𐐀𐐨")` | `"\ud801-\udc00𐐨"` |
| trainCase.norm.astral-upper-then-lower | `trainCase("𐐀a", {"normalize":true})` | `"\ud801-\udc00a"` |
| trainCase.norm.astral-upper-mid | `trainCase("A𐐀a", {"normalize":true})` | `"A\ud801-\udc00a"` |
| trainCase.norm.astral-upper-then-astral-lower | `trainCase("𐐀𐐨", {"normalize":true})` | `"\ud801-\udc00𐐨"` |
| titleCase.astral-upper-then-lower | `titleCase("𐐀a")` | `"\ud801 \udc00a"` |
| titleCase.astral-upper-mid | `titleCase("A𐐀a")` | `"A\ud801 \udc00a"` |
| titleCase.astral-upper-then-astral-lower | `titleCase("𐐀𐐨")` | `"\ud801 \udc00𐐨"` |
| titleCase.norm.astral-upper-then-lower | `titleCase("𐐀a", {"normalize":true})` | `"\ud801 \udc00a"` |
| titleCase.norm.astral-upper-mid | `titleCase("A𐐀a", {"normalize":true})` | `"A\ud801 \udc00a"` |
| titleCase.norm.astral-upper-then-astral-lower | `titleCase("𐐀𐐨", {"normalize":true})` | `"\ud801 \udc00𐐨"` |

splitByCase (unit split) moves only the low surrogate of the astral capital into the next part, and the
joiner lands between the two halves.

## Reference tests mapped here

- `test/scule.test.ts:46-52` (describe pascalCase, 7 rows with `normalize: true`) -> PASS
- `test/scule.test.ts:60-61` (describe camelCase, 2 rows with `normalize: true`) -> PASS
- `test/scule.test.ts:69-76` (describe kebabCase, 8 rows) -> PASS
- `test/scule.test.ts:84-85` (describe snakeCase, 2 rows) -> PASS
- `test/scule.test.ts:113-122` (describe trainCase, 10 rows) -> PASS
- `test/scule.test.ts:128-130` (describe trainCase, 3 rows with `normalize: true`) -> PASS
- `test/scule.test.ts:138-142` (describe titleCase, 5 rows) -> PASS
- `test/scule.test.ts:150-156` (describe flatCase, 7 rows) -> PASS
- `test/types.test-d.ts` (12 type tests) -> OUT-OF-SCOPE (user decision: "Type-level helpers in src/types.ts
  have no runtime behavior and are out of scope.")

Cases are `<fn>.ref.L<line>`.

## Risk tags and traps to read

- unicode: T5 (full case mapping in normalize and kebab/flat), final sigma in whole-part `toLowerCase`, T44
  (lone surrogates). Leaks `full-case-mapping`, `final-sigma`, `utf16-first-unit-casing` (via upperFirst and
  lowerFirst), `lone-surrogate-encoding`.
- regex: titleCase's `/.../i` without `u` does not fold `ſ` to `s`; Go `(?i)` does (leak
  `title-exception-regex`, tag `regex-i-ascii-only`).
- nullability: T41, T42 (`undefined` joiner and options; zero-argument calls), T43 (truthiness of `str` and
  `normalize`).
