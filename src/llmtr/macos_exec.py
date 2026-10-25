"""Shared pieces of the macOS backends: absolute tool paths, child environment, runner type
(v2; owner: M9 stub, M10 body).

Hammerspoon children get ``PATH=/usr/bin:/bin:/usr/sbin:/sbin`` and no locale (M8), so every
tool is called by absolute path and the child environment is built here.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Mapping

PBCOPY = "/usr/bin/pbcopy"
PBPASTE = "/usr/bin/pbpaste"
OSASCRIPT = "/usr/bin/osascript"
OPEN = "/usr/bin/open"
IOREG = "/usr/sbin/ioreg"
PS = "/bin/ps"

LOCALE_VAR = "LC_CTYPE"
LOCALE_VALUE = "UTF-8"

SUBPROCESS_TIMEOUT = 2.0
"""Seconds allowed for a macOS helper before it is treated as hung."""

Runner = Callable[..., "subprocess.CompletedProcess[bytes]"]
"""Same call shape as ``subprocess.run`` (bytes mode). Backends take it as ``run=`` so tests
inject a fake and nothing real is started."""


def child_env(env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Copy of ``env`` (default ``os.environ``) for a child process.

    Always sets ``LC_CTYPE=UTF-8``, even when ``env`` has no locale, and removes ``LC_ALL`` (it
    would override ``LC_CTYPE``). Never mutates ``env``.
    """
    result = dict(env if env is not None else os.environ)
    result.pop("LC_ALL", None)
    result[LOCALE_VAR] = LOCALE_VALUE
    return result


__all__ = [
    "IOREG",
    "LOCALE_VALUE",
    "LOCALE_VAR",
    "OPEN",
    "OSASCRIPT",
    "PBCOPY",
    "PBPASTE",
    "PS",
    "SUBPROCESS_TIMEOUT",
    "Runner",
    "child_env",
]
