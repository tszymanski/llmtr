"""Tests for llmtr.notify: notify-send argv, id replace-chaining, and never-raises behaviour."""

from __future__ import annotations

import subprocess

from llmtr import notify


def _completed(argv, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr=stderr)


def test_first_notify_argv_has_no_replace_id(monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return _completed(argv, stdout="42\n")

    monkeypatch.setattr(notify.subprocess, "run", fake_run)
    notify.NotifySendNotifier().notify("Translating...", "translategemma:12b", urgency="normal")
    assert calls[0] == [
        "notify-send",
        "--app-name=llmtr",
        "--print-id",
        "-u",
        "normal",
        "Translating...",
        "translategemma:12b",
    ]


def test_second_notify_replaces_previous_id(monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return _completed(argv, stdout="42\n")

    monkeypatch.setattr(notify.subprocess, "run", fake_run)
    notifier = notify.NotifySendNotifier()
    notifier.notify("first")
    notifier.notify("second")
    assert "--replace-id=42" in calls[1]
    assert "--print-id" in calls[1]


def test_default_urgency_is_normal(monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return _completed(argv)

    monkeypatch.setattr(notify.subprocess, "run", fake_run)
    notify.NotifySendNotifier().notify("hello")
    assert calls[0] == [
        "notify-send",
        "--app-name=llmtr",
        "--print-id",
        "-u",
        "normal",
        "hello",
        "",
    ]


def test_falls_back_to_plain_call_when_print_id_unsupported(monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        if "--print-id" in argv:
            return _completed(argv, returncode=1, stderr="unknown option")
        return _completed(argv)

    monkeypatch.setattr(notify.subprocess, "run", fake_run)
    notify.NotifySendNotifier().notify("hello", urgency="critical")
    assert calls[-1] == ["notify-send", "-u", "critical", "hello", ""]


def test_next_notify_after_fallback_has_no_replace_id(monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        if "--print-id" in argv:
            return _completed(argv, returncode=1, stderr="unknown option")
        return _completed(argv)

    monkeypatch.setattr(notify.subprocess, "run", fake_run)
    notifier = notify.NotifySendNotifier()
    notifier.notify("first")
    notifier.notify("second")
    assert not any("--replace-id" in part for part in calls[-1])


def test_notify_never_raises_when_binary_missing(monkeypatch):
    def fake_run(argv, **kwargs):
        raise FileNotFoundError("notify-send not found")

    monkeypatch.setattr(notify.subprocess, "run", fake_run)
    notify.NotifySendNotifier().notify("hello")  # must not raise


def test_notify_never_raises_on_timeout(monkeypatch):
    def fake_run(argv, **kwargs):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=2.0)

    monkeypatch.setattr(notify.subprocess, "run", fake_run)
    notify.NotifySendNotifier().notify("hello")  # must not raise
