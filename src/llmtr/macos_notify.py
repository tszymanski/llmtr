"""Notifications on macOS (v2; owner: M9 stub, M10 body).

Both classes implement ``llmtr.notify.Notifier`` and never raise (errors go to stderr).
"""

from __future__ import annotations

import subprocess
from collections.abc import Mapping

from llmtr.macos_exec import Runner
from llmtr.notify import Urgency

URL_SCHEME = "hammerspoon"
URL_HOST = "llmtr"
RUN_ID_ENV = "LLMTR_RUN_ID"
"""Set by ``llmtr.lua`` for the process it starts; default for the notification id is the PID."""

MAX_BODY_CHARS = 500
"""Longer bodies (a tone instruction) are cut with ``…`` so the URL stays short."""


def build_notify_url(run_id: str, summary: str, body: str, urgency: Urgency) -> str:
    """``hammerspoon://llmtr?action=notify&id=<run_id>&summary=…&body=…&urgency=…``, values
    percent-encoded (UTF-8, ``quote`` with ``safe=""``), body cut to ``MAX_BODY_CHARS``. Pure."""
    raise NotImplementedError


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
        raise NotImplementedError

    def notify(self, summary: str, body: str = "", *, urgency: Urgency = "normal") -> None:
        raise NotImplementedError


class OsascriptNotifier:
    """Fallback: ``/usr/bin/osascript`` ``display notification`` with title ``summary`` and text
    ``body``, passing both as ``argv`` items (no string escaping). Shows as "Script Editor" and
    cannot replace an earlier bubble (M8)."""

    def __init__(self, *, run: Runner = subprocess.run) -> None:
        raise NotImplementedError

    def notify(self, summary: str, body: str = "", *, urgency: Urgency = "normal") -> None:
        raise NotImplementedError


__all__ = [
    "MAX_BODY_CHARS",
    "RUN_ID_ENV",
    "URL_HOST",
    "URL_SCHEME",
    "HammerspoonNotifier",
    "OsascriptNotifier",
    "build_notify_url",
]
