# Task M16-fix1 — fix the M16 Mac acceptance findings D1–D3, O1, O2

Role: **Integration worker** (follow-up), claude in `sbx`, clone mode. Branch: `task/M16-fix1`.

Read first:
- `CLAUDE.md`;
- `docs/tasks/M16-mac-cursor.result.md`: the "Defects" and "Observations" sections are the spec,
  with exact texts and suggested fixes;
- `docs/architecture.md` §23.

The sandbox cannot reach `api.cursor.com`; use fakes only, as in M15.

## Change

**D1 — home path shown as `~`.** In `src/llmtr/errors.py`:
- Add a small helper `display_path(path, home=None) -> str`. It returns `~/<rest>` when `path` is
  under `home` (default `Path.home()`), else the path unchanged.
- `CursorKeyMissing` and `CursorKeyInsecure` use it in `user_message`. `self.path` stays absolute.
- Expected texts:
  - `No Cursor API key. Put it in ~/.config/llmtr/cursor-api-key (mode 600).`, plus
    ` or in the Keychain as llmtr-cursor` on macOS;
  - `Cursor API key file is readable by others. Run: chmod 600 ~/.config/llmtr/cursor-api-key`.
- `~` in the `chmod` hint is fine; the user runs it in a shell.
- A path outside home, such as a custom `XDG_CONFIG_HOME`, is shown in full.

**D2 — `engine` inside a table is an error.** In `src/llmtr/config.py` `parse_config`:
- When any table in the parsed data (e.g. `notify`, `ollama`, `cursor`, `models`, or any other
  table) has a key named `engine`, raise
  `ConfigError(source, "'engine' must be a top-level key: put it above any [section] (found as <table>.engine)")`.
- The check is for `engine` only. Other unknown keys stay ignored, as today.
- An `engine` at the top level keeps working.

**D3 — README key replace/remove and uninstall.** In `README.md`:
- **"Cursor engine (optional)" → "API key, macOS":** after the command, add the line
  *"To replace the key later, add `-U`: `security add-generic-password -U -s llmtr-cursor -a
  "$USER" -w`. To remove it: `security delete-generic-password -s llmtr-cursor`."*
- **"Cursor engine (optional)" → "Config.":** add *"`engine` is a top-level key: put it on the
  first line of `config.toml`, above any `[section]` (llmtr reports an error otherwise)."*
- **"Uninstall"** (and the macOS uninstall text if there is one): add *"The Cursor API key is not
  removed: delete `~/.config/llmtr/cursor-api-key` or the Keychain item (`security
  delete-generic-password -s llmtr-cursor`), and revoke the key in Cursor Dashboard → API Keys."*
- **Troubleshooting table:** add the D2 config error row.

**O1 — short ids.** In `src/llmtr/cursor_client.py`, `_short()` strips a leading `bc-` (agent
ids) or `run-` (run ids), then takes 6 characters. For example, `bc-9ee1a2b3…` gives `9ee1a2`.
- `cli._run_line` uses `cursor_client._short` instead of its own `[:6]`, so both places share one
  rule.
- Update the M15 tests that assert the old short form. This is the only allowed change to existing
  assertions.
- Fix architecture §23's wording if it says "first 6 characters".

**O2 — top-level help.** In `src/llmtr/cli.py`, the parser description names both engines, e.g.
*"… with a local Ollama model or a Cursor cloud agent (`--engine cursor`)."*

Out of scope: O3 (Python 3.13 in `uv tool install`) and O4 (full id in the cleanup argv).

## Tests

- **D1:**
  - `HOME` set to a `tmp_path` and a key path under it: the message shows `~/.config/…`;
  - a path outside home: shown in full;
  - `self.path` stays absolute;
  - both classes, and the macOS Keychain suffix.
- **D2:**
  - `parse_config({"notify": {"backend": "auto", "engine": "cursor"}})` → `ConfigError` naming
    `notify.engine`;
  - the same inside `[cursor]`;
  - a top-level `engine = "cursor"` with a `[notify]` table still parses.
- **O1:** `_short("bc-9ee1a2b3c4")` gives `"9ee1a2"`, `_short("run-20ab34cd")` gives `"20ab34"`,
  `_short("xyz")` gives `"xyz"`, and `_short(None)` gives `""`. The CLI run line uses the new form.
- **O2:** `build_parser().description` mentions Cursor.

## Files you may change

`src/llmtr/errors.py`, `src/llmtr/config.py`, `src/llmtr/cursor_client.py`, `src/llmtr/cli.py`,
`tests/test_cursor_key.py`, `tests/test_config.py`, `tests/test_cursor_client.py`,
`tests/test_cli.py`, `tests/test_interfaces.py`, `README.md`, `docs/architecture.md` (§23 only),
and `docs/tasks/M16-fix1.result.md`.

## Must pass

`uv run pytest`, `LLMTR_UNAME=Darwin uv run pytest`, `uv run ruff check .` and
`uv run ruff format --check .` all pass.

## Done when

1. D1, D2, D3, O1 and O2 are done as described, each with the tests listed.
2. Apart from the O1 short-id assertions, no existing test assertion changed.
3. All "Must pass" commands succeed in a final run after the last edit.
4. Only allowed files changed; result file written; committed on `task/M16-fix1`; `git status`
   clean.

## Reruns

Per `CLAUDE.md`:
- Run `uv run ruff format .` and `uv run ruff check --fix .` first.
- At most 3 fix-and-reruns of the same problem, and one restart.
- Record each rerun under "Reruns", or write "Reruns: none".

## Hand-back

Commit on `task/M16-fix1` (prefix `M16-fix1:`; end with a `Co-Authored-By` line naming the model
you actually run as). Do not push.

Short result file:
- what changed per item;
- the test counts for both runs;
- reruns;
- deviations.
