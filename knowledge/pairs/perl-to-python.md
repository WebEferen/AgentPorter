# Perl to Python

| Field | Value |
| --- | --- |
| Source | Perl 5.10 to 5.40 |
| Target | Python 3.10+ |
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

### T1. `sort` compares as strings by default

- Tags: `ordering`
- Source behavior: `sort LIST` without a block compares with `cmp` (string order).
- Target behavior: Python `sorted` compares numbers numerically.
- Detect: `join ",", sort (10, 9, 1)` is `1,10,9` in Perl; `sorted([10, 9, 1])` is `[1, 9, 10]` in Python.
- Port rule: port bare `sort` as `sorted(xs, key=perl_str)`, where `perl_str` stringifies numbers the way Perl does (T4); port `sort { $a <=> $b }` as numeric `sorted`, and translate other blocks into `key` functions or `functools.cmp_to_key`.

### T2. Hash order changes between runs

- Tags: `ordering`
- Source behavior: since Perl 5.18, `keys %h` order is randomized per process.
- Target behavior: Python `dict` iterates in insertion order.
- Detect: `join ",", keys %h` for a five-key hash printed `a,c,b,d,e` twice and `e,b,c,a,d` once in three runs; Python prints insertion order every time.
- Port rule: sort keys where output depends on order. When the Perl output order was random, compare those fixtures as sets and record it in the contract.

### T3. `==` compares numbers, `eq` compares strings

- Tags: `numeric`
- Source behavior: `==` converts both sides to numbers: `"1.0" == 1` is true, and `"abc" == 0` is true (with a warning).
- Target behavior: Python `==` never converts between `str` and numbers.
- Detect: `"1.0" == 1` is true in Perl; `"1.0" == 1` is `False` in Python.
- Port rule: port `==` on values that can be strings as a comparison of explicitly converted numbers, using a helper that mimics Perl's numification (leading number, else 0). Port `eq` as `==` on strings.

### T4. Numbers print with 15 significant digits

- Tags: `float-format`
- Source behavior: Perl stringifies floats with `%.15g`: `0.1 + 0.2` prints `0.3`, `3.0` prints `3`, `10/3` prints `3.33333333333333`.
- Target behavior: Python `str()` prints the shortest round-trip form and keeps `.0` on whole floats.
- Detect: `print 0.1 + 0.2` prints `0.3` in Perl; `print(0.1 + 0.2)` prints `0.30000000000000004` in Python.
- Port rule: format every number that becomes text with `format(x, '.15g')`, which also prints `3.0` as `3`.

### T5. `=~` searches, and `\Z` allows a final newline

- Tags: `regex`
- Source behavior: `$s =~ /x/` matches anywhere in the string, and `\Z` matches at the end or before a final newline (`\z` is the absolute end).
- Target behavior: `re.match` anchors at the start, and Python's `\Z` is the absolute end, like Perl's `\z`.
- Detect: `"a\n" =~ /a\Z/` is true in Perl; `re.search(r"a\Z", "a\n")` is `None` in Python.
- Port rule: port `=~` as `re.search`, Perl `\Z` as `(?=\n?\Z)`, and Perl `\z` as `\Z`. Check `$` too: it matches before a final newline in both languages.
