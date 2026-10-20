# Go to Rust

| Field | Value |
| --- | --- |
| Source | Go 1.18 to 1.24 |
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

### T1. Integer overflow wraps in Go

- Tags: `numeric`
- Source behavior: Go integer arithmetic wraps silently.
- Target behavior: Rust arithmetic panics on overflow in debug builds and wraps in release builds.
- Detect: `var x int32 = math.MaxInt32; x++` gives `-2147483648` in Go; the same increment on an `i32` in Rust panics with `attempt to add with overflow` in a debug build.
- Port rule: use `wrapping_add`, `wrapping_mul` (or `std::num::Wrapping`) wherever the Go code relied on wraparound (hashes, checksums, counters), and `checked_*` where overflow was a bug.

### T2. Missing map keys return the zero value

- Tags: `nullability`
- Source behavior: `m[k]` on a missing key returns the zero value; `v, ok := m[k]` reports presence.
- Target behavior: indexing a Rust `HashMap` with a missing key panics; `get` returns `None`.
- Detect: `m := map[string]int{}; m["x"]` is `0` in Go; Rust `m["x"]` panics.
- Port rule: port `m[k]` as `m.get(k).copied().unwrap_or_default()` and `v, ok := m[k]` as `match m.get(k)`. Port Go's `m[k]++` as `*m.entry(k).or_default() += 1`.

### T3. Go strings may hold invalid UTF-8

- Tags: `unicode`, `encoding`
- Source behavior: a Go `string` is any byte sequence; `range` over it yields U+FFFD for each invalid byte.
- Target behavior: Rust `String` must be valid UTF-8, so conversion from bytes fails.
- Detect: `string([]byte{0xff})` is a valid Go string whose `range` yields `U+FFFD`; Rust `String::from_utf8(vec![0xff])` returns `Err`.
- Port rule: carry data that can be non-UTF-8 as `Vec<u8>` or `&[u8]` (the bstr crate helps), and use `String::from_utf8_lossy` only where the Go code ranged over runes.

### T4. `append` can write into a shared backing array

- Tags: `mutability`
- Source behavior: `append` on a slice with spare capacity writes into the same backing array, so other slices of it see the change.
- Target behavior: a Rust port that copies (`to_vec()`) leaves the original untouched; the borrow checker rules out the aliasing form.
- Detect: `a := []int{1, 2, 3}; b := append(a[:1], 9)` leaves `a` as `[1 9 3]` in Go; `let mut b = a[..1].to_vec(); b.push(9);` leaves `a` as `[1, 2, 3]`.
- Port rule: find `append` calls on subslices; if fixtures show the aliasing effect, reproduce it with explicit index writes, otherwise record the fix as a divergence.

### T5. `fmt` prints maps with sorted keys

- Tags: `ordering`
- Source behavior: `fmt.Print` and `%v` sort map keys (Go 1.12+), even though map iteration order is random.
- Target behavior: `{:?}` on a Rust `HashMap` prints in an order that changes between runs.
- Detect: `fmt.Println(map[string]int{"b": 1, "a": 2})` prints `map[a:2 b:1]`; `println!("{:?}", hm)` prints `{"b": 1, "a": 2}` or `{"a": 2, "b": 1}`.
- Port rule: use `BTreeMap` for maps that are printed, or sort the entries before formatting, and match Go's `map[k:v k:v]` format if it appears in fixtures.
