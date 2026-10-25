"""Read-only macOS probes: focused app and Secure Input (v2; owner: M9 stub, M10 body).

Neither function raises; each returns ``None`` when it cannot tell.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import PurePosixPath

from llmtr.macos_exec import IOREG, OSASCRIPT, PS, Runner, child_env

SECURE_INPUT_KEY = "kCGSSessionSecureInputPID"
FRONTMOST_SCRIPT = (
    'tell application "System Events" to get bundle identifier of '
    "first application process whose frontmost is true"
)
_SECURE_INPUT_RE = re.compile(r'"kCGSSessionSecureInputPID"\s*=\s*(\d+)')
PROBE_TIMEOUT = 3.0
"""``ioreg -l -w 0`` took 0.36 s in M8; the app query 0.2-0.3 s."""


def focused_bundle_id(*, run: Runner = subprocess.run) -> str | None:
    """Bundle ID of the frontmost app (``com.microsoft.teams2``), via ``/usr/bin/osascript``
    ("bundle identifier of first application process whose frontmost is true"). Only for
    logging and ``[[keys.override]]``; ``None`` on any failure or empty output."""
    try:
        result = run(
            [OSASCRIPT, "-e", FRONTMOST_SCRIPT],
            capture_output=True,
            env=child_env(),
            timeout=PROBE_TIMEOUT,
            check=False,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", errors="replace").strip() or None


def parse_secure_input_pid(ioreg_output: str) -> int | None:
    """PID from a ``"kCGSSessionSecureInputPID"=<n>`` entry of ``ioreg -l -w 0`` output, else
    ``None``. Pure."""
    match = _SECURE_INPUT_RE.search(ioreg_output)
    return int(match.group(1)) if match else None


def secure_input_app(*, run: Runner = subprocess.run) -> str | None:
    """Name of the app holding Secure Input, or ``None`` if none (or it cannot be told).

    ``/usr/sbin/ioreg -l -w 0`` -> ``parse_secure_input_pid`` -> ``/bin/ps -p <pid> -o comm=``,
    basename of the path ("Google Chrome"). Called **only** after "nothing copied", to make the
    message specific.
    """
    try:
        listing = run(
            [IOREG, "-l", "-w", "0"],
            capture_output=True,
            env=child_env(),
            timeout=PROBE_TIMEOUT,
            check=False,
        )
        if listing.returncode != 0:
            return None
        pid = parse_secure_input_pid(listing.stdout.decode("utf-8", errors="replace"))
        if pid is None:
            return None
        ps = run(
            [PS, "-p", str(pid), "-o", "comm="],
            capture_output=True,
            env=child_env(),
            timeout=PROBE_TIMEOUT,
            check=False,
        )
        if ps.returncode != 0:
            return None
        command = ps.stdout.decode("utf-8", errors="replace").strip()
        return PurePosixPath(command).name or None
    except Exception:
        return None


__all__ = [
    "PROBE_TIMEOUT",
    "SECURE_INPUT_KEY",
    "focused_bundle_id",
    "parse_secure_input_pid",
    "secure_input_app",
]
