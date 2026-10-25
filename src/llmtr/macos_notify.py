"""Notifications on macOS (v2; owner: M9 stub, M10 body).

Both classes implement ``llmtr.notify.Notifier`` and never raise (errors go to stderr).
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping
from urllib.parse import quote

from llmtr.macos_exec import OPEN, OSASCRIPT, SUBPROCESS_TIMEOUT, Runner, child_env
from llmtr.notify import Urgency

URL_SCHEME = "hammerspoon"
URL_HOST = "llmtr"
RUN_ID_ENV = "LLMTR_RUN_ID"
"""Set by ``llmtr.lua`` for the process it starts; default for the notification id is the PID."""

MAX_BODY_CHARS = 500
"""Longer bodies (a tone instruction) are cut with ``…`` so the URL stays short."""


APPLESCRIPT = (
    "on run argv\ndisplay notification (item 2 of argv) with title (item 1 of argv)\nend run"
)
"""Text reaches AppleScript as ``argv`` items, never inside the script source."""


def build_notify_url(run_id: str, summary: str, body: str, urgency: Urgency) -> str:
    """``hammerspoon://llmtr?action=notify&id=<run_id>&summary=…&body=…&urgency=…``, values
    percent-encoded (UTF-8, ``quote`` with ``safe=""``), body cut to ``MAX_BODY_CHARS``. Pure."""
    if len(body) > MAX_BODY_CHARS:
        body = body[: MAX_BODY_CHARS - 1] + "…"
    query = "&".join(
        f"{key}={quote(value, safe='')}"
        for key, value in (
            ("action", "notify"),
            ("id", run_id),
            ("summary", summary),
            ("body", body),
            ("urgency", urgency),
        )
    )
    return f"{URL_SCHEME}://{URL_HOST}?{query}"


class HammerspoonNotifier:
    """Sends ``build_notify_url(...)`` with ``/usr/bin/open -g <url>`` (no focus change).

    One bubble per run: every call of one instance uses the same ``run_id``, and the Lua side
    replaces the bubble of that id, so "Translating…" is replaced by the result/error.
    ``run_id`` defaults to ``env["LLMTR_RUN_ID"]``, else ``str(os.getpid())``.
    """

    def __init__(
        self,
        env: Mapping[str, str] | None = None,
        *,
        run_id: str | None = None,
        run: Runner = subprocess.run,
    ) -> None:
        source = env if env is not None else os.environ
        self._run_id = run_id or source.get(RUN_ID_ENV) or str(os.getpid())
        self._run = run

    def notify(self, summary: str, body: str = "", *, urgency: Urgency = "normal") -> None:
        try:
            url = build_notify_url(self._run_id, summary, body, urgency)
            result = self._run(
                [OPEN, "-g", url],
                capture_output=True,
                timeout=SUBPROCESS_TIMEOUT,
                check=False,
            )
            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", errors="replace").strip()
                print(
                    f"llmtr: notification failed: open exited {result.returncode}: {stderr}",
                    file=sys.stderr,
                )
        except Exception as exc:
            print(f"llmtr: notification failed: {exc}", file=sys.stderr)


class OsascriptNotifier:
    """Fallback: ``/usr/bin/osascript`` ``display notification`` with title ``summary`` and text
    ``body``, passing both as ``argv`` items (no string escaping). Shows as "Script Editor" and
    cannot replace an earlier bubble (M8)."""

    def __init__(self, *, run: Runner = subprocess.run) -> None:
        self._run = run

    def notify(self, summary: str, body: str = "", *, urgency: Urgency = "normal") -> None:
        try:
            result = self._run(
                [OSASCRIPT, "-e", APPLESCRIPT, summary, body],
                capture_output=True,
                env=child_env(),
                timeout=SUBPROCESS_TIMEOUT,
                check=False,
            )
            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", errors="replace").strip()
                print(
                    f"llmtr: notification failed: osascript exited {result.returncode}: {stderr}",
                    file=sys.stderr,
                )
        except Exception as exc:
            print(f"llmtr: notification failed: {exc}", file=sys.stderr)


__all__ = [
    "MAX_BODY_CHARS",
    "RUN_ID_ENV",
    "URL_HOST",
    "URL_SCHEME",
    "HammerspoonNotifier",
    "OsascriptNotifier",
    "build_notify_url",
]
