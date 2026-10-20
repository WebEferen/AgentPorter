import random

import pytest

from shellquote import join, split

SEED = 95032
ROUNDS = 1000
_SURROGATES = 0x800
_ALPHABET = (
    " \t\n\r\x00'\"\\$`~*?!#[]{}()|&;<>=%^-_azAZ09\xe9\u20ac\u0301\u200d\U0001f600"
)


def _random_char(rng: random.Random) -> str:
    if rng.random() < 0.6:
        return rng.choice(_ALPHABET)
    code_point = rng.randrange(0x110000 - _SURROGATES)
    if code_point >= 0xD800:
        code_point += _SURROGATES
    return chr(code_point)


def _random_args(rng: random.Random) -> list[str]:
    return [
        "".join(_random_char(rng) for _ in range(rng.randrange(12)))
        for _ in range(rng.randrange(8))
    ]


@pytest.mark.parametrize("seed", [SEED], ids=["[ref: both_test.go::TestJoinSplit]"])
def test_join_split(seed: int) -> None:
    rng = random.Random(seed)
    for _ in range(ROUNDS):
        args = _random_args(rng)
        assert split(join(*args)) == args
