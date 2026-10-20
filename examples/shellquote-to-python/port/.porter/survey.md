# Survey: shellquote (github.com/kballard/go-shellquote), untagged, commit 95032a8

go-shellquote is a small Go library that joins argument lists into a `/bin/sh` command string and splits
such a string back into words using sh's word-splitting rules (README:6-7, README:20-34). Callers are Go
programs that build or parse shell command lines; the repo names no specific users. Verdict: a tiny, pure
port with low risk. It is 242 LOC across two logic files with two public functions, three exported error
values, and no third-party or I/O dependencies, smaller than the 400-LOC unit budget in `config.json`.
The risk sits in exact output fidelity: the hand-written `goto` state machine in `unquote.go` and Go's
byte-string semantics, where invalid UTF-8 passes through unchanged.

## Facts

| Fact | Value |
| --- | --- |
| Package | unknown |
| Commit | 95032a82bc51 |
| License | MIT (copyleft: none) |
| Kind | library |
| Primary language | go |
| Source LOC | 242 |
| Tests | 3 files, 104 LOC, 4 cases, ratio 0.43 |
| Test runners | go test |
| Public symbols | 5 |
| Modules by coupling | pure 1 |
| Runtimes | not declared |
| Sampled | no |

| Module | Language | LOC | Coupling | Signals | Risk tags | Public symbols |
| --- | --- | --- | --- | --- | --- | --- |
| root | go | 242 | pure |  | error-model, nullability, ordering, unicode | Join, UnterminatedSingleQuoteError, UnterminatedDoubleQuoteError, UnterminatedEscapeError, Split |

Notes on the facts:

- Package shows "unknown" because the repo has no `go.mod` (it predates Go modules; the last commit is
  2018-04-27). The import path is `github.com/kballard/go-shellquote` (README:4) and the Go package name is
  `shellquote` (doc.go:3). There are no git tags, so there is no version; the pin is commit
  95032a82bc518f77982ea72343cc1ade730072f0.
- "4 cases" counts test functions. The tables hold 28 fixed cases (11 Join, 12 Split, 5 error) plus one
  property test; see Flags.
- survey.json labels the three error values and `splitChars`, `singleChar`, `doubleChar`, `escapeChar`,
  `doubleEscapeChars` as constants. They are package-level `var`s (unquote.go:10-22). Only `specialChars`,
  `extraSpecialChars` and `prefixChars` are `const` (quote.go:23-27). survey.json also gives
  `UnterminatedEscapeError` an end line of 16; it is a single line at unquote.go:13.

## Scope

- Kind: library. There is no `main` package and no entry point; the whole package is the public API.
- In scope: package `shellquote`, all of it: `doc.go` (package doc), `quote.go` (`Join` plus the private
  `quote` helper), `unquote.go` (`Split`, private `splitWord`, the three `Unterminated*Error` values). The
  test files `both_test.go`, `quote_test.go` and `unquote_test.go` are the behavioral oracle for the
  contract.
- Out of scope: nothing to exclude. The repo has no generated code, vendored code, examples or platform
  shims. `README` is godoc text that duplicates the doc comments, and `LICENSE` is carried over unchanged.

## Where the risk is

Coupling for `root` is confirmed pure. The only imports are `bytes`, `errors`, `strings` and `unicode/utf8`
(quote.go:3-7, unquote.go:3-8). `/bin/sh` appears only in doc comments (quote.go:10, unquote.go:24) and is
never executed. All risk is semantic fidelity; there is no environment coupling. Rows split the single
module by file because that is where the risk differs.

| Module | Coupling | Why it is risky | Risk tags |
| --- | --- | --- | --- |
| root: `unquote.go` (`Split`, `splitWord`) | pure | Label-and-`goto` state machine (raw, escape, single, double at unquote.go:70-155) that must be restructured into loops without changing behavior. Escape rules depend on context: an unquoted backslash-newline is elided (unquote.go:106, and between words at unquote.go:43-54); inside double quotes only dollar, backtick, double quote, newline and backslash are escapable and any other backslash is kept literally (unquote.go:21, unquote.go:136-148). Slicing uses byte offsets from `utf8.DecodeRuneInString` and `strings.IndexRune` (unquote.go:74-77, unquote.go:117). | unicode, nullability |
| root: `unquote.go` error path | pure | `Split` uses named returns, so on error it returns the words collected so far together with the error (unquote.go:47-48, unquote.go:58-60). It returns a non-nil empty slice for empty or all-whitespace input (unquote.go:35). The three errors are sentinel values compared by identity in tests (unquote_test.go:22), and their message strings are visible API (unquote.go:11-13). A trailing backslash inside an open double quote decodes an empty remainder (width 0, unquote.go:138) and falls through to `UnterminatedDoubleQuoteError`; no test covers this. | error-model, nullability |
| root: `quote.go` (`Join`, `quote`) | pure | Two-mode quoting. It backslash-escapes the special characters (quote.go:24), but on space, tab or newline it rolls the shared buffer back with `buf.Truncate(origLen)` and restarts in single-quote mode (quote.go:58-61). `~` is escaped only at the start of a word (quote.go:26, quote.go:50). An embedded `'` is emitted as `'\''`, and quotes are opened lazily so a leading or trailing `'` produces no empty `''` pair (quote.go:75-101). An empty argument becomes `''` (quote.go:39-43). Tests compare exact output strings (quote_test.go:20-30), so any deviation from this "nice" output fails. Invalid UTF-8 bytes decode as U+FFFD and are copied through as the original bytes (quote.go:48-53). | unicode, ordering |

The `ordering` tag on `Join` looks like a false positive: it iterates its arguments in order (quote.go:14),
and there is no map iteration or concurrency anywhere in the package.

## Flags for the user

- License: MIT, no copyleft. The port must keep the copyright and permission notice (LICENSE:1, LICENSE:10-11).
- Tests: 3 files, 104 LOC, ratio 0.43. That is good coverage for the size: 11 exact-output Join cases
  (quote_test.go:20-30), 12 Split cases (unquote_test.go:32-43), 5 error cases matched by identity
  (unquote_test.go:50-54), and a `testing/quick` round-trip property, Join then Split returns the input
  (both_test.go:11-28). Gaps: no test feeds invalid UTF-8, no test covers a trailing backslash inside
  double quotes, and the fixed Join cases do not cover tab or newline in an argument (only the random
  property test can reach those). The `$''` quoting form is documented as unsupported (README:27-28,
  unquote.go:25-26) and is untested.
- Sampling: full scan. 6 of 6 code files were read (doc.go, quote.go, unquote.go and the three test files),
  along with README and LICENSE.
- Native code, FFI, subprocess or OS-specific paths: none found. There is no cgo, `syscall`, `unsafe`,
  `os/exec` or build tag in any `.go` file. The quoting rules target POSIX `/bin/sh` (README:21-30), and
  nothing handles Windows `cmd.exe` quoting.
- Input type: Go `string` values are arbitrary byte sequences, and both functions preserve non-UTF-8 bytes
  untouched (quote.go:48-53, unquote.go:74-77). Whether the port accepts only text, or bytes as well, is a
  contract decision; the source tests do not pin it down.
