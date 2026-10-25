"""Tests for llmtr.macos_exec."""

from __future__ import annotations

from llmtr import macos_exec


def test_child_env_sets_utf8_locale_when_env_has_none() -> None:
    env = macos_exec.child_env({"PATH": "/usr/bin"})
    assert env["LC_CTYPE"] == "UTF-8"
    assert env["PATH"] == "/usr/bin"


def test_child_env_empty_mapping_still_gets_locale() -> None:
    assert macos_exec.child_env({}) == {"LC_CTYPE": "UTF-8"}


def test_child_env_overrides_lc_ctype_and_drops_lc_all() -> None:
    env = macos_exec.child_env({"LC_ALL": "pl_PL.ISO8859-2", "LC_CTYPE": "C", "LANG": "pl_PL"})
    assert env["LC_CTYPE"] == "UTF-8"
    assert "LC_ALL" not in env
    assert env["LANG"] == "pl_PL"


def test_child_env_does_not_mutate_input() -> None:
    source = {"LC_ALL": "C"}
    macos_exec.child_env(source)
    assert source == {"LC_ALL": "C"}


def test_child_env_defaults_to_os_environ(monkeypatch) -> None:
    monkeypatch.setenv("LLMTR_TEST_MARKER", "1")
    monkeypatch.setenv("LC_ALL", "C")
    env = macos_exec.child_env()
    assert env["LLMTR_TEST_MARKER"] == "1"
    assert env["LC_CTYPE"] == "UTF-8"
    assert "LC_ALL" not in env


def test_tool_paths_are_absolute() -> None:
    for path in (
        macos_exec.PBCOPY,
        macos_exec.PBPASTE,
        macos_exec.OSASCRIPT,
        macos_exec.OPEN,
        macos_exec.IOREG,
        macos_exec.PS,
    ):
        assert path.startswith("/")
