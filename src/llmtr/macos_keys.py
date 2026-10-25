"""Copy/paste keystrokes on macOS via ``osascript`` -> System Events (v2; owner: M9 stub, M10 body).

The permissions are granted to Hammerspoon (it is the process tree's responsible app), not to
``osascript``: the messages therefore name **Hammerspoon**.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from llmtr.macos_exec import Runner

MODIFIER_NAMES: dict[str, str] = {
    "cmd": "command down",
    "command": "command down",
    "super": "command down",
    "ctrl": "control down",
    "control": "control down",
    "alt": "option down",
    "opt": "option down",
    "option": "option down",
    "shift": "shift down",
}
"""Combo modifier name -> AppleScript modifier."""

KEY_CODES: dict[str, int] = {"enter": 36, "tab": 48, "space": 49}
"""Named keys sent with ``key code`` instead of ``keystroke`` (letters and digits use
``keystroke``)."""

ACCESSIBILITY_ERROR = "1002"
AUTOMATION_ERROR = "-1743"
"""osascript error numbers found in stderr: no Accessibility / Automation denied."""

SEND_TIMEOUT = 30.0
"""Seconds allowed for one ``osascript`` call. Long because the first call blocks (M8: 43 s)
while the Automation dialog is open; a timeout maps to ``MacKeySendError("timeout")``."""


@dataclass(frozen=True)
class MacCombo:
    """A parsed combo: ``key`` is a character (``keystroke``) or a ``KEY_CODES`` name
    (``key code``); ``modifiers`` are AppleScript modifiers in input order."""

    key: str
    modifiers: tuple[str, ...]


def parse_mac_combo(combo: str) -> MacCombo:
    """``"cmd+c"`` -> ``MacCombo("c", ("command down",))``. Case-insensitive, ``+``-separated,
    modifiers first, exactly one key last. Raises ``ValueError`` for unknown names or a combo
    without exactly one non-modifier."""
    raise NotImplementedError


def build_applescript(combo: str) -> str:
    """``"cmd+c"`` -> ``tell application "System Events" to keystroke "c" using {command down}``
    (no ``using`` clause without modifiers; ``key code N`` for named keys). Raises ``ValueError``
    like ``parse_mac_combo``."""
    raise NotImplementedError


def classify_osascript_error(stderr: str) -> str:
    """``"accessibility"`` if ``stderr`` has ``(1002)`` / "not allowed to send keystrokes",
    ``"automation"`` if it has ``(-1743)`` / "Not authorized to send Apple events", else
    ``"failed"``. Pure."""
    raise NotImplementedError


class OsascriptKeySender:
    """``KeySender`` running ``/usr/bin/osascript -e <build_applescript(combo)>``.

    - ``available()``: ``/usr/bin/osascript`` exists and is executable. Cheap, never raises. It
      does **not** probe the permissions (a probe would show the Automation dialog and cost
      0.2 s); a missing permission surfaces in ``send`` as ``MacKeySendError``.
    - ``send``: ``ValueError`` for a malformed combo (before running anything); non-zero exit
      -> ``MacKeySendError(classify_osascript_error(stderr), detail=stderr)``;
      ``TimeoutExpired`` -> ``MacKeySendError("timeout")``; ``OSError`` ->
      ``MacKeySendError("failed")``.
    """

    def __init__(self, *, run: Runner = subprocess.run) -> None:
        raise NotImplementedError

    def available(self) -> bool:
        raise NotImplementedError

    def send(self, combo: str) -> None:
        raise NotImplementedError


__all__ = [
    "ACCESSIBILITY_ERROR",
    "AUTOMATION_ERROR",
    "KEY_CODES",
    "MODIFIER_NAMES",
    "SEND_TIMEOUT",
    "MacCombo",
    "OsascriptKeySender",
    "build_applescript",
    "classify_osascript_error",
    "parse_mac_combo",
]
