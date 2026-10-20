# Strategy: pyhumps -> rust (humps)

One unit, `cycle-humps`, ported as a code port: the Rust crate follows the source's regex pipeline
(`_is_none`, early returns, `ACRONYM_RE` title-casing, `SPLIT_RE` split, `UNDERSCORE_RE` substitution) with the
two lookarounds rewritten by hand around the `regex` crate, and exposes an idiomatic API with a `&str` entry
point and a `serde_json::Value` entry point per function. The unit is also the tracer bullet: it proves the
idiom map, the Rust fixture harness, the reference-test import and the verifier on the whole surface at once.
At the gate the user approves this single unit (over the symbol budget, see below), the API shape, the scope
cuts and the budgets.

## Per-unit strategy

| Unit | Layer | Strategy | Why |
| --- | --- | --- | --- |
| cycle-humps | core | code port | The contract is defined by regex quirks (`kebabize("HELLO world") == "hell-oworld"`, `pascalize("a_b") == "A_B"`, `decamelize("a_B") == "a__b"`); reimplementing from a prose spec would miss them. Pure logic, no runtime welding. |

## Public API

Crate `humps`, library `humps`, edition 2021, Rust stable. All functions at the crate root.

```rust
pub fn camelize(s: &str) -> String;      // also pascalize, kebabize, decamelize, depascalize, dekebabize
pub fn is_camelcase(s: &str) -> bool;    // also is_pascalcase, is_kebabcase, is_snakecase
pub fn camelize_value(v: &Value) -> Value;    // also pascalize_value, ..., dekebabize_value
pub fn is_camelcase_value(v: &Value) -> bool; // also is_pascalcase_value, is_kebabcase_value, is_snakecase_value
```

- `*_value` walks like `_process_keys`: an array becomes a new array of walked elements (strings inside arrays
  are values and stay untouched), an object becomes a new object with converted keys and walked values, in
  insertion order. A top-level string goes through the `&str` function.
- Top-level `Null`, `Bool` and `Number` follow the Python string path exactly (leak `string-path-for-scalars`):
  `Null` is `""`, `Bool` is `"True"`/`"False"`, integers are their decimal text, floats are Python `repr`
  (helper `py_float_repr`). When the early return fires (`isupper`/`isnumeric`), the original `Value` comes back
  unchanged (`camelize_value(&json!(5)) == json!(5)`); otherwise the result is a `Value::String`.
- `is_*_value(v)` is `*v == *_value(v)`, which matches Python `==` here because values are never converted.
- The `&str` functions return `s.to_owned()` on the early return, whitespace included
  (`camelize("HELLO WORLD") == "HELLO WORLD"`).

## Idiom map

Probe versions: CPython 3.14.6 (Unicode 16.0.0), rustc 1.93.1 (`char::UNICODE_VERSION` 17.0.0), regex 1.13.1
(regex-syntax 0.8.11, Unicode 16), serde_json 1.0.154. Seeded from `knowledge/pairs/python-to-rust.md` (a stub:
traps T1 to T5 only) and `GENERIC.md`.

