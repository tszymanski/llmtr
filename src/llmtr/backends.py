"""The one place that picks the desktop backends for the platform (v2; owner: M9 stub, M10 body).

Desktop side only (never imports the model side). ``cli.py`` calls ``make_notifier`` and
``make_desktop`` instead of building ``NotifySendNotifier`` / ``YdotoolKeySender`` itself.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from llmtr.clipboard import Clipboard, make_clipboard
from llmtr.config import KeysConfig
from llmtr.keys import KeySender, YdotoolKeySender, focused_app_id
from llmtr.macos_clipboard import PbClipboard
from llmtr.macos_keys import OsascriptKeySender
from llmtr.macos_notify import HammerspoonNotifier, OsascriptNotifier
from llmtr.macos_probes import focused_bundle_id, secure_input_app
from llmtr.notify import Notifier, NotifySendNotifier
from llmtr.platforms import Platform, detect_platform

LINUX_PASTE_HINT = "Result copied. Press Ctrl+V to paste."
MACOS_PASTE_HINT = "Result copied. Press ⌘V to paste."


@dataclass(frozen=True)
class Desktop:
    """Everything ``run_shortcut`` needs from the desktop for one platform."""

    platform: Platform
    make_clipboard: Callable[[], Clipboard]
    """Lazy: ``ClipboardUnavailable`` is raised inside ``run_shortcut``'s error handling."""
    keys: KeySender
    focused_app_id: Callable[[], str | None]
    """Linux: ``keys.focused_app_id``. macOS: ``focused_bundle_id`` only when
    ``[[keys.override]]`` is configured, else ``lambda: None`` (saves 0.25 s per run)."""
    paste_hint: str
    """Notification when the result stays on the clipboard (``LINUX_/MACOS_PASTE_HINT``)."""
    empty_selection_hint: Callable[[], str | None]
    """Called only after ``EmptySelection(used_keystrokes=True)``. macOS: ``secure_input_app``
    (the caller then reports ``SecureInputActive(app)``). Linux: ``lambda: None``."""


def make_notifier(
    platform: Platform | None = None,
    backend: str = "auto",
    env: Mapping[str, str] | None = None,
) -> Notifier:
    """Linux: ``NotifySendNotifier()``. macOS: ``HammerspoonNotifier(env)`` for ``"auto"`` and
    ``"hammerspoon"``, ``OsascriptNotifier()`` for ``"osascript"``. ``platform`` defaults to
    ``detect_platform()``. Safe before the config is loaded (``backend="auto"``)."""
    if (platform if platform is not None else detect_platform()) == "macos":
        if backend == "osascript":
            return OsascriptNotifier()
        return HammerspoonNotifier(env)
    return NotifySendNotifier()


def make_desktop(
    platform: Platform | None = None,
    env: Mapping[str, str] | None = None,
    *,
    keys_config: KeysConfig | None = None,
) -> Desktop:
    """Linux: ``make_clipboard(env)``, ``YdotoolKeySender(env)``, ``keys.focused_app_id``
    (exactly today's wiring). macOS: ``PbClipboard(env)``, ``OsascriptKeySender()``, the probes.
    ``keys_config`` (default ``KeysConfig()``) decides whether macOS queries the focused app."""
    if (platform if platform is not None else detect_platform()) == "macos":
        config = keys_config if keys_config is not None else KeysConfig()
        return Desktop(
            platform="macos",
            make_clipboard=lambda: PbClipboard(env),
            keys=OsascriptKeySender(),
            focused_app_id=focused_bundle_id if config.override else _no_app,
            paste_hint=MACOS_PASTE_HINT,
            empty_selection_hint=secure_input_app,
        )
    return Desktop(
        platform="linux",
        make_clipboard=lambda: make_clipboard(env),
        keys=YdotoolKeySender(env),
        focused_app_id=focused_app_id,
        paste_hint=LINUX_PASTE_HINT,
        empty_selection_hint=_no_app,
    )


def _no_app() -> str | None:
    return None


__all__ = [
    "LINUX_PASTE_HINT",
    "MACOS_PASTE_HINT",
    "Desktop",
    "make_desktop",
    "make_notifier",
]
