"""Tests for llmtr.selection: capture/deliver/restore with FakeClipboard, FakeKeySender and
FakeClock, so all timing is instant and no real desktop tool is touched."""

from __future__ import annotations

import pytest

from llmtr.config import KeysConfig
from llmtr.errors import Cancelled, EmptySelection, KeySendError
from llmtr.fakes import FakeClipboard, FakeClock, FakeKeySender
from llmtr.keys import KeyPair
from llmtr.selection import Captured, capture_selection, deliver_result, restore_clipboard

PAIR = KeyPair("ctrl+c", "ctrl+v")


def test_capture_selection_with_keystrokes_copies_and_saves_old_clipboard():
    clip = FakeClipboard("old")
    keys = FakeKeySender(on_send=lambda c: clip.set_text("selected") if c == "ctrl+c" else None)
    clock = FakeClock()
    captured = capture_selection(
        clip, keys, PAIR, KeysConfig(), sleep=clock.sleep, monotonic=clock.monotonic
    )
    assert captured == Captured(text="selected", saved_clipboard="old", used_keystrokes=True)
    assert keys.sent == ["ctrl+c"]
    assert clock.sleeps[0] == KeysConfig().start_delay


def test_capture_selection_empty_after_timeout_restores_and_raises():
    clip = FakeClipboard("old")
    keys = FakeKeySender()  # on_send does nothing: clipboard stays cleared
    clock = FakeClock()
    with pytest.raises(EmptySelection) as exc_info:
        capture_selection(
            clip, keys, PAIR, KeysConfig(), sleep=clock.sleep, monotonic=clock.monotonic
        )
    assert exc_info.value.used_keystrokes is True
    assert clip.get_text() == "old"


def test_capture_selection_empty_with_nothing_saved_does_not_restore():
    clip = FakeClipboard("")
    keys = FakeKeySender()
    clock = FakeClock()
    with pytest.raises(EmptySelection):
        capture_selection(
            clip, keys, PAIR, KeysConfig(), sleep=clock.sleep, monotonic=clock.monotonic
        )
    assert clip.history == [""]  # only the initial clear(); no spurious set_text("")


def test_capture_selection_key_send_error_restores_and_propagates():
    clip = FakeClipboard("old")
    keys = FakeKeySender(fail=KeySendError("boom"))
    clock = FakeClock()
    with pytest.raises(KeySendError):
        capture_selection(
            clip, keys, PAIR, KeysConfig(), sleep=clock.sleep, monotonic=clock.monotonic
        )
    assert clip.get_text() == "old"


def test_capture_selection_cancelled_during_start_delay_restores_and_propagates():
    clip = FakeClipboard("old")
    keys = FakeKeySender()

    def sleep(_seconds: float) -> None:
        raise Cancelled()

    with pytest.raises(Cancelled):
        capture_selection(clip, keys, PAIR, KeysConfig(), sleep=sleep, monotonic=lambda: 0.0)
    assert clip.get_text() == "old"
    assert keys.sent == []  # Cancelled during start_delay, before keys.send


def test_capture_selection_cancelled_during_poll_restores_and_propagates():
    clip = FakeClipboard("old")
    keys = FakeKeySender()  # on_send does nothing: clipboard stays cleared
    calls = {"n": 0}

    def sleep(_seconds: float) -> None:
        calls["n"] += 1
        if calls["n"] > 1:  # first call is start_delay; second is inside the poll loop
            raise Cancelled()

    with pytest.raises(Cancelled):
        capture_selection(clip, keys, PAIR, KeysConfig(), sleep=sleep, monotonic=lambda: 0.0)
    assert clip.get_text() == "old"
    assert keys.sent == ["ctrl+c"]


def test_capture_selection_unexpected_error_restores_and_propagates():
    clip = FakeClipboard("old")
    keys = FakeKeySender(fail=RuntimeError("boom"))
    clock = FakeClock()
    with pytest.raises(RuntimeError):
        capture_selection(
            clip, keys, PAIR, KeysConfig(), sleep=clock.sleep, monotonic=clock.monotonic
        )
    assert clip.get_text() == "old"


def test_capture_selection_cancelled_with_nothing_saved_does_not_restore():
    clip = FakeClipboard("")
    keys = FakeKeySender()

    def sleep(_seconds: float) -> None:
        raise Cancelled()

    with pytest.raises(Cancelled):
        capture_selection(clip, keys, PAIR, KeysConfig(), sleep=sleep, monotonic=lambda: 0.0)
    assert clip.history == [""]  # only the initial clear(); no spurious restore


def test_capture_selection_fallback_uses_existing_clipboard():
    clip = FakeClipboard("already copied")
    keys = FakeKeySender(is_available=False)
    captured = capture_selection(clip, keys, PAIR, KeysConfig())
    assert captured == Captured(text="already copied", saved_clipboard="", used_keystrokes=False)
    assert keys.sent == []


def test_capture_selection_fallback_empty_clipboard_raises():
    clip = FakeClipboard("")
    keys = FakeKeySender(is_available=False)
    with pytest.raises(EmptySelection) as exc_info:
        capture_selection(clip, keys, PAIR, KeysConfig())
    assert exc_info.value.used_keystrokes is False


def test_deliver_result_with_keystrokes_pastes_and_restores_old_clipboard():
    clip = FakeClipboard("selected")
    keys = FakeKeySender()
    clock = FakeClock()
    captured = Captured(text="selected", saved_clipboard="old", used_keystrokes=True)
    pasted = deliver_result("result", captured, clip, keys, PAIR, KeysConfig(), sleep=clock.sleep)
    assert pasted is True
    assert keys.sent == ["ctrl+v"]
    assert clip.get_text() == "old"


def test_deliver_result_fallback_leaves_result_on_clipboard():
    clip = FakeClipboard("")
    keys = FakeKeySender(is_available=False)
    captured = Captured(text="clip text", saved_clipboard="", used_keystrokes=False)
    pasted = deliver_result("result", captured, clip, keys, PAIR, KeysConfig())
    assert pasted is False
    assert clip.get_text() == "result"
    assert keys.sent == []


def test_deliver_result_key_send_error_leaves_result_on_clipboard():
    clip = FakeClipboard("selected")
    keys = FakeKeySender(fail=KeySendError("boom"))
    captured = Captured(text="selected", saved_clipboard="old", used_keystrokes=True)
    pasted = deliver_result("result", captured, clip, keys, PAIR, KeysConfig())
    assert pasted is False
    assert clip.get_text() == "result"


def test_restore_clipboard_restores_saved_text():
    clip = FakeClipboard("current")
    captured = Captured(text="x", saved_clipboard="old", used_keystrokes=True)
    restore_clipboard(captured, clip)
    assert clip.get_text() == "old"


def test_restore_clipboard_clears_when_saved_was_empty():
    clip = FakeClipboard("current")
    captured = Captured(text="x", saved_clipboard="", used_keystrokes=True)
    restore_clipboard(captured, clip)
    assert clip.get_text() == ""


def test_restore_clipboard_is_noop_in_fallback_mode():
    clip = FakeClipboard("current")
    captured = Captured(text="x", saved_clipboard="old", used_keystrokes=False)
    restore_clipboard(captured, clip)
    assert clip.get_text() == "current"


def test_restore_clipboard_never_raises():
    class BrokenClipboard(FakeClipboard):
        def set_text(self, text: str) -> None:
            raise RuntimeError("clipboard broke")

    captured = Captured(text="x", saved_clipboard="old", used_keystrokes=True)
    restore_clipboard(captured, BrokenClipboard("current"))  # must not raise
