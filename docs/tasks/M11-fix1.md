# Task M11-fix1 — Linux installer tests must force the Linux branch

Role: **Integration worker** (follow-up). Sandbox, clone mode. Branch: `task/M11-fix1`.
Read `CLAUDE.md` and `docs/architecture.md` §17.

## Problem (CI, 2026-10-26)

On the `test-macos` CI job (macOS runner) 14 tests in `tests/test_install.py` fail, e.g.
`test_uninstall_removes_only_llmtr_shortcuts_and_uv_tool`:
`install-macos.sh: line 46: rm: command not found`, return code 127. These tests check the
**Linux** installer but do not set `LLMTR_UNAME`, so on macOS `uname -s` is `Darwin` and
`install.sh` dispatches to `scripts/install-macos.sh`, which fails on the tests' restricted PATH.
Reproduced on Linux with `LLMTR_UNAME=Darwin uv run pytest tests/test_install.py` → the same
14 failures.

## Change

- `tests/test_install.py`: the helper that builds the subprocess env (around line 171) sets
  `env["LLMTR_UNAME"] = "Linux"`, with a one-line comment why. Nothing else in the tests changes.
- Add one test that proves it: with `LLMTR_UNAME=Darwin` in the **outer** environment
  (`monkeypatch.setenv`), a Linux installer test still takes the Linux path (e.g. a `--dry-run`
  prints the gsettings commands).
- If `uname` in the minimal tool list is no longer needed, leave it (harmless).

## Files you may change

`tests/test_install.py`, `docs/tasks/M11-fix1.result.md`.

## Must pass

- `uv run pytest`
- `LLMTR_UNAME=Darwin uv run pytest tests/test_install.py tests/test_install_macos.py` (simulates the
  macOS runner; must be all green)
- `uv run ruff check .`, `uv run ruff format --check .`

## Done when

1. Both pytest commands above pass, and ruff is clean, in a final run after the last edit.
2. Only the two allowed files changed; result file written; committed on `task/M11-fix1`;
   `git status` clean.

## Reruns

Per `CLAUDE.md`: at most 3 fix-and-reruns of the same problem, one restart; record each under
"Reruns" ("Reruns: none" if none). Run `uv run ruff format .` and `uv run ruff check --fix .` first.

## Hand-back

Commit on `task/M11-fix1` (prefix `M11-fix1:`; `Co-Authored-By` line naming the model you actually
run as). Do not push. Short result file: change, test output, reruns.
