# Python to Rust

| Field | Value |
| --- | --- |
| Source | Python 3.9 to 3.13 |
| Target | Rust stable (2021 or 2024 edition) |
| Status | stub |
| Last reviewed | 2026-10-20 |

This file is a stub: only section 15 has content so far. For every other
section the `strategy` skill falls back to `knowledge/pairs/GENERIC.md`.
Contributions are welcome; see `docs/adding-a-language-pair.md`.

## 1. Type system mapping

## 2. Error model

## 3. Null and absence

## 4. Concurrency and async

## 5. Iteration, generators, laziness

## 6. Numeric semantics

## 7. Strings, bytes, unicode, encodings

## 8. Dates, times, timezones

## 9. Regex dialect

## 10. I/O, paths, process, environment

## 11. Module layout, packaging, naming, visibility

## 12. Standard library equivalence

## 13. Common dependency equivalence

## 14. Test framework and tooling

## 15. Known traps

### T1. Integers are unbounded in Python

- Tags: `numeric`
- Source behavior: Python `int` has arbitrary precision and never overflows.
- Target behavior: Rust `i64` arithmetic panics on overflow in debug builds and wraps in release builds.
- Detect: `2**63` is `9223372036854775808` in Python; Rust `i64::MAX + 1` computed at runtime panics with `attempt to add with overflow` in debug and gives `-9223372036854775808` in release.
- Port rule: pick the integer type from the value range in the contract. Use `checked_*` operations or `i128` where the range is close to the limit, and `num-bigint` where it is unbounded. Never let behavior depend on the build profile.

### T2. Floor division and modulo

- Tags: `numeric`
- Source behavior: `//` floors and `%` takes the sign of the divisor: `-7 // 2` is `-4`, `-7 % 2` is `1`, `7 % -2` is `-1`.
- Target behavior: Rust `/` truncates and `%` takes the sign of the dividend: `-7 / 2` is `-3`, `-7 % 2` is `-1`. `rem_euclid` is always non-negative, so it matches Python only for positive divisors (`7i32.rem_euclid(-2)` is `1`).
- Detect: `-7 % 2` is `1` in Python and `-1` in Rust.
- Port rule: use helpers: `fn py_mod(a: i64, b: i64) -> i64 { let r = a % b; if r != 0 && ((r < 0) != (b < 0)) { r + b } else { r } }`, and `py_floordiv` built the same way.

### T3. String length and indexing

- Tags: `unicode`
- Source behavior: `len(s)` and `s[i]` count code points.
- Target behavior: `s.len()` counts UTF-8 bytes, and slicing `&s[a..b]` uses byte offsets and panics when they fall inside a character.
- Detect: `len("é")` is `1` in Python; `"é".len()` is `2` in Rust, and `&"é"[0..1]` panics with `byte index 1 is not a char boundary`.
- Port rule: use `s.chars().count()` and `s.chars().nth(i)` for code-point semantics, or keep a `Vec<char>` when the source indexes heavily. Convert any index that crosses the API boundary.

### T4. Float to string

- Tags: `float-format`
- Source behavior: `str(x)` and `repr(x)` print the shortest round-trip form, always with a decimal point or exponent: `str(1.0)` is `'1.0'`, `str(1e16)` is `'1e+16'`.
- Target behavior: Rust `{}` drops the `.0` and never uses exponent form: `format!("{}", 1.0)` is `"1"`, `format!("{}", 1e16)` is `"10000000000000000"`. `{:?}` gives `"1.0"` and `"1e16"`.
- Detect: `str(1.0)` is `'1.0'`; `format!("{}", 1.0)` is `"1"`.
- Port rule: write a `py_float_repr` helper that follows Python's rules (exponent form at `1e16` and above or below `1e-4`, exponent written as `e+16` or `e-05`) and use it everywhere a float becomes text.

### T5. Dict order versus `HashMap` order

- Tags: `ordering`
- Source behavior: `dict` iterates in insertion order (guaranteed since 3.7).
- Target behavior: `std::collections::HashMap` iterates in an order that changes from run to run.
- Detect: iterating `{"b": 1, "a": 2}` gives `b, a` on every Python run; a Rust `HashMap` with the same inserts can give `a, b` or `b, a`.
- Port rule: use `indexmap::IndexMap` where the source relied on insertion order, and `BTreeMap` only where the source sorted.
