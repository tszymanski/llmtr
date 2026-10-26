# Task M12-fix1 — fix the M12 acceptance defects D1–D5

Role: **Integration worker** (follow-up). Sandbox, clone mode. Branch: `task/M12-fix1`.
Runs **in parallel with M13-backends-cleanup** (`cli.py`, `test_cli.py`); do not touch those.
Read `CLAUDE.md` and `docs/tasks/M12-mac-acceptance.result.md` ("Defects": exact texts and
suggested fixes — they are the spec).

## Change

- **D1** `src/llmtr/errors.py`: the `accessibility` message of `MacKeySendError` becomes
  *"Keystrokes blocked. Turn on Hammerspoon in System Settings > Privacy & Security > Device Control
  and Data Access (Accessibility)."* Update every test that asserts the old text; update
  `docs/architecture.md` §14 (error classification table) and §19 (error table) and the README's
  "macOS permissions" item 1 to match. Other messages unchanged.
- **D2** `pyproject.toml`: `[build-system] requires = ["uv_build>=0.12.22,<0.14.0"]`; then
  `uv lock` (only if the lock changes) and `uv sync`. Check that `uv build` still works (into a temp
  dir, not committed).
- **D3** `README.md` "macOS notifications": "Translating…" stays while the job runs and disappears
  a few seconds after it ends; on success the pasted text is the result; errors and "Cancelled."
  get their own bubble.
- **D4** `README.md` "macOS troubleshooting": iTerm copies a selection to the clipboard by itself
  (Settings > General > Selection), so after a shortcut in iTerm the clipboard holds the selected
  text.
- **D5** `README.md` Karabiner step 4: the `` ` ``/`~` key and the key next to left Shift are
  swapped (e.g. `§` or `£` appears).

## Files you may change

`src/llmtr/errors.py` (that one message), tests that assert it (find them with grep; not
`tests/test_cli.py`, which M13 owns — if it asserts the text, say so in the result file instead),
`docs/architecture.md` (§14, §19 only), `README.md`, `pyproject.toml`, `uv.lock`,
`docs/tasks/M12-fix1.result.md`.

## Must pass

`uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`; `uv sync --locked`
succeeds; `grep -rn "Privacy & Security > Accessibility\." src tests` is empty.

## Done when

1. D1–D5 are done as described; the old D1 text appears nowhere in `src/`, `tests/`, the README
   or architecture §14/§19.
2. All "Must pass" commands succeed in a final run after the last edit.
3. Only allowed files changed; result file written; committed on `task/M12-fix1`; `git status`
   clean.

## Reruns

Per `CLAUDE.md`: run `uv run ruff format .` and `uv run ruff check --fix .` first; at most 3
fix-and-reruns of the same problem, one restart; record each under "Reruns" ("Reruns: none").

## Hand-back

Commit on `task/M12-fix1` (prefix `M12-fix1:`; `Co-Authored-By` line naming the model you actually
run as). Do not push. Short result file: what changed per defect, test output, reruns.
