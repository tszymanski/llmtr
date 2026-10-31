# M16-fix1 — result

## What changed
- **D1:** `errors.display_path(path, home=None)` returns `~/<rest>` under home, else the path
  unchanged. `CursorKeyMissing` and `CursorKeyInsecure` use it; `self.path` stays absolute.
  Not added to `__all__` (the interface test lists it exactly).
- **D2:** `config.parse_config` raises `ConfigError` ("'engine' must be a top-level key: put it
  above any [section] (found as <table>.engine)") when any table has an `engine` key. Other
  unknown keys are still ignored.
- **D3:** README: `-U` replace and delete steps, top-level `engine` note, uninstall note about
  the Cursor key, new troubleshooting row.
- **O1:** `cursor_client._short` strips `bc-`/`run-` then takes 6 characters; `cli._run_line`
  uses it. Architecture §23 wording fixed. One M15 assertion in `tests/test_cli.py` changed
  (`agent=7a1f00`).
- **O2:** top-level parser description names the Cursor engine.

## Tests
- `uv run pytest`: 609 passed, 2 skipped.
- `LLMTR_UNAME=Darwin uv run pytest`: 609 passed, 2 skipped.
- `uv run ruff check .` and `uv run ruff format --check .`: clean.
- New tests: D1 (3), D2 (3), O1 (1), O2 (1).

## Reruns
Reruns: none.

## Deviations
None. New dependencies: none.
