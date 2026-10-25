"""Tests for llmtr.macos_clipboard with a fake runner (no real pbcopy/pbpaste)."""

from __future__ import annotations

import subprocess

import pytest

from llmtr.clipboard import Clipboard
from llmtr.errors import ClipboardUnavailable
from llmtr.fakes import FakeRunner
from llmtr.macos_clipboard import PbClipboard
from llmtr.macos_exec import PBCOPY, PBPASTE


def test_satisfies_clipboard_protocol() -> None:
    assert isinstance(PbClipboard({}, run=FakeRunner()), Clipboard)


def test_get_text_decodes_utf8_and_uses_absolute_path() -> None:
    run = FakeRunner([FakeRunner.ok("Zażółć gęślą jaźń".encode())])
    assert PbClipboard({}, run=run).get_text() == "Zażółć gęślą jaźń"
    assert run.calls[0].argv == [PBPASTE]


def test_get_text_empty_output_is_empty_string() -> None:
    assert PbClipboard({}, run=FakeRunner([FakeRunner.ok(b"")])).get_text() == ""


def test_set_text_sends_utf8_on_stdin() -> None:
    run = FakeRunner([FakeRunner.ok()])
    PbClipboard({}, run=run).set_text("zażółć\nline 2")
    assert run.calls[0].argv == [PBCOPY]
    assert run.calls[0].input == "zażółć\nline 2".encode()


def test_clear_is_set_empty_text() -> None:
    run = FakeRunner([FakeRunner.ok()])
    PbClipboard({}, run=run).clear()
    assert run.calls[0].argv == [PBCOPY]
    assert run.calls[0].input == b""


@pytest.mark.parametrize("operation", ["get", "set", "clear"])
@pytest.mark.parametrize(
    "env", [{}, {"LC_ALL": "pl_PL.ISO8859-2"}, {"LANG": "pl_PL.ISO8859-2", "LC_CTYPE": "C"}]
)
def test_every_call_sets_lc_ctype_utf8_even_without_locale(operation, env) -> None:
    """M8 bug: Hammerspoon children have no locale and Polish text is garbled."""
    run = FakeRunner([FakeRunner.ok()])
    clip = PbClipboard(env, run=run)
    {"get": clip.get_text, "set": lambda: clip.set_text("x"), "clear": clip.clear}[operation]()
    child_env = run.calls[0].env
    assert child_env is not None
    assert child_env["LC_CTYPE"] == "UTF-8"
    assert "LC_ALL" not in child_env


def test_caller_env_is_not_mutated() -> None:
    env = {"LC_ALL": "C"}
    PbClipboard(env, run=FakeRunner([FakeRunner.ok()])).get_text()
    assert env == {"LC_ALL": "C"}


def test_non_zero_exit_raises_clipboard_unavailable_with_macos_message() -> None:
    run = FakeRunner([FakeRunner.ok(stderr=b"boom", returncode=1)])
    with pytest.raises(ClipboardUnavailable) as info:
        PbClipboard({}, run=run).get_text()
    assert info.value.user_message == "No working clipboard tool."
    assert "pbpaste failed" in info.value.detail and "boom" in info.value.detail


def test_missing_binary_and_timeout_raise_clipboard_unavailable() -> None:
    for exc in (FileNotFoundError("pbcopy"), subprocess.TimeoutExpired(PBCOPY, 2.0)):
        with pytest.raises(ClipboardUnavailable) as info:
            PbClipboard({}, run=FakeRunner([exc])).set_text("x")
        assert info.value.detail.startswith("pbcopy failed")
