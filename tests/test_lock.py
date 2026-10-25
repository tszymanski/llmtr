"""Tests for llmtr.lock: path defaults, flock-based mutual exclusion, cancel, and the
SIGTERM -> Cancelled handler. No real signals are sent to other processes: ``cancel_running``
uses an injected ``kill``, and the handler test signals the current process itself."""

from __future__ import annotations

import os
import signal
from pathlib import Path

import pytest

from llmtr import lock
from llmtr.errors import Cancelled


def test_default_lock_path_uses_runtime_dir():
    path = lock.default_lock_path({"XDG_RUNTIME_DIR": "/run/user/1000"})
    assert path == Path("/run/user/1000/llmtr/run.lock")


def test_default_lock_path_falls_back_to_cache_home():
    path = lock.default_lock_path({"XDG_CACHE_HOME": "/home/u/.cache"})
    assert path == Path("/home/u/.cache/llmtr/run.lock")


def test_default_lock_path_prefers_runtime_dir_over_cache_home():
    path = lock.default_lock_path({"XDG_RUNTIME_DIR": "/run/user/1000", "XDG_CACHE_HOME": "/x"})
    assert path == Path("/run/user/1000/llmtr/run.lock")


def test_run_lock_acquire_writes_pid(tmp_path):
    run_lock = lock.RunLock(tmp_path / "run.lock")
    assert run_lock.acquire() is True
    assert run_lock.holder_pid() == os.getpid()
    run_lock.release()


def test_run_lock_creates_parent_dirs(tmp_path):
    run_lock = lock.RunLock(tmp_path / "nested" / "dir" / "run.lock")
    assert run_lock.acquire() is True
    run_lock.release()


def test_second_lock_on_same_file_fails_while_first_holds(tmp_path):
    path = tmp_path / "run.lock"
    first = lock.RunLock(path)
    second = lock.RunLock(path)
    assert first.acquire() is True
    assert second.acquire() is False
    first.release()
    assert second.acquire() is True
    second.release()


def test_release_is_idempotent(tmp_path):
    run_lock = lock.RunLock(tmp_path / "run.lock")
    run_lock.acquire()
    run_lock.release()
    run_lock.release()  # must not raise


def test_context_manager_releases_on_exit(tmp_path):
    path = tmp_path / "run.lock"
    run_lock = lock.RunLock(path)
    assert run_lock.acquire() is True
    with run_lock:
        pass
    other = lock.RunLock(path)
    assert other.acquire() is True
    other.release()


def test_holder_pid_none_when_file_missing(tmp_path):
    run_lock = lock.RunLock(tmp_path / "missing.lock")
    assert run_lock.holder_pid() is None


def test_holder_pid_none_when_empty(tmp_path):
    path = tmp_path / "run.lock"
    path.write_text("")
    run_lock = lock.RunLock(path)
    assert run_lock.holder_pid() is None


def test_cancel_running_sends_signal_to_holder(tmp_path):
    run_lock = lock.RunLock(tmp_path / "run.lock")
    run_lock.acquire()
    sent = []
    result = lock.cancel_running(run_lock, kill=lambda pid, sig: sent.append((pid, sig)))
    assert result is True
    assert sent == [(os.getpid(), signal.SIGTERM)]
    run_lock.release()


def test_cancel_running_false_without_holder(tmp_path):
    run_lock = lock.RunLock(tmp_path / "missing.lock")
    assert lock.cancel_running(run_lock, kill=lambda pid, sig: None) is False


def test_cancel_running_false_when_process_already_gone(tmp_path):
    run_lock = lock.RunLock(tmp_path / "run.lock")
    run_lock.acquire()

    def fail(pid: int, sig: int) -> None:
        raise ProcessLookupError

    assert lock.cancel_running(run_lock, kill=fail) is False
    run_lock.release()


def test_install_cancel_handler_raises_cancelled_on_sigterm():
    old_handler = signal.getsignal(signal.SIGTERM)
    try:
        lock.install_cancel_handler()
        with pytest.raises(Cancelled):
            os.kill(os.getpid(), signal.SIGTERM)
    finally:
        signal.signal(signal.SIGTERM, old_handler)


def test_default_lock_path_on_macos_without_runtime_dir(tmp_path, monkeypatch):
    """macOS sets no XDG_RUNTIME_DIR: the cache fallback under HOME is used (architecture 15)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    assert lock.default_lock_path({}) == tmp_path / ".cache" / "llmtr" / "run.lock"
    assert lock.default_lock_path() == tmp_path / ".cache" / "llmtr" / "run.lock"
