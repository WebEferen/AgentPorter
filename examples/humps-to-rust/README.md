# pyhumps: Python to Rust

[pyhumps](https://github.com/nficano/humps) converts strings, and the keys of dicts and lists, between
camelCase, PascalCase, snake_case and kebab-case. This is version 3.8.0 ported to Rust as the crate
`humps`, with `serde_json::Value` standing in for dicts and lists.

- [original/](original/): the `humps` package, its `tests/`, `pyproject.toml`, README and license of
  pyhumps 3.8.0 (commit `dc56af8`).
- [port/](port/): the crate, Unicode tables generated to match CPython in `src/unicode_tables.rs`, the
  ported upstream tests in `tests/reference.rs`, the parity harness in `examples/porter_harness` and the
  `.porter/` workspace.

## Original and port

```python
import humps

humps.camelize("hello_world")          # "helloWorld"
humps.decamelize("APIResponse")        # "api_response"
humps.camelize({"first_name": "Ada"})  # {"firstName": "Ada"}
```

```rust
use serde_json::json;

assert_eq!(humps::camelize("hello_world"), "helloWorld");
assert_eq!(humps::decamelize("APIResponse"), "api_response");
assert_eq!(humps::camelize_value(&json!({"first_name": "Ada"})), json!({"firstName": "Ada"}));
```

Python's functions take a string or a dict or list. In Rust each one is split in two: `camelize` for
`&str` and `camelize_value` for `serde_json::Value`, and the same for the other nine.

## Result

DIVERGENT. Of 4627 recorded cases, 4625 match exactly and 2 differ. None fail. 18 of 18 upstream test
functions are ported and pass. Full report: [port/docs/PARITY.md](port/docs/PARITY.md).

- `oracle-depth-cap` (2 cases): two adversarial inputs nest 100 levels deep. The Python oracle stops
  serializing at 64 levels and records a truncation marker, so these fixtures hold the marker instead of
  pyhumps' real result, which the port returns. It is a recording limit, not a behavior difference; the
  oracle contract now documents it.
- `recursion-depth` (no cases): Rust has no nesting limit here; Python raises `RecursionError` near 990
  levels.
- `unicode-version` (no cases): sigma lowering at the end of a word uses Rust's Unicode 17 data, CPython
  3.14 uses Unicode 16, so a sigma next to a newly cased character can lower differently. Per-character
  mappings match CPython through the generated tables.

## How it was made

One unattended session (see [how the examples were made](../README.md#how-they-were-made)): $22.44,
105 turns, 81 minutes. Pre-approved answers:

```text
- deps gate: approve the proposed decisions when every MAP and SHIM candidate is registry-verified. Prefer the
  regex crate and rewrite lookarounds by hand; use fancy-regex only for a pattern that cannot be rewritten, and
  say which. serde_json as a dev-dependency for the parity harness is fine.
- strategy gate: approve the proposed units, order and budgets as written.
- Anything about the package: the crate is named humps (library name humps), Rust stable, edition 2021, an
  idiomatic Rust API. Dict and list inputs map to serde_json::Value. The fixtures keep the Python call ids;
  the bindings translate.
```

Where the run left the script:

- The verifier keeps every mismatching case as a fixture. When a 100-level case failed on the oracle's
  depth cap, the agent first cut it down to 60 levels (`adv.deep.camelize.60`), which breaks that rule. It
  declared the two later 100-level cases as `oracle-depth-cap` instead.
- `unicode-version` and `oracle-depth-cap` were accepted with "unattended:" notes.
- The review of the second attempt (a 40-line bindings fix) and the final verify ran inline to stay under
  the cap.

## Check it

```sh
cd port
cargo test
cargo run --release --example porter_harness -- --workspace .porter --run local
python3 ../../../scripts/porter.py parity collect --run local --dry-run
```

## License

The Unlicense, as upstream. `original/` and `port/` both carry it.
