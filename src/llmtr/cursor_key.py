"""Cursor API key lookup (v3, architecture section 23).

Order: the ``CURSOR_API_KEY`` env var, then (macOS only) the Keychain item ``llmtr-cursor``, then
the file ``$XDG_CONFIG_HOME/llmtr/cursor-api-key``, which must have mode ``0600`` (no group or
other bits). The key is never logged, never put in argv and never put in an exception.
"""

from __future__ import annotations

import os
import stat
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path

from llmtr.errors import CursorKeyInsecure, CursorKeyMissing
from llmtr.platforms import Platform

CURSOR_KEY_ENV = "CURSOR_API_KEY"
KEYCHAIN_SERVICE = "llmtr-cursor"
KEYCHAIN_TIMEOUT = 5.0
"""Seconds for ``security find-generic-password``."""

KEYCHAIN_ARGV = ("security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w")


def key_path(env: Mapping[str, str] | None = None) -> Path:
    """``$XDG_CONFIG_HOME/llmtr/cursor-api-key``; ``env`` defaults to ``os.environ``."""
    env = env if env is not None else os.environ
    base = env.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "llmtr" / "cursor-api-key"


def _from_keychain(run: Callable[..., subprocess.CompletedProcess[str]]) -> str:
    """The Keychain password, or ``""`` when it is not there or ``security`` fails."""
    try:
        result = run(
            list(KEYCHAIN_ARGV),
            capture_output=True,
            text=True,
            timeout=KEYCHAIN_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


def load_key(
    platform: Platform,
    env: Mapping[str, str] | None = None,
    *,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str:
    """Return the Cursor API key (see the module docstring for the order).

    Raises:
        CursorKeyInsecure: the key file has group/other permission bits (it is not read).
        CursorKeyMissing: no source has a non-empty key.
    """
    env = env if env is not None else os.environ
    from_env = env.get(CURSOR_KEY_ENV, "").strip()
    if from_env:
        return from_env

    macos = platform == "macos"
    if macos:
        from_keychain = _from_keychain(run)
        if from_keychain:
            return from_keychain

    path = key_path(env)
    try:
        mode = path.stat().st_mode
    except OSError:
        raise CursorKeyMissing(path, keychain=macos) from None
    if stat.S_IMODE(mode) & 0o077:
        raise CursorKeyInsecure(path)
    try:
        key = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        raise CursorKeyMissing(path, keychain=macos) from None
    if not key:
        raise CursorKeyMissing(path, keychain=macos)
    return key


__all__ = [
    "CURSOR_KEY_ENV",
    "KEYCHAIN_ARGV",
    "KEYCHAIN_SERVICE",
    "KEYCHAIN_TIMEOUT",
    "key_path",
    "load_key",
]
