"""Tests for llmtr.macos_notify with a fake runner (no real open/osascript)."""

from __future__ import annotations

import os
import subprocess
from urllib.parse import parse_qs, urlsplit

from llmtr.fakes import FakeRunner
from llmtr.macos_exec import OPEN, OSASCRIPT
from llmtr.macos_notify import (
    MAX_BODY_CHARS,
    HammerspoonNotifier,
    OsascriptNotifier,
    build_notify_url,
)
from llmtr.notify import Notifier


def test_build_notify_url_exact_string() -> None:
    url = build_notify_url("42", "Translating PL → EN…", "", "normal")
    assert url == (
        "hammerspoon://llmtr?action=notify&id=42"
        "&summary=Translating%20PL%20%E2%86%92%20EN%E2%80%A6&body=&urgency=normal"
    )


def test_build_notify_url_encodes_polish_text() -> None:
    url = build_notify_url("1", "Zażółć", "gęślą jaźń", "low")
    assert "summary=Za%C5%BC%C3%B3%C5%82%C4%87" in url
    assert "body=g%C4%99%C5%9Bl%C4%85%20ja%C5%BA%C5%84" in url


def test_build_notify_url_encodes_reserved_characters() -> None:
    url = build_notify_url("1", "a&b=c d", "x=1&y=2\nline 2 ?#%", "critical")
    assert "summary=a%26b%3Dc%20d" in url
    assert "body=x%3D1%26y%3D2%0Aline%202%20%3F%23%25" in url
    assert url.count("&") == 4  # only the four field separators are raw


def test_build_notify_url_round_trips() -> None:
    summary, body = "Tone: team (1/2)", 'Piszemy: „cześć”, & "hej" = ok\n\nkoniec'
    query = parse_qs(urlsplit(build_notify_url("7", summary, body, "critical")).query)
    assert query == {
        "action": ["notify"],
        "id": ["7"],
        "summary": [summary],
        "body": [body],
        "urgency": ["critical"],
    }


def test_build_notify_url_cuts_long_body() -> None:
    body = "ą" * (MAX_BODY_CHARS + 100)
    query = parse_qs(urlsplit(build_notify_url("1", "s", body, "normal")).query)
    cut = query["body"][0]
    assert len(cut) == MAX_BODY_CHARS and cut.endswith("…")
    short = "b" * MAX_BODY_CHARS
    assert parse_qs(urlsplit(build_notify_url("1", "s", short, "normal")).query)["body"] == [short]


def test_hammerspoon_notifier_runs_open_g_with_url() -> None:
    run = FakeRunner([FakeRunner.ok()])
    HammerspoonNotifier({}, run_id="9", run=run).notify("Hi", "there", urgency="critical")
    call = run.calls[0]
    assert call.argv == [OPEN, "-g", build_notify_url("9", "Hi", "there", "critical")]
    assert call.timeout == 2.0


def test_hammerspoon_notifier_uses_one_id_per_instance() -> None:
    run = FakeRunner([FakeRunner.ok(), FakeRunner.ok()])
    notifier = HammerspoonNotifier({"LLMTR_RUN_ID": "5"}, run=run)
    notifier.notify("Translating…")
    notifier.notify("Done")
    ids = [parse_qs(urlsplit(c.argv[2]).query)["id"] for c in run.calls]
    assert ids == [["5"], ["5"]]


def test_hammerspoon_notifier_run_id_defaults_to_pid() -> None:
    run = FakeRunner([FakeRunner.ok()])
    HammerspoonNotifier({}, run=run).notify("x")
    assert parse_qs(urlsplit(run.calls[0].argv[2]).query)["id"] == [str(os.getpid())]


def test_hammerspoon_notifier_never_raises(capsys) -> None:
    run = FakeRunner(
        [
            FileNotFoundError(OPEN),
            subprocess.TimeoutExpired(OPEN, 2.0),
            FakeRunner.ok(stderr=b"nope", returncode=1),
        ]
    )
    notifier = HammerspoonNotifier({}, run=run)
    for _ in range(3):
        notifier.notify("x")
    assert capsys.readouterr().err.count("llmtr: notification failed") == 3


def test_osascript_notifier_passes_text_as_argv() -> None:
    run = FakeRunner([FakeRunner.ok()])
    summary, body = 'He said "hi" \\ ś', "line 1\nline 2 ' end"
    OsascriptNotifier(run=run).notify(summary, body, urgency="critical")
    call = run.calls[0]
    assert call.argv[0] == OSASCRIPT
    assert call.argv[-2:] == [summary, body]
    script = call.argv[2]
    assert summary not in script and body not in script
    assert "item 2 of argv" in script and "item 1 of argv" in script
    assert call.env is not None and call.env["LC_CTYPE"] == "UTF-8"


def test_osascript_notifier_never_raises(capsys) -> None:
    run = FakeRunner([FileNotFoundError(OSASCRIPT), FakeRunner.ok(stderr=b"bad", returncode=1)])
    notifier = OsascriptNotifier(run=run)
    notifier.notify("x")
    notifier.notify("y")
    assert capsys.readouterr().err.count("llmtr: notification failed") == 2


def test_notifiers_satisfy_protocol() -> None:
    assert isinstance(HammerspoonNotifier({}, run=FakeRunner()), Notifier)
    assert isinstance(OsascriptNotifier(run=FakeRunner()), Notifier)
