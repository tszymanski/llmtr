"""Tests for llmtr.keys: keycode parsing, resolve_key_pair, and subprocess argv for ydotool and
gdbus, with subprocess.run faked."""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path

import pytest

from llmtr import keys
from llmtr.config import KeyOverride, KeysConfig
from llmtr.errors import KeySendError


def _completed(argv, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr=stderr)


# --- parse_combo -----------------------------------------------------------------------------


def test_parse_combo_ctrl_c():
    assert keys.parse_combo("ctrl+c") == [29, 46]


def test_parse_combo_ctrl_shift_c():
    assert keys.parse_combo("ctrl+shift+c") == [29, 42, 46]


def test_parse_combo_case_insensitive():
    assert keys.parse_combo("CTRL+C") == keys.parse_combo("ctrl+c")


def test_parse_combo_unknown_modifier_raises():
    with pytest.raises(ValueError):
        keys.parse_combo("meta+c")


def test_parse_combo_unknown_key_raises():
    with pytest.raises(ValueError):
        keys.parse_combo("ctrl+??")


def test_parse_combo_no_non_modifier_raises():
    with pytest.raises(ValueError):
        keys.parse_combo("ctrl+shift")


def test_parse_combo_malformed_raises():
    with pytest.raises(ValueError):
        keys.parse_combo("ctrl++c")


# --- resolve_key_pair --------------------------------------------------------------------------


def test_resolve_key_pair_default_without_app_id():
    pair = keys.resolve_key_pair(KeysConfig(), None)
    assert pair == keys.KeyPair("ctrl+c", "ctrl+v")


def test_resolve_key_pair_override_matches_case_insensitively():
    cfg = KeysConfig(
        override=(
            KeyOverride(app=("org.gnome.Terminal",), copy="ctrl+shift+c", paste="ctrl+shift+v"),
        )
    )
    pair = keys.resolve_key_pair(cfg, "ORG.GNOME.TERMINAL")
    assert pair == keys.KeyPair("ctrl+shift+c", "ctrl+shift+v")


def test_resolve_key_pair_falls_back_to_default_when_unmatched():
    cfg = KeysConfig(
        override=(KeyOverride(app=("kitty",), copy="ctrl+shift+c", paste="ctrl+shift+v"),)
    )
    pair = keys.resolve_key_pair(cfg, "firefox")
    assert pair == keys.KeyPair("ctrl+c", "ctrl+v")


# --- YdotoolKeySender.available --------------------------------------------------------------


@pytest.fixture
def short_dir():
    """A short temp dir: AF_UNIX paths are limited to ~108 bytes and ``tmp_path`` can be longer."""
    path = Path(tempfile.mkdtemp(dir="/tmp"))
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def ydotool_on_path(monkeypatch):
    monkeypatch.setattr(keys.shutil, "which", lambda name: "/usr/bin/ydotool")


def test_ydotool_available_with_live_daemon_socket(ydotool_on_path, short_dir):
    path = short_dir / "sock"
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as server:
        server.bind(str(path))
        sender = keys.YdotoolKeySender(env={"YDOTOOL_SOCKET": str(path)})
        assert sender.available() is True


def test_ydotool_unavailable_with_stale_socket_file(ydotool_on_path, short_dir):
    # ydotoold leaves its socket file behind when stopped: bind, then close without unlinking.
    path = short_dir / "sock"
    server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    server.bind(str(path))
    server.close()
    assert path.exists()
    sender = keys.YdotoolKeySender(env={"YDOTOOL_SOCKET": str(path)})
    assert sender.available() is False


def test_ydotool_unavailable_with_regular_file(ydotool_on_path, short_dir):
    path = short_dir / "sock"
    path.write_text("")
    sender = keys.YdotoolKeySender(env={"YDOTOOL_SOCKET": str(path)})
    assert sender.available() is False


def test_ydotool_unavailable_without_socket(ydotool_on_path, short_dir):
    sender = keys.YdotoolKeySender(env={"YDOTOOL_SOCKET": str(short_dir / "missing")})
    assert sender.available() is False


def test_ydotool_unavailable_with_too_long_socket_path(ydotool_on_path):
    sender = keys.YdotoolKeySender(env={"YDOTOOL_SOCKET": "/tmp/" + "x" * 200})
    assert sender.available() is False


def test_ydotool_unavailable_without_binary_even_with_live_socket(monkeypatch, short_dir):
    monkeypatch.setattr(keys.shutil, "which", lambda name: None)
    path = short_dir / "sock"
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as server:
        server.bind(str(path))
        sender = keys.YdotoolKeySender(env={"YDOTOOL_SOCKET": str(path)})
        assert sender.available() is False


