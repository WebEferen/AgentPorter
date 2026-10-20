# Contract: compare-versions 6.1.1

The port must reproduce the return values and errors of the five functions exported by `src/index.ts`
(`compareVersions`, `compare`, `satisfies`, `validate`, `validateStrict`) for any string input, observed
at the call boundary: a JSON value (an integer -1/0/1 or a boolean) or an error category plus its exact
message. It must reproduce the library's quirks, not the semver spec or npm: `parseInt` prefix parsing,
float64 segments, wildcard equality, missing segments counting as `0`, JS regex and whitespace semantics,
and the hand-rolled range grammar. Confidence is high. The source's own table-driven suite (339 runtime
cases) is harvested in full except four rows that pass a JavaScript function, every harvested assertion
agrees with the recorded fixtures, and hand-written edge cases plus seeded generators cover the quirks the
suite leaves open. 4215 fixtures were recorded from commit 497a7e0c5fc0 under Node 24.18.0.

## Public surface

| Symbol | Kind | Signature | Unit | In scope | Notes |
| --- | --- | --- | --- | --- | --- |
| src/compareVersions:compareVersions | function | `compareVersions(v1: string, v2: string): number` | satisfies-satisfies | yes | call id `compare-versions:compareVersions`; returns -1, 0 or 1; sort comparator |
| src/compare:compare | function | `compare(v1: string, v2: string, operator: CompareOperator): boolean` | satisfies-satisfies | yes | call id `compare-versions:compare`; operator checked at run time |
| src/satisfies:satisfies | function | `satisfies(version: string, range: string): boolean` | satisfies-satisfies | yes | call id `compare-versions:satisfies`; recursive range grammar |
| src/validate:validate | function | `validate(version: string): boolean` | validate-validate | yes | call id `compare-versions:validate`; never throws |
| src/validate:validateStrict | function | `validateStrict(version: string): boolean` | validate-validate | yes | call id `compare-versions:validateStrict`; never throws |
| src/utils:CompareOperator | type | `'>' \| '>=' \| '=' \| '<' \| '<=' \| '!='` | utils-utils | yes | re-exported; no fixtures (type only) |
| src/utils:semver | constant | the shared semver `RegExp` (`/.../i`) | utils-utils | yes, crate-private | not in the package API; no call id; pinned through validate and compareVersions |
| src/utils:validateAndParse | function | `validateAndParse(version: string): RegExpMatchArray` | utils-utils | yes, crate-private | not in the package API; pinned through compareVersions, compare, satisfies |
| src/utils:compareSegments | function | `compareSegments(a, b): number` | utils-utils | yes, crate-private | not in the package API; pinned through compareVersions |
| src/index:index | module | re-exports the five functions and the type | src-index | yes | package entry; no default export |
| lib/umd:window.compareVersions | export | UMD browser global | none | no: JS packaging, no Rust equivalent | |

The three `src/utils` exports are module exports used by sibling modules, not package API: `src/index.ts`
does not re-export them and the only way to reach them is a deep import of build output. They are in scope
because they are code the port needs. The final `decompose` drops out-of-scope symbols from every unit, so
marking them out of scope would leave the comparison core unowned. Each carries `noFixturesReason`, and the
Rust port keeps them crate-private.

Fixtures use the TypeScript call ids `compare-versions:<export>` (the package's import specifier, see
`callId` in api.json). The Rust bindings translate them; they are not renamed.

## Semantics the tests promise and the docs omit

- Ordering: `compareVersions` returns exactly -1, 0 or 1 (`strictEqual` in test/compare.ts), and works as a
  stable `Array.prototype.sort` comparator (test/sort.ts). Ties such as `1.0` and `1.0.0` keep input order.
- Identity and padding: missing segments are `0`, so `1`, `1.0`, `1.0.0` and `1.0.0.0` are equal; a fourth
  (Chromium) segment is compared; leading zeros are ignored (`01.0.0` equals `1`); a leading `v` is ignored.
- Wildcards: `x`, `X` and `*` equal any segment (test/compare.ts:127-152). The suite never checks the
  consequences: the order is not transitive, and `x` as a pre-release identifier is a wildcard too.
- Pre-release: a release is above its pre-releases; identifiers compare left to right with numeric
  identifiers as numbers (`beta.11` > `beta.2`); a missing identifier is `0`, so `1.0.0-alpha` equals
  `1.0.0-alpha.0` (not covered by the suite, recorded as edge cases).
