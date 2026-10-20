# Unit contract: root

Layer: core. Wave: 0. Depends on: none. Tracer unit; it is the whole package (quote.go, unquote.go).

## Symbols

| Symbol | Signature | Semantics |
| --- | --- | --- |
| root:Join (call id `github.com/kballard/go-shellquote:Join`) | `func Join(args ...string) string` | Quotes each argument for `/bin/sh` and joins with one space. `""` becomes `''`; an argument with space, tab or newline is single-quoted whole (`'` as `'\''`, no empty `''` at either end); otherwise `` \ ' " ` $ { [ \| & ; < > ( ) * ? ! `` are backslash-escaped and `~` only as the first character. No arguments gives `""`. |
| root:Split (call id `github.com/kballard/go-shellquote:Split`) | `func Split(input string) (words []string, err error)` | Splits on space, tab and newline only; removes quotes; backslash escapes anything outside quotes, nothing inside `'...'`, and only `` $ ` " \ `` and newline inside `"..."`; backslash-newline is removed. No expansion. Returns `[]` for blank input. |
| root:UnterminatedSingleQuoteError | `errors.New("Unterminated single-quoted string")` | Split error for an unclosed `'`. |
| root:UnterminatedDoubleQuoteError | `errors.New("Unterminated double-quoted string")` | Split error for an unclosed `"`, including a trailing backslash inside it. |
| root:UnterminatedEscapeError | `errors.New("Unterminated backslash-escape")` | Split error for a backslash at the end of input outside quotes. |

## Errors

- Unclosed single quote -> `UnterminatedSingleQuoteError` (message exactly `Unterminated single-quoted string`).
- Unclosed double quote, an escaped `\"` that leaves it open, or a backslash as the last character inside
  it -> `UnterminatedDoubleQuoteError` (message exactly `Unterminated double-quoted string`).
- Backslash as the last character outside quotes, at word start or inside a word ->
  `UnterminatedEscapeError` (message exactly `Unterminated backslash-escape`).
- The first problem in left-to-right order wins. On every error the original also returns the words
  completed before the failing word; the failing word's partial text is dropped. Fixtures record those
  words as `expect.value` on the error outcome (for example `split.err.single-after-words`: `a b 'c d` gives
  `["a", "b"]`; `split.err.escape-ends-word`: `a b\` gives `["a"]`).
- Python: one exception class per category with the Go name, `str(exc)` equal to the message. Whether the
  exception also carries the partial words is a strategy decision (unattended: recorded, not decided). If it
  does, add a target test that compares the carried words with `expect.value` for every Split error fixture,
  because parity does not compare that field.
- Join never raises.

## Fixtures

- `fixtures/root/oracle.json`: 1054 cases, recorded with go1.26.0 from commit 95032a8.
  - Join, 265 cases: 11 harvested, 54 hand-written, 200 generated (`join-random` 150, `join-unicode` 50).
  - Split, 789 cases: 17 harvested (5 errors), 72 hand-written (18 errors), 500 generated
    (`split-random` 300 with 147 errors, `split-grammar` 200), 200 derived round-trip cases.
  - Tags worth filtering on: `error`, `partial-words`, `untested-upstream` (3 trailing-backslash-in-double-quote
    cases), `roundtrip`, `whitespace`, `unicode`, `rollback`, `tilde`, `large`.
- Normalization: none. Strings and messages compare exactly.
- Call shape: Join's `input.args` are the variadic arguments, one string each (`[]` means no arguments).
  Split's `input.args` is `[input]`.
- Not covered by fixtures, on purpose: invalid UTF-8 input (leak `invalid-utf8`; JSON fixture strings cannot
  carry it and the Python API is `str`-only by default).

## Reference tests mapped here

- `quote_test.go::TestSimpleJoin` -> PASS (all 11 entries harvested as `join.ref.00` to `join.ref.10`).
- `unquote_test.go::TestSimpleSplit` -> PASS (12 entries, `split.ref.00` to `split.ref.11`).
- `unquote_test.go::TestErrorSplit` -> PASS (5 entries, `split.ref.err.00` to `split.ref.err.04`); the port
  asserts the exception class where Go compares sentinel identity.
- `both_test.go::TestJoinSplit` -> PASS, ported as a seeded property test (stdlib `random` with a fixed seed,
  per deps.md) and pinned by the 200 `roundtrip.*` fixtures. Go's `testing/quick` draws arbitrary code points;
  the Python generator should include astral characters, quotes, backslashes, tab and newline.

## Risk tags and traps to read

- error-model: GENERIC T32 (match the category by class, never by message), T35 (messages are API here and
  must be copied verbatim, not taken from a Python built-in).
- nullability: no GENERIC trap fits; `split` returns `[]`, never `None`, and the partial-words question
  above.
- unicode: GENERIC T1 and T2 (Go slices by byte offset; Python must iterate code points, which gives the
  same result for valid UTF-8; fixtures include astral, combining and ZWJ characters), T20 (do not use
  `\s`, `str.split()` or `str.isspace()`: separators are exactly space, tab, newline), T44 (invalid UTF-8,
  see the leak list).
- ordering: false positive from the survey; arguments and words keep input order and nothing iterates a map.
