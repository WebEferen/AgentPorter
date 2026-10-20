# shellquote

Join and split strings using `/bin/sh` word-splitting rules. A Python port of
[go-shellquote](https://github.com/kballard/go-shellquote) (commit `95032a8`), with the same output
character for character.

```python
>>> from shellquote import join, split
>>> join("ls", "-l", "my file", "don't")
"ls -l 'my file' don\\'t"
>>> split("ls -l 'my file' don\\'t")
['ls', '-l', 'my file', "don't"]
```

`join(*args)` quotes each argument and joins them with a space. Arguments containing a space, tab or
newline are single-quoted; otherwise shell metacharacters are backslash-escaped.

`split(s)` splits on space, tab and newline and removes single quotes, double quotes and backslash
escapes. It performs no expansion of any kind and does not support `$'...'` quoting.

## Errors

`split` raises a subclass of `ShellQuoteError` (itself a `ValueError`) for malformed input:

| Exception | Message |
| --- | --- |
| `UnterminatedSingleQuoteError` | `Unterminated single-quoted string` |
| `UnterminatedDoubleQuoteError` | `Unterminated double-quoted string` |
| `UnterminatedEscapeError` | `Unterminated backslash-escape` |

Each exception carries `words`, the words completed before the error:

```python
>>> from shellquote import ShellQuoteError
>>> try:
...     split("a b 'c d")
... except ShellQuoteError as exc:
...     print(type(exc).__name__, exc.words)
UnterminatedSingleQuoteError ['a', 'b']
```

Only `str` input is supported. Go strings may hold invalid UTF-8, which has no `str` equivalent.

## Parity with upstream

Upstream: `github.com/kballard/go-shellquote`, untagged, commit
`95032a82bc518f77982ea72343cc1ade730072f0`. Evidence date: 2026-10-20 (harness run `verify-final-v1`,
oracle recorded with go1.26.0). Full report: [docs/PARITY.md](docs/PARITY.md).

| Unit | Level | Fixtures (exact of total) | Reference tests (pass / total) | Divergences |
| --- | --- | --- | --- | --- |
| root (`join`, `split`, errors) | EXACT | 1083 of 1083 | 29 / 29 | none |

Divergences: none. Out of scope: invalid UTF-8 input (a `str` cannot hold it) and lone surrogates (Go
strings cannot hold them, so there is no oracle). `exc.words` exposes the partial words Go returns
alongside its errors.

## Development

```sh
uv sync
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
```

Porting evidence and parity status live in [PORTING.md](PORTING.md) and `.porter/`.

## License

MIT, see [LICENSE](LICENSE).
