# Task M3-fix1 — restore the clipboard when capture is interrupted

Role: **Desktop worker** (follow-up). Sandbox, clone mode. Branch: `task/M3-fix1`.
Read `CLAUDE.md`, `docs/architecture.md` §3.4 and §7 ("Second press … clipboard restored").

## Bug (found by the M4 re-review, confirmed by the orchestrator)

`src/llmtr/selection.py` `capture_selection`: after `clipboard.clear()` only `KeySendError` is
handled. A `Cancelled` raised by the SIGTERM handler during `sleep(timing.start_delay)` or the
copy poll loop (second press within ~1.25 s) — or any other exception there — leaves the clipboard
empty: `saved` is never restored, and `cli.run_shortcut` cannot restore it because `captured` is
still `None`.

## Fix

In `capture_selection`, once `clipboard.clear()` has run, restore `saved` (when non-empty) on
**any** exception before re-raising (`BaseException`, so `Cancelled`/`KeyboardInterrupt` are
covered), keeping today's behaviour for `KeySendError` and `EmptySelection`. Update the docstring.

## Tests (`tests/test_selection.py`)

- `Cancelled` raised from the injected `sleep` during `start_delay` → clipboard restored, error
  re-raised.
- `Cancelled` raised from `sleep` inside the poll loop → same.
- An unexpected `RuntimeError` from `keys.send` → same.
- Empty `saved` → nothing written back.

## Files you may change

`src/llmtr/selection.py`, `tests/test_selection.py`, `docs/tasks/M3-fix1.result.md`.

## Must pass

`uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`

## Hand-back

Commit on `task/M3-fix1` (prefix `M3-fix1:`, end each message with
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`). Do not push. Short result file.
