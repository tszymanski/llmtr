# Task M3-fix3 — empty clipboard reported as "Nothing is copied"

Role: **Desktop worker** (follow-up). Sandbox, clone mode. Branch: `task/M3-fix3`.
Read `CLAUDE.md` and `docs/architecture.md` §2 `clipboard.py`, §3.1.

## Bug (user desktop test; debug log captured by the orchestrator)

Shortcuts intermittently fail with "No working clipboard tool. Install wl-clipboard." Hidden
detail: `ClipboardUnavailable('Nothing is copied')` raised from `WlClipboard.get_text` inside the
`capture_selection` poll loop (2 of 7 presses at 17:22).

`capture_selection` clears the clipboard, sends Ctrl+C, then polls `get_text()`. If it polls
before the app has copied, `wl-paste` (wl-clipboard **2.2.1**, Ubuntu 25.10) prints
`Nothing is copied` to stderr and exits **1**. `WlClipboard.get_text` treats only
"No selection" / "No suitable type" as empty, so it raises instead of returning `""`.
Confirmed on the host: `wl-copy --clear; wl-paste --no-newline --type text` → stderr
`Nothing is copied`, exit 1.

## Fix

`WlClipboard.get_text`: treat an empty clipboard as `""` for every known wl-paste wording —
`Nothing is copied`, `No selection`, `No suitable type` (case-insensitive substring match; keep
the list in one module-level constant with a comment naming the wl-clipboard versions). Any other
non-zero exit still raises `ClipboardUnavailable` with the stderr text.

## Tests (`tests/test_clipboard.py`)

- Unit (monkeypatched `subprocess.run`): each wording, incl. `Nothing is copied` with exit 1 →
  `""`; an unknown error → `ClipboardUnavailable`.
- Real-subprocess regression (same hermetic fake-PATH approach as the M3-fix2 tests): a fake
  `wl-paste` that prints `Nothing is copied` to stderr and exits 1 → `get_text()` returns `""`.

## Files you may change

`src/llmtr/clipboard.py`, `tests/test_clipboard.py`, `docs/tasks/M3-fix3.result.md`.

## Must pass

`uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`

## Hand-back

Commit on `task/M3-fix3` (prefix `M3-fix3:`, end each message with
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`). Do not push. Short result file.
