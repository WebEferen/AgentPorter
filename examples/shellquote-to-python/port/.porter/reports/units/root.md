# Unit report: root

Status: DONE. Parity: EXACT. Attempts: 1.

## Checklist

Times are when `porter state unit task` recorded the step (state.json history).

| Task | Done at |
| --- | --- |
| read-contract | 2026-10-20T19:36:39Z |
| scaffold | 2026-10-20T19:40:46Z |
| implement | 2026-10-20T19:41:34Z |
| mark-divergences | 2026-10-20T19:41:34Z |
| port-tests | 2026-10-20T19:43:14Z |
| wire-fixtures | 2026-10-20T19:43:24Z |
| green | 2026-10-20T19:44:22Z |
| review | 2026-10-20T19:45:10Z |
| apply-findings | 2026-10-20T19:51:55Z |
| verify | 2026-10-20T19:57:03Z |
| report | recorded with this report |
| commit | in the `port(root)` commit |

## What was ported

- `src/shellquote/_quote.py`: `join` (Go `Join`, private `quote`).
- `src/shellquote/_unquote.py`: `split` (Go `Split`, `splitWord`), `ShellQuoteError(ValueError)` and the
  three exceptions `UnterminatedSingleQuoteError`, `UnterminatedDoubleQuoteError`,
  `UnterminatedEscapeError`, each with the Go message and `words` (the words completed before the error).
- `src/shellquote/__init__.py` (public API, `__all__`), `py.typed`, `pyproject.toml` (hatchling,
  `requires-python >=3.11`, dev group pytest, ruff, mypy), `LICENSE` (original MIT text), `README.md`.
- Tests: `tests/test_join.py`, `tests/test_split.py`, `tests/test_roundtrip.py` (seeded `random.Random`),
  `tests/test_fixtures.py` (every fixture through the bindings), `tests/oracle_fixtures.py`.
- Harness: `porter/harness.py` (plugin template, verbatim), `porter/bindings.py` (Go call ids to `join`
  and `split`).

## Decisions and divergences

- No DIVERGENCE markers and no `divergences.json`: every fixture matches exactly.
- unattended: partial words on split errors are kept as `exc.words` (decisions.md).
- unattended: invalid UTF-8 input is out of scope for the `str` API (decisions.md, strategy scope gauntlet).
- unattended: package version 0.1.0, because the source is untagged.
- Quote mode in `join` is written as `"\\'".join(f"'{p}'" if p else "" for p in word.split("'"))`, which
  is equivalent to Go's lazy-open loop; `split` is an index-based port of the four-state machine.

## Reference tests

PASS 29, OUT-OF-SCOPE 0, DIVERGENCE 0, FAIL 0.

## Review findings

- Applied: none. The reviewer found no correctness or contract issues (EXACT 1054/1054 at review time,
  plus its own 300,000-case differential fuzz against the Go original with 0 mismatches).
- Logged, not applied (style or other, per the implement skill):
  1. `pyproject.toml`: no sdist include list, so the sdist ships all of `.porter/` (runs, cache, the Go
     upstream copy), `porter/harness.py`, `uv.lock` and `PORTING.md`. The wheel is clean. Suggested fix:
     `[tool.hatch.build.targets.sdist] only-include = ["src", "tests", "porter/bindings.py",
     ".porter/fixtures", "README.md", "LICENSE"]`. Fix before any release.
  2. `src/shellquote/_unquote.py:59-64`: the top-level `i + 1 == n` escape check duplicates the one in
     `_split_word`; only the backslash-newline skip is needed there.
  3. `src/shellquote/_unquote.py`: `words` is threaded into the helpers only to build exceptions; `split`
     could attach it in one `except` block instead.
  4. `src/shellquote/_unquote.py:24, 31, 38`: subclass constructors take `words` positionally, so
     `UnterminatedEscapeError("oops").words` is a list of characters. Changing it needs `__reduce__` to keep
     pickling working.
  5. `src/shellquote/_unquote.py:4-6`: `_SINGLE_CHAR`, `_DOUBLE_CHAR`, `_ESCAPE_CHAR` mirror Go vars;
     plain literals would read better.

## Open questions

- Performance: median 3.2x slower than Go per case, up to 15x on large escape-heavy inputs; linear
  scaling. Not a contract item.
