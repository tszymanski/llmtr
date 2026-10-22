"""Unit tests for llmtr.langdetect (owner: M2)."""

from __future__ import annotations

import pytest

from llmtr.langdetect import choose_direction, detect_language


@pytest.mark.parametrize(
    "text",
    [
        "Cześć, jak się masz? Czy możesz mi pomóc?",
        "Dziękuję bardzo za pomoc, to jest świetne.",
    ],
)
def test_detects_polish_with_diacritics(text: str) -> None:
    assert detect_language(text) == "pl"


@pytest.mark.parametrize(
    "text",
    [
        "Nie wiem co robic, ale to nie jest dla mnie problem.",
        "Czy to jest ok, bo nie mam czasu na to teraz.",
    ],
)
def test_detects_polish_without_diacritics(text: str) -> None:
    assert detect_language(text) == "pl"


@pytest.mark.parametrize(
    "text",
    [
        "Hello, how are you today? I hope you are doing well.",
        "This is a test of the English language detector.",
    ],
)
def test_detects_english(text: str) -> None:
    assert detect_language(text) == "en"


@pytest.mark.parametrize("text", ["OK", "https://example.com/path", "Tomasz"])
def test_ties_resolve_to_english(text: str) -> None:
    assert detect_language(text) == "en"


def test_choose_direction_from_native_to_other() -> None:
    assert choose_direction("Dziękuję bardzo za wszystko.", "pl", "en") == ("pl", "en")


def test_choose_direction_from_other_to_native() -> None:
    assert choose_direction("Thank you very much for everything.", "pl", "en") == ("en", "pl")


def test_choose_direction_ambiguous_goes_to_native() -> None:
    assert choose_direction("OK", "pl", "en") == ("en", "pl")
