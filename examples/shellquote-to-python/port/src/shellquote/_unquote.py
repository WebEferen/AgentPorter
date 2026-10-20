from collections.abc import Sequence

_SPLIT_CHARS = " \n\t"
_SINGLE_CHAR = "'"
_DOUBLE_CHAR = '"'
_ESCAPE_CHAR = "\\"
_DOUBLE_ESCAPE_CHARS = '$`"\n\\'


class ShellQuoteError(ValueError):
    """Base class of the errors raised by split.

    ``words`` holds the words completed before the error.
    """

    def __init__(self, message: str, words: Sequence[str] = ()) -> None:
        super().__init__(message)
        self.words = list(words)


class UnterminatedSingleQuoteError(ShellQuoteError):
    """A single-quoted string is not closed."""

    def __init__(self, words: Sequence[str] = ()) -> None:
        super().__init__("Unterminated single-quoted string", words)


class UnterminatedDoubleQuoteError(ShellQuoteError):
    """A double-quoted string is not closed."""

    def __init__(self, words: Sequence[str] = ()) -> None:
        super().__init__("Unterminated double-quoted string", words)


class UnterminatedEscapeError(ShellQuoteError):
    """The input ends with a backslash outside quotes."""

    def __init__(self, words: Sequence[str] = ()) -> None:
        super().__init__("Unterminated backslash-escape", words)


def split(s: str) -> list[str]:
    """Split a string according to /bin/sh's word-splitting rules.

    Supports backslash escapes, single quotes and double quotes. Does not support
    $'' quoting or any kind of expansion (brace, parameter or pathname).

    Raises UnterminatedSingleQuoteError, UnterminatedDoubleQuoteError or
    UnterminatedEscapeError when the input has an unterminated quoted string or
    ends in a backslash escape.
    """
    words: list[str] = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c in _SPLIT_CHARS:
            i += 1
            continue
        if c == _ESCAPE_CHAR:
            if i + 1 == n:
                raise UnterminatedEscapeError(words)
            if s[i + 1] == "\n":
                i += 2
                continue
        word, i = _split_word(s, i, words)
        words.append(word)
    return words


def _split_word(s: str, i: int, words: list[str]) -> tuple[str, int]:
    """Read the word starting at s[i]; return it and the index after its end."""
    buf: list[str] = []
    n = len(s)
    start = i
    while i < n:
        c = s[i]
        if c == _SINGLE_CHAR:
            buf.append(s[start:i])
            end = s.find(_SINGLE_CHAR, i + 1)
            if end == -1:
                raise UnterminatedSingleQuoteError(words)
            buf.append(s[i + 1 : end])
            i = start = end + 1
        elif c == _DOUBLE_CHAR:
            buf.append(s[start:i])
            i = start = _split_double(s, i + 1, buf, words)
        elif c == _ESCAPE_CHAR:
            buf.append(s[start:i])
            if i + 1 == n:
                raise UnterminatedEscapeError(words)
            if s[i + 1] != "\n":
                buf.append(s[i + 1])
            i = start = i + 2
        elif c in _SPLIT_CHARS:
            buf.append(s[start:i])
            return "".join(buf), i + 1
        else:
            i += 1
    buf.append(s[start:])
    return "".join(buf), n


def _split_double(s: str, i: int, buf: list[str], words: list[str]) -> int:
    """Append quoted text at s[i:] to buf; return the index past the closing quote."""
    n = len(s)
    start = i
    while i < n:
        c = s[i]
        if c == _DOUBLE_CHAR:
            buf.append(s[start:i])
            return i + 1
        if c == _ESCAPE_CHAR:
            # A trailing backslash consumes nothing and leaves the quote open.
            if i + 1 < n and s[i + 1] in _DOUBLE_ESCAPE_CHARS:
                buf.append(s[start:i])
                if s[i + 1] != "\n":
                    buf.append(s[i + 1])
                start = i + 2
            i += 2
        else:
            i += 1
    raise UnterminatedDoubleQuoteError(words)