| Concern | Source idiom | Target idiom | Rule for this port |
| --- | --- | --- | --- |
| Errors | nothing raised on JSON input | infallible functions | No `Result` in the API. Inputs Python would reject or treat oddly are excluded by the types (scope gauntlet). |
| Absence | `None` -> `""` in `_is_none` | `Value::Null` -> `""` | Only reachable through `*_value`. |
| Dynamic dispatch | `isinstance(x, (list, Mapping))` | `match v { Value::Array, Value::Object, ... }` | One `match` in a private walker shared by the six converters, taking the `&str` function as `fn(&str) -> String` plus an early-return flag. |
| Early return of the original | `return str_or_iter` | private `enum Outcome { Original, Converted(String) }` | Needed so `*_value` returns the original `Value` (a number stays a number). |
| Numbers | `str(int)`, `repr(float)` | `i64`/`u64` `to_string()`, `py_float_repr(f64)` | `py_float_repr`: start from `format!("{:?}", f)` (same shortest digits and same 1e16 / 1e-4 thresholds as Python, probed: `1e-5` vs `1e-05`, `1e16` vs `1e+16`) and rewrite the exponent to a sign plus at least two digits. Unit tests for both thresholds. |
| Strings and indexing | `s[0]`, `s[1:]`, `s[:2]`, `m.group(0)[-1]` | `chars()` iteration | Code points, never byte offsets (T3). `s[0].upper()` uses `char::to_uppercase` (full mapping, `ß` -> `SS`); `.lower()` on the whole string uses `str::to_lowercase` (handles Final_Sigma, like Python). |
| `str.isupper` | Unicode cased/uppercase, titlecase letters make it false | helper `py_isupper(&str)` | At least one cased char and no lowercase or titlecase char. Rust has no titlecase test: carry a const table of the Lt code points generated from CPython 3.14 `unicodedata`. |
| `str.isnumeric` | Numeric_Type in {Digit, Decimal, Numeric}, includes Han numerals (`三`) | helper `py_isnumeric(&str)` | Non-empty and every char numeric. `char::is_numeric` (Nd, Nl, No) differs: generate the difference tables (both directions) from CPython 3.14 and apply them. |
| `str.title` in `_fix_abbreviations` | title-cases runs of `[A-Z\d]` | hand-written | Only ASCII capitals and Nd digits can occur: uppercase a letter at the start or after a non-letter, lowercase the rest. |
| Whitespace `\s` | `re.sub(r"\s+", "", s)`, Python `\s` = `str.isspace` | `regex` `[\s\x1C-\x1F]+` | The crate's `\s` is White_Space only; Python adds U+001C..U+001F. |
| Regex `ACRONYM_RE` | `([A-Z\d]+)(?=[A-Z\d]\|$)` | `[A-Z\d]+` with `find_iter` | For each maximal run: keep it all when it ends the string, else drop its last char; skip when empty. No `fancy-regex`. |
| Regex `UNDERSCORE_RE` | `(?<=[^\-_])[\-_]+[^\-_]` | `[\-_]+[^\-_]` with `find_iter` | Skip a match at offset 0 or preceded by `-`/`_`. Never a consuming group (`"a_b_c"` must give `aBC`). |
| Regex `SPLIT_RE` split | `re.split` keeps the captured group | `find_iter` helper pushing gaps and matches | Then drop empty pieces and join with the separator. |
| Regex `PASCAL_RE` | `sub(fn)` | `Regex::replace_all` with a closure | Same. |
| Regex compilation | module-level `re.compile` | `std::sync::LazyLock<Regex>` | Private statics; `.unwrap()` on literal patterns is fine (compile-time constants). |
| Dict and list | `dict`, `list`, insertion order | `serde_json::Value`, `Map` with `preserve_order` | Build fresh maps with `insert`: on a key collision the later value wins and the first position stays, as in Python. Never `Map::remove` (it is `swap_remove`). |
| Recursion | Python raises `RecursionError` near 990 levels | recursive walk | `DIVERGENCE(recursion-depth)` at the walker: no depth limit, deep input is bounded by the caller's stack (and serde_json's own 128 parse limit). |
| Module layout and naming | `humps.main`, re-exported from `humps` | `src/lib.rs` (API and walker), `src/pyfmt.rs` (Python string predicates and float repr), `src/unicode_tables.rs` (generated tables) | Private modules; everything public is at the root. snake_case names match the Python names. |

## Dropped workarounds and new substrate

- Dropped: the `.pyi` stubs and `StrOrIter` (Rust signatures carry the types); package metadata dunders
  (`__version__` and friends live in `Cargo.toml`).
- New substrate, all inside `cycle-humps`: `py_isupper`, `py_isnumeric`, `py_float_repr`, the Lt and numeric
  difference tables, the `find_iter`-based split helper and the two lookaround rewrites.

## Scope gauntlet

