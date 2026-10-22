# Task M3-fix4 — result

## What was done

- `src/llmtr/keys.py`: `YdotoolKeySender.available()` now requires `ydotool` on PATH **and** a
  successful `AF_UNIX`/`SOCK_DGRAM` `connect()` to the ydotoold socket (0.2 s timeout,
  `SOCKET_PROBE_TIMEOUT`; the probe socket is always closed via `with`). Any `OSError`
  (refused/stale, missing, permission, path too long) → `False`. Docstring explains that
  ydotoold leaves a stale socket file when stopped or killed. The local variable `socket` in
  `__init__` was renamed to `path` so it does not shadow the new `socket` import.
- `scripts/install-ydotool.sh`: the user unit gets `ExecStopPost=/bin/rm -f %t/.ydotool_socket`
  (defence in depth; the probe is the real fix).

## Tests (`tests/test_keys.py`)

Real sockets in a short `tempfile.mkdtemp(dir="/tmp")` dir, `shutil.which` monkeypatched:
live bound DGRAM socket → True; stale socket file (bind, close, no unlink) → False; regular
file → False; missing path → False; over-long path → False; ydotool not on PATH with a live
socket → False. The old `available()` tests that used a plain file as "socket" were replaced
(a plain file is now correctly unavailable). Argv/send tests unchanged and green (one local
variable renamed from `socket` to `sock_path`).

## Test output summary

- `uv run pytest`: all passed, 1 skipped (`ollama` marker).
- `uv run ruff check .`: all checks passed.
- `uv run ruff format --check .`: 65 files already formatted.
- `bash -n scripts/install-ydotool.sh`: OK.

## Deviations

None. Only the allowed files were changed.

## New dependencies

None (`socket` is stdlib).

## Open issues

- Not tested against a real ydotoold in the sandbox; the host should check
  `systemctl --user stop ydotoold` → "Result copied. Press Ctrl+V…" and that a live daemon still
  pastes. The existing unit file on the host only picks up `ExecStopPost` after re-running
  `scripts/install-ydotool.sh`.
- `uv` in this sandbox created the venv with CPython 3.14.4 (no 3.13 here); tests pass on it.
