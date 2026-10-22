# Task M8-spike — macOS spike on the test Mac

Role: **Mac spike worker**: a Claude Code session on the user's Mac, run **interactively with the
user present** (normal permission mode, no `--dangerously-skip-permissions`, no sandbox). Fresh
clone of `git@github.com:tszymanski/llmtr.git`. Branch: `task/M8-spike`.
Read `CLAUDE.md`, `docs/proposal.md` (section "macOS support (v2)") and this contract.

Test Mac: MacBook Pro M1, 16 GB, macOS 27.0.1. Karabiner-Elements is set up (Caps Lock held → ⌃⌥).

## Goal

Answer, with evidence from the real Mac, the questions the macOS design depends on, before any
production code is written. **This is a spike: no changes to `src/` or `tests/`.** Findings go to
`docs/tasks/M8-spike.result.md`; throwaway scripts go to `spike/macos/`.

## Ground rules

- Ask the user before every install (`brew`, `ollama pull`, `uv tool install`) and never use `sudo`.
- Steps marked **[user]** need the user to press keys, select text, or click in System Settings.
  Tell them exactly what to do and what should happen, wait for them, then record the result.
- Record every macOS permission prompt with its exact wording and which app it names.
- Keep timings in seconds with two decimals. Prefer shell and Lua for spike scripts; any Python goes
  through `uv run` (project rule).
- At the end, remove everything the spike added to `~/.hammerspoon/` (see S10).

## Steps

Record each as **PASS / FAIL / PARTIAL** with a one-line note.

**S1 — Environment.** `sw_vers`, `uname -m`, `brew --version`, `uv --version`,
`ollama --version`, `ollama list`, Hammerspoon version (install with
`brew install --cask hammerspoon` if missing, after asking), Karabiner-Elements version,
`sysctl iogpu.wired_limit_mb`. Then `uv sync`, `uv run pytest`, `uv run ruff check .`:
record whether the **existing** test suite passes on macOS (do not fix failures; list them).

**S2 — Clipboard.** `pbcopy`/`pbpaste` round trip with Polish diacritics (`zażółć gęślą jaźń`),
multi-line text, emoji, and 8000 characters; time each. What `pbpaste` returns for an empty
clipboard and **[user]** after copying an image in Preview (expected: empty output, exit 0). Does
`pbcopy` return immediately (no forked server holding pipes, unlike `wl-copy`)?

**S3 — Notifications.** `osascript -e 'display notification "Translating…" with title "llmtr"'`
from Terminal and from a Hammerspoon `hs.task`. **[user]** Is it shown, under which app name,
does it need a permission? Same with `hs.notify` for comparison (can it be withdrawn/replaced?).

**S4 — Hammerspoon hotkeys.** A spike file `~/.hammerspoon/llmtr_spike.lua`, loaded by one
`require("llmtr_spike")` line in `init.lua`, binds ⌃⌥T, ⌃⌥G, ⌃⌥R, ⇧⌃⌥R, ⇧⌃⌥T to an `hs.task`
that runs a spike script by absolute path and appends a timestamped line to a log.
- The child process's environment: dump `env` once; is `PATH` minimal, are `~/.local/bin`
  (uv tools) and `/opt/homebrew/bin` on it?
- **[user]** Press each combo in Slack, Chrome (or Safari), VS Code, Notes and Terminal: does the
  binding fire, and does the app also react to the key (conflict)? Table app × combo.
- **[user]** Same with **Caps Lock** instead of ⌃⌥ (Karabiner): does it fire identically?
- Bind once on key **press** and once on key **release** (`hs.hotkey.bind(mods, key, nil, fn)`):
  latency from press to script start.

