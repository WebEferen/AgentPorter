# Contract: shellquote (github.com/kballard/go-shellquote) at commit 95032a8, untagged

The Python package `shellquote` must reproduce two pure functions exactly: `Join`, which quotes a list of
arguments into one `/bin/sh` command string in a specific "nice" form, and `Split`, which splits such a
string back into words with sh quoting and escaping rules, plus the three error categories `Split` reports.
The observation boundary is the return value or the raised error (category and exact message) of each
call; there is no I/O, state or concurrency. Confidence is high: the 28 upstream table cases and the
round-trip property all reproduce on the recorded oracle, and 1054 fixtures recorded from the pinned source
cover every branch of both state machines, including paths the upstream tests miss.

Target shape (decided by the user): Python 3.11+, snake_case `join` and `split`, exceptions for errors.
Fixtures keep the Go call ids `github.com/kballard/go-shellquote:Join` and `...:Split`; the harness bindings
translate. Python's `shlex` is not a substitute (see `deps.md`): its quoting form, escape rules and error
model all differ from these fixtures.

## Public surface

| Symbol | Kind | Signature | Unit | In scope | Notes |
| --- | --- | --- | --- | --- | --- |
| root:Join | function | `func Join(args ...string) string` | root | yes | Never fails, no side effects. `Join()` is `""`. Python name `join`. |
| root:Split | function | `func Split(input string) (words []string, err error)` | root | yes | Never returns nil words. On error also returns the words completed so far. Python name `split`. |
| root:UnterminatedSingleQuoteError | constant (error value) | `errors.New("Unterminated single-quoted string")` | root | yes | Becomes an exception class of the same name. |
| root:UnterminatedDoubleQuoteError | constant (error value) | `errors.New("Unterminated double-quoted string")` | root | yes | Becomes an exception class of the same name. |
| root:UnterminatedEscapeError | constant (error value) | `errors.New("Unterminated backslash-escape")` | root | yes | Becomes an exception class of the same name. |

Nothing is out of scope. Private helpers and character sets (`quote`, `splitWord`, `specialChars`,
`extraSpecialChars`, `prefixChars`, `splitChars`, `singleChar`, `doubleChar`, `escapeChar`,
`doubleEscapeChars`) are not public; they belong to unit `root` in `plan.json` and their behavior is pinned
through `Join` and `Split`.

## Semantics the tests promise and the docs omit

Join (quote.go:12-102):

- Exact output form, compared character for character (quote_test.go:20-30). Per argument:
  - `""` becomes `''` (`join.empty-arg`, `join.ref.07`).
  - If the argument contains a space, tab or newline anywhere, the whole argument is written in single
    quotes and every earlier backslash escape for it is discarded (`join.special-then-space`: `a* b` gives
    `'a* b'`). Each `'` inside becomes `'\''`, quotes are opened lazily, so a leading or trailing `'` gives
    no empty `''` pair (`join.leading-quote-with-space`: `\''a b'`; `join.trailing-quote-with-space`:
    `'a b'\'`; `join.two-quotes-then-space`: `\'\'' x'`). Tab and newline stay literal inside the quotes.
  - Otherwise each of `` \ ' " ` $ { [ | & ; < > ( ) * ? ! `` is preceded by a backslash and every other
    character is copied as is.
  - `~` is escaped only as the first character of an argument (`\~user`, `u~ser`, `*~` gives `\*~`).
- Characters sh treats specially but Join does not escape: `#` (even at word start, where sh starts a
  comment), `]`, `}`, `=`, `%`, `^` (`join.not-escaped-punct`). Preserve this; it is the original's output.
- Only space, tab and newline trigger quoting. CR, VT, FF, NUL, other control characters, NBSP and every
  Unicode space are copied unquoted (`join.cr-not-quoted`, `join.unicode-space-not-quoted`, `join.nul-byte`).
- Arguments are joined with exactly one space. The quoting of one argument never affects another
  (`join.rollback-per-arg`: `a\* 'b c' d\?`).
