"""Unit tests for llmtr.prompts (owner: M2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from llmtr.config import TonePreset
from llmtr.prompts import (
    FIX_SYSTEM_PROMPT,
    TEXT_CLOSE,
    TEXT_OPEN,
    TONE_SYSTEM_PROMPT_TEMPLATE,
    TRANSLATEGEMMA_SEPARATOR,
    TRANSLATEGEMMA_TEMPLATE,
    build_fix_messages,
    build_tone_messages,
    build_translate_messages,
    strip_preamble,
)


def _template_from_proposal() -> str:
    text = (Path(__file__).parents[1] / "docs" / "proposal.md").read_text(encoding="utf-8")
    lines = [
        ln[2:] for ln in text.splitlines() if ln.startswith("> You are") or ln.startswith("> ")
    ]
    return " ".join(ln.strip() for ln in lines)


def test_translategemma_template_is_verbatim_from_proposal() -> None:
    assert _template_from_proposal() == TRANSLATEGEMMA_TEMPLATE


def test_build_translate_messages_pl_to_en() -> None:
    messages = build_translate_messages("Cześć", "pl", "en")
    expected_prompt = TRANSLATEGEMMA_TEMPLATE.format(
        SOURCE_LANG="Polish", SOURCE_CODE="pl", TARGET_LANG="English", TARGET_CODE="en"
    )
    assert messages == [
        {"role": "user", "content": expected_prompt + TRANSLATEGEMMA_SEPARATOR + "Cześć"}
    ]


def test_build_translate_messages_en_to_pl() -> None:
    messages = build_translate_messages("Hello", "en", "pl")
    expected_prompt = TRANSLATEGEMMA_TEMPLATE.format(
        SOURCE_LANG="English", SOURCE_CODE="en", TARGET_LANG="Polish", TARGET_CODE="pl"
    )
    assert messages == [
        {"role": "user", "content": expected_prompt + TRANSLATEGEMMA_SEPARATOR + "Hello"}
    ]


def test_build_translate_messages_keeps_text_unchanged() -> None:
    text = "  leading and trailing space  \n"
    messages = build_translate_messages(text, "pl", "en")
    assert messages[0]["content"].endswith(text)


def test_build_fix_messages() -> None:
    messages = build_fix_messages("some text")
    assert messages == [
        {"role": "system", "content": FIX_SYSTEM_PROMPT},
        {"role": "user", "content": f"{TEXT_OPEN}\nsome text\n{TEXT_CLOSE}"},
    ]


def test_build_tone_messages() -> None:
    preset = TonePreset(name="team", instruction="Casual and friendly.")
    messages = build_tone_messages("some text", preset)
    assert messages == [
        {
            "role": "system",
            "content": TONE_SYSTEM_PROMPT_TEMPLATE.format(instruction=preset.instruction),
        },
        {"role": "user", "content": f"{TEXT_OPEN}\nsome text\n{TEXT_CLOSE}"},
    ]


@pytest.mark.parametrize(
    ("output", "original", "expected"),
    [
        ("Hello there.", "Hi", "Hello there."),
        ("Sure, here you go:\nHello there.", "Hi", "Hello there."),
        ("Here is the translation:\nHello there.", "Hi", "Hello there."),
        ("Oto tłumaczenie:\nCześć.", "Hi", "Cześć."),
        ("Corrected: \nFixed text.", "Hi", "Fixed text."),
        (f"{TEXT_OPEN}\nHello there.\n{TEXT_CLOSE}", "Hi", "Hello there."),
        ("```\nHello there.\n```", "Hi", "Hello there."),
        ("```text\nHello there.\n```", "Hi", "Hello there."),
        ('"Hello there."', "Hi", "Hello there."),
        ("'Hello there.'", "Hi", "Hello there."),
        ("„Hello there.”", "Hi", "Hello there."),
        ("  \n  Hello there.  \n", "Hi", "Hello there."),
    ],
)
def test_strip_preamble_cleans_output(output: str, original: str, expected: str) -> None:
    assert strip_preamble(output, original) == expected


def test_strip_preamble_keeps_quotes_if_original_had_them() -> None:
    original = '"Hi there"'
    output = '"Hello there."'
    assert strip_preamble(output, original) == '"Hello there."'


def test_strip_preamble_restores_original_whitespace() -> None:
    original = "Hi there\n"
    output = "Hello there."
    assert strip_preamble(output, original) == "Hello there.\n"


def test_strip_preamble_empty_output_returns_empty_string() -> None:
    assert strip_preamble("   \n  ", "Hi") == ""


def test_strip_preamble_removes_only_one_preamble_line() -> None:
    output = "Sure, here you go:\nHere is the thing:\nActual content."
    assert strip_preamble(output, "x") == "Here is the thing:\nActual content."
