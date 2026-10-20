# Survey: scule 1.3.0

scule is the unjs string-case utility library (pascalCase, camelCase, kebabCase, snakeCase, flatCase,
trainCase, titleCase, plus splitByCase, upperFirst, lowerFirst and isUppercase), published on npm and used
across the unjs/Nuxt ecosystem to convert identifiers and HTTP header names. All runtime logic is in one pure
module, `src/index.ts`: 11 exported functions, about 120 lines of executable code once overload signatures
and the type-only import are removed. `src/types.ts` is type-level only and out of scope by user decision.
Verdict: a very small, low-risk port with no I/O, no runtime dependencies and no native code. The risk is
narrow: the output follows JavaScript string semantics (UTF-16 indexing, full Unicode case mapping, ASCII-only
regex classes) that the existing tests never exercise, so the contract needs generated fixtures with
non-ASCII input to pin it down.

## Facts

| Fact | Value |
| --- | --- |
| Package | scule 1.3.0 |
| Commit | 90d28593c842 |
| License | MIT (copyleft: none) |
| Kind | library |
| Primary language | typescript |
| Source LOC | 332 |
| Tests | 2 files, 235 LOC, 12 cases, ratio 0.71 |
| Test runners | mocha-style (describe/it), vitest |
| Public symbols | 37 |
| Modules by coupling | pure 2 |
| Runtimes | not declared |
| Sampled | no |

| Module | Language | LOC | Coupling | Signals | Risk tags | Public symbols |
| --- | --- | --- | --- | --- | --- | --- |
| src/index | typescript | 175 | pure |  | nullability, numeric, reflection | isUppercase, splitByCase, splitByCase, splitByCase, upperFirst, lowerFirst, pascalCase, pascalCase, pascalCase, camelCas |
| src/types | typescript | 157 | pure |  | nullability | CaseOptions, SplitByCase, JoinByCase, PascalCase, CamelCase, KebabCase, SnakeCase, TrainCase, FlatCase |

Corrections after reading the code:

- **Tests, "12 cases" is wrong.** The TypeScript case regex in the survey script (`\b(it|test)\s*\(\s*['"\`]`)
  only matches `test("name", ...)`. All 12 hits are the `test(...)` blocks in `test/types.test-d.ts`, which are
  compile-time type assertions on `src/types.ts` (out of scope). It missed all 11 `test.each([...])(...)`
  tables in `test/scule.test.ts`, which hold **63 parametrized runtime cases** (splitByCase 13, trainCase 13,
  kebabCase 8, pascalCase 7, flatCase 7, titleCase 5, upperFirst 3, lowerFirst 3, camelCase 2, snakeCase 2).
  In-scope ratio: 149 runtime test LOC against 175 LOC in `src/index.ts`, about 0.85.
- **Public symbols, "37" is inflated.** 28 entries come from `src/index.ts`, and 17 of them are TypeScript
  overload signatures repeating a name: splitByCase x3 (`src/index.ts:22,23,27`), pascalCase x3 (`:91,92,96`),
  camelCase x3 (`:107,108,112`), kebabCase x4 (`:122,123,126,130`), snakeCase x3, flatCase x3, trainCase x3,
  titleCase x3. Distinct runtime functions: **11**. The other 9 are exported types from `src/types.ts`. With the
  type helpers out of scope, only `CaseOptions` (`{ normalize?: boolean }`, `src/types.ts:42-44`) carries
  runtime meaning. In-scope public surface: 11 functions and 1 options shape. The src/index public-symbol cell
  above is also truncated ("camelCas") and repeats overload names.
- **Source LOC "332"** includes the 157 lines of `src/types.ts`, which emit no JavaScript. The in-scope file is
  `src/index.ts` (175), of which 55 lines are the type import (`:1-10`), overload declarations (`:22-26`,
  `:91-95`, `:107-111`, `:122-129`, `:141-144`, `:149-152`, `:157-161`, `:175-182`) and the type re-export (`:197`).
