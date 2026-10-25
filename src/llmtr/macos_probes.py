"""Read-only macOS probes: focused app and Secure Input (v2; owner: M9 stub, M10 body).

Neither function raises; each returns ``None`` when it cannot tell.
"""

from __future__ import annotations

import subprocess

from llmtr.macos_exec import Runner

SECURE_INPUT_KEY = "kCGSSessionSecureInputPID"
PROBE_TIMEOUT = 3.0
"""``ioreg -l -w 0`` took 0.36 s in M8; the app query 0.2-0.3 s."""


def focused_bundle_id(*, run: Runner = subprocess.run) -> str | None:
    """Bundle ID of the frontmost app (``com.microsoft.teams2``), via ``/usr/bin/osascript``
    ("bundle identifier of first application process whose frontmost is true"). Only for
    logging and ``[[keys.override]]``; ``None`` on any failure or empty output."""
    raise NotImplementedError


def parse_secure_input_pid(ioreg_output: str) -> int | None:
    """PID from a ``"kCGSSessionSecureInputPID"=<n>`` entry of ``ioreg -l -w 0`` output, else
    ``None``. Pure."""
    raise NotImplementedError


def secure_input_app(*, run: Runner = subprocess.run) -> str | None:
    """Name of the app holding Secure Input, or ``None`` if none (or it cannot be told).

    ``/usr/sbin/ioreg -l -w 0`` -> ``parse_secure_input_pid`` -> ``/bin/ps -p <pid> -o comm=``,
    basename of the path ("Google Chrome"). Called **only** after "nothing copied", to make the
    message specific.
    """
    raise NotImplementedError


__all__ = [
    "PROBE_TIMEOUT",
    "SECURE_INPUT_KEY",
    "focused_bundle_id",
    "parse_secure_input_pid",
    "secure_input_app",
]
