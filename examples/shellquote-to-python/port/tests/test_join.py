import pytest

from shellquote import join

SIMPLE_JOIN: list[tuple[list[str], str]] = [
    (["test"], "test"),
    (["hello goodbye"], "'hello goodbye'"),
    (["hello", "goodbye"], "hello goodbye"),
    (
        ["don't you know the dewey decimal system?"],
        "'don'\\''t you know the dewey decimal system?'",
    ),
    (
        ["don't", "you", "know", "the", "dewey", "decimal", "system?"],
        "don\\'t you know the dewey decimal system\\?",
    ),
    (["~user", "u~ser", " ~user", "!~user"], "\\~user u~ser ' ~user' \\!~user"),
    (
        ["foo*", "M{ovies,usic}", "ab[cd]", "%3"],
        "foo\\* M\\{ovies,usic} ab\\[cd] %3",
    ),
    (["one", "", "three"], "one '' three"),
    (["some(parentheses)"], "some\\(parentheses\\)"),
    (
        ["$some_ot~her_)spe!cial_*_characters"],
        "\\$some_ot~her_\\)spe\\!cial_\\*_characters",
    ),
    (["' "], "\\'' '"),
]


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        pytest.param(args, expected, id=f"[ref: quote_test.go::TestSimpleJoin::{i}]")
        for i, (args, expected) in enumerate(SIMPLE_JOIN)
    ],
)
def test_simple_join(args: list[str], expected: str) -> None:
    assert join(*args) == expected
