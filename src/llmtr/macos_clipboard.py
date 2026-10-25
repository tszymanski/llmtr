"""Text clipboard on macOS via ``pbcopy`` / ``pbpaste`` (v2; owner: M9 stub, M10 body)."""

from __future__ import annotations

import subprocess
from collections.abc import Mapping

from llmtr.macos_exec import Runner


class PbClipboard:
    """``Clipboard`` backed by ``/usr/bin/pbpaste`` and ``/usr/bin/pbcopy``.

    Every call runs with ``child_env(env)``, so ``LC_CTYPE=UTF-8`` is set even when the process
    has no locale (M8: otherwise Polish text is garbled in both directions).

    - ``get_text``: ``pbpaste``; exit 0 with empty output (empty or non-text clipboard) -> ``""``.
    - ``set_text``: text on ``pbcopy``'s stdin (UTF-8); it returns at once.
    - ``clear``: ``set_text("")``.

    A missing binary, a non-zero exit or a timeout raises ``ClipboardUnavailable``.
    """

    def __init__(
        self, env: Mapping[str, str] | None = None, *, run: Runner = subprocess.run
    ) -> None:
        raise NotImplementedError

    def get_text(self) -> str:
        raise NotImplementedError

    def set_text(self, text: str) -> None:
        raise NotImplementedError

    def clear(self) -> None:
        raise NotImplementedError


__all__ = ["PbClipboard"]
