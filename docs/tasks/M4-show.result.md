# M4-show result

## What was done

- `src/llmtr/cli.py`: added `--show` to the `tone` subcommand, in a mutually exclusive argparse
  group with `--next` (so `tone --show --next` is a usage error, exit 2, for free). Added
  `_run_tone_show(config, notifier, *, stdin)`: reads `current_tone(config, load_state())`,
  computes `(index, total)` from `config.tone.presets`, and either notifies
  `"Tone: <name> (<i>/<n>)"` with the instruction as body, or (with `--stdin`) prints
  `"<name> (<i>/<n>): <instruction>"` to stdout. No lock, clipboard, keys, client or `save_state`
  call. `tone --next` was left as-is — its notification already passed the instruction as the
  body, so no change was needed there.
- `install.sh`: added a fifth parallel-array slot `tone-show` (`<Shift><Super><Alt>t`,
  `tone --show`, name `llmtr tone --show`). `register_shortcuts`/`uninstall_shortcuts` already
  work generically off `SLOTS`/`llmtr_paths`, so the upgrade path (4 -> 5 entries, no duplicates)
  and `--uninstall` (removes all five) needed no extra code, only the array change and the final
  echo message.
- `tests/test_install.py`: `LLMTR_*` constants extended to five entries; added
  `OLD_LLMTR_PATHS` (the old four-slot list) and
  `test_install_upgrades_old_four_entry_list_to_five_without_duplicating`, which seeds the fake
  `gsettings` state with the old four-entry `custom-keybindings` array plus another app's
  shortcut, runs a plain install, and checks the fifth entry is added once with the right
  name/binding and nothing is duplicated. Renamed two "four" tests to "five" to match.
- `tests/test_cli.py`: added a `_three_preset_config_file` helper (team + formal + concise) and
  six tests: `--show` notification title/body with 3 presets and a stored tone; fallback when the
  stored tone is unknown (falls back to `current_tone`'s own fallback, index 1); `--show --stdin`
  output; `--show --next` -> exit 2; state file unchanged by `--show` (including the unknown-name
  case); and a test that monkeypatches `make_clipboard`/`YdotoolKeySender`/`OllamaClient` to raise
  if called, proving `--show` never touches them.
- `README.md`: shortcuts table gets the `Shift+Super+Alt+T` / `llmtr tone --show` row; new "Tone
  presets" section with a `[[tone.preset]]` example and how `--next`/`--show` behave; "four" ->
  "five" in the three places describing the installer's shortcut count.

## Test output summary

- `uv run pytest`: 194 passed, 1 skipped (the `@pytest.mark.ollama` test, as expected without
  `LLMTR_OLLAMA_TESTS=1`).
- `uv run ruff check .`: all checks passed.
- `uv run ruff format --check .`: all files already formatted.
- `bash -n install.sh`: OK.
- Manual check: `llmtr tone --help` shows `[--next | --show]`; `llmtr tone --show --stdin` with a
  3-preset config printed `team (1/3): <instruction>`; `llmtr tone --show --next` failed with
  argparse's own `error: argument --next: not allowed with argument --show` and exit 2.

## Deviations

None. `build_parser`'s mutual-exclusion change is the one the contract pre-approved.

## New dependencies

None.

## Open issues

None.