def test_ydotool_socket_path_falls_back_to_runtime_dir(tmp_path):
    sender = keys.YdotoolKeySender(env={"XDG_RUNTIME_DIR": str(tmp_path)})
    assert sender._socket_path == tmp_path / ".ydotool_socket"


def test_ydotool_socket_path_falls_back_to_tmp():
    sender = keys.YdotoolKeySender(env={})
    assert str(sender._socket_path) == "/tmp/.ydotool_socket"


# --- YdotoolKeySender.send ---------------------------------------------------------------------


def test_ydotool_send_argv_order(monkeypatch, tmp_path):
    sock_path = tmp_path / "sock"
    sock_path.write_text("")
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return _completed(argv)

    monkeypatch.setattr(keys.subprocess, "run", fake_run)
    sender = keys.YdotoolKeySender(env={"YDOTOOL_SOCKET": str(sock_path)})
    sender.send("ctrl+c")
    argv, run_kwargs = calls[0]
    assert argv == ["ydotool", "key", "125:0", "56:0", "29:1", "46:1", "46:0", "29:0"]
    assert run_kwargs["env"]["YDOTOOL_SOCKET"] == str(sock_path)


def test_ydotool_send_releases_super_and_alt_first(monkeypatch, tmp_path):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return _completed(argv)

    monkeypatch.setattr(keys.subprocess, "run", fake_run)
    sender = keys.YdotoolKeySender(env={"YDOTOOL_SOCKET": str(tmp_path / "sock")})
    sender.send("ctrl+v")
    assert calls[0][:4] == ["ydotool", "key", "125:0", "56:0"]


def test_ydotool_send_failure_raises_key_send_error(monkeypatch, tmp_path):
    def fake_run(argv, **kwargs):
        return _completed(argv, returncode=1, stderr=b"no daemon")

    monkeypatch.setattr(keys.subprocess, "run", fake_run)
    sender = keys.YdotoolKeySender(env={"YDOTOOL_SOCKET": str(tmp_path / "sock")})
    with pytest.raises(KeySendError):
        sender.send("ctrl+c")


def test_ydotool_send_hang_raises_key_send_error(monkeypatch, tmp_path):
    def fake_run(argv, **kwargs):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=2.0)

    monkeypatch.setattr(keys.subprocess, "run", fake_run)
    sender = keys.YdotoolKeySender(env={"YDOTOOL_SOCKET": str(tmp_path / "sock")})
    with pytest.raises(KeySendError):
        sender.send("ctrl+c")


def test_ydotool_send_malformed_combo_raises_value_error(tmp_path):
    sender = keys.YdotoolKeySender(env={"YDOTOOL_SOCKET": str(tmp_path / "sock")})
    with pytest.raises(ValueError):
        sender.send("ctrl+shift")


# --- focused_app_id ----------------------------------------------------------------------------


def test_focused_app_id_parses_window_calls_output(monkeypatch):
    windows = [
        {"id": 1, "wm_class": "org.gnome.TextEditor", "focus": False},
        {"id": 2, "wm_class": "firefox", "focus": True},
    ]
    output = f"({json.dumps(windows)!r},)"

    def fake_run(argv, **kwargs):
        return _completed(argv, stdout=output)

    monkeypatch.setattr(keys.subprocess, "run", fake_run)
    assert keys.focused_app_id() == "firefox"


def test_focused_app_id_none_when_nothing_focused(monkeypatch):
    windows = [{"id": 1, "wm_class": "firefox", "focus": False}]
    output = f"({json.dumps(windows)!r},)"

    def fake_run(argv, **kwargs):
        return _completed(argv, stdout=output)

    monkeypatch.setattr(keys.subprocess, "run", fake_run)
    assert keys.focused_app_id() is None


def test_focused_app_id_none_on_nonzero_exit(monkeypatch):
    def fake_run(argv, **kwargs):
        return _completed(argv, returncode=1, stderr="no such extension")

    monkeypatch.setattr(keys.subprocess, "run", fake_run)
    assert keys.focused_app_id() is None


def test_focused_app_id_none_on_unparsable_output(monkeypatch):
    def fake_run(argv, **kwargs):
        return _completed(argv, stdout="not json at all")

    monkeypatch.setattr(keys.subprocess, "run", fake_run)
    assert keys.focused_app_id() is None


def test_focused_app_id_never_raises_when_gdbus_missing(monkeypatch):
    def fake_run(argv, **kwargs):
        raise FileNotFoundError("gdbus not found")

    monkeypatch.setattr(keys.subprocess, "run", fake_run)
    assert keys.focused_app_id() is None


def test_focused_app_id_never_raises_on_timeout(monkeypatch):
    def fake_run(argv, **kwargs):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=0.5)

    monkeypatch.setattr(keys.subprocess, "run", fake_run)
    assert keys.focused_app_id() is None
