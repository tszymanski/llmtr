# Task M11-fix2 — empty arrays under `set -u` on bash < 4.4

Role: **Integration worker** (follow-up). Sandbox, clone mode. Branch: `task/M11-fix2`.
Read `CLAUDE.md`, `install.sh`, `scripts/install-macos.sh`.

## Problem (CI `test-macos`, 2026-10-26)

`tests/test_install.py::test_install_is_idempotent_on_second_run` fails on the macOS runner: after
an install with no other custom shortcuts, the stored `custom-keybindings` value is empty.

Cause (confirmed by the orchestrator in Docker `bash:3.2`): `install.sh` runs with `set -u`. In bash
< 4.4, expanding an **empty** array (`"${others[@]}"`) under `set -u` is an "unbound variable"
error. In `register_shortcuts` it happens inside `"$(array_literal "${others[@]}" "${llmtr[@]}")"`,
so only the subshell dies and `install.sh` writes an **empty** keybinding list (wiping custom
shortcuts) and exits 0. `uninstall_shortcuts` has the same pattern. The macOS runner's `bash` is
3.2; Linux runners have bash 5, so Linux CI never sees it. Real users on old distros (bash 4.2/4.3)
would lose their shortcuts.

```
$ docker run --rm bash:3.2 bash -c 'set -u; a=(); x="$(printf "[%s]" "${a[@]}")"; echo "rc=$? x=[$x]"'
bash: a[@]: unbound variable
rc=1 x=[]
```

## Change

- `install.sh`: every expansion of an array that can be empty uses the bash-3.2-safe form
  `${arr[@]+"${arr[@]}"}` (check all of them, not only the two above; `for x in "${arr[@]}"` loops
  over possibly-empty arrays too). No other behaviour change.
- `scripts/install-macos.sh`: audit the same way; fix only if an array can be empty there.
- `tests/test_install.py`: a regression test that does not depend on the runner's bash version,
  e.g. a test that greps `install.sh` (and `install-macos.sh`) for unguarded `"${name[@]}"`
  expansions of arrays declared empty, **or** one that runs `install.sh` with a `bash` from PATH
  that is a fake wrapper turning on bash-3.2-like behaviour if you find a reliable way. Keep it
  simple and deterministic; explain the choice in the result file.

## Files you may change

`install.sh`, `scripts/install-macos.sh`, `tests/test_install.py`, `tests/test_install_macos.py`
(only if `install-macos.sh` changes), `docs/tasks/M11-fix2.result.md`.

## Must pass

`uv run pytest`, `LLMTR_UNAME=Darwin uv run pytest`, `uv run ruff check .`,
`uv run ruff format --check .`, `bash -n install.sh scripts/install-macos.sh scripts/install-ydotool.sh`.

## Done when

1. No unguarded expansion of a possibly-empty array is left in `install.sh` (and
   `install-macos.sh`); the regression test exists and passes.
2. All "Must pass" commands succeed in a final run after the last edit.
3. Only allowed files changed; result file written; committed on `task/M11-fix2`; `git status`
   clean.

## Reruns

Per `CLAUDE.md`: run `uv run ruff format .` and `uv run ruff check --fix .` first; at most 3
fix-and-reruns of the same problem, one restart; record each under "Reruns" ("Reruns: none").

## Hand-back

Commit on `task/M11-fix2` (prefix `M11-fix2:`; `Co-Authored-By` line naming the model you actually
run as). Do not push. Short result file: every expansion changed (file:line), the test and why,
test output, reruns.
