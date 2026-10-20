# Python parity harness

`harness.py` runs every recorded case in `.porter/fixtures/<unit>/*.json` through your port and writes
`.porter/runs/<run>/<unit>.json` (see [CONTRACT.md](../../oracles/CONTRACT.md)). It never compares;
`porter parity collect` does. Standard library only, Python 3.9 or newer.

`porter` below is `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/porter.py`.

## Copy it into the port

```sh
mkdir -p porter
cp ${CLAUDE_PLUGIN_ROOT}/knowledge/harnesses/python/harness.py porter/
cp ${CLAUDE_PLUGIN_ROOT}/knowledge/harnesses/python/bindings.example.py porter/bindings.py
```

## Run it

From the port root, with the port's virtualenv active:

```sh
python porter/harness.py --workspace .porter --run <run> [--unit <unit>]... [--bindings porter/bindings.py] \
    [--path <dir>]... [--timeout <seconds>]
porter parity collect --run <run>
```

The current directory, its `src/` folder (when present) and every `--path` go on `sys.path`, so bindings can
import the port without installing it. The default run id is the UTC time. Exit code 0 when runs were
written, 2 when the harness cannot run.

## Bindings

`bindings.py` defines `BINDINGS`, a dict from each source call id to `f(args, kwargs, input)`, and nothing
else. Tagged inputs arrive decoded: `$bytes` as `bytes`, `$set` as `set`, `$map` as `dict`, `$float` as
`float`, `$int` as `int`, `$decimal` as `Decimal`, `$datetime` as `datetime`, `$undefined` as `None`.
`input` is the whole decoded input, so `input["init"]` holds constructor arguments for `Class.method` calls.
A coroutine returned by a binding is awaited.

Bindings translate calling conventions only (an options object to keyword arguments, a receiver built from
`init`). They never convert or patch a result. When the source returned JavaScript `undefined` and the port
returns `None`, return `UNDEFINED` (`from harness import UNDEFINED`); it serializes as `{"$undefined": true}`.
A call id without a binding gets the outcome category `MissingBinding`.

## Serialization

The same rules as the Python oracle (`knowledge/oracles/python/README.md`): tuples and lists become arrays,
sets become sorted `$set`, non-string-key dicts become `$map`, bytes become `$bytes`, special floats become
`$float`, big ints become `$int`, enums become `$enum`, dataclasses and plain objects become `$type` with
public fields sorted.

## Errors and timeouts

The category is the exception class name and the message is `str(exc)`. Each case gets `--timeout` seconds
(default 10), enforced with `SIGALRM` on POSIX and a daemon thread elsewhere.

## Limitations

- Field names in `$type` objects are the port's attribute names. A port of a camelCase source must keep the
  source's names for those objects to match.