| Item | Decision | Reason |
| --- | --- | --- |
| The 10 public functions, `&str` and `Value` entry points | now | The whole public surface. |
| Top-level `Null`/`Bool`/`Number` in `*_value` | now, Python behavior reproduced | Keeps the 100 `strategy-decision` fixtures as parity, no divergence needed. |
| `ACRONYM_RE`, `PASCAL_RE`, `SPLIT_RE`, `UNDERSCORE_RE` | private | Not exported by `__all__`; ported as private code. |
| `_separate_words` rows from `tests/test_separate_words.py` | now, as a `#[cfg(test)]` test | Private helper; the harness only sees the public API. |
| Non-str keys, tuples, sets, bytes, Mapping subclasses, ints beyond 64 bits, NaN/Infinity, lone surrogates | out of scope | Not representable in `&str` or `serde_json::Value`; leak `unrepresentable-inputs`, no fixtures recorded. |
| Python `RecursionError` | divergence `recursion-depth` | Runtime limit, not behavior callers rely on. |
| Generic map inputs (`HashMap`, `BTreeMap`, serde structs) | seam for later | A trait over map types can wrap the same walker. |

## Risk register

| Risk | Mitigation | Signal that it is happening |
| --- | --- | --- |
| Unicode predicate tables drift: Python 3.14 is Unicode 16, Rust 1.93 std is Unicode 17, `isnumeric` and `isupper` differ from `char::is_numeric` and `char::is_uppercase` | Generated tables from CPython 3.14 for the differences; fixtures were recorded on 3.14 | Fixture failures tagged `unicode`, `numeric` or in `gen-chars.*` |
| Lookaround rewrites subtly wrong (overlap, start of string, multibyte last char) | Follow the deps.md rewrite rules exactly; unit tests for `"a_b_c"`, `"_a"`, `"ABc"`, `"A١"` | Failures in `separators`, `gen-words.*` |
| `py_float_repr` differs from Python `repr` | Rewrite only the exponent of Rust `{:?}`; unit tests at 1e16 and 1e-4 | `strategy-decision` float cases fail |
| Key order regressions are invisible to parity (objects compared without order) | Rust unit tests on key sequence and collision position | Only the unit tests catch it |
| Rust test names cannot carry `[ref: ...]`, and `porter parity reftests` has no cargo format | Tests in `tests/reference.rs` carry `/// [ref: <id>]` doc lines; `.porter/tools/cargo_junit.py` runs `cargo test --test reference`, maps names to refs and writes JUnit for `porter parity reftests junit` | reftests.json shows UNRESOLVED rows |

## Scaffold

- Package layout: `Cargo.toml`, `src/lib.rs`, `src/pyfmt.rs`, `src/unicode_tables.rs`, `tests/reference.rs`
  (ported reference tests), `examples/porter_harness/main.rs` and `bindings.rs` (fixture harness).
- Toolchain: build `cargo build`, test `cargo test`, lint `cargo clippy --all-targets -- -D warnings`, format
  `cargo fmt --all -- --check`, typecheck `cargo check --all-targets`, docs `cargo doc --no-deps`.
- Dependencies: `regex = { version = "1.13", default-features = false, features = ["std", "unicode-perl"] }`,
  `serde_json = { version = "1.0.154", features = ["preserve_order"] }`; dev:
  `serde_json = { version = "1.0.154", features = ["preserve_order", "float_roundtrip"] }`. `rust-version = "1.85"`
  (indexmap 2.14.2 through `preserve_order`; `LazyLock` needs 1.80).
- Harness: `knowledge/harnesses/rust/` copied to `examples/porter_harness/`; bindings in
  `examples/porter_harness/bindings.rs`, one entry per Python call id (`humps.main:camelize`, ...). A string
  argument calls the `&str` function, anything else the `*_value` function; bindings never patch results.
- Reference tests: one Rust test per pytest function (18), iterating its parametrize table, tagged with the
  function-level id used in the harvested origins (`tests/test_camelize.py::test_camelize`).
- CI: none in this run (nothing is pushed); the commands above are the local gate.

## Budgets

Attempts per unit: 3. Discovered units before returning to the user: 5. PORT depth and LOC: 1, 2000.
`cycle-humps` holds 10 public symbols against a budget of 8: the converters and predicates form one call
cycle (`kebabize` -> `is_camelcase`/`is_pascalcase`, `is_kebabcase`/`is_snakecase` -> `kebabize`) and share one
fixture file. The cut-down alternative would be a predicates unit (4) and a converters unit (6) with
`kebabize`'s predicate calls as the seam, which needs the fixtures re-filed.
