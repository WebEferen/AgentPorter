# Python oracle driver

`oracle.py` records what the pinned Python source does. It reads every case in
`.porter/oracle/expanded/<unit>.json`, imports the source package, calls each case, and writes
`.porter/fixtures/<unit>/oracle.json` plus `.porter/oracle/timings/<unit>.json` as
[CONTRACT.md](../CONTRACT.md) describes. Standard library only, Python 3.9 or newer.

`porter` below is `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/porter.py`.

## Run it

Nothing to copy. Run the driver with the interpreter that has the source's dependencies installed (the
source project's virtualenv), so imports behave exactly as they do for the source's users:

```sh
porter fixtures expand
<source venv>/bin/python ${CLAUDE_PLUGIN_ROOT}/knowledge/oracles/python/oracle.py --workspace .porter \
    [--unit <unit>]... [--package-version <v>] [--commit <sha>] [--path <dir>]... [--timeout <seconds>]
porter fixtures validate
```

The driver puts `config.source.path` (joined with `config.source.subpath`) on `sys.path`, preferring its
`src/` folder when there is one. `--path` adds more directories, for example when the checkout path inside a
container differs from the one in `config.json`. Without a checkout the installed package is used.
The version comes from `--package-version`, then `config.source.package.version`, then installed
package metadata.

Exit codes: 0 when fixtures were written (thrown exceptions are outcomes), 2 when the driver cannot run:
a call that does not resolve, a CLI unit, missing expanded cases.

## How calls resolve

`module:qualname` is imported with `importlib` and walked attribute by attribute.

| Call | Input | What runs |
| --- | --- | --- |
| `pkg.mod:func` | `args`, `kwargs` | `func(*args, **kwargs)` |
| `pkg.mod:Class` | `args`, `kwargs` | `Class(*args, **kwargs)` |
| `pkg.mod:Class.method` | `init`, `args`, `kwargs` | `Class(*init.args, **init.kwargs).method(*args, **kwargs)` |
| `pkg.mod:Class.method` | `args` (no `init`) | the attribute as found: static and class methods work |
| `pkg.mod:NAME` | `{}` | reads the attribute |

A coroutine result is awaited with `asyncio.run`.

## Serialization

| Python | JSON |
| --- | --- |
| `list`, `tuple` | array |
| `set`, `frozenset` | `{"$set": [...]}` sorted by canonical JSON |
| `dict` with only `str` keys | object |
| other `dict` | `{"$map": [[k, v], ...]}` in insertion order |
| `bytes`, `bytearray`, `memoryview` | `{"$bytes": "<base64>"}` |
| `nan`, `inf`, `-inf`, `-0.0` | `{"$float": ...}` |
| `int` beyond 2^53 | `{"$int": "..."}` |
| `Decimal` | `{"$decimal": str(value)}` |
| `datetime`, `date`, `time` | `{"$datetime": value.isoformat()}` |
| `Enum` member | `{"$enum": "Type.MEMBER"}` (checked before `int`, so `IntEnum` stays an enum) |
| dataclass, namedtuple, object with `__dict__` or `__slots__` | `{"$type": "Name", ...}` with public fields (no leading underscore), sorted |
| generator, `range`, `map`, `filter`, `zip`, dict views | array, capped at 10000 items |
| function, class | `{"$type": "function" or "class", "name": qualname}` |
| exception value | `{"$type": "Name", "message": str(exc)}` |
| anything else | `{"$type": "Name", "repr": repr(value)}` |

Tagged values in case inputs are decoded before the call: `$float`, `$int`, `$bytes`, `$decimal`,
`$datetime`, `$set` (to `set`), `$map` (to `dict`) and `$undefined` (to `None`).

## Errors and timeouts

The category is the exception class name (`ValueError`, `KeyError`), the message is `str(exc)`. A
`sys.exit(n)` records as category `SystemExit` with message `n`. An
`ImportError` or `AttributeError` raised while a resolvable call runs is an outcome (an optional dependency
that is missing, for example). One raised while resolving the call id exits 2.

Each case gets `--timeout` seconds (default 10). On POSIX the driver uses `SIGALRM`, which interrupts pure
Python loops. Elsewhere it runs the case on a daemon thread and stops waiting, but cannot stop the thread.

## Limitations

- C extensions that block in native code ignore `SIGALRM` until they return.
- Output printed by the source goes to the driver's stdout.
- Objects without `__dict__` or `__slots__` fall back to `repr`, which rarely matches another language.