**S5 — Copy/paste keystrokes via `osascript`.** A spike script that mimics the `llmtr` flow
without a model: save clipboard → send ⌘C with
`osascript -e 'tell application "System Events" to keystroke "c" using command down'` → poll
`pbpaste` until it changes (max 1 s) → result = upper-cased text → `pbcopy` → send ⌘V → wait 0.3 s
→ restore old clipboard. Triggered by the S4 hotkey.
- **Permissions:** which prompts appear (Accessibility for Hammerspoon? Automation "Hammerspoon
  wants to control System Events"? anything for `osascript`)? Does granting **only Hammerspoon**
  suffice? Record the exact System Settings entries needed.
- **[user]** Run it in Slack, Chrome, VS Code, Notes, Terminal, iTerm (if installed). Pass = the
  selection is replaced by its upper-case version and the old clipboard is back.
- With the **press** binding vs the **release** binding: does ⌘C get mixed with the still-held ⌃⌥
  (wrong action or nothing copied)? Is a start delay still needed on release?
- Time from hotkey to paste (without the model).

**S6 — Alternative: keystrokes from Hammerspoon.** Same flow, but the Lua side sends the keys with
`hs.eventtap.keyStroke({"cmd"}, "c")` / `"v"` and calls the script only for the transform.
Compare reliability and permissions with S5; recommend one for M9.

**S7 — Limits.** **[user]** With Terminal → Secure Keyboard Entry on, and in a password field in a
browser: what happens (expected: copy fails)? How can the script detect it (clipboard unchanged
after ⌘C)? Is `ioreg -l -w 0 | grep SecureInput` usable to detect Secure Input?

**S8 — Focused app.** `osascript -e 'tell application "System Events" to get bundle identifier of
first application process whose frontmost is true'` from the hotkey: correct for each app in S5,
and how long does it take? (Only to confirm per-app overrides stay unnecessary.)

**S9 — Models and latency.** Use the existing CLI's engine-only mode, which needs no desktop tools:
`time (printf '%s' "$TEXT" | uv run llmtr translate --stdin)` (and `fix`, `tone`). **Ask before
pulling** any missing model (`translategemma:12b`, `gemma3`, `gemma3:12b`). Cases, matching the
Linux table in `docs/proposal.md` "Model notes": PL→EN sentence cold and loaded, PL→EN paragraph
(~60 words), EN→PL paragraph (~70 words), EN→PL long text (~220 words). Also:
- tone with `gemma3:12b` vs `gemma3` (4b) on one paragraph (`--model`);
- **switch cost**: translate → tone → translate with `gemma3:12b`, then with 4b; `ollama ps`
  after each step (which models stay loaded, memory);
- `translategemma:27b`: do not pull; note that it does not fit.
Output a timing table and a recommendation for the user's tone model on this Mac.

**S10 — Cleanup.** Remove `~/.hammerspoon/llmtr_spike.lua` and the `require` line, reload
Hammerspoon, and restore the user's clipboard. Leave Hammerspoon, Karabiner and the models
installed. Confirm `git status` shows only allowed files.

## Files you may change

`spike/macos/**` (new, throwaway scripts — keep them, M10 may reuse or delete them),
`docs/tasks/M8-spike.result.md`. Nothing in `src/`, `tests/`, `install.sh`, docs other than the
result file, or the user's config.

## Must pass

`uv run ruff check .` and `uv run ruff format --check .` (in case of Python in `spike/`);
`bash -n` on every shell script in `spike/macos/`. `uv run pytest` is **recorded**, not fixed (S1).

## Out of scope

Production code, installer, README, CI, macOS Services, Shortcuts.app, Karabiner configuration
changes.

## Hand-back

`docs/tasks/M8-spike.result.md` with: environment (S1), a results table S1–S10 (status + note), the
app × combo table (S4), app × flow table (S5/S6), timing tables (S4, S5, S9), the exact permission
prompts and Settings entries, and **recommendations for M9**: keystroke method (S5 vs S6), press
vs release binding, notification method, Secure Input handling, tone model for 16 GB. Add the
Karabiner setup steps the user needed (driver extension, Input Monitoring, Devices → Modify events)
for the README in M11.

Commit on `task/M8-spike` (prefix `M8-spike:`, end each message with
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`), then **push only that branch**:
`git push -u origin task/M8-spike`. Never push `main`.
