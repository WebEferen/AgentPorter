# Go parity harness

A small program inside the port that runs every recorded case in `.porter/fixtures/<unit>/*.json` through
the port and writes `.porter/runs/<run>/<unit>.json` (see [CONTRACT.md](../../oracles/CONTRACT.md)). It never
compares; `porter parity collect` does. Go 1.21 or newer, standard library only.

`porter` below is `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/porter.py`.

## Copy it into the port

```sh
mkdir -p cmd/porter-harness
cp ${CLAUDE_PLUGIN_ROOT}/knowledge/harnesses/go/{harness.go,value.go} cmd/porter-harness/
cp ${CLAUDE_PLUGIN_ROOT}/knowledge/harnesses/go/bindings.example.go cmd/porter-harness/bindings.go
```

`bindings.go` does not compile as copied: it imports a placeholder package. Replace the import with the
port's package and keep only entries for call ids that appear in the fixtures.

`value.go` is the same file the Go oracle uses (input accessors and contract serialization). Keep both copies
identical.

## Run it

From the port's module root:

```sh
go run ./cmd/porter-harness --workspace .porter --run <run> [--unit <unit>]... [--timeout <seconds>]
porter parity collect --run <run>
```

The default run id is the UTC time. Exit code 0 when runs were written, 2 when the harness cannot run.

## Bindings

`bindings.go` declares `var bindings = map[string]Call{...}`, one entry per source call id. `Call` is
`func(in Input) (any, error)`:

- `in.Str(i)`, `in.Int(i)`, `in.Int64(i)`, `in.Float(i)`, `in.Bool(i)`, `in.Bytes(i)`, `in.Strs(i)`,
  `in.Time(i)` read positional arguments and decode tags. `in.Arg(i)` is the raw value (numbers are
  `json.Number`, objects are `map[string]any`).
- `in.Has(name)` and `in.Kw(name)` read `kwargs`. `in.Init` holds `init` for `Type.Method` calls.
- `in.IsUndefined(i)` is true when argument `i` is missing or `{"$undefined": true}` (a JavaScript source
  called without that argument).
- Return the port's result and error unchanged. Several results become `[]any{a, b}`. Return `Undefined`
  where the JavaScript source returned `undefined` and the Go port signals "no value" (for example `ok == false`).

Bindings translate calling conventions only and never patch a result. An input that does not fit the
accessors becomes the outcome category `BindingError`; a call id without a binding becomes `MissingBinding`.

## Serialization, errors and timeouts

Serialization follows `value.go`, documented in `knowledge/oracles/go/README.md`: big integers become
`$int`, special floats become `$float`, `[]byte` becomes `$bytes`, non-string-key maps become `$map`
sorted by key, `time.Time` becomes `$datetime`, structs become `$type` with exported fields under their
`json` tag names.

A returned error's category is its `Sentinels` name when `errors.Is` matches, otherwise its type name without
the pointer. Name the port's sentinel errors in an `init` in `bindings.go`; an error type named after the
source category (`type Error struct`) matches without an error map. A panic becomes category `panic`. A case
past `--timeout` (default 10 seconds) becomes `timeout`; its goroutine keeps running until the program exits.

## Limitations

- Go maps have no order, so `$map` entries are sorted by key.
- A nil slice and an empty slice both serialize as `[]`.
