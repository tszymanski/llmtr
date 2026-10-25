"""Tests for llmtr.backends: platform -> backends mapping (nothing is run)."""

from __future__ import annotations

import pytest

from llmtr import backends
from llmtr.clipboard import WlClipboard
from llmtr.config import KeyOverride, KeysConfig
from llmtr.keys import YdotoolKeySender
from llmtr.keys import focused_app_id as linux_focused_app_id
from llmtr.macos_clipboard import PbClipboard
from llmtr.macos_keys import OsascriptKeySender
from llmtr.macos_notify import HammerspoonNotifier, OsascriptNotifier
from llmtr.macos_probes import focused_bundle_id, secure_input_app
from llmtr.notify import NotifySendNotifier


def test_make_notifier_linux_ignores_backend() -> None:
    for backend in ("auto", "hammerspoon", "osascript"):
        assert isinstance(backends.make_notifier("linux", backend), NotifySendNotifier)


@pytest.mark.parametrize("backend", ["auto", "hammerspoon"])
def test_make_notifier_macos_hammerspoon(backend) -> None:
    assert isinstance(backends.make_notifier("macos", backend, {}), HammerspoonNotifier)


def test_make_notifier_macos_osascript() -> None:
    assert isinstance(backends.make_notifier("macos", "osascript"), OsascriptNotifier)


def test_make_notifier_default_platform_is_detected() -> None:
    from llmtr.platforms import detect_platform

    expected = HammerspoonNotifier if detect_platform() == "macos" else NotifySendNotifier
    assert isinstance(backends.make_notifier(), expected)


def test_make_notifier_hammerspoon_uses_env_run_id() -> None:
    notifier = backends.make_notifier("macos", "auto", {"LLMTR_RUN_ID": "77"})
    assert notifier._run_id == "77"  # type: ignore[attr-defined]


def test_make_desktop_macos() -> None:
    desktop = backends.make_desktop("macos", {})
    assert desktop.platform == "macos"
    assert isinstance(desktop.keys, OsascriptKeySender)
    assert isinstance(desktop.make_clipboard(), PbClipboard)
    assert desktop.paste_hint == backends.MACOS_PASTE_HINT == "Result copied. Press ⌘V to paste."
    assert desktop.empty_selection_hint is secure_input_app


def test_make_desktop_macos_skips_focused_app_query_without_overrides() -> None:
    desktop = backends.make_desktop("macos", {}, keys_config=KeysConfig())
    assert desktop.focused_app_id() is None
    assert desktop.focused_app_id is not focused_bundle_id


def test_make_desktop_macos_queries_focused_app_with_overrides() -> None:
    keys = KeysConfig(override=(KeyOverride(app=("com.apple.Terminal",), copy="c", paste="v"),))
    desktop = backends.make_desktop("macos", {}, keys_config=keys)
    assert desktop.focused_app_id is focused_bundle_id


def test_make_desktop_linux_is_todays_wiring() -> None:
    desktop = backends.make_desktop("linux", {"WAYLAND_DISPLAY": "wayland-0"})
    assert desktop.platform == "linux"
    assert isinstance(desktop.keys, YdotoolKeySender)
    assert desktop.focused_app_id is linux_focused_app_id
    assert (
        desktop.paste_hint == backends.LINUX_PASTE_HINT == "Result copied. Press Ctrl+V to paste."
    )
    assert desktop.empty_selection_hint() is None


def test_make_desktop_linux_clipboard_is_lazy_and_uses_env(monkeypatch) -> None:
    monkeypatch.setattr("llmtr.clipboard.shutil.which", lambda name: f"/usr/bin/{name}")
    desktop = backends.make_desktop("linux", {"WAYLAND_DISPLAY": "wayland-0"})
    assert isinstance(desktop.make_clipboard(), WlClipboard)


def test_make_desktop_linux_clipboard_error_is_raised_lazily(monkeypatch) -> None:
    from llmtr.errors import ClipboardUnavailable

    monkeypatch.setattr("llmtr.clipboard.shutil.which", lambda name: None)
    desktop = backends.make_desktop("linux", {})  # must not raise here
    with pytest.raises(ClipboardUnavailable):
        desktop.make_clipboard()
