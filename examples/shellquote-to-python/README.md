# go-shellquote: Go to Python

[go-shellquote](https://github.com/kballard/go-shellquote) joins and splits strings with `/bin/sh`
word-splitting rules. The upstream has no tags, so this port is pinned to commit `95032a8`.

- [original/](original/): the Go package (`quote.go`, `unquote.go`, `doc.go`), its tests, README and license.
- [port/](port/): the Python package `shellquote` in `src/`, the pytest suite, the parity harness in
  `porter/` and the `.porter/` workspace.

## Original and port

```go
import "github.com/kballard/go-shellquote"

shellquote.Join("ls", "-l", "my file", "don't")
// "ls -l 'my file' don\\'t"
words, err := shellquote.Split("ls -l 'my file' don\\'t")
// ["ls" "-l" "my file" "don't"], nil
```

```python
from shellquote import join, split

join("ls", "-l", "my file", "don't")
# "ls -l 'my file' don\\'t"
split("ls -l 'my file' don\\'t")
# ['ls', '-l', 'my file', "don't"]
```

Go's returned errors became exceptions (`UnterminatedSingleQuoteError` and two more, all `ValueError`
subclasses). Each one carries `words`, the partial result Go returns next to its error.

## Result

EXACT: all 1083 recorded cases match, and 29 of 29 upstream tests are ported and pass. No divergences.
Full report: [port/docs/PARITY.md](port/docs/PARITY.md).

Out of scope, so no fixtures: invalid UTF-8 input (a Python `str` can't hold it) and lone surrogates (a Go
string can't hold them).

## How it was made

One unattended session (see [how the examples were made](../README.md#how-they-were-made)): $14.60,
103 turns, 48 minutes. Pre-approved answers:

```text
- deps gate: approve the proposed decisions when every MAP and SHIM candidate is registry-verified. Prefer the
  Python standard library, but do not swap in shlex where its behavior differs from the Go original.
- strategy gate: approve the proposed units, order and budgets as written.
- Anything about the package: the Python package is named shellquote, Python 3.11 or newer, pytest, ruff and
  mypy, an idiomatic Python API (snake_case functions, exceptions for errors). The fixtures keep the Go call
  ids; the bindings translate.
```

The upstream has no `go.mod`, and the survey at the time left the package name empty. The name in
`.porter/config.json`, `parity.json` and the report was filled in when the example was copied here. The
survey now takes it from the git remote.

## Check it

```sh
cd port
uv run pytest
uv run python porter/harness.py --workspace .porter --run local
python3 ../../../scripts/porter.py parity collect --run local --dry-run
```

## License

MIT, from go-shellquote (Kevin Ballard). `original/` and `port/` both keep the notice.
