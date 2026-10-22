"""Keystrokes llmtr sends (copy/paste) via ydotool, and per-app key choice (owner: M3).

A key combo is a string like ``"ctrl+c"`` or ``"ctrl+shift+v"``: ``+``-separated, case
insensitive, modifiers first, exactly one non-modifier key last.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from llmtr.config import KeysConfig
from llmtr.errors import KeySendError

MODIFIER_KEYCODES: dict[str, int] = {
    "ctrl": 29,  # KEY_LEFTCTRL
    "shift": 42,  # KEY_LEFTSHIFT
    "alt": 56,  # KEY_LEFTALT
    "super": 125,  # KEY_LEFTMETA
}
"""Linux input-event codes (``linux/input-event-codes.h``) used by ``ydotool key``."""

KEY_CODES: dict[str, int] = {
    # QWERTY key codes from linux/input-event-codes.h; not alphabetically contiguous.
    "q": 16,
    "w": 17,
    "e": 18,
    "r": 19,
    "t": 20,
    "y": 21,
    "u": 22,
    "i": 23,
    "o": 24,
    "p": 25,
    "a": 30,
    "s": 31,
    "d": 32,
    "f": 33,
    "g": 34,
    "h": 35,
    "j": 36,
    "k": 37,
    "l": 38,
    "z": 44,
    "x": 45,
    "c": 46,
    "v": 47,
    "b": 48,
    "n": 49,
    "m": 50,
    "1": 2,
    "2": 3,
    "3": 4,
    "4": 5,
    "5": 6,
    "6": 7,
    "7": 8,
    "8": 9,
    "9": 10,
    "0": 11,
    "insert": 110,
    "enter": 28,
    "tab": 15,
    "space": 57,
    "f1": 59,
    "f2": 60,
    "f3": 61,
    "f4": 62,
    "f5": 63,
    "f6": 64,
    "f7": 65,
    "f8": 66,
    "f9": 67,
    "f10": 68,
    "f11": 87,
    "f12": 88,
}
"""Non-modifier key names -> Linux input-event codes (``linux/input-event-codes.h``)."""

GDBUS_TIMEOUT = 0.5
"""Seconds allowed for the Window Calls D-Bus call before giving up."""

SOCKET_PROBE_TIMEOUT = 0.2
"""Seconds allowed for the ydotoold socket probe in ``YdotoolKeySender.available``."""

RELEASE_SUPER_ALT: tuple[str, ...] = (
    f"{MODIFIER_KEYCODES['super']}:0",
    f"{MODIFIER_KEYCODES['alt']}:0",
)
"""Explicit key-up events sent before every combo (architecture section 10): GNOME may still
consider the shortcut's own Super+Alt held right after it fires, which would turn the copy/paste
combo into an unintended Super/Alt-modified one. Releasing a key that is not actually down is a
no-op for ydotool/the kernel, so this is safe to send unconditionally."""


@dataclass(frozen=True)
class KeyPair:
    """The copy and paste combos to send for the focused app."""

    copy: str
    paste: str


@runtime_checkable
class KeySender(Protocol):
    """Sends key combos to the focused window."""

    def available(self) -> bool:
        """True if keystrokes can be sent right now (tool installed and daemon reachable).
        Must be cheap and never raise."""
        ...

    def send(self, combo: str) -> None:
        """Press and release ``combo``. Raises ``KeySendError`` on failure, ``ValueError`` for a
        malformed combo."""
        ...


def parse_combo(combo: str) -> list[int]:
    """``"ctrl+shift+c"`` -> ``[29, 42, 46]`` (modifier codes, then the key code).

    Letters, digits, ``insert``, ``enter``, ``tab``, ``space`` and ``f1``-``f12`` are enough
    for v1. Raises ``ValueError`` for unknown names or a combo without exactly one non-modifier.
    """
    parts = combo.lower().split("+")
    if len(parts) < 1 or any(not p for p in parts):
        raise ValueError(f"Malformed key combo: {combo!r}")
    *modifiers, key = parts
    codes = []
    for mod in modifiers:
        if mod not in MODIFIER_KEYCODES:
            raise ValueError(f"Unknown modifier {mod!r} in combo {combo!r}")
        codes.append(MODIFIER_KEYCODES[mod])
    if key not in KEY_CODES:
        raise ValueError(f"Unknown key {key!r} in combo {combo!r}")
    codes.append(KEY_CODES[key])
    return codes


class YdotoolKeySender:
    """``ydotool key <code>:1 ... <code>:0`` (presses in order, releases in reverse)."""

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        """``env`` (default ``os.environ``) is used to locate ``YDOTOOL_SOCKET``."""
        self._env = env if env is not None else os.environ
        path = self._env.get("YDOTOOL_SOCKET")
        if not path:
            runtime_dir = self._env.get("XDG_RUNTIME_DIR")
            path = f"{runtime_dir}/.ydotool_socket" if runtime_dir else "/tmp/.ydotool_socket"
        self._socket_path = Path(path)

    def available(self) -> bool:
        """``ydotool`` on PATH and ydotoold accepts a connection on its socket
        (``$YDOTOOL_SOCKET``, else ``$XDG_RUNTIME_DIR/.ydotool_socket``, else
        ``/tmp/.ydotool_socket``).

        Checking that the socket file exists is not enough: ydotoold does not remove its socket
        when it stops or is killed, so a stale file would make ``send`` fail with "Connection
        refused" instead of using the clipboard-only fallback. ydotoold listens on a datagram
        socket, so the probe is an ``AF_UNIX``/``SOCK_DGRAM`` ``connect()`` (a stale file gives
        ``ConnectionRefusedError``). Any ``OSError`` means unavailable.
        """
        try:
            if shutil.which("ydotool") is None:
                return False
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as probe:
                probe.settimeout(SOCKET_PROBE_TIMEOUT)
                probe.connect(str(self._socket_path))
            return True
        except OSError:
            return False

    def send(self, combo: str) -> None:
        codes = parse_combo(combo)
        press = [f"{code}:1" for code in codes]
        release = [f"{code}:0" for code in reversed(codes)]
        argv = ["ydotool", "key", *RELEASE_SUPER_ALT, *press, *release]
        run_env = dict(self._env)
        run_env["YDOTOOL_SOCKET"] = str(self._socket_path)
        try:
            result = subprocess.run(
                argv,
                env=run_env,
                capture_output=True,
                timeout=2.0,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise KeySendError(str(exc)) from exc
        if result.returncode != 0:
            raise KeySendError(result.stderr.decode(errors="replace").strip())


def focused_app_id() -> str | None:
    """App id / WM class of the focused window, or ``None`` if it cannot be found.

    GNOME Wayland exposes this only through a Shell extension; M3 implements the "Window Calls"
    extension D-Bus call (``gdbus call --session --dest org.gnome.Shell --object-path
    /org/gnome/Shell/Extensions/Windows --method org.gnome.Shell.Extensions.Windows.List``,
    pick the entry with ``focus: true``, return its ``wm_class``) with a short timeout.
    Must never raise and must return within ~0.5 s.
    """
    try:
        result = subprocess.run(
            [
                "gdbus",
                "call",
                "--session",
                "--dest",
                "org.gnome.Shell",
                "--object-path",
                "/org/gnome/Shell/Extensions/Windows",
                "--method",
                "org.gnome.Shell.Extensions.Windows.List",
            ],
            capture_output=True,
            text=True,
            timeout=GDBUS_TIMEOUT,
            check=False,
        )
        if result.returncode != 0:
            return None
        output = result.stdout
        start, end = output.find("["), output.rfind("]")
        if start == -1 or end == -1 or end < start:
            return None
        windows = json.loads(output[start : end + 1])
        for window in windows:
            if window.get("focus"):
                wm_class = window.get("wm_class")
                return str(wm_class) if wm_class else None
        return None
    except Exception:
        return None


def resolve_key_pair(keys: KeysConfig, app_id: str | None) -> KeyPair:
    """The first ``keys.override`` whose ``app`` contains ``app_id`` (case-insensitive), else
    the default ``(keys.copy, keys.paste)``. ``app_id=None`` -> default. Pure."""
    if app_id is not None:
        lowered = app_id.lower()
        for override in keys.override:
            if lowered in (app.lower() for app in override.app):
                return KeyPair(override.copy, override.paste)
    return KeyPair(keys.copy, keys.paste)


__all__ = [
    "MODIFIER_KEYCODES",
    "KEY_CODES",
    "KeyPair",
    "KeySender",
    "YdotoolKeySender",
    "focused_app_id",
    "parse_combo",
    "resolve_key_pair",
]