- Unicode passes through by code point, including astral characters, combining marks, ZWJ sequences and a
  literal U+FFFD (`join.unicode-plain`, `join.replacement-char`).

Split (unquote.go:33-156):

- Separators are exactly space, tab and newline; runs of them count as one; leading and trailing ones are
  ignored. CR (so CRLF leaves `\r` on the word), VT, FF, NBSP and Unicode spaces are word characters.
- Returns `[]` (never nil or None) for empty or whitespace-only input (`split.empty`, `split.spaces-only`).
- Quote removal and concatenation: `a'b'"c"\d` is one word `abcd`; `''` and `""` are empty words.
- Outside quotes a backslash escapes the next character, whatever it is (`\é` gives `é`); backslash-newline
  is removed entirely, at word start, inside a word or between words (`foo\<nl>bar` gives `foobar`).
- Inside single quotes everything is literal, backslashes and newlines included; there is no escape.
- Inside double quotes a backslash escapes only `$`, backtick, `"`, `\` and newline (backslash-newline is
  removed); before any other character the backslash is kept (`"\a\n\'"` gives `\a\n\'`).
- No expansion of any kind: `$HOME`, `~`, globs, braces, `|`, `;`, `&&`, redirections and `#` are
  literal text. `$'...'` is not supported: `$'a\nb'` gives `$a\nb` (`split.dollar-single-unsupported`).
- Errors (untested upstream where marked):
  - An unclosed `'` gives UnterminatedSingleQuoteError.
  - An unclosed `"` gives UnterminatedDoubleQuoteError, including an escaped `\"` that leaves the quote
    open and a backslash as the last character inside an open double quote (`split.err.double-trailing-backslash`,
    untested upstream: the backslash consumes nothing and the quote is still open, unquote.go:136-151).
  - A backslash as the last character outside quotes gives UnterminatedEscapeError.
  - The first problem met scanning left to right wins (`'a "b` is a single-quote error).
