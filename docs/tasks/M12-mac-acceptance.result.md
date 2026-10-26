# M12-mac-acceptance — result

Worker: Mac acceptance worker, interactive Claude Code session (Claude Opus 5.5) on the test Mac
with the user present, branch `task/M12-mac-acceptance`, 2026-10-26. No sandbox, no `sudo`, no
code changes.

## Environment

| Item | Value |
| --- | --- |
| `main` at start | `3353667` Orchestrator: M12 Mac acceptance contract, rerun rule counts same problem only, park M13 cleanup … |
| Machine | MacBook Pro M1, 16 GB, macOS 27.0.1 |
| `/bin/bash` | GNU bash 3.2.57(1)-release (arm64-apple-darwin26) |
| uv | 0.13.5 (Homebrew) |
| llmtr runtime | uv tool venv, Python 3.14 (Homebrew; no `.python-version` pin, see M8) |
| Hammerspoon | 1.1.1 |
| Karabiner-Elements | 16.3.0 |
| Ollama | 0.40.9; models `translategemma:12b`, `gemma3`, `gemma3:12b` |
| Apps | Teams, Chrome, VS Code, Notes, Terminal, iTerm |

State before A1 (recorded for A12): `~/.hammerspoon/` held only an empty `Spoons/` (no `init.lua`);
no `~/.config/llmtr/`, no `~/.cache/llmtr/`; `~/.local/state/llmtr/llmtr.log` existed from M8; no
uv tools; Hammerspoon running with Accessibility on, Automation → System Events on and
Notifications allowed (all granted in M8).

## Results

