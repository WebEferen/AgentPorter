# Rust parity harness

A cargo example inside the port that runs every recorded case in `.porter/fixtures/<unit>/*.json` through the
port and writes `.porter/runs/<run>/<unit>.json` (see [CONTRACT.md](../../oracles/CONTRACT.md)). It never
compares; `porter parity collect` does. Its only dependency is `serde_json`, as a dev-dependency, so the port's
own dependency tree does not change.

`porter` below is `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/porter.py`.

## Copy it into the port

```sh
mkdir -p examples/porter_harness
cp ${CLAUDE_PLUGIN_ROOT}/knowledge/harnesses/rust/main.rs examples/porter_harness/main.rs
cp ${CLAUDE_PLUGIN_ROOT}/knowledge/harnesses/rust/bindings.example.rs examples/porter_harness/bindings.rs
cargo add --dev serde_json
```

## Run it

```sh
cargo run --example porter_harness -- --workspace .porter --run <run> [--unit <unit>]... [--timeout <seconds>]
porter parity collect --run <run>
```

The default run id is the UTC time. Exit code 0 when runs were written, 2 when the harness cannot run.

## Bindings

`bindings.rs` has `pub fn bindings() -> Vec<(&'static str, Binding)>`, one entry per source call id. A
`Binding` is `fn(&Input) -> Result<Value, Failure>`:

- `input.str(i)`, `input.i64(i)`, `input.f64(i)`, `input.bool(i)`, `input.bytes(i)`, `input.strs(i)` read
  positional arguments and decode tags (`$int`, `$float`, `$bytes`). `input.arg(i)` is the raw
  `serde_json::Value`, `input.kw(name)` reads `kwargs`, and `input.init` holds `init` for `Type.method` calls.
  An accessor that does not fit returns a `Failure` with category `BindingError`, so use `?`.
- Serialize the port's result with `.to_contract()`. Bindings translate calling conventions only and never
  patch a result. Return `undefined()` where the JavaScript source returned `undefined` and the port returns
  `None`.
- `?` on any `std::error::Error` turns it into a `Failure` whose category is the error type's name (last path
  segment, generics dropped). Return concrete error types: `Box<dyn Error>` would report `Box`. An error type
  named after the source category (`struct Error`) matches without an error map. `Failure::new(category,
  message)` builds one by hand.
- A call id without a binding becomes the outcome category `MissingBinding`.

## Serialization

`ToContract` is implemented for integers (beyond 2^53 they become `$int`), `f64` and `f32` (special values
become `$float`; `f32` uses its shortest text), `bool`, `char`, `str`, `String`, `()`, `Option`, slices,
arrays, `Vec`, `HashSet` and `BTreeSet` (sorted `$set`), `HashMap` and `BTreeMap` (an object when every key
serializes to a string, else `$map` sorted by key), tuples up to four (arrays), `Box`, references and `Value`
itself.

For the port's own types, implement `ToContract` in `bindings.rs` (the trait is local, so that is allowed) with
the helpers:

```rust
impl ToContract for mylib::Point {
    fn to_contract(&self) -> Value {
        object("Point", [("x", self.x.to_contract()), ("y", self.y.to_contract())])
    }
}
```

`enum_member("Color", "Red")`, `datetime(iso)` and `bytes(&[u8])` cover the other tags. `Vec<u8>` serializes
as an array of numbers, so call `bytes` for byte strings.

## Panics and timeouts

Each case runs on its own thread. A panic becomes category `panic` with the panic message (the default panic
hook is silenced). A case past `--timeout` (default 10 seconds) becomes `timeout`; the thread cannot be
stopped and keeps running until the harness exits.

## Limitations

- No reflection: every struct, enum or newtype the port returns needs a `ToContract` impl.
- `serde_json` keeps object keys sorted. That does not affect parity, which compares objects by key.
