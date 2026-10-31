# Task M17-fix1 — fix the M17 Linux acceptance findings D4–D6

Role: **Integration worker** (follow-up), claude in `sbx`, clone mode. Branch: `task/M17-fix1`.

Read first:
- `CLAUDE.md`;
- `docs/tasks/M17-linux-cursor.result.md`: the "Defects" section is the spec, with exact texts
  and suggested fixes;
- `docs/architecture.md` §2 (`errors.py` table), §7, §19 and §23.

The sandbox cannot reach `api.cursor.com`; use fakes only, as in M15.

## Change

**D4 — config errors: `~` path, and the fix first.** The GNOME bubble shows only about one line of
the summary and cannot be expanded, so the useful part must come first.
- In `src/llmtr/errors.py`, `ConfigError.__init__` builds the message as
  `f"Config error: {problem} (in {display_path(path)})"`. Use the existing `display_path`.
  `self.path` stays absolute and `self.problem` unchanged. This applies to every `ConfigError`.
- In `src/llmtr/config.py` `parse_config`, the misplaced-`engine` problem becomes
  `"put 'engine' on the first line, above any [section] (found as <table>.engine)"`.
- Expected texts:
  - `Config error: put 'engine' on the first line, above any [section] (found as notify.engine) (in ~/.config/llmtr/config.toml)`;
  - `Config error: 'notify.backend' must be one of auto, hammerspoon, osascript (in /x/config.toml)`
    for a path outside home.
- Update the docs that quote the old form: `docs/architecture.md` (the `ConfigError` row in §2, the "Bad config" row in §7 and
  the "Bad `notify.backend`" row in §19) and the README troubleshooting row for
  `engine`.

**D5 — README key file on a new machine.** In `README.md` "Cursor engine (optional)" → "API key,
Linux", the code block becomes:

```bash
mkdir -p ~/.config/llmtr
install -m 600 /dev/null ~/.config/llmtr/cursor-api-key
```

**D6 — README clipboard-only order.** In `README.md`:
- "Requirements", the `ydotool` bullet: replace "you copy by hand, trigger the shortcut, then
  paste by hand" with *"press Ctrl+C first, then the shortcut, then Ctrl+V; the shortcut uses
  whatever is on the clipboard"*.
- "Cursor engine (optional)", next to the privacy note: add *"Without ydotool, the shortcut sends
  the current clipboard to Cursor, so copy the text you want first."*
- "Troubleshooting", the "result stays on the clipboard" bullet: add the same Ctrl+C-first hint.

Out of scope: a notification body for errors, other error texts, O6–O8.

## Tests

- **D4:**
  - `HOME` set to a `tmp_path`, config path under it: the message is
    `Config error: <problem> (in ~/.config/llmtr/config.toml)`;
  - a path outside home is shown in full (the `/x/config.toml` case);
  - `self.path` stays absolute and `self.problem` is the bare problem;
  - the misplaced-`engine` message, for `[notify]` and `[cursor]`, starts with
    `Config error: put 'engine' on the first line`;
  - a CLI test: a misplaced `engine` with the shortcut path gives a critical notification whose
    summary starts with `Config error: put 'engine'`.
- Update the existing assertions that quote the old `Config error in …:` form
  (`tests/test_config.py`, `tests/test_cli.py`) and the D2 `engine` assertion. These are the only
  allowed changes to existing assertions.

## Files you may change

`src/llmtr/errors.py`, `src/llmtr/config.py`, `tests/test_config.py`, `tests/test_cli.py`,
`tests/test_cursor_key.py` (only if it needs the `HOME` fixture), `README.md`,
`docs/architecture.md` (the rows named above only), and `docs/tasks/M17-fix1.result.md`.

## Must pass

`uv run pytest`, `LLMTR_UNAME=Darwin uv run pytest`, `uv run ruff check .` and
`uv run ruff format --check .` all pass.

## Done when

1. D4, D5 and D6 are done as described, D4 with the tests listed.
2. Apart from the `Config error` text assertions named above, no existing test assertion changed.
3. `grep -rn "Config error in" src tests README.md docs/architecture.md` finds nothing.
4. All "Must pass" commands succeed in a final run after the last edit.
5. Only allowed files changed; result file written; committed on `task/M17-fix1`; `git status`
   clean.

## Reruns

Per `CLAUDE.md`:
- Run `uv run ruff format .` and `uv run ruff check --fix .` first.
- At most 3 fix-and-reruns of the same problem, and one restart.
- Record each rerun under "Reruns", or write "Reruns: none".

## Hand-back

Commit on `task/M17-fix1` (prefix `M17-fix1:`; end with a `Co-Authored-By` line naming the model
you actually run as). Do not push.

Short result file:
- what changed per item, with the new message texts;
- the test counts for both runs;
- reruns;
- deviations.
