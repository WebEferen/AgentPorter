from typing import Any

import pytest
from oracle_fixtures import SPLIT_CALL, case_id, load_cases

from shellquote import (
    ShellQuoteError,
    UnterminatedDoubleQuoteError,
    UnterminatedEscapeError,
    UnterminatedSingleQuoteError,
    split,
)

SIMPLE_SPLIT: list[tuple[str, list[str]]] = [
    ("hello", ["hello"]),
    ("hello goodbye", ["hello", "goodbye"]),
    ("hello   goodbye", ["hello", "goodbye"]),
    ("glob* test?", ["glob*", "test?"]),
    (
        "don\\'t you know the dewey decimal system\\?",
        ["don't", "you", "know", "the", "dewey", "decimal", "system?"],
    ),
    (
        "'don'\\''t you know the dewey decimal system?'",
        ["don't you know the dewey decimal system?"],
    ),
    ("one '' two", ["one", "", "two"]),
    (
        "text with\\\na backslash-escaped newline",
        ["text", "witha", "backslash-escaped", "newline"],
    ),
    ('text "with\na" quoted newline', ["text", "with\na", "quoted", "newline"]),
    (
        '"quoted\\d\\\\\\" text with\\\na backslash-escaped newline"',
        ['quoted\\d\\" text witha backslash-escaped newline'],
    ),
    (
        "text with an escaped \\\n newline in the middle",
        ["text", "with", "an", "escaped", "newline", "in", "the", "middle"],
    ),
    ('foo"bar"baz', ["foobarbaz"]),
]

ERROR_SPLIT: list[tuple[str, type[ShellQuoteError]]] = [
    ("don't worry", UnterminatedSingleQuoteError),
    ("'test'\\''ing", UnterminatedSingleQuoteError),
    ("\"foo'bar", UnterminatedDoubleQuoteError),
    ("foo\\", UnterminatedEscapeError),
    ("   \\", UnterminatedEscapeError),
]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param(text, expected, id=f"[ref: unquote_test.go::TestSimpleSplit::{i}]")
        for i, (text, expected) in enumerate(SIMPLE_SPLIT)
    ],
)
def test_simple_split(text: str, expected: list[str]) -> None:
    assert split(text) == expected


@pytest.mark.parametrize(
    ("text", "error"),
    [
        pytest.param(text, error, id=f"[ref: unquote_test.go::TestErrorSplit::{i}]")
        for i, (text, error) in enumerate(ERROR_SPLIT)
    ],
)
def test_error_split(text: str, error: type[ShellQuoteError]) -> None:
    with pytest.raises(ShellQuoteError) as excinfo:
        split(text)
    assert excinfo.type is error


def test_split_errors_are_value_errors() -> None:
    with pytest.raises(ValueError, match=r"^Unterminated single-quoted string$"):
        split("'")


@pytest.mark.parametrize(
    "case",
    [
        c
        for c in load_cases()
        if c["call"] == SPLIT_CALL and c["expect"]["kind"] == "error"
    ],
    ids=case_id,
)
def test_error_carries_completed_words(case: dict[str, Any]) -> None:
    with pytest.raises(ShellQuoteError) as excinfo:
        split(case["input"]["args"][0])
    assert excinfo.value.words == case["expect"]["value"]