- **Risk tags miss `unicode` and `regex` for src/index.** The code reaches Unicode behavior through plain
  `toLowerCase`/`toUpperCase`, `for...of` and `str[0]`, and its regexes live in constants
  (`NUMBER_CHAR_RE.test`, `titleCaseExceptions.test`), so the scanner patterns did not fire. Both are added
  below. `numeric` comes from `Math.max` at `src/index.ts:65`, which is harmless index arithmetic; the real
  numeric concern there is UTF-16 length, covered under unicode.
- Kind "library" and coupling "pure 2" are correct (evidence below).

## Scope

- Kind: library. No CLI, service or app. The only entry points are the package exports (`package.json:8-18`,
  pointing at the built `dist/index.*`); the `"./*": "./*"` subpath export only exposes published files.
- In scope: `src/index.ts`, all 11 exported functions: `isUppercase`, `splitByCase`, `upperFirst`,
  `lowerFirst`, `pascalCase`, `camelCase`, `kebabCase`, `snakeCase`, `flatCase`, `trainCase`, `titleCase`,
  plus the `CaseOptions` options shape (`normalize`). `isUppercase` is exported (`src/index.ts:15`) but not
  documented in README.md. The 63 runtime cases in `test/scule.test.ts` seed the contract.
- Out of scope:
  - `src/types.ts`: type-level helpers (`SplitByCase`, `JoinByCase`, `PascalCase`, `CamelCase`, `KebabCase`,
    `SnakeCase`, `TrainCase`, `FlatCase` and private helpers) that compute literal result types at compile
    time. No runtime behavior; excluded by user decision. Only `CaseOptions` carries over, as the options shape.
  - `test/types.test-d.ts`: 12 type tests (39 `assertType`/`expectTypeOf` assertions) on those types.
  - `export * from "./types"` at `src/index.ts:197`: re-exports types only.
  - Build and tooling (unbuild, eslint, prettier, changelogen, `.github/workflows/*.yml`, `pnpm-lock.yaml`):
    Node packaging, not library behavior.

## Where the risk is

Coupling is confirmed pure for both modules. `src/index.ts` imports only types (`import type` at
`src/index.ts:1-10`), has no external imports, no I/O, no globals and no module-level mutable state (the two
constants at `:12-13` and `:172-173` are read-only). `src/types.ts` contains only `type` declarations
(`src/types.ts:1-167`) and emits no code. All rows below are in `src/index.ts` unless stated.

