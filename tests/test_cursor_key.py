"""Unit tests for llmtr.cursor_key (M15). No real Keychain: ``run`` is a ``FakeRunner``."""

from __future__ import annotations

import logging
import subprocess

import pytest

from llmtr import cursor_key, log
from llmtr.config import LogConfig
from llmtr.cursor_client import UrllibCursorTransport
from llmtr.errors import CursorKeyInsecure, CursorKeyMissing
from llmtr.fakes import FakeRunner

SECRET = "key_TESTONLY_0123456789abcdef"


def _text_ok(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="")


def _env(tmp_path, **extra: str) -> dict[str, str]:
    return {"XDG_CONFIG_HOME": str(tmp_path / "config"), **extra}


def _write_key(tmp_path, content: str, mode: int = 0o600):
    path = tmp_path / "config" / "llmtr" / "cursor-api-key"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(mode)
    return path


def test_key_path_uses_xdg_config_home(tmp_path) -> None:
    assert cursor_key.key_path(_env(tmp_path)) == (tmp_path / "config" / "llmtr" / "cursor-api-key")


def test_constants() -> None:
    assert cursor_key.CURSOR_KEY_ENV == "CURSOR_API_KEY"
    assert cursor_key.KEYCHAIN_SERVICE == "llmtr-cursor"


@pytest.mark.parametrize("platform", ["linux", "macos"])
def test_env_var_wins_over_keychain_and_file(tmp_path, platform) -> None:
    _write_key(tmp_path, "from-file")
    run = FakeRunner()  # no response queued: any call would fail the test
    key = cursor_key.load_key(platform, _env(tmp_path, CURSOR_API_KEY=f" {SECRET}\n"), run=run)
    assert key == SECRET
    assert run.calls == []


def test_empty_env_var_is_ignored(tmp_path) -> None:
    _write_key(tmp_path, "from-file")
    assert cursor_key.load_key("linux", _env(tmp_path, CURSOR_API_KEY="")) == "from-file"


def test_keychain_used_on_macos_with_exact_argv(tmp_path) -> None:
    _write_key(tmp_path, "from-file")
    run = FakeRunner([_text_ok(f"{SECRET}\n")])
    assert cursor_key.load_key("macos", _env(tmp_path), run=run) == SECRET
    assert run.calls[0].argv == ["security", "find-generic-password", "-s", "llmtr-cursor", "-w"]
    assert run.calls[0].timeout == 5.0


def test_keychain_not_used_on_linux(tmp_path) -> None:
    _write_key(tmp_path, "from-file")
    run = FakeRunner()
    assert cursor_key.load_key("linux", _env(tmp_path), run=run) == "from-file"
    assert run.calls == []


def test_keychain_exit_44_falls_through_to_file(tmp_path) -> None:
    _write_key(tmp_path, "from-file\n")
    run = FakeRunner([_text_ok("", returncode=44)])
    assert cursor_key.load_key("macos", _env(tmp_path), run=run) == "from-file"
    assert len(run.calls) == 1


def test_keychain_timeout_falls_through_to_file(tmp_path) -> None:
    _write_key(tmp_path, "from-file")
    run = FakeRunner([subprocess.TimeoutExpired(["security"], 5.0)])
    assert cursor_key.load_key("macos", _env(tmp_path), run=run) == "from-file"


def test_file_0600_is_read_and_stripped(tmp_path) -> None:
    _write_key(tmp_path, f"  {SECRET}\n\n")
    assert cursor_key.load_key("linux", _env(tmp_path)) == SECRET


@pytest.mark.parametrize("mode", [0o644, 0o640, 0o604, 0o660])
def test_file_with_group_or_other_bits_is_insecure(tmp_path, mode) -> None:
    path = _write_key(tmp_path, SECRET, mode)
    with pytest.raises(CursorKeyInsecure) as info:
        cursor_key.load_key("linux", _env(tmp_path))
    assert info.value.user_message == (
        f"Cursor API key file is readable by others. Run: chmod 600 {path}"
    )
    assert SECRET not in str(info.value) and SECRET not in info.value.detail


def test_missing_file_names_the_path(tmp_path) -> None:
    path = cursor_key.key_path(_env(tmp_path))
    with pytest.raises(CursorKeyMissing) as info:
        cursor_key.load_key("linux", _env(tmp_path))
    assert info.value.user_message == f"No Cursor API key. Put it in {path} (mode 600)."


def test_empty_file_is_missing(tmp_path) -> None:
    path = _write_key(tmp_path, "  \n")
    with pytest.raises(CursorKeyMissing) as info:
        cursor_key.load_key("linux", _env(tmp_path))
    assert str(path) in info.value.user_message


def test_missing_on_macos_mentions_keychain(tmp_path) -> None:
    run = FakeRunner([_text_ok("", returncode=44)])
    path = cursor_key.key_path(_env(tmp_path))
    with pytest.raises(CursorKeyMissing) as info:
        cursor_key.load_key("macos", _env(tmp_path), run=run)
    assert info.value.user_message == (
        f"No Cursor API key. Put it in {path} (mode 600) or in the Keychain as llmtr-cursor."
    )


def test_key_not_in_transport_repr_errors_or_log(tmp_path, caplog) -> None:
    env = _env(tmp_path, XDG_STATE_HOME=str(tmp_path / "state"))
    _write_key(tmp_path, SECRET)
    key = cursor_key.load_key("linux", env)
    transport = UrllibCursorTransport(key)
    assert SECRET not in repr(transport)
    logger = log.setup_logging(LogConfig(level="debug"), env)
    try:
        with caplog.at_level(logging.DEBUG, logger="llmtr"):
            cursor_key.load_key("linux", env)
        _write_key(tmp_path, SECRET, 0o644)
        with pytest.raises(CursorKeyInsecure) as info:
            cursor_key.load_key("linux", env)
        assert SECRET not in repr(info.value)
    finally:
        assert logger is not None
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()
    assert SECRET not in caplog.text
    log_file = log.log_path(env)
    assert not log_file.exists() or SECRET not in log_file.read_text(encoding="utf-8")


# --- display_path / ~ in messages (M16-fix1 D1) -----------------------------------------------


def test_display_path_collapses_home(tmp_path) -> None:
    from llmtr.errors import display_path

    assert display_path(tmp_path / ".config" / "k", home=tmp_path) == "~/.config/k"
    assert display_path("/elsewhere/k", home=tmp_path) == "/elsewhere/k"


def test_key_messages_use_tilde_under_home(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    path = tmp_path / ".config" / "llmtr" / "cursor-api-key"
    missing = CursorKeyMissing(path)
    assert missing.user_message == (
        "No Cursor API key. Put it in ~/.config/llmtr/cursor-api-key (mode 600)."
    )
    assert missing.path == path and missing.path.is_absolute()
    on_mac = CursorKeyMissing(path, keychain=True)
    assert on_mac.user_message.endswith("(mode 600) or in the Keychain as llmtr-cursor.")
    assert "~/.config" in on_mac.user_message and str(tmp_path) not in on_mac.user_message
    insecure = CursorKeyInsecure(path)
    assert insecure.user_message == (
        "Cursor API key file is readable by others. Run: chmod 600 ~/.config/llmtr/cursor-api-key"
    )
    assert insecure.path == path


def test_key_messages_show_path_outside_home_in_full(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    other = tmp_path / "xdg" / "llmtr" / "cursor-api-key"
    assert f"Put it in {other} (mode 600)" in CursorKeyMissing(other).user_message
    assert CursorKeyInsecure(other).user_message.endswith(f"chmod 600 {other}")
