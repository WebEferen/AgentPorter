_SPECIAL_CHARS = "\\'\"`${[|&;<>()*?!"
_EXTRA_SPECIAL_CHARS = " \t\n"
_PREFIX_CHARS = "~"


def join(*args: str) -> str:
    """Quote each argument and join them with a space.

    Passed to /bin/sh, the result splits back into the original arguments.
    """
    return " ".join(_quote(arg) for arg in args)


def _quote(word: str) -> str:
    if not word:
        return "''"
    if any(c in _EXTRA_SPECIAL_CHARS for c in word):
        return "\\'".join(f"'{part}'" if part else "" for part in word.split("'"))
    return "".join(
        "\\" + c if c in _SPECIAL_CHARS or (i == 0 and c in _PREFIX_CHARS) else c
        for i, c in enumerate(word)
    )
