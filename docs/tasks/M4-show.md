# Task M4-show — `llmtr tone --show` and its shortcut

Role: **Integration worker** (follow-up). Sandbox, clone mode. Branch: `task/M4-show`.
Read `CLAUDE.md`, `docs/architecture.md` §2 `cli.py` and §3.2, `install.sh`, `README.md`.

## Why

The user wants to see the current tone without rewriting text or switching it. They now have three
presets in `~/.config/llmtr/config.toml`: `team`, `formal`, `concise`.

## Behaviour

- New flag on the `tone` subcommand: `--show`. The orchestrator approves the change to
  `build_parser` (it was frozen in M1).
- `llmtr tone --show` sends one notification. Title: `Tone: <name> (<i>/<n>)`, for example
  `Tone: formal (2/3)`. Body: the preset's instruction. Exit code 0. No lock, clipboard, keys or
  Ollama call, and the state file is not modified.
- `llmtr tone --show --stdin` prints `<name> (<i>/<n>): <instruction>` to stdout instead of
  notifying, for terminal use.
- `--show` with `--next` → usage error (exit 2), via an argparse mutually exclusive group.
- The current tone comes from the state file through the existing config functions (do not
  change `config.py`). If the stored tone no longer exists in config, show what `current_tone`
  falls back to.
- Keep `tone --next` as it is. Make its notification body the new preset's instruction too, if
  that is a one-line change.

## Installer

- Add a fifth shortcut slot `tone-show`: `<Shift><Super><Alt>t` → `<abs llmtr> tone --show`,
  name `llmtr tone --show`. Re-runs stay idempotent: an existing install with four entries
  upgrades to five, never duplicates. `--uninstall` removes all five.
- Update `tests/test_install.py` for five entries, including an upgrade test that starts with the
  old four-entry list.
- README: the shortcuts table gets the new row, plus a short "Tone presets" section showing
  `[[tone.preset]]` and how `--next` / `--show` work.

## Tests (`tests/test_cli.py`)

`--show` notification title/body with 3 presets and a stored tone; fallback when the stored tone
is unknown; `--show --stdin` output; `--show --next` → exit 2; state file unchanged; no clipboard,
keys or client used (fakes assert nothing was called).

## Files you may change

`src/llmtr/cli.py`, `tests/test_cli.py`, `install.sh`, `tests/test_install.py`, `README.md`,
`docs/tasks/M4-show.result.md`.

## Must pass

`uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `bash -n install.sh`

## Hand-back

Commit on `task/M4-show` (prefix `M4-show:`, end each message with
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`). Do not push. Short result file.
