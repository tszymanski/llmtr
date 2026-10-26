# Task M13-backends-cleanup — route the Linux wiring through backends.py

Role: **Desktop worker** (follow-up, user-approved 2026-10-26). Sandbox, clone mode.
Branch: `task/M13-backends-cleanup`. Runs **in parallel with M12-fix1**; do not touch its files
(`errors.py`, README, architecture, `pyproject.toml`, `uv.lock`).
Read `CLAUDE.md`, `docs/architecture.md` §12 (platform selection) and
`docs/tasks/M10-macos-backends.result.md` ("Deviations").

## Problem

M10 kept the Linux wiring in `cli.py` (`_make_desktop`, `_make_notifier` build
`NotifySendNotifier`, `make_clipboard`, `YdotoolKeySender`, `focused_app_id` from `cli`'s own
imports) because the v1 tests in `tests/test_cli.py` monkeypatch those names on `cli`. So the Linux
branch in `backends.py` is tested but unused, and the platform choice lives in two places, against
§12 ("one place").

## Change

- `src/llmtr/cli.py`: get the notifier and desktop for **every** platform from `backends.py`
  (`make_notifier`, `make_desktop`); remove `cli`'s private Linux duplicates and imports that are
  no longer used.
- `tests/test_cli.py`: change the v1 tests to patch the Linux backends where they are now looked
  up (e.g. `llmtr.backends.NotifySendNotifier`), or better, inject a fake `Desktop`/notifier through
  the existing `desktop=`/parameters. Keep every test's intent and assertions; do not delete
  tests. The autouse platform fixture stays.
- `src/llmtr/backends.py` only if a small change is needed for injection (no behaviour change).
- Behaviour on Linux and macOS must not change: same messages, exit codes, log lines.

## Files you may change

`src/llmtr/cli.py`, `tests/test_cli.py`, `src/llmtr/backends.py` (minimal),
`tests/test_backends.py` (only if `backends.py` changes), `docs/tasks/M13-backends-cleanup.result.md`.

## Must pass

`uv run pytest`, `LLMTR_UNAME=Darwin uv run pytest` (macOS runner simulation),
`uv run ruff check .`, `uv run ruff format --check .`

## Done when

1. `cli.py` no longer imports `NotifySendNotifier`, `YdotoolKeySender`, `make_clipboard` or
   `focused_app_id` (check with grep), and both platforms go through `backends.py`.
2. The number of tests in `tests/test_cli.py` is not lower than before; all pass.
3. All "Must pass" commands succeed in a final run after the last edit.
4. Only allowed files changed; result file written; committed on `task/M13-backends-cleanup`;
   `git status` clean.

## Reruns

Per `CLAUDE.md`: run `uv run ruff format .` and `uv run ruff check --fix .` first; at most 3
fix-and-reruns of the same problem, one restart; record each under "Reruns" ("Reruns: none").

## Hand-back

Commit on `task/M13-backends-cleanup` (prefix `M13-backends-cleanup:`; `Co-Authored-By` line naming
the model you actually run as). Do not push. Short result file: what moved, test count
before/after, test output, reruns.