- On error Go also returns the words completed before the failing word; the failing word's partial text is
  dropped (`a b\` returns `[a]`, `a \` returns `[a]`). See leak `split-partial-words-on-error`.
- Round trip (both_test.go:11-28): for any list of valid strings, `Split(Join(args...))` returns `args`
  without error. Verified on the oracle for all 200 generated argument lists.

## Error model

| Source error | When | Target category (error-map.json) |
| --- | --- | --- |
| UnterminatedSingleQuoteError, message `Unterminated single-quoted string` | Split: a `'` with no closing `'` | UnterminatedSingleQuoteError (same name, no mapping) |
| UnterminatedDoubleQuoteError, message `Unterminated double-quoted string` | Split: a `"` with no closing `"`, including a trailing backslash inside the open quote | UnterminatedDoubleQuoteError (same name, no mapping) |
| UnterminatedEscapeError, message `Unterminated backslash-escape` | Split: input ends with a backslash outside quotes | UnterminatedEscapeError (same name, no mapping) |

`Join` has no error path. Go sentinels are matched by identity (`err == UnterminatedSingleQuoteError`,
unquote_test.go:22); the Python equivalent is matching the exception class. The Python harness reports
`type(exc).__name__` and `str(exc)`, so the classes keep the Go names (already valid PEP 8 exception names)
and `str(exc)` must be exactly the Go message, with no words or position appended.

unattended: `contract/error-map.json` is not written, because the conservative target keeps the source
names and parity grades them EXACT without a map. If the strategy phase renames the exceptions, it must add
`error-map.json` mapping each Go name to the new one.

## Leak list

Internals that leak into observable behavior and must be preserved or consciously diverged from (details
and evidence in `api.json` `leaks`):

- `invalid-utf8`: Go strings carry arbitrary bytes and both functions copy invalid UTF-8 through unchanged
  (probed on the pinned source: `Join("a\xff b")` is `'a\xff b'`, `Split("a\xffb c")` is `["a\xffb" "c"]`,
  the round trip holds). A Python `str` cannot hold such bytes. Scope decision for the strategy phase.
  unattended: the conservative default is a `str`-only Python API that promises nothing for invalid UTF-8;
  a bytes API is out of scope unless the strategy adds it. No fixture uses invalid UTF-8.
- `split-partial-words-on-error`: named results make `Split` return the completed words with every error.
  Recorded as `expect.value` on all 170 Split error outcomes. unattended: the strategy phase decides whether
  the Python exception carries them (for example an attribute) or drops them; parity does not compare the
  field, so a target test must read it if the words are kept.
- `split-empty-not-nil`: `Split` returns a non-nil empty slice; Python returns `[]`, never `None`.
- `error-sentinels`: names are the categories and messages are exact API; first error in scan order wins.
- `go-separator-and-escape-sets`: fixed ASCII sets (space, tab, newline), not Unicode whitespace; Python's
  `str.split()`, `str.isspace()` and regex `\s` would change results.

Free to differ:

- The `goto` state machine, the shared buffer with `Truncate` rollback, private helper names and the private
  character-set variables.
- Byte offsets against code-point indexes (identical results for valid UTF-8).
- Whether `join` is variadic or takes one iterable; the binding maps fixture `input.args`.
- Any exception base class above the three named classes (for example `ValueError`), as long as the class
  names and `str(exc)` match.
- Performance and allocation.

## Observation boundary per unit

| Unit | Observed | Normalization |
| --- | --- | --- |
| root | Join: return value (string). Split: return value (list of strings), or error category and exact message; on error outcomes `expect.value` also records the words Go returned (informational, not compared by parity). | none |

## Fixtures

```text
| Unit | Files | Cases | Kinds | Origins |
| --- | --- | --- | --- | --- |
| root | 1 | 1054 | error 170, value 884 | derived 200, generated 700, hand-written 126, reference-test 28 |
```

- Harvested (28): every table entry of `TestSimpleJoin` (11), `TestSimpleSplit` (12) and `TestErrorSplit`
  (5); origin `reference-test:<file>::<test>::<table index>`. All reproduce the upstream expectations.
- Hand-written (126): 54 Join and 72 Split edge cases: empty input, whitespace sets, every special
  character, `~` placement, quote placement around the single-quote rollback, escapes in each quoting
  mode, no-expansion, Unicode (astral, combining, ZWJ, U+FFFD), NUL and control characters, large inputs
  (10 000 to 20 000 characters, 500 arguments) and 18 error paths with partial words.
- Generated (700, fixed seeds): `join-random` (150, seed 20180427, special-heavy alphabet with tab, newline
  and CR), `join-unicode` (50, seed 95032), `split-random` (300, seed 4242, quote- and backslash-heavy,
  147 errors), `split-grammar` (200, seed 7, well-formed tokens in every quoting style).
- Derived (200): the round-trip property. `oracle/derive_roundtrip.py` turns every generated Join outcome
  into a Split case (origin `derived:both_test.go::TestJoinSplit:from=<join case>`), and its `check` mode
  confirmed `Split(Join(x)) == x` for all 200.

Recording: the Go driver copy in `oracle/driver/` builds against `oracle/driver/upstream/`, which is
`git archive 95032a82bc518f77982ea72343cc1ade730072f0` of the source checkout plus a one-line `go.mod`
(the repo predates modules and a `replace` target needs one); `quote.go` and `unquote.go` are
byte-identical to the checkout, and the upstream test suite passes there on go1.26.0. `oracle/driver/main.go`
carries one workspace patch: when a call returns a value together with an error, the value is kept as
`expect.value` on the error outcome. Re-recording reproduces every outcome (`fixtures diff`: 0 changed).
Re-record in this order: `porter fixtures expand`, the driver (`cd .porter/oracle/driver && go run .
--workspace ../.. --unit root`), `python3 -I .porter/oracle/derive_roundtrip.py .porter derive`, expand and
the driver again, then `derive_roundtrip.py .porter check`.
