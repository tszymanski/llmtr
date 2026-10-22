"""Single-run lock and cancel-on-second-press (owner: M3).

One lock file, ``$XDG_RUNTIME_DIR/llmtr/run.lock`` (fallback ``$XDG_CACHE_HOME/llmtr/run.lock``),
held with ``fcntl.flock(LOCK_EX | LOCK_NB)`` for the whole job; the holder's PID is written into
it. The kernel drops the lock when the process dies, so a crash never leaves a stale lock.

Second press: the new process fails to acquire, reads the PID, sends it ``SIGTERM`` and exits
without starting a job. The first process's ``SIGTERM`` handler (``install_cancel_handler``)
raises ``Cancelled`` in the main thread, which interrupts the blocking HTTP read; ``cli.py``
then restores the clipboard and notifies "Cancelled.".
"""

from __future__ import annotations

import contextlib
import fcntl
import os
import signal
from collections.abc import Callable, Mapping
from pathlib import Path
from types import TracebackType

from llmtr.errors import Cancelled


def default_lock_path(env: Mapping[str, str] | None = None) -> Path:
    """See the module docstring; ``env`` defaults to ``os.environ``."""
    env = env if env is not None else os.environ
    runtime_dir = env.get("XDG_RUNTIME_DIR")
    if runtime_dir:
        return Path(runtime_dir) / "llmtr" / "run.lock"
    cache_home = env.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(cache_home) / "llmtr" / "run.lock"


class RunLock:
    """Non-blocking exclusive lock on a file. Usable as a context manager only after a
    successful ``acquire`` (``__exit__`` calls ``release``)."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._fd: int | None = None

    def acquire(self) -> bool:
        """Try to take the lock without waiting. On success write ``os.getpid()`` into the file
        and return True; return False if another process holds it. Creates parent dirs."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self._path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            return False
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode())
        os.fsync(fd)
        self._fd = fd
        return True

    def release(self) -> None:
        """Unlock and close. Idempotent."""
        if self._fd is not None:
            with contextlib.suppress(OSError):
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            os.close(self._fd)
            self._fd = None

    def holder_pid(self) -> int | None:
        """PID written by the current holder, or None if unreadable/empty."""
        try:
            content = self._path.read_text().strip()
        except OSError:
            return None
        try:
            return int(content) if content else None
        except ValueError:
            return None

    def __enter__(self) -> RunLock:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.release()


def cancel_running(
    lock: RunLock,
    *,
    sig: int = signal.SIGTERM,
    kill: Callable[[int, int], None] | None = None,
) -> bool:
    """Signal the holder of ``lock``. ``kill`` defaults to ``os.kill`` (injected in tests).
    Returns True if a signal was sent; False if no PID or the process is already gone."""
    kill = kill if kill is not None else os.kill
    pid = lock.holder_pid()
    if pid is None:
        return False
    try:
        kill(pid, sig)
    except ProcessLookupError:
        return False
    return True


def install_cancel_handler() -> None:
    """Install a ``SIGTERM`` handler that raises ``llmtr.errors.Cancelled``. Call once, in the
    main thread, right after acquiring the lock."""

    def _handler(signum: int, frame: object) -> None:
        raise Cancelled()

    signal.signal(signal.SIGTERM, _handler)


__all__ = ["RunLock", "cancel_running", "default_lock_path", "install_cancel_handler"]
