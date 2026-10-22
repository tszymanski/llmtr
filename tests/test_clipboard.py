"""Tests for llmtr.clipboard: subprocess argv and error mapping, with subprocess.run faked."""

from __future__ import annotations

import contextlib
import os
import shutil
import signal
import stat
import subprocess
import time
from pathlib import Path

import pytest

from llmtr import clipboard
from llmtr.errors import ClipboardUnavailable


def _completed(returncode=0, stdout=b"", stderr=b""):
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=stderr)


def test_wl_clipboard_get_text_argv(monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return _completed(stdout=b"hello")

    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)
    assert clipboard.WlClipboard().get_text() == "hello"
    assert calls[0] == ["wl-paste", "--no-newline", "--type", "text"]


def test_wl_clipboard_get_text_empty_selection_is_empty_string(monkeypatch):
    monkeypatch.setattr(
        clipboard.subprocess,
        "run",
        lambda argv, **kw: _completed(returncode=1, stderr=b"No selection"),
    )
    assert clipboard.WlClipboard().get_text() == ""


@pytest.mark.parametrize(
    "stderr",
    [
        b"No selection",
        b"No suitable type",
        b"Nothing is copied",
        b"nothing is copied",
    ],
)
def test_wl_clipboard_get_text_empty_wordings_are_empty_string(monkeypatch, stderr):
    monkeypatch.setattr(
        clipboard.subprocess,
        "run",
        lambda argv, **kw: _completed(returncode=1, stderr=stderr),
    )
    assert clipboard.WlClipboard().get_text() == ""


def test_wl_clipboard_get_text_other_failure_raises(monkeypatch):
    monkeypatch.setattr(
        clipboard.subprocess, "run", lambda argv, **kw: _completed(returncode=1, stderr=b"boom")
    )
    with pytest.raises(ClipboardUnavailable):
        clipboard.WlClipboard().get_text()


def test_wl_clipboard_set_text_argv(monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return _completed()

    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)
    clipboard.WlClipboard().set_text("hi")
    argv, kwargs = calls[0]
    assert argv == ["wl-copy"]
    assert kwargs["input"] == b"hi"


def test_wl_clipboard_clear_argv(monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return _completed()

    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)
    clipboard.WlClipboard().clear()
    assert calls[0] == ["wl-copy", "--clear"]


def test_wl_clipboard_hang_raises_clipboard_unavailable(monkeypatch):
    def fake_run(argv, **kwargs):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=2.0)

    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)
    with pytest.raises(ClipboardUnavailable):
        clipboard.WlClipboard().get_text()


def test_wl_clipboard_missing_binary_raises(monkeypatch):
    def fake_run(argv, **kwargs):
        raise FileNotFoundError("wl-paste not found")

    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)
    with pytest.raises(ClipboardUnavailable):
        clipboard.WlClipboard().get_text()


def test_xclip_get_text_argv(monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return _completed(stdout=b"text")

    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)
    assert clipboard.XclipClipboard().get_text() == "text"
    assert calls[0] == ["xclip", "-selection", "clipboard", "-o"]


def test_xclip_get_text_empty_on_failure(monkeypatch):
    monkeypatch.setattr(
        clipboard.subprocess, "run", lambda argv, **kw: _completed(returncode=1, stderr=b"no owner")
    )
    assert clipboard.XclipClipboard().get_text() == ""


def test_xclip_set_text_argv(monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return _completed()

    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)
    clipboard.XclipClipboard().set_text("hi")
    argv, kwargs = calls[0]
    assert argv == ["xclip", "-selection", "clipboard"]
    assert kwargs["input"] == b"hi"


def test_xclip_set_text_failure_raises(monkeypatch):
    monkeypatch.setattr(
        clipboard.subprocess, "run", lambda argv, **kw: _completed(returncode=1, stderr=b"boom")
    )
    with pytest.raises(ClipboardUnavailable):
        clipboard.XclipClipboard().set_text("hi")


def test_xclip_clear_sends_empty_input(monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(kwargs.get("input"))
        return _completed()

    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)
    clipboard.XclipClipboard().clear()
    assert calls[0] == b""


def test_make_clipboard_prefers_wayland_when_tools_present(monkeypatch):
    monkeypatch.setattr(clipboard.shutil, "which", lambda name: f"/usr/bin/{name}")
    cb = clipboard.make_clipboard({"WAYLAND_DISPLAY": "wayland-0"})
    assert isinstance(cb, clipboard.WlClipboard)


def test_make_clipboard_falls_back_to_xclip_without_wayland(monkeypatch):
    monkeypatch.setattr(
        clipboard.shutil, "which", lambda name: "/usr/bin/xclip" if name == "xclip" else None
    )
    cb = clipboard.make_clipboard({})
    assert isinstance(cb, clipboard.XclipClipboard)


def test_make_clipboard_falls_back_to_xclip_when_wl_tools_missing(monkeypatch):
    monkeypatch.setattr(
        clipboard.shutil, "which", lambda name: "/usr/bin/xclip" if name == "xclip" else None
    )
    cb = clipboard.make_clipboard({"WAYLAND_DISPLAY": "wayland-0"})
    assert isinstance(cb, clipboard.XclipClipboard)


