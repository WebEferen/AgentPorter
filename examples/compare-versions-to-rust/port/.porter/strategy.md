# Strategy: compare-versions 6.1.1 -> rust (compare-versions-port)

compare-versions is 214 lines of pure TypeScript, so the port is a single std-only Rust library crate
(`compare_versions_port`, edition 2021, stable) with an idiomatic API: `&str` arguments and
`Result<_, Error>` for failures. The comparison core (utils-utils) and the range grammar
(satisfies-satisfies) are code ports, because the contract asks for the library's quirks (`parseInt`
prefixes, float64 segments, wildcard equality, JS regex and whitespace rules) and the shortest way to keep
them is to follow the source logic line by line. validate-validate is the tracer bullet: two boolean
matchers over the shared semver grammar, with 1,174 fixtures and no error paths, which proves the scaffold,
the harness and the review loop before the error-heavy unit. src-index lands last and pins the public
surface. At the gate you approve the four units and their order, the one planned divergence (non-string
arguments), the error mapping, and the budgets.

## Per-unit strategy

| Unit | Layer | Strategy | Why |
| --- | --- | --- | --- |
| utils-utils | foundation | code port | `tryParse`/`forceType`/`compareStrings` encode JS coercion rules that fixtures pin exactly; translate them literally into Rust helpers. Also owns `Error` and `CompareOperator`. |
| validate-validate (tracer) | core | contract port | Two predicates; reimplement as hand-written matchers that accept exactly the regex languages. |
| satisfies-satisfies | core | code port | The hand-rolled range grammar (replace, split with limit, recursion, lazy `some`/`every`) has quirks the fixtures pin; follow the source structure. |
| src-index | entry | contract port | `src/lib.rs` re-exports and crate docs; no logic. |

## Idiom map

Seeded from `knowledge/pairs/GENERIC.md` (there is no typescript-to-rust pair file) and specialized to this
codebase.

| Concern | Source idiom | Target idiom | Rule for this port |
| --- | --- | --- | --- |
| Errors | `throw new Error(msg)` / `throw new TypeError(msg)` | `Result<T, Error>` with one public `enum Error` | Variants `InvalidVersion(String)` and `InvalidOperator`; `Display` reproduces the source messages byte for byte (`Invalid argument not valid semver ('<input>' received)`, `Invalid operator, expected one of >\|>=\|=\|<=\|<\|!=`). Implements `std::error::Error`. Error map: `TypeError` and `Error` both report `Error` (contract/error-map.json), graded EQUIVALENT. Check order follows the source: operator before versions, v1 before v2. |
| Absence | `undefined` regex groups, `a[i] \|\| '0'`, `r2 ?? 'x'` | `Option<&str>` in a fixed-size parsed struct or `[Option<&str>; 5]` | `None` and the empty string both read as `"0"` in segment comparison, as `\|\|` does. |
| Dynamic types | `typeof x !== 'string'` checks, any JS value accepted | `&str` parameters | Non-string inputs cannot be expressed; planned divergence `non-string-arguments` covers fixtures named `*nonstring*` (see scope). |
| Operator | `CompareOperator` string union, checked at run time | `pub enum CompareOperator` with `FromStr`, plus `compare(v1, v2, op: &str)` | `compare` keeps a `&str` operator so the invalid-operator error stays reachable (it is reachable from `satisfies` anyway); `CompareOperator` implements `FromStr` with the same error. The operator list in the message keeps `Object.keys` order `>\|>=\|=\|<=\|<\|!=`. |
| Numbers | `parseInt(v, 10)` returning float64, `isNaN` | `fn parse_int(&str) -> Option<f64>` | Leading JS whitespace skipped, optional sign, longest ASCII digit prefix parsed with `str::parse::<f64>()` (correctly rounded, matches V8); no digits gives `None` (the NaN branch). Comparison of two numbers uses f64 `partial_cmp`. |
| Number to string | `String(n)` in `forceType` when one side is a number and the other a string | `fn js_number_to_string(f64) -> String` | ECMAScript Number::toString: `-0` prints `0`, `Infinity`, shortest round-trip digits, exponent form `1e+21` from 1e21 upward. Build it from `format!("{:e}")` digits; std only. |
| Strings | JS string compare (UTF-16 code units) | `str` `Ord` | Byte order equals code-unit order for every string the semver matcher accepts (ASCII only). Inputs are `&str`; error messages embed the input unchanged. |
| Regex | ECMAScript `RegExp` (`semver` with `/i`, `validateStrict`, `/([><=]+)\s+/g`, `/\s{2,}/g`, `/^([<>=~^]+)/`, `/^[v\d]/`) | hand-written matchers on `&str`, std only | No `regex` crate (the user prefers std; it is the verified fallback in deps.md). `\d` is ASCII `0-9`; `/i` folds ASCII only (no Kelvin sign or long s); `$` is end of input only; `\s` is the ECMAScript WhiteSpace plus LineTerminator set (ASCII tab, LF, VT, FF, CR, space, plus U+FEFF, U+00A0, U+1680, U+2000-U+200A, U+2028, U+2029, U+202F, U+205F, U+3000), not `char::is_whitespace`. `trim()` uses the same set. |
| Split | `split('\|\|')`, `split(' - ', 2)`, `split(' ')` | `str::split`, `splitn(2, ..)` then drop the remainder | JS `split(sep, 2)` keeps only the first two pieces and discards the rest; `splitn(2)` keeps the rest in the second piece, so take the first two pieces of a plain `split` instead. |
| Short-circuit | `.some(...)`, `.every(...)` | `Iterator::any` / `try_fold` over `Result<bool>` | An error thrown by a later comparator must not surface once the result is decided (leak `range-lazy-evaluation`): evaluate in order and stop at the first deciding value or the first error. |
| Sorting | `array.sort(compareVersions)` (stable) | `slice.sort_by(\|a, b\| ...)` | `sort_by` is stable. `compare_versions` returns `Result<Ordering, Error>`; the binding maps `Ordering` to -1/0/1. |
| Dates, async, I/O | none | none | Not used. |
| Module layout and naming | `src/*.ts`, camelCase exports | `src/{utils,validate,compare,compare_versions,satisfies}.rs`, snake_case | `compareVersions` -> `compare_versions`, `validateStrict` -> `validate_strict`. Fixtures keep the TypeScript call ids (`compare-versions:<export>`); `examples/porter_harness/bindings.rs` translates them. |

