"""Copy/paste keystrokes on macOS via ``osascript`` -> System Events (v2; owner: M9 stub, M10 body).

The permissions are granted to Hammerspoon (it is the process tree's responsible app), not to
``osascript``: the messages therefore name **Hammerspoon**.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

from llmtr.errors import MacKeySendError
from llmtr.macos_exec import OSASCRIPT, Runner, child_env

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
    parts = [part.strip().lower() for part in combo.split("+")]
    if not parts or any(not part for part in parts):
        raise ValueError(f"Malformed combo {combo!r}")
    *mods, key = parts
    modifiers: list[str] = []
    for mod in mods:
        if mod not in MODIFIER_NAMES:
            raise ValueError(f"Unknown modifier {mod!r} in combo {combo!r}")
        modifiers.append(MODIFIER_NAMES[mod])
    if key in MODIFIER_NAMES:
        raise ValueError(f"Combo {combo!r} has no key besides modifiers")
    if key not in KEY_CODES and not (len(key) == 1 and key.isascii() and key.isalnum()):
        raise ValueError(f"Unknown key {key!r} in combo {combo!r}")
    return MacCombo(key=key, modifiers=tuple(modifiers))


def build_applescript(combo: str) -> str:
    """``"cmd+c"`` -> ``tell application "System Events" to keystroke "c" using {command down}``
    (no ``using`` clause without modifiers; ``key code N`` for named keys). Raises ``ValueError``
    like ``parse_mac_combo``."""
    parsed = parse_mac_combo(combo)
    if parsed.key in KEY_CODES:
        action = f"key code {KEY_CODES[parsed.key]}"
    else:
        action = f'keystroke "{parsed.key}"'
    script = f'tell application "System Events" to {action}'
    if parsed.modifiers:
        script += f" using {{{', '.join(parsed.modifiers)}}}"
    return script


def classify_osascript_error(stderr: str) -> str:
    """``"accessibility"`` if ``stderr`` has ``(1002)`` / "not allowed to send keystrokes",
    ``"automation"`` if it has ``(-1743)`` / "Not authorized to send Apple events", else
    ``"failed"``. Pure."""
    lowered = stderr.lower()
    if f"({ACCESSIBILITY_ERROR})" in stderr or "not allowed to send keystrokes" in lowered:
        return "accessibility"
    if f"({AUTOMATION_ERROR})" in stderr or "not authorized to send apple events" in lowered:
        return "automation"
    return "failed"


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
        self._run = run

    def available(self) -> bool:
        try:
            return os.access(OSASCRIPT, os.X_OK)
        except Exception:  # pragma: no cover - defensive, must never raise
            return False

    def send(self, combo: str) -> None:
        script = build_applescript(combo)
        try:
            result = self._run(
                [OSASCRIPT, "-e", script],
                capture_output=True,
                env=child_env(),
                timeout=SEND_TIMEOUT,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise MacKeySendError("timeout", str(exc)) from exc
        except OSError as exc:
            raise MacKeySendError("failed", str(exc)) from exc
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            raise MacKeySendError(classify_osascript_error(stderr), stderr)


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
