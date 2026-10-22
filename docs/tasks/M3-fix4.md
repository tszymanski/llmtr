# Task M3-fix4 — clipboard fallback when ydotoold is stopped

Role: **Desktop worker** (follow-up). Sandbox, clone mode. Branch: `task/M3-fix4`.
Read `CLAUDE.md`, `docs/architecture.md` §2 `keys.py`, §3.1 (fallback), and
`scripts/install-ydotool.sh`.

## Bug (user desktop test 2026-10-05; root cause confirmed by the orchestrator on the host)

With `systemctl --user stop ydotoold`, the shortcut shows "Could not send keystrokes. Is
ydotoold running?" instead of the clipboard-only fallback ("Result copied. Press Ctrl+V…").

Cause: ydotoold **does not remove its socket file when it stops**. The stale
`/run/user/1000/.ydotool_socket` stays, so `YdotoolKeySender.available()` (which only checks
`path.exists()`) returns True. `ydotool key` then fails with "failed to connect socket …:
Connection refused" → `KeySendError`.

Host measurements (ydotool 1.0.4):
- live ydotoold: `socket(AF_UNIX, SOCK_DGRAM).connect(path)` → OK; `SOCK_STREAM` → `EPROTOTYPE`
  ("Protocol wrong type for socket").
- stopped ydotoold (stale file): `SOCK_DGRAM` connect → `ConnectionRefusedError`.
- a killed ydotoold also leaves its socket file behind.

## Fix

1. `src/llmtr/keys.py` — `YdotoolKeySender.available()`: `ydotool` on PATH **and** a
   `socket.AF_UNIX`/`SOCK_DGRAM` `connect()` to the socket path succeeds (always close the
   socket, with a short timeout). Any `OSError` (refused, missing, permission, path too long)
   → False. Update the docstring to explain the stale-socket reason.
2. `scripts/install-ydotool.sh` — the user service gets
   `ExecStopPost=/bin/rm -f %t/.ydotool_socket` so a clean stop removes the file. Defence in
   depth only; the probe in (1) is the real fix.

## Tests (`tests/test_keys.py`)

Use real sockets in a **short** temp dir (`tempfile.mkdtemp(dir="/tmp")`, because AF_UNIX paths
are limited to about 108 bytes and pytest's `tmp_path` can be too long), and monkeypatch
`shutil.which` for ydotool:
- a live bound `SOCK_DGRAM` socket → `available()` True;
- a stale file (bind, then close the socket without unlinking) → False;
- missing path → False;
- ydotool not on PATH → False even with a live socket.
Keep the existing argv tests green.

## Files you may change

`src/llmtr/keys.py`, `tests/test_keys.py`, `scripts/install-ydotool.sh`,
`docs/tasks/M3-fix4.result.md`.

## Must pass

`uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`,
`bash -n scripts/install-ydotool.sh`

## Hand-back

Commit on `task/M3-fix4` (prefix `M3-fix4:`, end each message with
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`). Do not push. Short result file.