## Dropped workarounds and new substrate

- Dropped: the `typeof` guards (`Invalid argument expected string`, `Invalid operator type, expected string
  but got <typeof>`) and the four V8 runtime messages; the type system makes them unreachable.
- Dropped: UMD/ESM packaging, the `window.compareVersions` global, `.d.ts`, source maps.
- New substrate, owned by utils-utils: ECMAScript whitespace predicate, ASCII-only semver matcher, JS
  `parseInt` and Number-to-String emulation. No other unit re-implements them.

## Scope gauntlet

| Item | Decision | Reason |
| --- | --- | --- |
| compareVersions, compare, satisfies, validate, validateStrict, CompareOperator | now | The package API (src/index.ts). |
| semver, validateAndParse, compareSegments | now, crate-private | Needed by every function; not package API (contract.md). |
| Non-string arguments (48 fixtures named `*nonstring*`, incl. the 4 `ignore-message` V8 cases) | out of scope, divergence `non-string-arguments` | A `&str` API cannot receive them. The implementing unit records the divergence in `divergences.json` with the glob `*nonstring*`. |
| 4 reference-test rows that pass a JS function (test/compare.ts:160, :258, :269 row 275, test/validate.ts:12) | out of scope | No JSON form; contract marks them OUT-OF-SCOPE. |
| `window.compareVersions` UMD global | out of scope | JS packaging only. |
| A `semver`-crate-compatible or spec-correct mode | seam for later | Would be a separate API; this port reproduces compare-versions, quirks included. |

## Risk register

| Risk | Mitigation | Signal that it is happening |
| --- | --- | --- |
| Hand-written matchers accept a different language than the JS regexes (backtracking around optional groups, `/i`, Unicode digits) | Matchers follow the regex structure group by group; validate-validate (tracer) has 1,174 fixtures including `gen-validate-unicode` and `gen-strict-unicode` | Tracer fixtures fail on `edge-val-*` or `gen-*-unicode` cases |
| float64 and Number-to-String emulation differs from V8 (rounding past 2^53, exponent form, `-0`, Infinity) | Dedicated helpers in utils-utils with unit tests from the contract; fixtures `gen-cv-bignum`, `gen-cv-2pow53*` | Mismatches in satisfies-satisfies on `*bignum*`, `*2pow53*`, `*number-to-string*` cases |
| Range grammar evaluation order or split semantics differ (lazy evaluation, `split(' - ', 2)`, `\s` set) | Code port of `satisfies` structure; leak globs from api.json in the review checklist | Error-vs-value mismatches in `gen-sat-junk` or `*split-limit*` cases |
| Error precedence differs (operator before versions, v1 before v2) | Order of checks copied from source | Message mismatches on error fixtures |

## Scaffold

- Package layout:

  ```text
  Cargo.toml                 # name compare-versions-port, lib name compare_versions_port, edition 2021, MIT
  LICENSE                    # MIT, keeps the original copyright notice (Ole Michelsen) plus the port's
  src/lib.rs                 # crate docs, mod declarations, pub use of the public surface
  src/utils.rs               # Error, CompareOperator, semver matcher, parse_int, number_to_string, compare_segments
  src/validate.rs            # validate, validate_strict
  src/compare_versions.rs    # compare_versions
  src/compare.rs             # compare
  src/satisfies.rs           # satisfies
  tests/<file>.rs            # ported reference tests (compare, satisfies, sort, validate)
  examples/porter_harness/   # main.rs (from knowledge/harnesses/rust) and bindings.rs
  ```

- Toolchain: build `cargo build`, test `cargo test`, lint `cargo clippy --all-targets -- -D warnings`,
  format `cargo fmt --all -- --check`, typecheck `cargo check --all-targets`. Rust stable (local 1.93.1);
  no `rust-version` declared (the crate uses no recent features). No runtime dependencies;
  `serde_json` as a dev-dependency for the harness only.
- Harness: `knowledge/harnesses/rust/main.rs` copied to `examples/porter_harness/main.rs`; bindings in
  `examples/porter_harness/bindings.rs`, one entry per TypeScript call id. Run with
  `cargo run --example porter_harness -- --workspace .porter --run <run> --unit <unit>`.
- CI: none in this run (nothing is pushed). A later `.github/workflows/ci.yml` would run fmt, clippy,
  test and the harness on stable.

## Budgets

Attempts per unit: 3. Discovered units before returning to the user: 5. PORT depth and LOC: 1, 2000
(no PORT dependencies). Unit size: at most 400 LOC and 8 public symbols, merge below 30 LOC (config
defaults; every unit fits).
