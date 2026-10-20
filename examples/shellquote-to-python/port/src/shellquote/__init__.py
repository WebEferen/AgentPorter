"""Join and split strings using sh's word-splitting rules."""

from shellquote._quote import join
from shellquote._unquote import (
    ShellQuoteError,
    UnterminatedDoubleQuoteError,
    UnterminatedEscapeError,
    UnterminatedSingleQuoteError,
    split,
)

__all__ = [
    "ShellQuoteError",
    "UnterminatedDoubleQuoteError",
    "UnterminatedEscapeError",
    "UnterminatedSingleQuoteError",
    "join",
    "split",
]