- Build metadata is ignored entirely (test/compare.ts:92-104).
- Ranges: `^`, `~`, the six operators, space-separated sets, `||` and ` - ` hyphen ranges, with whitespace
  after operators tolerated (test/satisfies.ts:127-137). A range without a pre-release accepts pre-release
  versions, and a range with one rejects every release, both unlike npm.
- Errors: tests match messages by regex, and the category matters (`TypeError` for types, `Error` for
  values). The full messages are listed in the error model below.
- Precision, locale, timezone, encoding: no locale or timezone use. Numbers are float64, which the suite does
  not test; strings are ASCII after the regex, so encoding cannot affect results except through the JS regex
  dialect (see the leak list).

## Error model

| Source error | When | Target category (error-map.json) |
| --- | --- | --- |
| `Error`: `Invalid argument not valid semver ('<input>' received)` | a version or comparator does not match the semver regex; v1 before v2 | `Error` |
| `Error`: `Invalid operator, expected one of >\|>=\|=\|<=\|<\|!=` | `compare` operator, or a `satisfies` comparator prefix, outside the six operators (and not `^`/`~` in satisfies) | `Error` |
| `TypeError`: `Invalid argument expected string` | a version argument is not a string (cases named `*nonstring*`) | `Error` |
| `TypeError`: `Invalid operator type, expected string but got <typeof>` | `compare` operator is not a string; checked first (cases named `*nonstring*`) | `Error` |
| `TypeError`: V8 text (`range.replace is not a function`, ...) | `satisfies` range is not a string; 4 cases with `ignore-message` | `Error` |

error-map.json is a proposal for the strategy gate: the Rust harness names a category after the error type,
so one `compare_versions_port::Error` enum reports `Error` for all of them and grades EQUIVALENT. Messages are
compared, so its `Display` must reproduce the text above.

## Leak list

Internals that leak into observable behavior and must be preserved or consciously diverged from. Full text and
case globs are in `api.json.leaks`.

- `semver-regex-dialect`: ECMAScript RegExp without `u`. `\d` is ASCII only, `/i` does not fold the Kelvin
  sign, long s or dotless i into `[a-z]`, and `$` does not match before a trailing newline. Rust's `regex` is
  Unicode-aware by default and differs on all three unless the pattern opts out.
- `semver-prefix-run`: any run of `v ^ ~ < > =` (and `V`) before the first digit is accepted by
  compareVersions; validate additionally needs a lowercase `v` or a digit first.
- `parseint-prefix`: segments go through `parseInt(v, 10)`: `10a` is 10, `1-2` is 1, `-5` is negative.
- `float64-segments`: numbers above 2^53 round, 309+ digit runs become Infinity. u64 parsing differs.
- `number-to-string`: in a number-vs-string comparison the number is formatted by JS `String()` (`-0` to
  `0`, `Infinity`, exponent form).
