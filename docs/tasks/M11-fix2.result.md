# M11-fix2 — result

Worker: Integration (Claude Opus 5.5). Branch `task/M11-fix2`.

## Done

Every expansion of an array declared empty (`=()`) in `install.sh` now uses the bash-3.2-safe
form `${arr[@]+"${arr[@]}"}`:

- `install.sh:92` — `for lp in "${llmtr[@]}"` in `other_keybinding_paths` (filled from
  `SLOTS`, so never empty in practice, but declared empty; guarded for consistency).
- `install.sh:193` — `array_literal "${others[@]}" "${llmtr[@]}"` in `register_shortcuts`
  (the CI failure: `others` is empty when the user has no other custom shortcuts).
- `install.sh:209` — `array_literal "${others[@]}"` in `uninstall_shortcuts` (line split in two
  to stay within the line width).
- `install.sh:99-100` — a two-line comment above `array_literal` explaining the form.

Left unchanged: `"${SLOTS[@]}"` (line 74) and `"${!SLOTS[@]}"` (line 195). `SLOTS` is a fixed,
non-empty literal, so these can't hit the bug. `"$@"` is not affected by `set -u` in bash 3.2.

`scripts/install-macos.sh`: audited, no arrays (only `"$@"`), no change.

## Regression test (`tests/test_install.py`)

- `test_possibly_empty_arrays_are_expanded_bash32_safe[install.sh / install-macos.sh]`: a static
  check. It finds every array declared empty (`name=()`, including `local -a a=() b=()`), drops the
  guarded `${name[@]+"${name[@]}"}` forms, and fails if any `${name[@]}` / `${name[*]}` is left.
- `test_empty_array_check_catches_unguarded_expansion`: a self-test so the checker can't silently
  match nothing.

Why static: the result is the same whatever bash the runner has (Linux CI has bash 5, macOS has
3.2). A fake `bash` wrapper can't reproduce the bash < 4.4 behaviour, and `docker run bash:3.2`
is not available here (Docker Hub gives 403 in the sandbox). Checked against the pre-fix
`install.sh`: the test fails and lists all 4 old unguarded expansions (`llmtr` at 92, `others`
and `llmtr` at 191, `others` at 206).

Not checked here: running the fixed script under a real bash 3.2. The macOS CI job
(`test_install_is_idempotent_on_second_run`) is the end-to-end check.

## Test output (final run after the last edit)

- `uv run pytest`: 474 passed, 1 skipped
- `LLMTR_UNAME=Darwin uv run pytest`: 474 passed, 1 skipped
- `uv run ruff check .`: All checks passed
- `uv run ruff format --check .`: 110 files already formatted
- `bash -n install.sh scripts/install-macos.sh scripts/install-ydotool.sh`: ok (each also checked
  separately)

## Deviations

None. Only `install.sh`, `tests/test_install.py` and this file changed.

## Reruns

Reruns: none.

## New dependencies

None (`re` is in the standard library).

## Open issues

- Not checked on a real bash 3.2 here. Confirm with the macOS CI job.
