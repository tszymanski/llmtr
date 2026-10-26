# M13-backends-cleanup — result

## What moved

- `src/llmtr/cli.py`: removed `_make_notifier` / `_make_desktop` and the imports of
  `NotifySendNotifier`, `YdotoolKeySender`, `make_clipboard`, `focused_app_id`, `LINUX_PASTE_HINT`.
  `main` and `run_shortcut` now call `backends.make_notifier` / `backends.make_desktop` for both
  platforms (grep for the four names in `cli.py` is empty).
- `tests/test_cli.py`: the v1 tests now patch the names where they are looked up
  (`backends.NotifySendNotifier`, `backends.make_clipboard`, `backends.YdotoolKeySender`; fakes take
  an optional `env`). The macOS wiring test patches `backends` directly. Intent and assertions are
  unchanged; the autouse platform fixture stays.
- `backends.py` and `tests/test_backends.py` unchanged. No behaviour change on either platform.

## Tests

`tests/test_cli.py`: 55 tests before, 55 after. Whole suite: 471 passed, 1 skipped (both runs).

```
uv run pytest                     -> 471 passed, 1 skipped
LLMTR_UNAME=Darwin uv run pytest  -> 471 passed, 1 skipped
uv run ruff check .               -> All checks passed!
uv run ruff format --check .      -> 106 files already formatted
```

## Reruns

none

## New dependencies

None.

## Open issues

None.
