# Ruby to TypeScript

| Field | Value |
| --- | --- |
| Source | Ruby 2.7 to 3.4 |
| Target | TypeScript 5.x, ESM, on Node 20+ |
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

### T1. Only `nil` and `false` are falsy

- Tags: `nullability`
- Source behavior: Ruby treats `0`, `""` and `[]` as true.
- Target behavior: JavaScript treats `0`, `''` and `NaN` as false.
- Detect: `0 ? "t" : "f"` is `"t"` in Ruby and `'f'` in JavaScript.
- Port rule: port Ruby conditions as explicit checks: `x !== null && x !== undefined && x !== false`, or a `rubyTruthy(x)` helper.

### T2. Integer division and modulo floor

- Tags: `numeric`
- Source behavior: `Integer#/` floors, and `%` takes the sign of the divisor: `-7 / 2` is `-4`, `-7 % 3` is `2`.
- Target behavior: JavaScript `/` returns a float (`-3.5`), `Math.trunc` gives `-3`, and `%` takes the sign of the dividend (`-7 % 3` is `-1`).
- Detect: `-7 / 2` is `-4` in Ruby and `-3.5` in JavaScript.
- Port rule: track which values are Integers. Port `a / b` on Integers as `Math.floor(a / b)` and `a % b` as `((a % b) + b) % b`; keep Float division where either operand is a Float.

### T3. Symbol keys and string keys are different

- Tags: `reflection`
- Source behavior: `{a: 1}` has the Symbol key `:a`; looking it up with the String `"a"` returns `nil`.
- Target behavior: JavaScript object keys are strings, so `a: 1` and `'a'` are the same key.
- Detect: `{a: 1}["a"]` is `nil` in Ruby; `({ a: 1 })['a']` is `1` in JavaScript.
- Port rule: find hashes that mix Symbol and String keys, or are looked up both ways (Rails `HashWithIndifferentAccess` hides this). Use a `Map` with tagged keys where both kinds coexist.

### T4. Hash order with integer-like keys

- Tags: `ordering`
- Source behavior: `Hash` iterates in insertion order for all keys.
- Target behavior: JavaScript objects list integer-like keys first, ascending.
- Detect: `{"b" => 1, "1" => 2}.keys` is `["b", "1"]` in Ruby; `Object.keys({ b: 1, '1': 2 })` is `['1', 'b']`.
- Port rule: use `Map` for hashes whose keys can look like integers, and serialize it in insertion order.

### T5. `nil` interpolates as an empty string

- Tags: `nullability`
- Source behavior: `"#{nil}"` and `nil.to_s` give `""`.
- Target behavior: template literals turn `null` into `'null'` and `undefined` into `'undefined'`.
- Detect: `"x#{nil}"` is `"x"` in Ruby; `` `x${null}` `` is `'xnull'` in JavaScript.
- Port rule: wrap interpolated values that can be `nil` with `?? ''`.