| Module | Coupling | Why it is risky | Risk tags |
| --- | --- | --- | --- |
| src/index: splitByCase | pure | Iterates code points (`for (const char of str)`, `:43`) but measures and slices in UTF-16 units (`buff.length > 1`, `buff.at(-1)`, `buff.slice`, `:63-65`). A cased astral letter followed by a lowercase letter splits a surrogate pair: `"A\u{10400}a"` gives `["A\ud801", "\udc00a"]`, lone surrogates that a UTF-8 string cannot represent. | numeric, unicode (added) |
| src/index: case detection | pure | `isUppercase` is `char !== char.toLowerCase()` (`:19`), so any char whose JS lowercase differs counts as upper, and uncased chars (space, CJK, emoji) count as lower: whitespace is a plain char, not a splitter (`"foo bar"` stays one part). Digits match `/\d/` without the `u` flag (`:12`, ASCII 0-9 only) and return `undefined`, which suppresses the next rising edge (`"foo1BAR"` is one part, `"fooBAR"` is two) while the falling edge still fires (`"foo123Bar"` gives `["foo123", "Bar"]`). The exported function accepts any string: `isUppercase("a1")` is `undefined`, `isUppercase("aB")` is `true`. | nullability, regex (added), unicode (added) |
| src/index: splitter state | pure | Tri-state `boolean \| undefined` flags compared with `=== true/false` (`:40-41`, `:54-63`). `previousSplitter` is never set back to true (the splitter branch `continue`s at `:50` before `:75`), so it really means "a non-splitter char has been seen". A literal port of the names invites a "fix" that changes output. | nullability |
| src/index: upperFirst / lowerFirst | pure | `str[0]` is the first UTF-16 unit (`:84`, `:88`), so a leading astral letter is never re-cased, and `toUpperCase` applies full mappings that change length (`upperFirst("ßa")` is `"SSa"`; also ŉ, ﬀ). Every pascal, camel, train and title result passes through these. | unicode (added) |
| src/index: lowercasing in joins | pure | kebab, snake, flat and `normalize: true` call `toLowerCase()` on whole parts (`:102`, `:136`, `:168`, `:191-192`), which applies context-sensitive rules: `kebabCase("ΑΣ")` is `"ας"` (final sigma), `kebabCase("İstanbul")` is `"i̇stanbul"` (two code points for İ). Per-character lowercasing gives different output. | unicode (added) |
| src/index: titleCase | pure | Minor words are a non-Unicode case-insensitive regex (`:172-173`), applied to every part including the first: `titleCase("the-end")` is `"the End"`. | regex (added) |
| src/index: string-or-array input | pure | Seven case functions accept `string \| readonly string[]` and branch on `Array.isArray` (`:101`, `:135`, `:166`, `:187`); overloads add zero-arg forms and `kebabCase(str, joiner)` (`:126-129`); `splitByCase` takes an optional separator list compared per code point (`:31`, `:45`). The API shape needs a decision before units are cut. | reflection, nullability |
| src/index: empty parts, empty input | pure | Per-function differences that are easy to normalize by accident: kebab, snake and flat keep empty parts (`"foo--bar"` stays `"foo--bar"`, `test/scule.test.ts:73`); train and title drop them via `.filter(Boolean)` (`:167`, `:188`); pascal and camel drop them through `upperFirst("")`. `splitByCase("")` is `[]` but `splitByCase("-")` is `["", ""]` (`:34`, `:47`, `:78`). | nullability |
| src/types | pure (type-only) | Out of scope. Its result types disagree with the runtime in places (`TrainCase` passes `Joiner` as the accumulator and drops `Normalize` for string input, `src/types.ts:158`), so it must not be used as a behavior reference. | nullability |

## Flags for the user

- License: MIT (`LICENSE`, `package.json:6`). No copyleft. Keep the copyright notice (Pooya Parsa) with the port.
- Tests: 63 parametrized runtime cases in `test/scule.test.ts` (149 LOC against 175 source LOC, about 0.85),
  not the 12 the facts table reports; those 12 are type tests on out-of-scope code. Every runtime input is
  ASCII. Gaps: no direct test of `isUppercase`; `pascalCase` and `camelCase` are only tested with
  `normalize: true` (`test/scule.test.ts:54`, `:63`), so their default mode rests on README examples; no runtime
  test covers array input, a custom `kebabCase` joiner, `titleCase` with `normalize`, digits before uppercase,
  whitespace, or any non-ASCII text. The contract should add fixtures generated from the JS implementation for
  these, including final sigma, İ, ß, astral cased letters and emoji.
- Docs disagree with code: `README.md:86-87` says `trainCase("FooBARb")` gives `Foo-Ba-Rb`; the code gives
  `Foo-BA-Rb` (`splitByCase` yields `["Foo", "BA", "Rb"]` per `test/scule.test.ts:21`, and `trainCase` without
  `normalize` keeps `BA`, `src/index.ts:166-169`, consistent with `AcceptCH` -> `Accept-CH` at
  `test/scule.test.ts:117`). Treat the code as the reference.
- Sampling: full scan. All 4 code files read in full (`src/index.ts`, `src/types.ts`, `test/scule.test.ts`,
  `test/types.test-d.ts`), plus README.md, the v1.1.1 to v1.3.0 entries of CHANGELOG.md, package.json, LICENSE,
  tsconfig.json and `.github/workflows/ci.yml`. Not read: `pnpm-lock.yaml` (dev tooling lockfile) and
  `.github/workflows/autofix.yml`.
- Native code, FFI, subprocess or OS-specific paths: none found. No runtime dependencies (`package.json`
  lists devDependencies only); CI runs Node 18 on ubuntu-latest (`.github/workflows/ci.yml`).
