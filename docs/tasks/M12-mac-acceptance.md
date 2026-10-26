# Task M12-mac-acceptance — real install and acceptance on the test Mac

Role: **Mac acceptance worker**: a Claude Code session on the user's Mac, run **interactively with
the user present** (normal permission mode, no `--dangerously-skip-permissions`, no sandbox), as in
M8. Use the existing clone: `git checkout main && git pull`, then create branch `task/M12-mac-acceptance`.
Read `CLAUDE.md`, `docs/proposal.md` ("macOS support (v2)"), `README.md` (macOS section — the user
follows it as a new user would), `docs/architecture.md` §16–19, and `docs/tasks/M11-macos-install.result.md`
("Mac checklist for M12").

Test Mac: MacBook Pro M1, 16 GB, macOS 27.0.1; Hammerspoon 1.1.1, Karabiner 16.3.0, models
`translategemma:12b`, `gemma3`, `gemma3:12b` (from M8).

## Goal

Prove that v2 works on the real Mac by installing it from the repo **as the README says** and
walking through the checklist below with the user. **This is acceptance, not development: do not
change `src/`, `tests/`, `scripts/`, `install.sh`, `macos/` or `README.md`.** Every defect goes into
the result file with exact steps, output and a suggested fix; the orchestrator turns them into fix
tasks.

## Ground rules

- Ask before every install or permission change; never `sudo`.
- Steps marked **[user]** need the user. Say exactly what to press or click and what should
  happen, wait, then record what happened.
- Record every dialog and Settings screen with its exact wording.
- Before A1, note the state you will change (`~/.hammerspoon/`, Settings entries for Hammerspoon,
  `~/.config/llmtr/`) so A12 can restore what the user wants restored.
- Do not write absolute home paths, usernames or session scratchpad paths into committed files
  (the repo is public); use `~` or `$HOME`.

## Checklist

Record each item as **PASS / FAIL / PARTIAL** with a one-line note; timings in seconds, two decimals.

- **A1 — Install (bash 3.2).** `/bin/bash --version` (expect 3.2). `./install.sh --dry-run`, then
  `./install.sh`. `~/.hammerspoon/llmtr.lua` holds the real absolute `llmtr` path on the
  `local LLMTR = "…"` line (valid Lua); `init.lua` has `require("llmtr")` exactly once; run
  `./install.sh` a second time and check again. The printed steps match the README.
- **A2 — Settings panes.** **[user]** Do the three `x-apple.systempreferences:` links open the right
  panes on macOS 27 (Accessibility / "Device Control and Data Access", Automation, Notifications)?
  If one opens the wrong pane, find the right URL and record it.
- **A3 — Permissions missing.** With Hammerspoon's Accessibility **off**: select text in Notes, press
  ⌃⌥T → the message names Hammerspoon and Accessibility; the clipboard is unchanged. Same with
  Automation (System Events) off, if the user agrees to toggle it. Then grant both; record the
  first-⌘C dialog text and compare it with the README.
- **A4 — Shortcuts.** **[user]** After *Reload Config*: each of ⌃⌥T, ⌃⌥G, ⌃⌥R, ⇧⌃⌥R, ⇧⌃⌥T in Notes
  does the right thing (translate, fix, tone, next tone, show tone). Also with Caps Lock (Karabiner)
  for ⌃⌥T.
- **A5 — Apps.** **[user]** Translate a short Polish sentence in Teams, Chrome, VS Code, Notes,
  Terminal and iTerm: the selection is replaced (terminals: pasted at the cursor), the old clipboard
  is restored. Table app × result, with hotkey → paste time from `llmtr log`.
- **A6 — Polish text.** A Polish → English and an English → Polish run started by the shortcut:
  no garbled characters in either direction (ąęłóżźćńś; M8 locale bug).
- **A7 — Notifications.** "Translating…" appears under Hammerspoon, is replaced by the result or
  error, and disappears after ~8 s (~15 s after an error). Measure the delay between `llmtr`
  sending a notification and the bubble appearing (e.g. a stopwatch on the user's side, or log
  timestamps vs. the user's report). Try `[notify] backend = "osascript"` once and compare.
- **A8 — Cancel.** **[user]** Start a long English → Polish translate (~220 words, from
  `spike/macos/texts/en_long.txt`), press ⌃⌥T again within 5 s → "Cancelled.", the old clipboard
  is back, nothing is pasted.
- **A9 — Secure Input.** **[user]** ⌃⌥T in a browser password field → "Nothing copied: secure
  input is active in <app>." (or the plain message if the app cannot be named); the clipboard is
  unchanged.
- **A10 — Environment.** From `llmtr log` and one diagnostic run: `LLMTR_RUN_ID` reaches `llmtr`,
  `HOME` is set, tools are found without `PATH` (no "not found" errors).
- **A11 — Speed sanity.** One loaded translate of a paragraph and one tone: times close to M8's
  (12–21 s, 9–15 s). Only to catch regressions; no tuning.
- **A12 — Uninstall.** `./install.sh --uninstall`: `llmtr.lua` gone, the `require` line gone, the rest
  of `init.lua` byte-identical, `~/.config/llmtr/` kept, Hammerspoon kept. Then reinstall if the
  user wants to keep using llmtr, and restore anything else the user asks for.
- **A13 — Optional: Karabiner README.** Do the README's Karabiner steps match what was needed on
  this Mac in M8?

## Done when

1. Every item A1–A12 has a status and a note (A13 may be "skipped").
2. Every FAIL/PARTIAL has exact steps, the output/message seen, and a suggested fix (file and
   change), so the orchestrator can write a fix task without asking.
3. The result file is written (sections below), committed on `task/M12-mac-acceptance`, and the
   branch is pushed; `git status` shows only the result file changed.

Stop as soon as these hold. If the Mac cannot continue (e.g. the install fails at A1 and blocks
everything), record it, skip what depends on it, and finish.

## Reruns

An item may be repeated **at most 3 times** for the **same problem** (e.g. a flaky "nothing
copied"); the session may restart or `--continue` **at most once**. Record every repeat under
**"Reruns"** in the result file: item, why, what changed. "Reruns: none" if none. A flaky item that
needs a retry to pass is **PARTIAL**, not PASS.

## Files you may change

`docs/tasks/M12-mac-acceptance.result.md` only.

## Hand-back

Result file sections: **Environment** (versions, `git log -1` of `main`), **Results** table A1–A13,
**App table** (A5), **Timings** (A5, A7, A8, A11), **Dialogs and Settings** (exact texts, correct
URLs), **Defects** (one per FAIL/PARTIAL, with suggested fix), **Reruns**, **Restored state** (what
was put back after A12), **Verdict**: ready / ready with minor fixes / not ready.

Commit on `task/M12-mac-acceptance` (prefix `M12-mac-acceptance:`; end the message with a
`Co-Authored-By` line naming the model you actually run as), then **push only that branch**:
`git push -u origin task/M12-mac-acceptance`. Never push `main`.
