# Survey: compare-versions 6.1.1

compare-versions is a zero-dependency TypeScript library on npm (MIT, Ole Michelsen) that compares semver-like version strings, works as an `Array.sort` comparator, checks npm-style ranges and validates version strings. It runs unchanged in browsers, Node and React Native. Verdict: a small, pure port. It has 214 source LOC in 6 modules exposing 5 functions and 1 type, with no I/O, no runtime dependencies and no native code, and a table-driven suite of 339 test cases pins most of the behavior. All of the risk is semantic. The comparison core relies on JavaScript coercion (`parseInt` prefix parsing, float64 numbers, string fallback when types differ), and `satisfies` hand-rolls a range grammar that departs from both the semver spec and npm on pre-releases. The port has to reproduce the library's quirks, not the spec.

## Facts

| Fact | Value |
| --- | --- |
| Package | compare-versions 6.1.1 |
| Commit | 497a7e0c5fc0 |
| License | MIT (copyleft: none) |
| Kind | library |
| Primary language | typescript |
| Source LOC | 214 |
| Tests | 4 files, 581 LOC, 12 cases, ratio 2.71 |
| Test runners | mocha-style (describe/it) |
| Public symbols | 10 |
| Modules by coupling | pure 6 |
| Runtimes | not declared |
| Sampled | no |

| Module | Language | LOC | Coupling | Signals | Risk tags | Public symbols |
| --- | --- | --- | --- | --- | --- | --- |
| src/compare | typescript | 48 | pure |  | error-model, ordering, reflection | compare |
| src/compareVersions | typescript | 26 | pure |  |  | compareVersions |
| src/index | typescript | 5 | pure |  |  | index |
| src/satisfies | typescript | 58 | pure |  | nullability, regex | satisfies |
| src/utils | typescript | 43 | pure |  | error-model, numeric, reflection | CompareOperator, semver, validateAndParse, compareSegments |
| src/validate | typescript | 34 | pure |  | reflection, regex | validate, validateStrict |

Corrections to the printed facts (tables above kept as printed):

- Tests: the 12 "cases" are static `it('...')` call sites. The suites are table-driven: `runTests`/`runThrows` helpers call `it` inside `dataSet.forEach` (test/compare.ts:11-20, test/compare.ts:209-230, test/satisfies.ts:5-11), and literal arrays are iterated with `.forEach` (test/compare.ts:155-171, test/validate.ts:5-33, 38-74, 77-124). At runtime mocha generates 339 cases: test/compare.ts 145, test/satisfies.ts 98, test/validate.ts 93, test/sort.ts 3. One of them (test/compare.ts:269-285) loops 7 assertions inside a single `it`, so there are 345 assertions in total.
- Public symbols: 10 counts every `export` in src/ plus the `index` module itself. The package entry (src/index.ts:1-5) re-exports 6: `compareVersions`, `compare`, `satisfies`, `validate`, `validateStrict` and the type `CompareOperator`. `semver`, `validateAndParse` and `compareSegments` are exported from src/utils.ts for internal use and are not part of the documented API.

## Scope

- Kind: library. One package, no CLI, no runtime dependencies (package.json has only devDependencies). All three entry points (`main`, `module`, `types`) are build outputs of src/index.ts.
- In scope: all six modules under src/ (compare, compareVersions, satisfies, validate, utils, index). test/ is the behavioral contract.
- Out of scope:
  - lib/ (ESM and UMD output of tsc and rollup, package.json `scripts.build`): generated and not in the repo.
  - The UMD browser global `window.compareVersions` (README "Browser" section): JS packaging only, no logic.
  - CHANGELOG.md, .github/workflows/ci.yml, package-lock.json, tsconfig.json, .mocharc.json, .editorconfig: history and tooling.

## Where the risk is

