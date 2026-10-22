"""PL/EN language detection and translation direction (owner: M2).

Stdlib-only heuristic, no model call. Scoring (see ``docs/architecture.md``):

- each Polish diacritic letter (``POLISH_LETTERS``, either case) adds 3 to the Polish score;
- each lower-cased word token found in ``POLISH_STOPWORDS`` adds 1 to Polish, each found in
  ``ENGLISH_STOPWORDS`` adds 1 to English;
- ``"pl"`` wins only with a strictly higher score; ties (incl. 0:0 such as "OK" or a URL)
  give ``"en"``, so ambiguous text is translated *into* Polish, matching the proposal's
  "Polish in -> English out, otherwise -> Polish".
"""

from __future__ import annotations

import re
from typing import Literal

Language = Literal["pl", "en"]

POLISH_LETTERS = frozenset("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")

_POLISH_WORDS = (
    "a aby ale bo być był była było by czy dla do go i ich im jak jako jest jestem już "
    "ktoś która które który mam ma mi mnie może na nam nas nie nic niż o od oraz po pod "
    "przez przy się są ta tak takie też to tu tylko w we więc z za ze że żeby"
)
_ENGLISH_WORDS = (
    "a about all an and are as at be but by can do for from have he i if in is it its "
    "me my not of on or our so that the their there this to was we were what which will "
    "with would you your"
)

POLISH_STOPWORDS = frozenset(_POLISH_WORDS.split())
ENGLISH_STOPWORDS = frozenset(_ENGLISH_WORDS.split())


def detect_language(text: str) -> Language:
    """Return ``"pl"`` or ``"en"`` for ``text`` using the scoring described above."""
    polish_score = 3 * sum(1 for ch in text if ch in POLISH_LETTERS)
    tokens = re.findall(r"\w+", text.lower())
    for token in tokens:
        if token in POLISH_STOPWORDS:
            polish_score += 1
    english_score = sum(1 for token in tokens if token in ENGLISH_STOPWORDS)
    return "pl" if polish_score > english_score else "en"


def choose_direction(text: str, native: str, other: str) -> tuple[str, str]:
    """Return ``(source, target)`` language codes for translating ``text``.

    ``detect_language(text) == native`` -> ``(native, other)``; otherwise ``(other, native)``.
    """
    if detect_language(text) == native:
        return native, other
    return other, native


__all__ = [
    "ENGLISH_STOPWORDS",
    "POLISH_LETTERS",
    "POLISH_STOPWORDS",
    "Language",
    "choose_direction",
    "detect_language",
]
