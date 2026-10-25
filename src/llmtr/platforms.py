"""Platform detection and platform-dependent key defaults (v2; owner: M9 stub, M10 body).

The platform is chosen once, at startup, from ``sys.platform``. Everything here is pure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Platform = Literal["linux", "macos"]


@dataclass(frozen=True)
class KeyDefaults:
    """Defaults of ``[keys] copy``, ``[keys] paste`` and ``[keys] start_delay`` for a platform."""

    copy: str
    paste: str
    start_delay: float


LINUX_KEY_DEFAULTS = KeyDefaults(copy="ctrl+c", paste="ctrl+v", start_delay=0.25)
"""Equal to the ``KeysConfig`` dataclass defaults; a test keeps them in sync."""

MACOS_KEY_DEFAULTS = KeyDefaults(copy="cmd+c", paste="cmd+v", start_delay=0.0)
"""M8: the shortcuts fire on key release, so no delay is needed for the modifiers."""


def detect_platform(sys_platform: str | None = None) -> Platform:
    """``"macos"`` for ``"darwin"``, ``"linux"`` for everything else (today's behaviour).

    ``sys_platform`` defaults to ``sys.platform``; tests pass it explicitly.
    """
    raise NotImplementedError


def key_defaults(platform: Platform) -> KeyDefaults:
    """``LINUX_KEY_DEFAULTS`` or ``MACOS_KEY_DEFAULTS``."""
    raise NotImplementedError


__all__ = [
    "LINUX_KEY_DEFAULTS",
    "MACOS_KEY_DEFAULTS",
    "KeyDefaults",
    "Platform",
    "detect_platform",
    "key_defaults",
]
