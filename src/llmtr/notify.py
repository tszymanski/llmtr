"""Desktop notifications via notify-send (owner: M3)."""

from __future__ import annotations

import subprocess
import sys
from typing import Literal, Protocol, runtime_checkable

Urgency = Literal["low", "normal", "critical"]

APP_NAME = "llmtr"

SUBPROCESS_TIMEOUT = 2.0
"""Seconds allowed for ``notify-send`` before it is treated as hung."""


@runtime_checkable
class Notifier(Protocol):
    """Shows short notifications. A later call replaces the previous notification of the same
    run where the backend supports it (so "Translating…" is replaced by the error/hint)."""

    def notify(self, summary: str, body: str = "", *, urgency: Urgency = "normal") -> None:
        """Show a notification. Must never raise: a broken notifier must not break a job."""
        ...


class NotifySendNotifier:
    """``notify-send --app-name=llmtr --print-id [--replace-id=<last id>] -u <urgency>``.

    Keeps the id printed by the previous call and passes it as ``--replace-id``. Falls back to
    plain ``notify-send`` if those flags are unsupported. Errors are swallowed (written to
    stderr).
    """

    def __init__(self) -> None:
        self._last_id: str | None = None

    def notify(self, summary: str, body: str = "", *, urgency: Urgency = "normal") -> None:
        try:
            self._notify(summary, body, urgency)
        except Exception as exc:  # pragma: no cover - defensive, must never raise
            print(f"llmtr: notification failed: {exc}", file=sys.stderr)

    def _notify(self, summary: str, body: str, urgency: Urgency) -> None:
        argv = [f"--app-name={APP_NAME}", "--print-id"]
        if self._last_id is not None:
            argv.append(f"--replace-id={self._last_id}")
        argv += ["-u", urgency, summary, body]
        try:
            result = subprocess.run(
                ["notify-send", *argv],
                capture_output=True,
                text=True,
                timeout=SUBPROCESS_TIMEOUT,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            result = None
        if result is not None and result.returncode == 0:
            self._last_id = result.stdout.strip() or None
            return
        # --print-id/--replace-id unsupported (or notify-send missing the flags): plain call.
        subprocess.run(
            ["notify-send", "-u", urgency, summary, body],
            capture_output=True,
            timeout=SUBPROCESS_TIMEOUT,
            check=False,
        )
        self._last_id = None


__all__ = ["APP_NAME", "NotifySendNotifier", "Notifier", "Urgency"]
