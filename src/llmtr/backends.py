"""The one place that picks the desktop backends for the platform (v2; owner: M9 stub, M10 body).

Desktop side only (never imports the model side). ``cli.py`` calls ``make_notifier`` and
``make_desktop`` instead of building ``NotifySendNotifier`` / ``YdotoolKeySender`` itself.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from llmtr.clipboard import Clipboard
from llmtr.config import KeysConfig
from llmtr.keys import KeySender
from llmtr.notify import Notifier
from llmtr.platforms import Platform

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
    raise NotImplementedError


def make_desktop(
    platform: Platform | None = None,
    env: Mapping[str, str] | None = None,
    *,
    keys_config: KeysConfig | None = None,
) -> Desktop:
    """Linux: ``make_clipboard(env)``, ``YdotoolKeySender(env)``, ``keys.focused_app_id``
    (exactly today's wiring). macOS: ``PbClipboard(env)``, ``OsascriptKeySender()``, the probes.
    ``keys_config`` (default ``KeysConfig()``) decides whether macOS queries the focused app."""
    raise NotImplementedError


__all__ = [
    "LINUX_PASTE_HINT",
    "MACOS_PASTE_HINT",
    "Desktop",
    "make_desktop",
    "make_notifier",
]
