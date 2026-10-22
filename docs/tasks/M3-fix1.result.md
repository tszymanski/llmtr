# M3-fix1 result — restore the clipboard when capture is interrupted

## What was done

`capture_selection` (`src/llmtr/selection.py`) now wraps `sleep(timing.start_delay)`,
`keys.send(pair.copy)` and the copy poll loop in a single `try: ... except BaseException:`
block, keyed off `saved = clipboard.get_text()` captured just before `clipboard.clear()`. Any
exception raised in that span — `Cancelled` from the SIGTERM handler during either `sleep` call,
`KeySendError`, the `EmptySelection` raised when the poll times out, or an unexpected error such
as `RuntimeError` — now restores `saved` (when non-empty) before re-raising. Replaced the two
separate ad hoc restores (around `keys.send` and around the timeout check) with this one handler;
behaviour for `KeySendError` and `EmptySelection` is unchanged. Updated the docstring to describe
the new blanket restore instead of the two special cases.

## Tests added (`tests/test_selection.py`)

- `test_capture_selection_cancelled_during_start_delay_restores_and_propagates`
- `test_capture_selection_cancelled_during_poll_restores_and_propagates`
- `test_capture_selection_unexpected_error_restores_and_propagates` (`RuntimeError` from `keys.send`)
- `test_capture_selection_cancelled_with_nothing_saved_does_not_restore`

## Test output summary

`uv run pytest`: 249 passed, 1 skipped (the skipped test is the pre-existing `@pytest.mark.ollama`
test, skipped because `LLMTR_OLLAMA_TESTS` is unset).
`uv run ruff check .`: all checks passed.
`uv run ruff format --check .`: 46 files already formatted.

## Deviations

None.

## New dependencies

None.

## Open issues

None.
