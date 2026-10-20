# Go oracle driver

Go cannot call a function by name, so the Go oracle is a small program you assemble per source: `main.go`
(the driver), `value.go` (input accessors and contract serialization) and a `dispatch.go` that maps every
call id to a Go call. It writes `.porter/fixtures/<unit>/oracle.json` and
`.porter/oracle/timings/<unit>.json` as [CONTRACT.md](../CONTRACT.md) describes. Go 1.21 or newer.

`porter` below is `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/porter.py`.

## Set it up

```sh
mkdir -p .porter/oracle/go
cp ${CLAUDE_PLUGIN_ROOT}/knowledge/oracles/go/{main.go,value.go} .porter/oracle/go/
cp ${CLAUDE_PLUGIN_ROOT}/knowledge/oracles/go/dispatch.example.go .porter/oracle/go/dispatch.go
cp ${CLAUDE_PLUGIN_ROOT}/knowledge/oracles/go/go.mod.example .porter/oracle/go/go.mod
```

In `go.mod`, set the `require` line to the source module path and point the `replace` line at the checkout
in `config.source.path`, so the oracle builds the pinned source. Then add one `dispatch` entry per call id in
`.porter/oracle/cases/*.json`.

A source from before Go modules has no `go.mod`, and `replace` needs one in the directory it points at. Do
not add it to the checkout. Export the pinned commit next to the driver and give that copy a `go.mod`:

```sh
mkdir -p .porter/oracle/go/upstream
git -C <checkout> archive <commit> | tar -x -C .porter/oracle/go/upstream
printf 'module <import path>\n\ngo 1.21\n' > .porter/oracle/go/upstream/go.mod
```

and use `replace <import path> => ./upstream`.

## Run it

```sh
porter fixtures expand
cd .porter/oracle/go && go mod tidy && go run . --workspace ../.. \
    [--unit <unit>]... [--package-version <v>] [--commit <sha>] [--timeout <seconds>]
porter fixtures validate
```

Exit codes: 0 when fixtures were written (returned errors and panics are outcomes), 2 when the driver
cannot run: a call id without a dispatch entry, an input that does not fit the dispatch entry, a CLI unit.

## Dispatch entries

Each entry is `func(in Input) (any, error)`: unpack the input, call the source, return what it returns.

- `in.Str(i)`, `in.Int(i)`, `in.Int64(i)`, `in.Float(i)`, `in.Bool(i)`, `in.Bytes(i)`, `in.Strs(i)`,
  `in.Time(i)` read positional arguments and decode tags (`$float`, `$int`, `$bytes`, `$datetime`).
  `in.Arg(i)` is the raw value, with numbers as `json.Number`.
- `in.Has(name)` and `in.Kw(name)` read `kwargs`. `in.Init` holds `init` for `Type.Method` calls: build the
  receiver from it, then call the method.
- Several return values become `[]any{a, b}`, matching a source that returns a tuple.
- A wrong argument type panics with `ArgError`, which the driver reports and exits 2. That is a case
  authoring problem, not an outcome.

The call id is only a map key, so any form works. Use the contract form: `example.com/x:Func`,
`example.com/x:Type.Method`, `example.com/x:Const`.

## Serialization

| Go | JSON |
| --- | --- |
| integers beyond 2^53, `*big.Int` | `{"$int": "..."}` |
| `float32` | shortest float32 text, so `0.1` stays `0.1` |
| NaN, ±Inf, -0 | `{"$float": ...}` |
| `[]byte`, `[N]byte` | `{"$bytes": "<base64>"}` |
| other slices and arrays (nil included) | array |
| map with string keys | object |
| other maps | `{"$map": [[k, v], ...]}` sorted by canonical key JSON |
| `time.Time` | `{"$datetime": RFC 3339 with nanoseconds}` |
| struct | `{"$type": "Name", ...}` with exported fields, using `json` tag names |
| `error` value in a result | `{"$type": "Name", "message": err.Error()}` |
| nil pointer or interface | `null` |
| func, chan | `{"$type": "func" or "chan"}` |
| `Undefined` | `{"$undefined": true}` |

## Errors, panics and timeouts

A returned error's category is the name registered in `Sentinels` when `errors.Is` matches, otherwise its
type name without the pointer (`*ParseError` becomes `ParseError`). Register sentinels in an `init` in
`dispatch.go`: without that, `errors.New` errors all get the category `errorString`. When the function also
returns a non-zero result next to the error (the words parsed so far, a partial count), the outcome keeps it
as `value`. Return it from the dispatch entry together with the error.

A panic is an outcome with category `panic`. A case that runs past `--timeout` (default 10 seconds) gets
category `timeout`; its goroutine cannot be stopped and keeps running until the program exits.

## Limitations

- Go maps have no order, so `$map` entries are sorted instead of being in insertion order as the contract says.
- A nil slice and an empty slice both become `[]`.
- Unexported fields are not visible. Generic functions need a concrete instantiation in the dispatch entry.
- `value.go` is shared with the Go harness (`knowledge/harnesses/go/value.go`); keep the two copies identical.
