# Strategy: shellquote (github.com/kballard/go-shellquote) -> python (shellquote)

The whole library is 213 LOC of pure code with two public functions and three error values, so the port
is one unit, `root`, which is also the tracer bullet. It is a code port: `join` and `split` follow the
two Go state machines step for step (restructured from `goto` into loops), because the 1054 recorded
fixtures pin the output character for character. The Python API is idiomatic (`join`, `split`,
exception classes) and the harness bindings translate the Go call ids. At the gate the user approves the
single unit, its order and budgets, and the scope cuts below.

## Per-unit strategy

| Unit | Layer | Strategy | Why |
| --- | --- | --- | --- |
| root | core | code port | The quoting rollback and the four-state split machine (raw, escape, single, double) are exact-output algorithms; adapting the source logic is the shortest path to EXACT parity. No runtime welding. |

## Idiom map

Seeded from `knowledge/pairs/GENERIC.md` (there is no go-to-python pair file) and specialized to this
codebase. Probes ran on go1.26.0 (fixtures) and CPython 3.14.6.

| Concern | Source idiom | Target idiom | Rule for this port |
| --- | --- | --- | --- |
| Errors | `var X = errors.New(msg)` sentinels, returned as `(words, err)`, compared with `==` | exception classes `UnterminatedSingleQuoteError`, `UnterminatedDoubleQuoteError`, `UnterminatedEscapeError`, all subclasses of `ShellQuoteError(ValueError)`, raised by `split` | Keep the Go names (the harness category is `type(exc).__name__`, so no `error-map.json` is needed). `str(exc)` is exactly the Go message (probe: `str(E("Unterminated backslash-escape", ["a"]))` is the bare message). The first error in scan order wins. |
| Partial results on error | named returns hand back the words completed before the error (`a b\` returns `["a"]` with UnterminatedEscapeError, fixture `split.err.escape-ends-word`) | `exc.words: list[str]` on every split exception | unattended: the user said "exceptions for errors" but not what happens to the partial words. Conservative option: keep the information on the exception rather than drop it. A target test checks `exc.words` against `expect.value` for all 170 Split error fixtures, because parity does not compare it. |
| Absence | `Split` returns a non-nil empty slice; `Join()` returns `""` | `split` returns `[]`, `join()` returns `""` | Never return `None` (fixtures `split.empty`, `split.spaces-only`). |
| Variadic arguments | `func Join(args ...string) string` | `def join(*args: str) -> str` | Mirrors Go's variadic and avoids the footgun where a bare `str` passed as an iterable is joined per character. The binding spreads fixture `input.args`. |
| Strings and bytes | `string` is bytes; `utf8.DecodeRuneInString`, byte offsets, `strings.IndexRune` | `str` of code points; iterate with indexes, `str.find` | Identical for valid UTF-8 (probe: `"a😀b"` iterates as 3 code points, Go decodes 3 runes; fixtures `join.unicode-plain`, `split.err.unicode-partial`). Invalid UTF-8 is out of scope (below). |
| Whitespace and character sets | fixed sets: split on `" \n\t"`, quote on `" \t\n"`, escape `` \'"`${[|&;<>()*?! ``, prefix `~`, double-quote escapes `` $`"\n\ `` | module-level `str` constants used with `in` | Never use `str.split()`, `str.isspace()` or regex `\s`: probe `"a\rb\x0bc\xa0d e".split()` gives 5 words, Go gives one word per fixture `split.cr-not-separator`, `split.unicode-space-not-separator`, `join.cr-not-quoted`. |
| Buffers | `bytes.Buffer` shared across words, `Truncate(origLen)` rollback in `quote` | a per-word `list[str]` joined at the end; the rollback discards the list | No truncation needed; output identical (fixture `join.rollback-per-arg`). |
| Control flow | labels and `goto` (`quote:`, `raw:`, `escape:`, `single:`, `double:`, `done:`) | a `while` loop over a state variable, or one helper per state | Free to differ per the contract; each state keeps the same consume and emit rules. |
| Numbers, regex, dates, async | not used | not used | none |
| Module layout and naming | package `shellquote`, files `quote.go`, `unquote.go`, exported `Join`, `Split` | `src/shellquote/__init__.py` re-exports from `_quote.py` and `_unquote.py`; `py.typed` | snake_case functions, PascalCase exceptions, private helpers prefixed `_`. `__all__` lists the public names. |

Standard library equivalence (GENERIC section 12), one row per Go import:

| Go import | Python | Differences the fixtures touch |
| --- | --- | --- |
| `bytes` | `list[str]` + `"".join` | none |
| `errors` | `Exception` subclasses | identity comparison becomes `isinstance` / `except` |
| `strings` | `in`, `str.find` | `IndexRune` returns a byte offset, `find` a code-point index; both are only used to slice the same string |
| `unicode/utf8` | implicit in `str` | invalid UTF-8 (out of scope) |

## Dropped workarounds and new substrate

- Dropped: the shared `bytes.Buffer` and `Truncate` rollback (a fresh list per word), the byte-offset
  arithmetic `len(input)-len(cur)-l` (code-point indexes), and Go's `goto`.
- New substrate: none. The exception base class `ShellQuoteError` is new API with no Go counterpart; it
  lets callers catch all three errors at once and subclasses `ValueError` like `shlex` does.

## Scope gauntlet

| Item | Decision | Reason |
| --- | --- | --- |
| `Join`, `Split`, three error values | now | the whole public surface, unit `root` |
| Partial words on `Split` errors | now, as `exc.words` | unattended: conservative option, keeps what Go returns |
| Invalid UTF-8 input (leak `invalid-utf8`) | out of scope | unattended: a `str` API cannot receive invalid UTF-8 bytes; Go copies them through (`Join("a\xff b")` is `'a\xff b'`). No fixture uses them. Seam for later: a `bytes` overload that decodes with `surrogateescape` and re-encodes the result. |
| Lone surrogates in a Python `str` | out of scope | Go strings cannot hold them, so there is no oracle; the port treats them as ordinary characters. |
| `$'...'` quoting, expansions | out of scope (as in the original) | the original does not support them either (unquote.go:25-28); fixtures pin the literal behavior |
| A CLI | out of scope | the original is a library only |

## Risk register

| Risk | Mitigation | Signal that it is happening |
| --- | --- | --- |
| Quote-mode rollback differs: a special character before a space keeps its backslash, or a leading/trailing `'` emits an empty `''` pair | port `quote` branch for branch; fixtures `join.special-then-space`, `join.leading-quote-with-space`, `join.trailing-quote-with-space`, `join.two-quotes-then-space` | Join mismatches on any argument containing space, tab or newline |
| Double-quote escape edge: a trailing backslash inside an open `"` must consume nothing and end in UnterminatedDoubleQuoteError (Go decodes an empty remainder as width 0) | guard the index past the end explicitly; fixtures `split.err.double-trailing-backslash*`, `split.err.double-only-backslash` | an `IndexError`, or UnterminatedEscapeError where the fixture says double quote |
| Whitespace semantics leak in through `str.split()` / `isspace()` | idiom map rule plus review check; fixtures `split.cr-not-separator`, `split.crlf`, `split.unicode-space-not-separator` | Split mismatches on CR, NBSP or Unicode spaces |
| Partial words lost or wrong on errors (parity cannot see them) | target test over all 170 Split error fixtures comparing `exc.words` with `expect.value` | that test fails; parity stays green |

## Scaffold

- Package layout:

  ```text
  pyproject.toml
  LICENSE                      (MIT, copyright line kept from the original)
  README.md
  src/shellquote/__init__.py   (public API, __all__)
  src/shellquote/_quote.py     (join)
  src/shellquote/_unquote.py   (split, exceptions)
  src/shellquote/py.typed
  tests/test_join.py           (ported TestSimpleJoin, [ref: quote_test.go::TestSimpleJoin])
  tests/test_split.py          (ported TestSimpleSplit, TestErrorSplit, exc.words over error fixtures)
  tests/test_roundtrip.py      (ported TestJoinSplit with seeded random.Random)
  tests/test_fixtures.py       (runs the harness bindings over .porter/fixtures in pytest)
  porter/harness.py, porter/bindings.py
  ```

- Toolchain: build hatchling via `pyproject.toml`, `requires-python = ">=3.11"`; test pytest 9.1.1;
  lint `ruff check`; format `ruff format`; typecheck `mypy --strict src tests` (mypy 2.4.0). Dev
  dependencies in `[dependency-groups] dev`. Runtime dependencies: none.
- Harness: `knowledge/harnesses/python/harness.py` copied to `porter/harness.py`; bindings in
  `porter/bindings.py` map `github.com/kballard/go-shellquote:Join` to `join(*input["args"])` and
  `...:Split` to `split(input["args"][0])`.
- CI: none in this run (nothing is pushed). A later `.github/workflows/ci.yml` would run ruff, mypy and
  pytest on Python 3.11 to 3.15.

## Budgets

Attempts per unit: 3. Discovered units before returning to the user: 5. PORT depth and LOC: 1, 2000
(no PORT dependencies, so unused). Unit size: 213 LOC of 400, 5 public symbols of 8.