def test_make_clipboard_raises_when_nothing_available(monkeypatch):
    monkeypatch.setattr(clipboard.shutil, "which", lambda name: None)
    with pytest.raises(ClipboardUnavailable):
        clipboard.make_clipboard({"WAYLAND_DISPLAY": "wayland-0"})


# --- Regression tests for the "wl-copy forks a background server" hang (M3-fix2) ---
#
# These run real subprocesses against fake wl-copy/xclip scripts, on a hermetic PATH, to
# reproduce the bug: a tool that writes stdin to a file then forks a child which inherits
# stdout/stderr and keeps them open. `set_text` must not wait for that child to exit.

_FAKE_TOOL_SCRIPT = """#!/bin/sh
cat > "$LLMTR_TEST_OUT"
if [ -n "$LLMTR_TEST_STDERR_MSG" ]; then
    echo "$LLMTR_TEST_STDERR_MSG" >&2
fi
if [ "${LLMTR_TEST_EXIT:-0}" = "0" ]; then
    ( sleep 30 ) &
    echo $! >> "$LLMTR_TEST_PID"
fi
exit "${LLMTR_TEST_EXIT:-0}"
"""


def _write_fake_tool(bin_dir: Path, name: str) -> None:
    path = bin_dir / name
    path.write_text(_FAKE_TOOL_SCRIPT)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


@pytest.fixture
def fake_clipboard_path(tmp_path, monkeypatch):
    """Put fake ``wl-copy``/``xclip`` scripts first on a hermetic PATH (those two scripts plus
    whatever directories provide ``sh``, ``sleep`` and ``cat``), and kill any background
    sleepers the scripts forked once the test is done."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_tool(bin_dir, "wl-copy")
    _write_fake_tool(bin_dir, "xclip")

    path_dirs = [str(bin_dir)]
    for tool in ("sh", "sleep", "cat"):
        found = shutil.which(tool)
        assert found, f"{tool} must be on PATH to build the hermetic test PATH"
        tool_dir = str(Path(found).parent)
        if tool_dir not in path_dirs:
            path_dirs.append(tool_dir)
    monkeypatch.setenv("PATH", os.pathsep.join(path_dirs))

    out_file = tmp_path / "captured"
    pid_file = tmp_path / "pids"
    pid_file.write_text("")
    monkeypatch.setenv("LLMTR_TEST_OUT", str(out_file))
    monkeypatch.setenv("LLMTR_TEST_PID", str(pid_file))
    monkeypatch.delenv("LLMTR_TEST_EXIT", raising=False)
    monkeypatch.delenv("LLMTR_TEST_STDERR_MSG", raising=False)

    yield out_file

    for line in pid_file.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        with contextlib.suppress(ProcessLookupError, ValueError):
            os.kill(int(line), signal.SIGKILL)


def test_wl_clipboard_set_text_does_not_block_on_forked_server(fake_clipboard_path):
    out_file = fake_clipboard_path
    start = time.monotonic()
    clipboard.WlClipboard().set_text("hello world")
    elapsed = time.monotonic() - start
    assert elapsed < 1.0
    assert out_file.read_text() == "hello world"


def test_xclip_set_text_does_not_block_on_forked_server(fake_clipboard_path):
    out_file = fake_clipboard_path
    start = time.monotonic()
    clipboard.XclipClipboard().set_text("hello world")
    elapsed = time.monotonic() - start
    assert elapsed < 1.0
    assert out_file.read_text() == "hello world"


_FAKE_WL_PASTE_EMPTY_SCRIPT = """#!/bin/sh
echo "Nothing is copied" >&2
exit 1
"""


def test_wl_clipboard_get_text_real_nothing_is_copied_is_empty_string(tmp_path, monkeypatch):
    """Regression for M3-fix3: a real ``wl-paste`` (wl-clipboard 2.2.1) that prints "Nothing is
    copied" to stderr and exits 1 must be treated as an empty clipboard, not a failure."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    path = bin_dir / "wl-paste"
    path.write_text(_FAKE_WL_PASTE_EMPTY_SCRIPT)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    sh_dir = str(Path(shutil.which("sh")).parent)
    monkeypatch.setenv("PATH", os.pathsep.join([str(bin_dir), sh_dir]))

    assert clipboard.WlClipboard().get_text() == ""


def test_wl_clipboard_set_text_real_failure_raises_with_stderr(fake_clipboard_path, monkeypatch):
    monkeypatch.setenv("LLMTR_TEST_EXIT", "1")
    monkeypatch.setenv("LLMTR_TEST_STDERR_MSG", "boom")
    with pytest.raises(ClipboardUnavailable) as exc_info:
        clipboard.WlClipboard().set_text("hi")
    assert "boom" in exc_info.value.detail


def test_xclip_set_text_real_failure_raises_with_stderr(fake_clipboard_path, monkeypatch):
    monkeypatch.setenv("LLMTR_TEST_EXIT", "1")
    monkeypatch.setenv("LLMTR_TEST_STDERR_MSG", "boom")
    with pytest.raises(ClipboardUnavailable) as exc_info:
        clipboard.XclipClipboard().set_text("hi")
    assert "boom" in exc_info.value.detail
