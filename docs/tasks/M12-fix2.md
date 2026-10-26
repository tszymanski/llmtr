# Task M12-fix2 — one bubble on cancel (macOS)

Role: **Mac fix worker**: a Claude Code session on the user's Mac, run **interactively with the
user present** (normal permission mode, no sandbox), as in M8/M12. In the existing clone:
`git checkout main && git pull`, then branch `task/M12-fix2`. Unlike M12, this task **may change
code** (files below), because the bug can only be reproduced on the Mac.
Read `CLAUDE.md`, `docs/architecture.md` §16 (Lua side) and §18, `src/llmtr/cli.py`
(`run_shortcut`, the `Cancelled` branch), `src/llmtr/macos_notify.py`, `macos/llmtr.lua.in`, and
`docs/tasks/M12-mac-acceptance.result.md` (A7, A8, and the note after D5).

## Problem

M12 A8: during a long translate, a second ⌃⌥T cancels it correctly, but the user sees **two
bubbles**: "Translating…" stays and a separate "Cancelled." appears. Wanted (user, 2026-10-26):
**one bubble per cancelled job** — "Translating…" is replaced by "Cancelled.", which then
disappears like other bubbles; the second press shows nothing of its own.

By design this should already happen: the cancelled (first) process catches `Cancelled` and
notifies "Cancelled." with **its own** `LLMTR_RUN_ID`, and the Lua handler replaces the bubble
stored for that id. The second process only calls `cancel_running` and returns without notifying.
So something differs on the real Mac. Hypotheses to check (not an exhaustive list):

1. The "Cancelled." URL arrives with a different `id` than "Translating…" (e.g. env not passed,
   `os.getpid()` fallback, string/number key mismatch in Lua).
2. The Lua `notify` action creates the new bubble but the old one is not withdrawn (e.g. the
   stored object is missing or already replaced by the `onExit` timer path), or macOS keeps the
   withdrawn banner on screen / in Notification Center.
3. The second process sends a notification after all (some path in `main`/`run_shortcut`).
4. The first process is killed before its `open -g` call completes, and "Cancelled." comes from
   somewhere else.

## Steps

1. **Reproduce** with the installed version (`./install.sh` from current `main`) and a long text
   (`spike/macos/texts/en_long.txt`): **[user]** select, ⌃⌥T, ⌃⌥T again within 5 s. Record what
   the user sees.
2. **Instrument** to find which process sends which bubble: temporary logging in the **installed**
   `~/.hammerspoon/llmtr.lua` (e.g. `print` of `action`, `id`, `summary` per URL event and of each
   `onExit` with its id and exit code; read in the Hammerspoon console) and `llmtr log`
   (`LLMTR_LOG_LEVEL=DEBUG` if useful). Do not commit the instrumentation.
3. **Find the cause**, write it down with evidence (log lines), then **fix** it in the repo files
   below, with a unit test where the cause is in Python (fakes only), or a template text test
   where it is in Lua (as `tests/test_install_macos.py` already does).
4. **Verify on the Mac**: `./install.sh`, *Reload Config*, repeat step 1 three times: one bubble
   each time ("Translating…" → "Cancelled.", gone after ~8 s), nothing pasted, clipboard restored.
   Also re-check that a normal translate (no cancel) and an error (e.g. Secure Input in a password
   field) still show one bubble each.
5. **Clean up** the instrumentation (reinstall from the fixed repo).

## Files you may change

`macos/llmtr.lua.in`, `src/llmtr/cli.py` (the cancel/notify path only), `src/llmtr/macos_notify.py`,
`tests/test_cli.py`, `tests/test_macos_notify.py`, `tests/test_install_macos.py` (Lua template text
tests), `README.md` ("macOS notifications": drop "and 'Cancelled.' get their own bubble" once
fixed), `docs/architecture.md` (§16/§18, only if the design changes),
`docs/tasks/M12-fix2.result.md`. Linux behaviour must not change.

## Must pass

`uv run pytest`, `LLMTR_UNAME=Darwin uv run pytest`, `uv run ruff check .`,
`uv run ruff format --check .`, `bash -n install.sh scripts/install-macos.sh`.

## Done when

1. The cause is identified with evidence (log lines) in the result file.
2. Step 4 passes 3/3 on the Mac for cancel, plus one normal translate and one error, one bubble
   each.
3. All "Must pass" commands succeed in a final run after the last edit.
4. Instrumentation removed; the installed `~/.hammerspoon/llmtr.lua` is the one generated from the
   committed template.
5. Result file written; committed on `task/M12-fix2`; branch pushed; `git status` clean.

If the cause turns out to be macOS itself (e.g. withdrawn banners cannot be removed from the
screen), stop: record the evidence and the options (e.g. no "Translating…" banner, or an
`hs.alert` instead), commit the result file only, push, and finish — the user decides.

## Reruns

Per `CLAUDE.md`: run `uv run ruff format .` and `uv run ruff check --fix .` first; at most 3
fix-and-reruns of the same problem (including Mac verification attempts that fail for the same
reason), one session restart. A check that only passes on a retry counts as failed. Record each
under "Reruns" ("Reruns: none").

## Rules

Ask before installing anything; never `sudo`. No absolute home paths, usernames or scratchpad
paths in committed files (the repo is public).

## Hand-back

Result file sections: **Reproduction**, **Evidence** (log lines), **Cause**, **Fix** (files,
tests), **Mac verification** (table: run × bubbles seen), **Reruns**, **Open issues**.
Commit on `task/M12-fix2` (prefix `M12-fix2:`; `Co-Authored-By` line naming the model you actually
run as), then **push only that branch**: `git push -u origin task/M12-fix2`. Never push `main`.
