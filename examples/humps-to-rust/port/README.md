# humps

Rust port of [pyhumps](https://github.com/nficano/humps) 3.8.0: convert strings and the keys of
`serde_json::Value` objects between camelCase, PascalCase, snake_case and kebab-case.

```rust
assert_eq!(humps::camelize("hello_world"), "helloWorld");
assert_eq!(humps::decamelize("APIResponse"), "api_response");
let v = humps::camelize_value(&serde_json::json!({"first_name": "Ada"}));
assert_eq!(v, serde_json::json!({"firstName": "Ada"}));
```

## Parity with upstream

Upstream: pyhumps 3.8.0, commit `dc56af8dff5c1f3a6421f2d8ed55940df820ec58`. Evidence recorded 2026-10-20 on
CPython 3.14.6 (Unicode 16.0.0) and checked with rustc 1.93.1. Full report: [docs/PARITY.md](docs/PARITY.md).

| Unit | Level | Pass | Divergent | Failed |
| --- | --- | --- | --- | --- |
| cycle-humps (all 10 functions) | DIVERGENT | 4625 | 2 | 0 |

Reference tests: 18 of 18 upstream test functions ported and passing.

Divergences:

- `recursion-depth`: no nesting limit; Python raises `RecursionError` near 990 levels.
- `unicode-version`: Final_Sigma context uses Rust std's Unicode 17 data, so a sigma next to U+0295 or a character
  newly cased in Unicode 17 can lower differently.
- `oracle-depth-cap`: two fixtures nested 100 levels deep hold the recording driver's truncation marker; the port
  returns Python's real result.

Not representable in this API and out of scope: non-string keys, tuples, sets, bytes, integers beyond 64 bits,
NaN and Infinity, lone surrogates.
