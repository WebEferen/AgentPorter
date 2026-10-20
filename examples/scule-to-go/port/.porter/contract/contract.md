# Contract: scule 1.3.0

The Go port must return the same values as scule 1.3.0 (commit 90d28593c842, `src/index.ts`) for the 11
exported functions, observed at the return value of each call. Nothing in the library does I/O, keeps state or
throws for inputs inside its TypeScript signatures, so the whole contract is input-to-output on strings, string
arrays and one tri-state boolean. The existing tests are thin (63 ASCII-only rows, no `isUppercase`, no array
input, no joiner, no non-ASCII), so most of the corpus is hand-written edge cases and seeded generators recorded
from the pinned source. Confidence is high for ASCII and BMP text, and for characters above U+FFFF wherever
the original's output is valid text. For 21 inputs with astral capitals the original returns lone UTF-16
surrogates. Fixture strings must be UTF-8, so those cases were removed from the fixtures and are listed, with
the original's output as escaped text, in the unit contracts as documented divergences.

## Public surface

Call ids keep the TypeScript export names (user decision: "The fixtures keep the TypeScript call ids; the
bindings translate."). Fixtures call `./src/index.ts:<name>`; `api.json` ids are `src/index:<name>` with
`callId` set.

| Symbol | Kind | Signature | Unit | In scope | Notes |
| --- | --- | --- | --- | --- | --- |
| src/index:isUppercase | function | `isUppercase(char = ""): boolean \| undefined` | split | yes | Undocumented in README. `undefined` when any ASCII digit is present. |
| src/index:splitByCase | function | `splitByCase(str: string, separators?: readonly string[]): string[]` | split | yes | Omitted separators mean `["-", "_", "/", "."]`; `[]` means none. |
| src/index:upperFirst | function | `upperFirst(str: string): string` | split | yes | Re-cases the first UTF-16 unit only. |
| src/index:lowerFirst | function | `lowerFirst(str: string): string` | split | yes | Same, lowercase. |
| src/index:pascalCase | function | `pascalCase(): ""`, `pascalCase(str: string \| readonly string[], opts?: CaseOptions): string` | cases | yes | String or array input. |
| src/index:camelCase | function | `camelCase(): ""`, `camelCase(str: string \| readonly string[], opts?: CaseOptions): string` | cases | yes | `lowerFirst(pascalCase(str \|\| "", opts))`. |
| src/index:kebabCase | function | `kebabCase(): ""`, `kebabCase(str: string \| readonly string[], joiner?: string): string` | cases | yes | Joiner defaults to `"-"` via `??`; `""` is a valid joiner. |
| src/index:snakeCase | function | `snakeCase(): ""`, `snakeCase(str: string \| readonly string[]): string` | cases | yes | `kebabCase(str \|\| "", "_")`. |
| src/index:flatCase | function | `flatCase(): ""`, `flatCase(str: string \| readonly string[]): string` | cases | yes | `kebabCase(str \|\| "", "")`. |
| src/index:trainCase | function | `trainCase(): ""`, `trainCase(str: string \| readonly string[], opts?: CaseOptions): string` | cases | yes | Drops empty parts. README example at :86-87 is wrong. |
| src/index:titleCase | function | `titleCase(): ""`, `titleCase(str: string \| readonly string[], opts?: CaseOptions): string` | cases | yes | Minor words lowercased, first word included. |
| src/types:CaseOptions | type | `{ normalize?: boolean }` | cases | yes | Becomes a Go options struct `{ Normalize bool }`. No fixtures of its own (noFixturesReason): exercised by the `normalize` cases. |
| src/types:SplitByCase | type | type-level | none | no: user decision "Type-level helpers in src/types.ts have no runtime behavior and are out of scope." | |
| src/types:JoinByCase | type | type-level | none | no: same user decision | |
| src/types:PascalCase | type | type-level | none | no: same user decision | |
| src/types:CamelCase | type | type-level | none | no: same user decision | |
| src/types:KebabCase | type | type-level | none | no: same user decision | |
| src/types:SnakeCase | type | type-level | none | no: same user decision | |
| src/types:TrainCase | type | type-level | none | no: same user decision | Also disagrees with the runtime (src/types.ts:158). |
| src/types:FlatCase | type | type-level | none | no: same user decision | |

Not listed: the private constants `NUMBER_CHAR_RE`, `STR_SPLITTERS`, `titleCaseExceptions` and the private
helper types in `src/types.ts` (not exported); `export * from "./types"` (re-exports types only).

**CaseOptions decision:** in scope, as a runtime options shape. It is the only thing in `src/types.ts` that a
caller passes at runtime, and Go needs a named struct for it. It belongs to unit `cases`, the unit of the four functions that take it; the symbol carries
`noFixturesReason` in api.json because a type has nothing to call.

## Semantics the tests promise and the docs omit

- Parts come out in input order with their case preserved. A lower-to-upper change starts a new part
  (`fooBar` -> `foo`, `Bar`). An upper-to-lower change after two or more uppercase units moves the last
  uppercase character into the next part (`FooBARb` -> `Foo`, `BA`, `Rb`; `ALink` -> `A`, `Link`;
  `XMLHttpRequest` -> `XML`, `Http`, `Request`).
- ASCII digits are neutral: they block the next lower-to-upper split (`foo1BAR` stays whole) but not a later
  upper-to-lower split (`foo123Bar` -> `foo123`, `Bar`). `isUppercase` returns `undefined` for any argument
  containing 0-9.
- Separators split unconditionally, and consecutive separators make empty parts (`foo--bar-Baz` ->
  `foo`, ``, `bar`, `Baz`). kebab, snake and flat keep them (`foo--bar` -> `foo--bar`); pascal, camel, train and
  title lose them.
- A custom separator list replaces the defaults (`new-name-value` with `["_"]` stays one part). Each separator
  must be exactly one code point to ever match. An empty list disables splitting on characters entirely.
- Whitespace is not a separator and counts as lowercase (`Foo Bar` -> `Foo `, `Bar`).
- `normalize: true` lowercases each part before `upperFirst` (`FooBARb` -> `FooBaRb`). Without it, upper runs
  survive (`AcceptCH` -> `Accept-CH`, `WWWAuthenticate` -> `WWW-Authenticate`). A missing `opts`, `{}` and
  `{normalize: false}` behave the same.
- titleCase lowercases the 18 minor words in any position and any input case (`this-IS-aTitle` ->
  `This is a Title`, `the-end` -> `the End`, `A` -> `a`).
- Array input is taken as the parts, unsplit. Zero-argument and `undefined` calls return `""` (`isUppercase`
  returns `false`).
- Encoding: JavaScript strings are UTF-16. Case mapping is full Unicode mapping and locale-independent. See the
  leak list for where this shows.
- Errors: none. No function throws for inputs inside its TypeScript signature.

## Error model

| Source error | When | Target category (error-map.json) |
| --- | --- | --- |
| none | No call inside the TypeScript signatures throws. All 2948 recorded outcomes are values. | not applicable |
| TypeError (not recorded) | Inputs outside the signatures, for example `isUppercase(null)` or an array holding non-strings. Out of contract (see "Free to differ"). | not applicable |

No `error-map.json` is written: there is no error outcome to map.

## Leak list

Internals that leak into observable behavior. Full text, symbols and fixture tags are in `api.json` `leaks`.
GENERIC.md trap ids in brackets.

- **utf16-first-unit-casing** [T1, T2]: `upperFirst`/`lowerFirst` re-case `str[0]`, a UTF-16 unit, so a leading
  character above U+FFFF is never re-cased: `upperFirst("𐐨abc")` is `"𐐨abc"`. Applies to every part in
  pascal, camel, train and title. Representable in Go; preserve it.
- **utf16-falling-edge-split** [T1, T2]: `splitByCase`'s falling edge uses `buff.length > 1`, `buff.at(-1)` and
  `buff.slice` in UTF-16 units. A single astral capital counts as length 2 and the cut moves only its low
  surrogate: `splitByCase("𐐀a")` is `["\ud801","\udc00a"]`. pascal, camel and flat glue the halves back into
  valid text (`flatCase("𐐀a")` is `"𐐀a"`, capital kept, because lowercasing ran on the halves). Those cases
  stay in the fixtures (tags `astral-upper`, `utf16-falling-edge`); preserve them. The cases whose output keeps
  a lone surrogate were removed (next item).
- **lone-surrogate-encoding** [T44]: for 21 inputs (splitByCase, kebabCase, snakeCase, trainCase and titleCase
  on `𐐀a`, `A𐐀a`, `𐐀𐐨`; train and title with and without normalize) the original returns lone surrogates.
  They were recorded once and then removed from the fixtures, because fixture strings must be UTF-8
  (`knowledge/oracles/CONTRACT.md`: "Strings stay strings (UTF-8)") and porter's tooling fails on them. Each
  removed input and its original output, as escaped text, is listed under "Removed cases" in
  `units/split.md` (3) and `units/cases.md` (18). A Go string cannot hold a lone surrogate
  as valid UTF-8 (`encoding/json` turns an unpaired `\udXXX` into U+FFFD), so the port's result for these
  inputs is a documented divergence; the strategy phase picks the target behavior.
- **code-point-iteration**: separators match single code points (astral `😀` works; `--`, `::`, `""` and
  decomposed `e\u0301` never match). Combining marks are lowercase characters (`CAFE\u0301` -> `CAF`, `E\u0301`).
- **full-case-mapping** [T5, T6]: `ß` -> `SS`, `ŉ` -> `ʼN`, `ﬀ` -> `FF`, `ǰ` -> `J̌`, `ΐ` -> 3 code points,
  `İ` -> `i\u0307`. Go's `strings.ToUpper`/`ToLower` are one-to-one and differ. No locale rules.
- **final-sigma**: lowercasing whole parts applies Final_Sigma (`ΑΣ` -> `ας`). Per-rune lowercasing does not.
- **is-uppercase-definition**: upper means "lowercasing changes it" over the whole argument, not category Lu:
  `Ⅻ`, `Ⓐ`, `ǅ`, Kelvin sign are upper; `𝐀` (Lu, no lowercase mapping), emoji, CJK, spaces, combining marks
  are lower.
- **ascii-digit-tristate** [T20]: `/\d/` is ASCII-only; `isUppercase` returns `undefined` (fixture
  `{"$undefined": true}`; Go binding returns the harness `Undefined` marker). `٣`, `１`, `²` are lowercase.
- **title-exception-regex**: `/.../i` without `u` never folds non-ASCII to ASCII, so `aſ`, `iſ`, `ıs` are not
  minor words. Go `(?i)` folds `ſ` to `s` and would differ.
- **separators-nil-vs-empty** [T41, T42]: omitted or `undefined` separators mean the defaults; `[]` means none.
- **joiner-nullish** [T42]: `kebabCase` joiner `??` `"-"`; `""` is kept.
- **empty-parts**: kept by kebab, snake, flat; dropped by train, title (`filter(Boolean)`), pascal, camel.
- **array-input**: arrays are parts, never re-split.
- **whitespace-not-splitter**: `"FOO BAR"` -> `FO`, `O `, `BAR`.
- **separator-resets-case**: a separator resets the previous-case state, so no edge fires right after it
  (`-ABc` -> ``, `A`, `Bc`). The `previousSplitter` flag is redundant and can go.
- **undefined-defaults** [T42, T43]: zero-argument and `undefined` calls give `""` (`false` for
  `isUppercase`); `normalize` is a truthiness check.
- **unicode-version**: recorded on Node 24.18.0 (ICU 78.3, Unicode 17.0); Go's `unicode` is 15.0.0. The corpus
  only uses characters whose case mappings date from Unicode 11 or earlier, so it does not depend on the gap.
- **readme-traincase**: README.md:86-87 says `trainCase("FooBARb")` is `Foo-Ba-Rb`; the code gives `Foo-BA-Rb`
  (fixture `trainCase.doc.L86`). The code wins.

Free to differ:

- Go names (call ids keep the TypeScript names; bindings translate).
- How overloads, optional arguments, string-or-array input and the options object become Go API (slice
  variants, variadics, an options struct), provided the nil-versus-empty separator and `""` joiner cases still
  come out the same.
- The type-level results in `src/types.ts`.
- Private constants and helpers: the regexes may become table lookups if they match the same strings; snake
  and flat need not delegate to kebab; the state flag names.
- `nil` or empty slice from `splitByCase("")` (both serialize as `[]`).
- Inputs outside the TypeScript signatures (null, numbers, objects, non-string array elements).
- Performance and layout.

## Observation boundary per unit

| Unit | Observed | Normalization |
| --- | --- | --- |
| split | return values (string arrays, strings; `true`, `false` or `undefined` for isUppercase) | none |
| cases | return values (strings; CaseOptions observed through the 288 `normalize` cases) | none |

## Fixtures

```text
| Unit | Files | Cases | Kinds | Origins |
| --- | --- | --- | --- | --- |
| cases | 1 | 1982 | value 1982 | doc 11, generated 1150, hand-written 777, reference-test 44 |
| split | 1 | 966 | value 966 | doc 3, generated 760, hand-written 184, reference-test 19 |
```

`porter fixtures validate`: 2948 cases in 2 units, 0 errors. Every oracle.json encodes as UTF-8 (no lone
surrogate escapes).

- Harvested (`reference-test:test/scule.test.ts:<line>`): all 63 rows of the 11 `test.each` tables. Every
  recorded value equals the table's expectation. `test/types.test-d.ts` is type-level and out of scope.
- README examples (`doc:README.md:<line>`): 14, including the disagreeing trainCase example.
- Hand-written (961): a shared list of 56 inputs (case transitions, digits, whitespace, separators, Latin-1,
  ß/ẞ, Greek sigma, Turkish İ/ı, ǅ digraphs, ligatures, NFD combining marks, Cyrillic, CJK, letter numbers,
  circled and fullwidth letters, emoji and ZWJ sequences, astral lower and upper letters, mathematical
  alphanumerics, a 1800-character input) run through splitByCase and all seven case functions, and again with
  `{normalize: true}` for pascal, camel, train and title; array input (10 shapes); no-argument and
  `undefined` calls; splitByCase custom separators (empty list, undefined, multi-character, empty string,
  emoji, precomposed and decomposed é, letters, digits, duplicates); 44 direct isUppercase cases; 26 to 30
  upperFirst and lowerFirst cases on special casing; kebabCase joiners; HTTP header names for trainCase;
  titleCase minor words including the long-s and dotless-i folding traps.
- Generated (1910, fixed seeds 101-110 and 201-220): random strings over an ASCII alphabet and over a mixed
  alphabet of the risky characters above, word concatenations, random separator lists, random joiners, random
  arrays, random `normalize`. The generator alphabets contain no astral capitals, so no generated case
  produces a lone surrogate.
- Tags mark every risk family (`unicode`, `astral`, `full-case-mapping`, `final-sigma`, `utf16-first-char`,
  `utf16-falling-edge`, `regex-i-ascii-only`, `digits`, `array-input`, `normalize`, ...).
- Removed (21): hand-written cases whose recorded output contained lone surrogates (every expect containing
  U+D800 to U+DFFF, and only those; no input contained one). They are excluded from the case specs and listed
  with their original outputs in the unit contracts.

Recording. The package entry points at `dist/`, which the checkout does not have, and building it would mean
installing dev dependencies in the source checkout. Instead the oracle loads the pinned `src/index.ts`
directly with Node's built-in type stripping. `.porter/oracle/driver/` is a copy of the plugin's JavaScript
oracle (`knowledge/oracles/javascript/`; there is no `typescript/` oracle) plus `ts-resolve.mjs`, a preload
that resolves the source's extensionless `./types` import and loads `.ts` files as ES modules. Only resolution
changes; the executed code is the pinned file with types erased. From the workspace root, with Node 22.18+ or
23.6+ (type stripping on by default and `module.registerHooks`; recorded with 24.18.0):

```sh
python3 <plugin>/scripts/porter.py fixtures expand
node --import ./.porter/oracle/driver/ts-resolve.mjs .porter/oracle/driver/oracle.mjs --workspace .porter
python3 <plugin>/scripts/porter.py fixtures validate
```

## Contract rerun: units re-filed

The draft cut (src-titlecase, src-isuppercase, types-types) had a call cycle: splitByCase calls isUppercase,
while pascalCase, kebabCase and trainCase call splitByCase. The contract was rerun to re-file the same case
specs into an acyclic cut, then re-recorded from the same pinned original with the same driver command:
`split` (isUppercase, splitByCase, upperFirst, lowerFirst; 966 cases) and `cases` (pascalCase, camelCase,
kebabCase, snakeCase, flatCase, trainCase, titleCase and CaseOptions; 1982 cases). Case names, inputs, seeds
and per-function counts are unchanged.
