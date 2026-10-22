"""Capture the selected text and put the result back (owner: M3).

Combines ``Clipboard`` and ``KeySender``; knows nothing about models. Time is injected
(``sleep``/``monotonic``) so tests run instantly with fakes.
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Callable
from dataclasses import dataclass

from llmtr.clipboard import Clipboard
from llmtr.config import KeysConfig
from llmtr.errors import EmptySelection, KeySendError
from llmtr.keys import KeyPair, KeySender

POLL_INTERVAL = 0.03
"""Seconds between clipboard polls while waiting for the copied text."""


@dataclass(frozen=True)
class Captured:
    """Result of ``capture_selection``."""

    text: str
    """The selected text (never empty: empty raises ``EmptySelection``)."""
    saved_clipboard: str
    """Clipboard text before llmtr touched it; restored afterwards (``""`` if it was empty)."""
    used_keystrokes: bool
    """False in clipboard-only fallback (no ydotool): ``text`` is the existing clipboard and the
    clipboard must not be restored."""


def capture_selection(
    clipboard: Clipboard,
    keys: KeySender,
    pair: KeyPair,
    timing: KeysConfig,
    *,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> Captured:
    """Get the selected text.

    With keystrokes (``keys.available()``):
      1. ``saved = clipboard.get_text()``; 2. ``clipboard.clear()``;
      3. ``sleep(timing.start_delay)``; 4. ``keys.send(pair.copy)``;
      5. poll ``clipboard.get_text()`` every ``POLL_INTERVAL`` until non-empty or
         ``timing.copy_timeout`` passes; 6. if still empty: raise
         ``EmptySelection(used_keystrokes=True)``.
    Fallback (``not keys.available()``): ``text = clipboard.get_text()``; empty ->
      ``EmptySelection(used_keystrokes=False)``; ``saved_clipboard=""``.

    Once ``clipboard.clear()`` has run, any exception raised before the text is captured
    (``KeySendError``, ``EmptySelection``, a ``Cancelled`` from the SIGTERM handler during
    ``sleep``, or anything else) restores ``saved`` (when non-empty) before propagating.

    Raises ``EmptySelection``, ``ClipboardUnavailable``, ``KeySendError``.
    """
    if not keys.available():
        text = clipboard.get_text()
        if not text:
            raise EmptySelection(used_keystrokes=False)
        return Captured(text=text, saved_clipboard="", used_keystrokes=False)

    saved = clipboard.get_text()
    clipboard.clear()
    try:
        sleep(timing.start_delay)
        keys.send(pair.copy)

        deadline = monotonic() + timing.copy_timeout
        text = clipboard.get_text()
        while not text and monotonic() < deadline:
            sleep(POLL_INTERVAL)
            text = clipboard.get_text()

        if not text:
            raise EmptySelection(used_keystrokes=True)
    except BaseException:
        if saved:
            clipboard.set_text(saved)
        raise

    return Captured(text=text, saved_clipboard=saved, used_keystrokes=True)


def deliver_result(
    result: str,
    captured: Captured,
    clipboard: Clipboard,
    keys: KeySender,
    pair: KeyPair,
    timing: KeysConfig,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    """Put ``result`` in place of the selection.

    With keystrokes: ``clipboard.set_text(result)``; ``keys.send(pair.paste)``;
    ``sleep(timing.paste_delay)``; ``restore_clipboard(...)``; return True.
    Fallback, or ``KeySendError`` on paste: leave ``result`` on the clipboard and return False
    (the caller shows "Result copied. Press Ctrl+V to paste.").
    """
    clipboard.set_text(result)
    if not captured.used_keystrokes:
        return False
    try:
        keys.send(pair.paste)
    except KeySendError:
        return False
    sleep(timing.paste_delay)
    restore_clipboard(captured, clipboard)
    return True


def restore_clipboard(captured: Captured, clipboard: Clipboard) -> None:
    """Put ``captured.saved_clipboard`` back (or ``clear()`` if it was ``""``); no-op when
    ``captured.used_keystrokes`` is False. Used after a paste and on error/cancel. Never raises
    (clipboard failures here are ignored)."""
    if not captured.used_keystrokes:
        return
    with contextlib.suppress(Exception):
        if captured.saved_clipboard:
            clipboard.set_text(captured.saved_clipboard)
        else:
            clipboard.clear()


__all__ = [
    "POLL_INTERVAL",
    "Captured",
    "capture_selection",
    "deliver_result",
    "restore_clipboard",
]
