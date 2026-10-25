"""Text clipboard on macOS via ``pbcopy`` / ``pbpaste`` (v2; owner: M9 stub, M10 body)."""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from pathlib import Path

from llmtr.errors import ClipboardUnavailable
from llmtr.macos_exec import PBCOPY, PBPASTE, SUBPROCESS_TIMEOUT, Runner, child_env

MESSAGE = "No working clipboard tool."


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
        self._env = child_env(env)
        self._run = run

    def get_text(self) -> str:
        result = self._call([PBPASTE])
        return result.stdout.decode("utf-8", errors="replace")

    def set_text(self, text: str) -> None:
        self._call([PBCOPY], input_bytes=text.encode("utf-8"))

    def clear(self) -> None:
        self.set_text("")

    def _call(
        self, argv: list[str], input_bytes: bytes | None = None
    ) -> subprocess.CompletedProcess[bytes]:
        name = Path(argv[0]).name
        try:
            result = self._run(
                argv,
                input=input_bytes,
                capture_output=True,
                env=self._env,
                timeout=SUBPROCESS_TIMEOUT,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ClipboardUnavailable(f"{name} failed: {exc}", MESSAGE) from exc
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            raise ClipboardUnavailable(f"{name} failed: {stderr or result.returncode}", MESSAGE)
        return result


__all__ = ["PbClipboard"]
