# Dependencies: shellquote (github.com/kballard/go-shellquote) -> python

go-shellquote has no third-party dependencies. The repo has no `go.mod` or other manifest, so
`porter.py deps-graph` found nothing and `porter.py usage-scan` found no third-party imports; the list
below comes from reading the import blocks (quote.go:3-7, unquote.go:3-8). All four runtime imports are
Go standard library packages and all four are ABSORB into the Python standard library and builtins.
Nothing needs a registry package, nothing is PORT or VENDOR, and there are no gate items.

Python's `shlex` was considered as a drop-in for the whole package and rejected because its behavior
differs from the Go original (probes on CPython 3.14.6, see the `strings` row in `deps.json`):
`shlex.quote("don't")` gives `'don'"'"'t'` where Go gives `don\'t`, `shlex.quote("foo*")` gives
`'foo*'` where Go gives `foo\*`, `shlex.split` keeps an unquoted backslash-newline as a newline where Go
elides it, and `shlex` raises one `ValueError` where Go has three distinct errors.

## Runtime dependencies

| Dependency | Version | Role | Used surface | Decision | Candidate | Confidence | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| bytes | Go stdlib | runtime-library | `bytes.Buffer`: WriteByte, WriteString, WriteRune, Truncate, Len, Reset, String | ABSORB | `list[str]` + `str.join` (or `io.StringIO`) | HIGH | quote.go:13-20, quote.go:37-61, unquote.go:34, unquote.go:68-155 |
| errors | Go stdlib | runtime-library | `errors.New` (3 sentinel values) | ABSORB | `Exception` subclasses | HIGH | unquote.go:10-14 |
| strings | Go stdlib | runtime-library | `strings.ContainsRune`, `strings.IndexRune` | ABSORB | `in` operator, `str.find` | HIGH | quote.go:50, 58, 77; unquote.go:40, 88, 117, 140 |
| unicode/utf8 | Go stdlib | runtime-library | `utf8.DecodeRuneInString` | ABSORB | iteration over `str` code points | HIGH | quote.go:48; unquote.go:39, 50, 74, 105, 130, 138 |

`unicode/utf8` coverage is partial in one respect: Go strings can carry invalid UTF-8, which
`DecodeRuneInString` reads as U+FFFD (width 1) and the code copies through as raw bytes. A Python `str`
API cannot receive those bytes. That is a contract scope question for the next phase, not a missing
dependency.

## API deltas for MAP and SHIM

None: there are no MAP or SHIM decisions.

## Dev, build and test tools

| Source tool | Target tool | Note |
| --- | --- | --- |
| `go test` (`testing`) | pytest 9.1.1 (MIT, `cache/registry/pypi/pytest.json`) | Table-driven tests become `pytest.mark.parametrize`. |
| `testing/quick` + `reflect.DeepEqual` | standard library `random` with a fixed seed, in pytest | Stdlib first, per the user. hypothesis 6.170.5 (MPL-2.0, `cache/registry/pypi/hypothesis.json`) is the alternative if shrinking is wanted. |
| `gofmt`, `go vet` | ruff 0.17.1 (MIT, `cache/registry/pypi/ruff.json`) | `ruff format`, `ruff check`. |
| Go compiler type checks | mypy 2.4.0 (MIT, `cache/registry/pypi/mypy.json`) | `strict = true`. |

## Gate items

None. `porter.py registry verify-deps` reported 4 NOT_APPLICABLE (stdlib ABSORB, no registry candidate).
