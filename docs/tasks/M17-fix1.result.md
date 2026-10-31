# M17-fix1 — result

## Changes
- **D4:** `ConfigError` message is now `Config error: <problem> (in <display_path(path)>)`;
  `self.path` stays absolute, `self.problem` bare. Misplaced engine problem:
  `put 'engine' on the first line, above any [section] (found as <table>.engine)`.
  - `Config error: put 'engine' on the first line, above any [section] (found as notify.engine) (in ~/.config/llmtr/config.toml)`
  - `Config error: 'notify.backend' must be one of auto, hammerspoon, osascript (in /x/config.toml)`
  - Docs updated: architecture §2, §7, §19 rows; README troubleshooting `engine` row.
  - Tests: two new in `tests/test_config.py` (`~` under HOME, full path outside, path/problem
    attributes), one new CLI test (misplaced `engine` → critical notification starting
    `Config error: put 'engine'`); existing assertions updated (notify.backend in config and CLI
    tests, D2 engine assertion).
- **D5:** README key file block now has `mkdir -p ~/.config/llmtr` before `install -m 600`.
- **D6:** README ydotool bullet, Cursor privacy note and troubleshooting bullet carry the
  Ctrl+C-first hint.

## Test counts
- `uv run pytest`: 612 passed, 2 skipped.
- `LLMTR_UNAME=Darwin uv run pytest`: 612 passed, 2 skipped.
- `ruff check .` and `ruff format --check .`: clean. `grep "Config error in"`: no hits.

## Reruns
Reruns: none.

## Deviations
- The tests/test_cli.py `notify.backend` assertion uses `display_path(path)` (imported from
  `llmtr.errors`) so it holds even if tmp is under home.
- `uv run` created `.venv` with Python 3.14.4 (system default), not 3.13; not investigated
  (out of scope).