| Module | Coupling | Why it is risky | Risk tags |
| --- | --- | --- | --- |
| src/satisfies | pure | Hand-written range grammar that recurses on `\|\|`, ` - ` and spaces (src/satisfies.ts:22-33). JS `split(' - ', 2)` silently drops anything after the second piece (line 25). Operator prefixes other than the six compare operators, `^` and `~` (for example `=>` or `~>`) fall through to `compare` and throw (lines 36-41). A range without a pre-release accepts pre-release versions, so `satisfies('1.2.4-beta', '^1.2.3')` is true where npm says false (lines 50-54). The fourth (Chromium) segment is ignored for `^` and `~` (line 46). | nullability, regex (scanner); add error-model, recursion |
| src/utils | pure | The comparison core behind every compare path. `tryParse` uses `parseInt` (line 26), which reads a leading digit prefix (`'10a'` becomes 10) and returns float64, so digit runs past 2^53 lose precision and can compare equal. `forceType` (line 31) compares mixed number/string pairs as strings. Wildcards `x`, `X`, `*` equal anything (lines 23, 34), which makes the order non-transitive. Missing segments default to `'0'` (line 46). The `semver` regex (line 7) is case-insensitive and accepts any run of `v^~<>=` as a prefix, so `compareVersions('>=1.0.0', '1.0.0')` returns 0. It has no `u` flag, so identifiers are ASCII and string order is ASCII order. Throws `TypeError` vs `Error` with exact messages that tests match (lines 10-17). | error-model, numeric, reflection (scanner); add regex, nullability |
| src/compareVersions | pure | Pre-release precedence reuses `compareSegments` and is not semver precedence. A missing identifier counts as `'0'`, so `1.0.0-alpha` equals `1.0.0-alpha.0` (src/compareVersions.ts:24-25 with src/utils.ts:46), and `parseInt` sorts `11` after `10a` where semver puts numeric identifiers first. `pop()` can return undefined (lines 16-17). The -1/0/1 result is used directly as a sort comparator (test/sort.ts:18). | none from scanner; add nullability, ordering |
| src/compare | pure | Runtime `typeof` check on the operator (src/compare.ts:44-47). Tests pass null, undefined, boolean, number, object and function and match the type name in the error message (test/compare.ts:232-267). The "expected one of" message lists operators in `Object.keys` insertion order (lines 32-41, 51). | error-model, ordering, reflection |
| src/validate | pure | Two regexes. `validate` is a string check plus `^[v\d]` plus the shared `semver` regex (src/validate.ts:16-17). `validateStrict` is the semver.org regex (line 34). Both use only plain regex features (no lookaround, no backreferences). Tests include non-string inputs (test/validate.ts:7-12). | reflection, regex |
| src/index | pure | Re-exports only (src/index.ts:1-5). | none |

Coupling confirmed pure for all six modules. src/utils.ts has no imports, and every other module imports only relative `./*.js` files (src/compare.ts:1-2, src/compareVersions.ts:1, src/satisfies.ts:1-2, src/validate.ts:1, src/index.ts:1-5). There is no I/O, timer, global or environment access anywhere in src/. No module was marked runtime-welded or native.

## Flags for the user

- License: MIT (LICENSE: "Copyright (c) 2015-2021 Ole Michelsen"), no copyleft. MIT asks that the copyright notice travel with substantial portions, so the port should carry it.
- Tests: 4 files, 581 LOC, ratio 2.71, with 339 generated cases (345 assertions) rather than the 12 printed above. That is strong coverage for a library this size: every public function has its own table. Gaps that only the source pins down: numeric segments above 2^53, pre-release versions against ranges without a pre-release, the ` - ` split limit, and odd operator prefixes passed to `satisfies`. Two rows are duplicated (test/compare.ts:109-110, test/satisfies.ts:111-112). Tests run under mocha with ts-node and match errors by message regex (`assert.throws`).
- Docs: README's "Validate version numbers (strict)" example calls `validate` instead of `validateStrict`, and read literally three of its five expected values are wrong (`validate('1.0')`, `validate('1.x')` and `validate('v1.02')` all return true). The JSDoc for `validateStrict` (src/validate.ts:26-30) names `validate` too, though its values hold for both. README also claims "full semver" and npm range compatibility, which the pre-release behavior above contradicts. Treat source and tests as the contract, not the README.
- Sampling: full scan, 10 of 10 code files. I also read all of src/ and test/, README.md, LICENSE, package.json, tsconfig.json, .mocharc.json, the CI workflow and CHANGELOG.md back to 3.5.0.
- Native code, FFI, subprocess or OS-specific paths: none found.