- `string-order`: case-sensitive code-unit order (`Beta` < `alpha`).
- `wildcard-equality`, `missing-segment-zero`, `prerelease-precedence`: see the semantics above.
- `prerelease-in-ranges`, `fourth-segment-ignored`, `range-split-limit`, `range-whitespace`,
  `range-lazy-evaluation`: the range grammar's departures from npm, JS `split(' - ', 2)`, ECMAScript `\s`
  and `trim()` (both include U+FEFF, Rust's do not), and short-circuit evaluation that skips malformed
  comparators after the deciding one.
- `error-classes-and-messages`, `operator-list-order`, `typeof-names`, `error-precedence`: exact messages,
  the `Object.keys` order of the operator list, JS `typeof` names, and which check fails first.
- `non-string-arguments`: every function accepts any JS value at run time. 48 cases have `nonstring` in
  their name. A `&str` API cannot receive them, so the strategy has to decide: one divergence covering
  `*nonstring*`, or bindings over `serde_json::Value`.
- `runtime-error-messages`: four satisfies cases carry V8's own message (normalized with `ignore-message`).
- `sort-comparator`: the sort tests depend on a stable sort.

Depends on the JS runtime (decision for the strategy phase): `semver-regex-dialect`, `range-whitespace`
(ECMAScript `\s`/`trim`), `float64-segments` and `number-to-string` (JS Number), `typeof-names`,
`runtime-error-messages` (V8), `non-string-arguments` (dynamic typing), `sort-comparator` (stable
`Array.prototype.sort`).

Free to differ:

- module layout and helper names (`tryParse`, `forceType`, `isWildcard`, `compareStrings`, `operatorResMap`);
- the parsed representation (the source uses a `RegExpMatchArray` with `undefined` holes);
- whether the matchers are regexes, as long as the accepted language is identical, leaks included;
- the shape of the Rust error type and the operator type (string or enum), within the error map and fixtures;
- compareVersions' Rust return type (`i32` or `Ordering`), as long as the binding serializes -1, 0, 1;
- performance and regex engine complexity; JS packaging (ESM, UMD, browser global, source maps, `.d.ts`).

## Observation boundary per unit

| Unit | Observed | Normalization |
| --- | --- | --- |
| satisfies-satisfies | return values (integers, booleans) and errors (category, message) of compareVersions, compare, satisfies | none, except `ignore-message` on 4 cases whose message is generated by V8 |
| validate-validate | return values (booleans) of validate, validateStrict | none |
| utils-utils | nothing directly (no call id); covered through the two units above | n/a |
| src-index | nothing directly (re-exports); every export is called through the package entry | n/a |

## Fixtures

```text
| Unit | Files | Cases | Kinds | Origins |
| --- | --- | --- | --- | --- |
| satisfies-satisfies | 1 | 3041 | error 644, value 2397 | generated 2450, hand-written 255, reference-test 336 |
| validate-validate | 1 | 1174 | value 1174 | generated 1000, hand-written 82, reference-test 92 |
```

How they were recorded:

- Oracle: the plugin's JavaScript driver, copied to `.porter/oracle/driver/oracle.mjs`, on Node 24.18.0.
  The checkout has no `lib/` (build output is not committed) and no `node_modules`, so the pinned source was
  compiled exactly as `npm run build:esm` does (`tsc -p tsconfig.json --module esnext --target es2017`) with
  the lockfile's TypeScript 5.5.3, installed under `.porter/oracle/node_modules/`, into
  `.porter/oracle/build/lib/esm/` (both gitignored). `.porter/oracle/driver/source-entry-hook.mjs`, loaded with
  `node --import`, redirects the package entry points (`lib/umd/index.js`, `lib/esm/index.js`) to that build.
  The source tree was not modified (`git status` clean at 497a7e0c5fc0 after recording).
- Re-record:

  ```sh
  node .porter/oracle/node_modules/typescript/bin/tsc -p <source>/tsconfig.json --module esnext --target es2017 --outDir .porter/oracle/build/lib/esm
  printf '{"type": "module"}\n' > .porter/oracle/build/lib/esm/package.json
  porter fixtures expand
  node --import ./.porter/oracle/driver/source-entry-hook.mjs ./.porter/oracle/driver/oracle.mjs --workspace .porter
  porter fixtures validate
  ```

- Harvested (origin `reference-test:<file>::L<line>`, the line of the table row that generates the mocha
  test; the looped `it` at test/compare.ts:269 uses `::L269` for all its rows): all 339 runtime tests except
  the four rows that pass a JavaScript function, which JSON cannot carry (test/compare.ts:160, :258, :269 row
  275, test/validate.ts:12). The three sort tests become every ordered pair of their inputs (90 cases).
  Recording checked all 338 harvested assertions against the suite's expected values and replayed the three
  sorts: no mismatch.
- Hand-written (origin `hand-written`, 337 cases): empty, whitespace, malformed, error precedence, prefix
  runs, wildcards and non-transitivity, `parseInt` prefixes, negatives, Number-to-String, 2^53 and u64
  boundaries, Infinity, 10,000-character inputs, Unicode digits and case folding, range whitespace (NBSP,
  BOM, U+2028), lazy evaluation, the split limit, npm divergences, non-string inputs.
- Generated (origin `generated:<block>:seed=<n>`, fixed seeds): `gen-cv-grammar`, `gen-cv-prerelease`,
  `gen-cv-bignum`, `gen-cv-2pow53`, `gen-cv-2pow53-prerelease`, `gen-cv-junk`, `gen-compare-ops`,
  `gen-sat-ranges`, `gen-sat-junk`, `gen-validate-grammar`, `gen-strict-grammar`, `gen-validate-unicode`,
  `gen-strict-unicode`.
