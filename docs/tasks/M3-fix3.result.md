# Task M3-fix3 — result

## What was done

`WlClipboard.get_text` now treats an empty clipboard as `""` for every known `wl-paste` stderr
wording, matched case-insensitively as a substring: `no selection`, `no suitable type`,
`nothing is copied` (the last one is wl-clipboard 2.2.1's wording, seen 2/7 presses on the host).
The wordings live in one module-level constant, `WL_PASTE_EMPTY_CLIPBOARD_WORDINGS`, with a
comment naming which wl-clipboard versions produce each. Any other non-zero exit still raises
`ClipboardUnavailable` with the stderr text.

## Tests

Added to `tests/test_clipboard.py`:

- `test_wl_clipboard_get_text_empty_wordings_are_empty_string` — parametrized unit test
  (monkeypatched `subprocess.run`) covering all three wordings, including `Nothing is copied`
  with exit 1, plus a differently-cased variant.
- `test_wl_clipboard_get_text_real_nothing_is_copied_is_empty_string` — real-subprocess
  regression: a fake `wl-paste` script on a hermetic PATH that prints `Nothing is copied` to
  stderr and exits 1; asserts `get_text()` returns `""`.

Existing `test_wl_clipboard_get_text_other_failure_raises` (unrelated stderr, exit 1 →
`ClipboardUnavailable`) is unchanged and still passes, confirming the fix doesn't swallow real
failures.

## Test output summary

`uv run pytest`: all tests pass (one `ollama`-marked test skipped, as expected without
`LLMTR_OLLAMA_TESTS=1`).
`uv run ruff check .`: all checks passed.
`uv run ruff format --check .`: all files already formatted.

## Deviations

None. Only `src/llmtr/clipboard.py` and `tests/test_clipboard.py` were changed, as allowed.

## New dependencies

None.

## Open issues

None.
