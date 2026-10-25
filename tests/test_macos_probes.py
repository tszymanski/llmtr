"""Tests for llmtr.macos_probes with a fake runner (no real osascript/ioreg/ps)."""

from __future__ import annotations

import subprocess

from llmtr.fakes import FakeRunner
from llmtr.macos_exec import IOREG, OSASCRIPT, PS
from llmtr.macos_probes import focused_bundle_id, parse_secure_input_pid, secure_input_app

IOREG_EXCERPT = """\
    | |   "IOConsoleUsers" = ({"kCGSSessionUserIDKey"=501,"kCGSSessionOnConsoleKey"=Yes,\
"kCGSSessionSecureInputPID"=612,"kCGSSessionLoginDoneKey"=Yes,"kCGSSessionUserNameKey"="u"})
"""
IOREG_NO_SECURE = """\
    | |   "IOConsoleUsers" = ({"kCGSSessionUserIDKey"=501,"kCGSSessionOnConsoleKey"=Yes})
"""
CHROME = b"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome\n"


def test_parse_secure_input_pid_found() -> None:
    assert parse_secure_input_pid(IOREG_EXCERPT) == 612


def test_parse_secure_input_pid_with_spaces_around_equals() -> None:
    assert parse_secure_input_pid('"kCGSSessionSecureInputPID" = 77') == 77


def test_parse_secure_input_pid_absent() -> None:
    assert parse_secure_input_pid(IOREG_NO_SECURE) is None
    assert parse_secure_input_pid("") is None


def test_secure_input_app_found_uses_absolute_paths() -> None:
    run = FakeRunner([FakeRunner.ok(IOREG_EXCERPT.encode()), FakeRunner.ok(CHROME)])
    assert secure_input_app(run=run) == "Google Chrome"
    assert run.calls[0].argv == [IOREG, "-l", "-w", "0"]
    assert run.calls[1].argv == [PS, "-p", "612", "-o", "comm="]


def test_secure_input_app_none_active_skips_ps() -> None:
    run = FakeRunner([FakeRunner.ok(IOREG_NO_SECURE.encode())])
    assert secure_input_app(run=run) is None
    assert len(run.calls) == 1


def test_secure_input_app_failures_return_none() -> None:
    cases = [
        [FakeRunner.ok(b"", returncode=1)],
        [FileNotFoundError(IOREG)],
        [subprocess.TimeoutExpired(IOREG, 3.0)],
        [FakeRunner.ok(IOREG_EXCERPT.encode()), FakeRunner.ok(b"", returncode=1)],
        [FakeRunner.ok(IOREG_EXCERPT.encode()), FakeRunner.ok(b"\n")],
        [FakeRunner.ok(IOREG_EXCERPT.encode()), OSError("ps")],
    ]
    for responses in cases:
        assert secure_input_app(run=FakeRunner(responses)) is None


def test_focused_bundle_id_ok() -> None:
    run = FakeRunner([FakeRunner.ok(b"com.microsoft.teams2\n")])
    assert focused_bundle_id(run=run) == "com.microsoft.teams2"
    assert run.calls[0].argv[:2] == [OSASCRIPT, "-e"]
    assert "frontmost" in run.calls[0].argv[2]


def test_focused_bundle_id_empty_and_failures_return_none() -> None:
    for response in (
        FakeRunner.ok(b"\n"),
        FakeRunner.ok(b"", stderr=b"err", returncode=1),
        FileNotFoundError(OSASCRIPT),
        subprocess.TimeoutExpired(OSASCRIPT, 3.0),
    ):
        assert focused_bundle_id(run=FakeRunner([response])) is None
