# C++ to Rust

| Field | Value |
| --- | --- |
| Source | C++11 to C++23 |
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

### T1. Unsigned wraparound is defined in C++

- Tags: `numeric`
- Source behavior: unsigned arithmetic wraps modulo 2^n by definition.
- Target behavior: Rust unsigned arithmetic panics on overflow in debug builds.
- Detect: `uint32_t x = 0; x - 1` is `4294967295` in C++; `x - 1` with `x: u32 = 0` computed at runtime panics with `attempt to subtract with overflow` in a debug Rust build.
- Port rule: use `wrapping_sub`, `wrapping_add` and `wrapping_mul` (or `Wrapping<u32>`) wherever the C++ code uses unsigned wraparound.

### T2. Integer promotion widens small types

- Tags: `numeric`
- Source behavior: operands narrower than `int` are promoted to `int` before arithmetic, so `uint8_t` sums do not overflow.
- Target behavior: Rust arithmetic stays in the operand type.
- Detect: `uint8_t a = 200, b = 100; int c = a + b;` gives `300`; Rust `a + b` on `u8` panics in debug and gives `44` in release.
- Port rule: widen explicitly before the operation (`i32::from(a) + i32::from(b)`), following C++'s usual arithmetic conversions, including signed and unsigned mixing.

### T3. `char` signedness depends on the platform

- Tags: `encoding`
- Source behavior: plain `char` is signed on x86-64 and Apple arm64 and unsigned on Linux aarch64.
- Target behavior: a Rust port uses `u8`, which is unsigned everywhere.
- Detect: `char c = (char)0xE9; (int)c` is `-23` on x86-64 Linux and on Apple arm64, and `233` on Linux aarch64; Rust `0xE9u8 as i32` is `233`.
- Port rule: record which platform recorded the fixtures. Where the C++ code converts `char` to `int` or compares it with negative values, use `i8` (`b as i8 as i32`) to reproduce signed behavior.

### T4. `std::map` is ordered

- Tags: `ordering`
- Source behavior: `std::map` and `std::set` iterate in key order.
- Target behavior: `HashMap` and `HashSet` iterate in an order that changes between runs.
- Detect: iterating `std::map<std::string, int>{{"b", 1}, {"a", 2}}` gives `a, b`; a Rust `HashMap` with the same entries can give either order.
- Port rule: port `std::map` to `BTreeMap` and `std::set` to `BTreeSet`. `std::unordered_map` order is unspecified too; if fixtures captured it, sort before output.

### T5. iostream prints 6 significant digits by default

- Tags: `float-format`
- Source behavior: `std::cout << x` uses `%g`-style formatting with precision 6.
- Target behavior: Rust `{}` prints the shortest round-trip representation.
- Detect: `std::cout << 0.1 + 0.2` prints `0.3`; `println!("{}", 0.1 + 0.2)` prints `0.30000000000000004`.
- Port rule: write a `%g` formatter that honors the stream's current precision and flags (`std::fixed`, `std::setprecision`), and route every float output through it.