| Item | Status | Note |
| --- | --- | --- |
| A1 Install (bash 3.2) | PASS | `--dry-run` and two real runs, exit 0. `local LLMTR = "$HOME/.local/bin/llmtr"` (absolute), the file is the template with only the path replaced, `luac -p` OK. `init.lua` holds `require("llmtr")` exactly once after both runs; the second run leaves `llmtr.lua` byte-identical. Both Hammerspoon paths were seen (not running → started; running → "Reload Config"). Printed steps match the README. A uv-build version warning is printed (D2) |
| A2 Settings panes | PASS | All three URLs open the right pane on macOS 27: Accessibility ("Device Control and Data Access"), Automation, and Notifications (which landed on Hammerspoon's page, probably the last page viewed) |
| A3 Permissions missing | PARTIAL | Accessibility off: correct message, clipboard unchanged. Automation off: correct message. After `tccutil reset`: first-⌘C dialog matches the README word for word; unanswered gives the timeout message after 30.21 s; after Allow it works. **But the Accessibility message (and the installer's step 1) names a Settings entry that is not called that on macOS 27 (D1)** |
| A4 Shortcuts | PASS | ⌃⌥T translate, ⌃⌥G fix (gemma3), ⌃⌥R tone (gemma3:12b), ⇧⌃⌥R next tone, ⇧⌃⌥T show tone all correct in Notes; Caps+T (Karabiner) translates too |
| A5 Apps | PASS | Replaced in Teams, Chrome, VS Code, Notes; pasted at the cursor in Terminal and iTerm. Old clipboard restored (in iTerm the "old clipboard" is the selection itself, because of iTerm's copy-on-select, see D4). 2.24–3.37 s |
| A6 Polish text | PASS | PL→EN ("Źrebię ćwiczyło na łące, a żółty wąż…" → "The foal was practicing on the meadow…") and EN→PL ("Młody koń ćwiczył na łące, … żółta żmija spokojnie spała…"): no garbled characters |
| A7 Notifications | PASS | "Translating PL → EN…" / "translategemma:12b" appears under Hammerspoon in ≤ 1 s (user's estimate) and goes away by itself. On success no result bubble follows (the paste is the result); the README wording suggests otherwise (D3). `osascript` backend: one "Script Editor" bubble that stays in Notification Center. Hammerspoon channel: no visible extra delay |
| A8 Cancel | PASS | 221-word EN→PL, second ⌃⌥T: `outcome=cancelled` after 6.82 s, "Cancelled." bubble, text unchanged, nothing pasted within 60 s, clipboard restored |
| A9 Secure Input | PASS | Chrome password field: "Nothing copied: secure input is active in Google Chrome.", clipboard unchanged (1.68 s) |
| A10 Environment | PASS | With Hammerspoon started from Spotlight, `llmtr`'s environment has `LLMTR_RUN_ID=1`, `HOME`, `LC_CTYPE=UTF-8`, `PATH=/usr/bin:/bin:/usr/sbin:/sbin`. No "not found" / "No such file" in the log. So `setEnvironment` merges (architecture §22 open point settled) |
| A11 Speed sanity | PASS | translate PL paragraph loaded 12.53 s, EN→PL paragraph 22.26 s, tone loaded 10.31 s; within ~5–15% of M8 under similar swap pressure |
| A12 Uninstall | PASS | `llmtr.lua` gone, `require` line gone, the rest of `init.lua` byte-identical (test comment + blank line), `~/.config/llmtr/` and Hammerspoon kept, uv tool gone. Reinstalled at the user's request; Reload Config + ⌃⌥T works |
| A13 Karabiner README | PASS | Checked against the M8 records (no new run): all steps that were needed are in the README. One small wording point (D5) |

## App table (A5)

Short Polish sentence typed by the user ("Czy możesz to sprawdzić?"), ⌃⌥T, translategemma:12b
loaded. "Time" is `duration` from `llmtr log` (the `llmtr` process: copy, model, paste,
0.3 s paste delay, restore). Hotkey → process start adds ~0.03 s (M8).

| App | Result | Old clipboard back | Time (s) |
| --- | --- | --- | --- |
| Teams | replaced | yes | 3.37 |
| Chrome | replaced | yes | 2.28 |
| VS Code | replaced | yes | 2.28 |
| Notes | replaced | yes | 2.40 |
| Terminal | pasted at cursor | yes (checked with a marker on a separate run) | 2.36 / 2.87 |
| iTerm | pasted at cursor | yes, but iTerm had already put the selection on the clipboard (copy-on-select) | 2.24 |

## Timings

| What | Value (s) |
| --- | --- |
| A3 Accessibility off → error bubble (`duration`) | 0.59, 0.30 |
| A3 Automation off → error bubble | 0.41 |
| A3 Automation dialog unanswered → timeout bubble | 30.21 |
| A3 first translate after Allow | 5.69 |
| A4 translate / fix / tone / tone --next / tone --show | 3.96 / 5.56 / 11.92 (model switch) / 0.10 / 0.08 |
| A5 short sentence per app | 2.24–3.37 |
| A6 PL→EN / EN→PL sentence | 5.48 / 6.64 |
| A7 sending a bubble: `open -g hammerspoon://llmtr?…` vs `osascript display notification` (3 runs) | 0.11–0.16 vs 0.14–0.19 |
| A7 bubble on screen after key release (user) | ≤ 1 (both backends; shown side by side, Hammerspoon and Script Editor appeared together) |
| A8 second press → cancelled | 6.82 (A10 run: 6.11) |
| A9 Secure Input message | 2.50, 1.68 |
| A11 translate PL 56 w (cold-ish / loaded) | 15.98 / 12.53 (M8: 11.71–13.89) |
| A11 translate EN→PL 71 w, loaded | 22.26 (M8: 18.85–21.18) |
| A11 tone EN 71 w, gemma3:12b (after switch / loaded) | 19.51 / 10.31 (M8: 18.27–18.30 / 8.90–8.92) |

A11 conditions: Teams, Chrome and VS Code open; swap 7.98 of 9.2 GB used.

Bubble lifetimes (~8 s after the run, ~15 s after an error) were not timed with a stopwatch; the
user confirmed that the bubbles go away by themselves.

## Dialogs and Settings

| Where | Exact text / result |
| --- | --- |
| `x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility` | opens Privacy & Security → **Device Control and Data Access** (list: Hammerspoon, Karabiner-Core-Service). Correct |
| `x-apple.systempreferences:com.apple.preference.security?Privacy_Automation` | opens **Automation** (Hammerspoon → System Events; iTerm → System Events, left over from M8). Correct |
| `x-apple.systempreferences:com.apple.Notifications-Settings.extension` | opens **Notifications**, here directly on Hammerspoon's page (likely remembered from M8). Correct |
| Switching Hammerspoon off under Device Control and Data Access | only the system authentication prompt (Touch ID / password) |
| First ⌘C after `tccutil reset AppleEvents org.hammerspoon.Hammerspoon` | *"“Hammerspoon” wants access to control “System Events”. Allowing control will provide access to documents and data in “System Events”, and to perform actions within that app."* / *"Hammerspoon needs to send events to automate applications."* / [Don't Allow] [Allow]. Identical to the README |
| Bubble, Accessibility off | *"Keystrokes blocked. Turn on Hammerspoon in System Settings > Privacy & Security > Accessibility."* (log: `osascript is not allowed to send keystrokes. (1002)`) |
| Bubble, Automation off | *"Keystrokes blocked. In System Settings > Privacy & Security > Automation, allow Hammerspoon to control System Events."* (log: `Not authorized to send Apple events to System Events. (-1743)`) |
| Bubble, dialog unanswered | *"Keystrokes timed out. Answer the Hammerspoon permission prompt, then retry."* |
| Bubble, progress | title *"Translating PL → EN…"*, body *"translategemma:12b"* |
| Bubble, cancel | *"Cancelled."* (from the second run, shown after "Translating…") |
| Bubble, password field | *"Nothing copied: secure input is active in Google Chrome."* |

All bubbles show under **Hammerspoon** (banner header "Hammerspoon").

## Defects

**D1 (minor, user-visible) — "Accessibility" is not what macOS 27 calls the pane.** Found by the
user in A3.
- Steps: Hammerspoon's Accessibility off → select text → ⌃⌥T.
- Seen: *"Keystrokes blocked. Turn on Hammerspoon in System Settings > Privacy & Security >
  Accessibility."* On macOS 27.0.1, Privacy & Security has no "Accessibility" entry. The list is
  under **"Device Control and Data Access"** (the deep link `…?Privacy_Accessibility` opens it).
  The installer's step 1 mentions both names; the bubble does not.
- Suggested fix: `src/llmtr/errors.py` (the `accessibility` message of `MacKeySendError`, around
  line 126):
  *"Keystrokes blocked. Turn on Hammerspoon in System Settings > Privacy & Security > Device Control
  and Data Access (Accessibility)."* Then update any test that asserts the text
  (`tests/test_interfaces.py` mentions Accessibility), architecture §14 (error classification table) and §19, and
  README "macOS permissions" item 1 (*"`llmtr` tells you to turn Hammerspoon on here"*).

**D2 (minor, cosmetic) — uv-build version warning on every install.**
- Steps: `./install.sh` with uv 0.13.5.
- Seen: `warning: build_system.requires = ["uv-build>=0.12.22,<0.13.0"]` does not contain the
  current uv version 0.13.5`. The install still succeeds.
- Suggested fix: `pyproject.toml` `[build-system] requires = ["uv-build>=0.12.22,<0.14.0"]` (or the
  range uv now generates), then `uv lock`.

**D3 (minor, docs) — README says "Translating…" is replaced by the result.**
- Seen: on success there is no result bubble. "Translating…" stays until 8 s after the run and the
  pasted text is the result (as designed, architecture §16/§18). Only errors and "Cancelled." show a
  second message, and "Cancelled." comes from the second run, so it is a separate bubble.
- Suggested fix: `README.md` "macOS notifications": *"'Translating…' stays while the job runs and
  disappears a few seconds after it ends; errors and 'Cancelled.' get their own bubble."*

**D4 (minor, docs) — iTerm copy-on-select changes the "old clipboard".**
- Steps: clipboard holds X; in iTerm select text with the mouse; ⌃⌥T.
- Seen: iTerm's default "Copy to pasteboard on selection" puts the selection on the clipboard
  before `llmtr` runs, so `llmtr` restores the selection, not X. `llmtr` behaves correctly
  (Terminal kept X).
- Suggested fix: one line in README "macOS troubleshooting": *"iTerm copies a selection to the
  clipboard by itself (Settings > General > Selection), so after a shortcut in iTerm the clipboard
  holds the selected text."* No code change.

**D5 (trivial, docs) — Karabiner ISO note.** README step 4 says `` ` ``/`~` "produce `§`". On this Mac
in M8 the user saw `~` turn into `£` (UK-style layout). Suggested wording: *"or the `` ` ``/`~` key and
the key next to left Shift are swapped (e.g. `§` or `£` appears)"*.

Not a defect: "Cancelled." appears as a second bubble rather than replacing "Translating…", because
the cancelling press is its own `llmtr` run with its own `LLMTR_RUN_ID`. If a single bubble is
wanted, the orchestrator could make the second run withdraw the first run's id. That's an
optional nicety.

## Reruns

The contract rule is about repeating an item for the same problem. No item needed a retry to pass.
These were procedure repeats, listed for completeness:

- A3a, once: the user had copied the test sentence from my message after I set the clipboard
  marker, so the "clipboard unchanged" check was not valid. Repeated without copying: PASS.
- A3c, re-grant: the first-⌘C dialog did not appear after switching System Events back on (the
  grant was restored directly). With the user's OK, ran `tccutil reset AppleEvents
  org.hammerspoon.Hammerspoon` and repeated: dialog recorded.
- A5, iTerm: an extra check (select only, no shortcut) to explain the clipboard result; then
  Terminal was repeated with a fresh marker: marker kept.
- A9, once: the user had copied `secret123` from my message, so the clipboard check was not
  valid. Repeated with the password typed by hand: PASS.

Session restarts: none.

## Restored state

- **llmtr reinstalled** (user's choice): `~/.hammerspoon/llmtr.lua` plus `init.lua` containing only
  `require("llmtr")` (the A12 test comment was removed). Hammerspoon config reloaded and working.
- **Permissions** as before: Accessibility on (switched off and on in A3); Automation →
  System Events on (reset with `tccutil` and re-allowed through the dialog); Notifications
  unchanged.
- **New:** `~/.config/llmtr/config.toml` with `[notify] backend = "auto"` (same as the default).
  It was created for A7 (`osascript` test, then switched back) and kept to check A12. The user can
  delete it. `~/.cache/llmtr/run.lock` was created by normal use.
- Left as before: Hammerspoon, Karabiner, the models, the iTerm Automation entry from M8.
- The clipboard holds whatever the user last copied (markers were only used during tests).

## Verdict

**Ready with minor fixes.** Every flow works on the real Mac: install, uninstall, five shortcuts,
six apps, Polish text, cancel, Secure Input, permission errors, and the clean Hammerspoon
environment. The defects are message wording (D1) and docs or cosmetics (D2–D5). D1 should be
fixed before a release, because a user following the bubble will not find "Accessibility" on
macOS 27.
