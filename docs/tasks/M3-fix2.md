# Task M3-fix2 — wl-copy / xclip must not block llmtr

Role: **Desktop worker** (follow-up). Sandbox, clone mode. Branch: `task/M3-fix2`.
Read `CLAUDE.md` and `docs/architecture.md` §2 `clipboard.py`.

## Bug (found on the host desktop by the user, reproduced by the orchestrator)

Pressing `Super+Alt+T` in Slack shows "No working clipboard tool. Install wl-clipboard." although
`wl-copy`/`wl-paste` are installed and `WAYLAND_DISPLAY=wayland-0`.

Reproduction on the host: `WlClipboard().get_text()` 0.11 s OK, `clear()` 0.07 s OK, but
`WlClipboard().set_text("x")` fails after exactly 2.00 s (`SUBPROCESS_TIMEOUT`) with
`ClipboardUnavailable`.

Cause: `wl-copy` (without `--clear`) forks a background process that keeps serving the clipboard.
`_run` uses `capture_output=True`, so the child inherits our stdout/stderr pipes and
`subprocess.run` waits for EOF that never comes → `TimeoutExpired` → `ClipboardUnavailable`.
`xclip -selection clipboard` (set) forks and stays alive the same way.

The existing unit tests monkeypatch `subprocess.run`, so they could not see this.

## Fix

- `WlClipboard.set_text` and `XclipClipboard.set_text`: run the tool so no pipe is held open by the
  forked server — `stdout=subprocess.DEVNULL`, and stderr to `DEVNULL` or a temporary file (read it
  for the error message only when the exit code is non-zero). Keep the timeout; only the
  foreground process's exit is awaited.
- Leave `get_text` and `clear` behaviour unchanged unless the same issue applies (`xclip` clear
  goes through `set_text`).
- Keep the existing argv-assertion tests working (adjust them to the new call shape).

## Regression tests (`tests/test_clipboard.py`)

Add tests that run **real subprocesses** against fake `wl-copy` and `xclip` scripts in a temp dir
placed first on `PATH` (hermetic: PATH = that dir + the dir of `/bin/sh`, `sleep`, `cat`). The fake
reads stdin into a file, then forks a background child that inherits stdout/stderr and sleeps 30 s
(e.g. `( sleep 30 ) &` in sh), then exits 0. Assert `set_text` returns in well under 1 s and the
file holds the text. Kill the background sleepers in a fixture teardown (record their PID in a
file). Also test that a fake exiting 1 with a message on stderr raises `ClipboardUnavailable`.

## Files you may change

`src/llmtr/clipboard.py`, `tests/test_clipboard.py`, `docs/tasks/M3-fix2.result.md`.

## Must pass

`uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`

## Hand-back

Commit on `task/M3-fix2` (prefix `M3-fix2:`, end each message with
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`). Do not push. Short result file.
