"""Clipboard access, text only (owner: M3).

Only the CLIPBOARD selection is used; PRIMARY is never read (``wl-paste --primary`` hangs on
the host). Only ``text/plain`` content is saved and restored; images or files on the clipboard
are not preserved (v1 limitation).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from llmtr.errors import ClipboardUnavailable

SUBPROCESS_TIMEOUT = 2.0
"""Seconds allowed for a clipboard subprocess before it is treated as hung."""

WL_PASTE_EMPTY_CLIPBOARD_WORDINGS = (
    "no selection",  # wl-clipboard <2.2.0
    "no suitable type",  # wl-clipboard <2.2.0, when the clipboard holds a non-text type
    "nothing is copied",  # wl-clipboard 2.2.1 (Ubuntu 25.10): seen when polling right after clear()
)
"""Case-insensitive substrings of ``wl-paste`` stderr that mean "clipboard is empty", across the
wl-clipboard versions we've observed. Any other non-zero exit is a real failure."""


@runtime_checkable
class Clipboard(Protocol):
    """Text clipboard."""

    def get_text(self) -> str:
        """Current clipboard text; ``""`` when empty or not text. Raises ``ClipboardUnavailable``
        if the tool fails or hangs (implementations use a subprocess timeout)."""
        ...

    def set_text(self, text: str) -> None:
        """Replace the clipboard with ``text``. Raises ``ClipboardUnavailable``."""
        ...

    def clear(self) -> None:
        """Empty the clipboard. Raises ``ClipboardUnavailable``."""
        ...


class WlClipboard:
    """``wl-paste --no-newline --type text`` / ``wl-copy`` / ``wl-copy --clear``.

    ``wl-paste`` exiting non-zero with "No selection"/"No suitable type" means ``""``.
    ``wl-copy`` forks a server process; it must not block llmtr.
    """

    def get_text(self) -> str:
        result = _run(["wl-paste", "--no-newline", "--type", "text"])
        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace")
            stderr_lower = stderr.lower()
            if any(wording in stderr_lower for wording in WL_PASTE_EMPTY_CLIPBOARD_WORDINGS):
                return ""
            raise ClipboardUnavailable(stderr.strip())
        return result.stdout.decode(errors="replace")

    def set_text(self, text: str) -> None:
        result = _run(["wl-copy"], input_bytes=text.encode(), detached=True)
        if result.returncode != 0:
            raise ClipboardUnavailable(result.stderr.decode(errors="replace").strip())

    def clear(self) -> None:
        result = _run(["wl-copy", "--clear"])
        if result.returncode != 0:
            raise ClipboardUnavailable(result.stderr.decode(errors="replace").strip())


class XclipClipboard:
    """``xclip -selection clipboard`` fallback (X11/XWayland)."""

    def get_text(self) -> str:
        result = _run(["xclip", "-selection", "clipboard", "-o"])
        if result.returncode != 0:
            # xclip exits non-zero when no process owns the selection (empty clipboard).
            return ""
        return result.stdout.decode(errors="replace")

    def set_text(self, text: str) -> None:
        result = _run(
            ["xclip", "-selection", "clipboard"], input_bytes=text.encode(), detached=True
        )
        if result.returncode != 0:
            raise ClipboardUnavailable(result.stderr.decode(errors="replace").strip())

    def clear(self) -> None:
        self.set_text("")


def make_clipboard(env: Mapping[str, str] | None = None) -> Clipboard:
    """``WlClipboard`` if ``WAYLAND_DISPLAY`` is set and ``wl-copy``/``wl-paste`` are on PATH,
    else ``XclipClipboard`` if ``xclip`` is on PATH, else raise ``ClipboardUnavailable``.
    ``env`` defaults to ``os.environ``.
    """
    env = env if env is not None else os.environ
    if env.get("WAYLAND_DISPLAY") and shutil.which("wl-copy") and shutil.which("wl-paste"):
        return WlClipboard()
    if shutil.which("xclip"):
        return XclipClipboard()
    raise ClipboardUnavailable("No wl-clipboard or xclip found on PATH.")


def _run(
    argv: list[str], input_bytes: bytes | None = None, *, detached: bool = False
) -> subprocess.CompletedProcess[bytes]:
    """Run a clipboard tool and wait for it to exit.

    ``detached=True`` is for tools that may fork a background process to keep serving the
    clipboard (``wl-copy``, and ``xclip`` on set): stdout/stderr must not be pipes, or the
    forked child inherits the write end and our wait for EOF never returns (``capture_output``
    would then block for the full timeout even though the foreground process already exited).
    stderr is instead captured to a temporary file, read back only on a non-zero exit.
    """
    if detached:
        with tempfile.TemporaryFile() as stderr_file:
            try:
                result = subprocess.run(
                    argv,
                    input=input_bytes,
                    stdout=subprocess.DEVNULL,
                    stderr=stderr_file,
                    timeout=SUBPROCESS_TIMEOUT,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise ClipboardUnavailable(str(exc)) from exc
            stderr_bytes = b""
            if result.returncode != 0:
                stderr_file.seek(0)
                stderr_bytes = stderr_file.read()
        return subprocess.CompletedProcess(argv, result.returncode, stdout=b"", stderr=stderr_bytes)
    try:
        return subprocess.run(
            argv,
            input=input_bytes,
            capture_output=True,
            timeout=SUBPROCESS_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ClipboardUnavailable(str(exc)) from exc


__all__ = ["Clipboard", "WlClipboard", "XclipClipboard", "make_clipboard"]
