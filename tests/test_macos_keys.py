"""Tests for llmtr.macos_keys with a fake runner (no real osascript)."""

from __future__ import annotations

import subprocess

import pytest

from llmtr import macos_keys
from llmtr.errors import KeySendError, MacKeySendError
from llmtr.fakes import FakeRunner
from llmtr.keys import KeySender
from llmtr.macos_exec import OSASCRIPT
from llmtr.macos_keys import (
    MacCombo,
    OsascriptKeySender,
    build_applescript,
    classify_osascript_error,
    parse_mac_combo,
)

STDERR_1002 = (
    "74:80: execution error: System Events got an error: osascript is not allowed to send "
    "keystrokes. (1002)"
)
STDERR_1743 = "execution error: Not authorized to send Apple events to System Events. (-1743)"


@pytest.mark.parametrize(
    ("combo", "expected"),
    [
        ("cmd+c", MacCombo("c", ("command down",))),
        ("CMD+V", MacCombo("v", ("command down",))),
        ("cmd+shift+v", MacCombo("v", ("command down", "shift down"))),
        ("ctrl+alt+t", MacCombo("t", ("control down", "option down"))),
        ("super+opt+1", MacCombo("1", ("command down", "option down"))),
        ("enter", MacCombo("enter", ())),
        ("cmd+tab", MacCombo("tab", ("command down",))),
        ("c", MacCombo("c", ())),
    ],
)
def test_parse_mac_combo(combo, expected) -> None:
    assert parse_mac_combo(combo) == expected


@pytest.mark.parametrize(
    "combo", ["", "cmd+", "+c", "cmd", "cmd+shift", "cmd+c+v", "hyper+c", "cmd+f5", "cmd+ł", "c c"]
)
def test_parse_mac_combo_rejects_bad_combos(combo) -> None:
    with pytest.raises(ValueError):
        parse_mac_combo(combo)


@pytest.mark.parametrize(
    ("combo", "script"),
    [
        ("cmd+c", 'tell application "System Events" to keystroke "c" using {command down}'),
        (
            "cmd+shift+v",
            'tell application "System Events" to keystroke "v" using {command down, shift down}',
        ),
        ("c", 'tell application "System Events" to keystroke "c"'),
        ("enter", 'tell application "System Events" to key code 36'),
        ("cmd+space", 'tell application "System Events" to key code 49 using {command down}'),
        ("alt+tab", 'tell application "System Events" to key code 48 using {option down}'),
    ],
)
def test_build_applescript(combo, script) -> None:
    assert build_applescript(combo) == script


def test_build_applescript_never_passes_quotes_through() -> None:
    with pytest.raises(ValueError):
        build_applescript('cmd+"')


def test_classify_osascript_error_with_real_m8_strings() -> None:
    assert classify_osascript_error(STDERR_1002) == "accessibility"
    assert classify_osascript_error(STDERR_1743) == "automation"
    assert classify_osascript_error("not allowed to send keystrokes") == "accessibility"
    assert classify_osascript_error("Not authorized to send Apple events") == "automation"
    assert classify_osascript_error("syntax error") == "failed"
    assert classify_osascript_error("") == "failed"


def test_send_runs_absolute_osascript_with_script_and_utf8_env() -> None:
    run = FakeRunner([FakeRunner.ok()])
    OsascriptKeySender(run=run).send("cmd+c")
    call = run.calls[0]
    assert call.argv == [OSASCRIPT, "-e", build_applescript("cmd+c")]
    assert call.env is not None and call.env["LC_CTYPE"] == "UTF-8"
    assert call.timeout == macos_keys.SEND_TIMEOUT


def test_send_bad_combo_runs_nothing() -> None:
    run = FakeRunner()
    with pytest.raises(ValueError):
        OsascriptKeySender(run=run).send("cmd+shift")
    assert run.calls == []


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (FakeRunner.ok(stderr=STDERR_1002.encode(), returncode=1), "accessibility"),
        (FakeRunner.ok(stderr=STDERR_1743.encode(), returncode=1), "automation"),
        (FakeRunner.ok(stderr=b"something else", returncode=1), "failed"),
        (subprocess.TimeoutExpired(OSASCRIPT, 30.0), "timeout"),
        (FileNotFoundError(OSASCRIPT), "failed"),
    ],
)
def test_send_errors_map_to_mac_key_send_error(response, reason) -> None:
    with pytest.raises(MacKeySendError) as info:
        OsascriptKeySender(run=FakeRunner([response])).send("cmd+v")
    assert info.value.reason == reason
    assert isinstance(info.value, KeySendError)
    assert info.value.user_message == MacKeySendError.MESSAGES[reason]
    if reason == "accessibility":
        assert info.value.detail == STDERR_1002


def test_available_checks_osascript_executable(monkeypatch) -> None:
    seen: list[tuple[str, int]] = []

    def fake_access(path, mode):
        seen.append((path, mode))
        return True

    monkeypatch.setattr(macos_keys.os, "access", fake_access)
    sender = OsascriptKeySender(run=FakeRunner())
    assert sender.available() is True
    assert seen[0][0] == OSASCRIPT
    monkeypatch.setattr(macos_keys.os, "access", lambda path, mode: False)
    assert sender.available() is False


def test_satisfies_key_sender_protocol() -> None:
    assert isinstance(OsascriptKeySender(run=FakeRunner()), KeySender)
