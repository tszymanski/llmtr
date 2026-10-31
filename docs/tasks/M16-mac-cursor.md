# Task M16-mac-cursor — Cursor engine acceptance on the test Mac

Role: **Mac acceptance worker**: a Claude Code session on the user's Mac, run **interactively with
the user present** (normal permission mode, no sandbox), as in M12.

Setup: in the existing clone run `git checkout main && git pull`, then create the branch
`task/M16-mac-cursor`.

Read first:
- `CLAUDE.md`;
- `docs/proposal.md` ("Cursor engine (v3, spike)");
- `README.md`, sections "macOS" and "Cursor engine (optional)": the user follows them as a new
  user would;
- `docs/architecture.md` §16–18 and §23;
- `docs/tasks/M15-cursor-engine.result.md` ("open issues").

Test Mac: MacBook Pro M1, 16 GB, macOS 27.0.1, with Hammerspoon and Karabiner as in M12. llmtr v2
is installed from M12.

## Goal

Prove that the Cursor engine (M15) works on the real Mac when started by the Hammerspoon
shortcuts. Linux and the real API are already checked (M15 review). This task is about the
**Mac-only parts**:
- the Keychain lookup (`security find-generic-password -s llmtr-cursor -w`) from a Hammerspoon
  child, including its `PATH` and any Keychain dialog;
- the detached `llmtr cursor-cleanup` child started from a Hammerspoon task;
- notifications, cancel and the clipboard with this engine;
- the README steps for macOS.

**This is acceptance, not development.** Do not change `src/`, `tests/`, `scripts/`, `install.sh`,
`macos/` or `README.md`. Every defect goes into the result file with exact steps, the output seen
and a suggested fix. The orchestrator turns defects into fix tasks.

## Ground rules

- **The API key.**
  - The user puts the key into the Keychain themselves with the README command, which prompts for
    it. Suggest a **separate key for the Mac** (Cursor Dashboard → API Keys, e.g. named
    `llmtr-mac`), so it can be revoked on its own.
  - The worker never prints, `cat`s, logs or echoes the key, and never runs
    `security find-generic-password … -w` itself (it would print the key into the transcript).
  - To check that the item exists, use `security find-generic-password -s llmtr-cursor`
    **without** `-w`, and record only the exit code.
- **Public repo.** Committed files must contain:
  - no key, account e-mail, user or team name, username, absolute home path or session
    scratchpad path (use `~`);
  - agent and run ids only shortened (first 6 characters).
- **Budget.** About 20 Cursor runs in total. Ask the user before going over 30.
- **Ask before changes.** Ask before every install, permission change or Keychain change. Never use
  `sudo`.
- **[user]** steps: say exactly what to press or click and what should happen, wait, then record
  what happened. Record every dialog with its exact wording and buttons.
- **Restore later.** Before K1, note the state you will change (`~/.config/llmtr/config.toml`, the
  Keychain item, `~/.hammerspoon/llmtr.lua`), so K10 can restore what the user wants.
- **Timings** in seconds with two decimals, taken from `llmtr log` (run lines carry `duration`,
  `engine=cursor` and a short `agent=`).

**Listing agents without printing the key.** Run from the repo; it prints only counts and
statuses:

```bash
uv run python - <<'EOF'
from llmtr import cursor_key
from llmtr.cursor_client import UrllibCursorTransport
from llmtr.platforms import detect_platform
t = UrllibCursorTransport(cursor_key.load_key(detect_platform()))
items = t.request("GET", "https://api.cursor.com/v1/agents?includeArchived=true&limit=100",
                  None, 30).get("items", [])
left = [a for a in items if str(a.get("name", "")).startswith("llmtr-")]
print(f"llmtr agents left: {len(left)}", [a.get("status") for a in left])
EOF
```

## Checklist

Record each item as **PASS / FAIL / PARTIAL** with a one-line note.

**K1 — Update and install.**
- `git log -1 --oneline` of `main`.
- `./install.sh`, as the README says. Afterwards `llmtr --help` lists `cursor-cleanup`, and
  `llmtr translate --help` shows `--engine`.
- **[user]** In the Hammerspoon menu, choose *Reload Config*.

**K2 — No key yet.** Do this before the Keychain item exists. If an item `llmtr-cursor` already
exists, record that and skip to K3.
- In Terminal: `echo "Dzień dobry" | llmtr translate --engine cursor --stdin`. Expect exit ≠ 0
  and the message `No Cursor API key. Put it in ~/.config/llmtr/cursor-api-key (mode 600) or in
  the Keychain as llmtr-cursor.` (record the exact text).
- Set `engine = "cursor"` at the top of `~/.config/llmtr/config.toml`, after asking.
- **[user]** In Notes, select text and press ⌃⌥T. Expect the same message as a notification, and
  the clipboard unchanged.

**K3 — Keychain item.**
- **[user]** Run the README command `security add-generic-password -s llmtr-cursor -a "$USER" -w`
  and paste the key at the prompt.
- Record the prompt texts. Check with `security find-generic-password -s llmtr-cursor; echo $?`,
  without `-w`, expecting exit 0.
- Then in Terminal: `echo "Dzień dobry, jak się masz?" | llmtr translate --stdin`, which uses the
  config engine. Expect English output; record the time.

**K4 — Keychain from Hammerspoon.** This is the main risk of this task.
- **[user]** In Notes, select a short Polish sentence and press ⌃⌥T.
- Is any **Keychain dialog** shown, e.g. "security wants to use your confidential information
  stored in "llmtr-cursor" in your keychain"? Record its exact wording, its buttons, and which
  button the user chose. If one is shown, press ⌃⌥T a second time: does it appear again?
- Did the selection get replaced by the translation? Does the log line show `engine=cursor` and
  the duration?
- If the result is `No Cursor API key…` even though K3 passed, `security` was probably not found
  or failed in the Hammerspoon child.
  - Check with a one-off Hammerspoon console call:
    `hs.execute("command -v security; echo PATH=$PATH")` (prints no secret).
  - Record the result. The suggested fix is an absolute `/usr/bin/security` in
    `src/llmtr/cursor_key.py`, plus a test.

**K5 — Modes and apps.** **[user]**, with the shortcut and the Cursor engine:

| Run | Where | What to check |
| --- | --- | --- |
| ⌃⌥T PL→EN, a paragraph (`spike/macos/texts/pl_paragraph.txt`) | Notes | Selection replaced, old clipboard restored afterwards |
| ⌃⌥T EN→PL, a paragraph (`spike/macos/texts/en_paragraph.txt`) | VS Code or Teams | Polish diacritics intact (ąęłóżźćńś) |
| ⌃⌥G fix, a Polish sentence with two typos | Notes | Typos fixed, nothing else changed |
| ⌃⌥R tone, current preset | Notes | Rewritten in the preset's tone, same language |

Table each run with its result and its time from `llmtr log`, and compare with M14's 6–14 s. Also
record the "Translating…" bubble text and body; expect `gpt-5.4-nano (Cursor)` as the body.

**K6 — Cancel.** **[user]**
- Select the long text (`spike/macos/texts/en_long.txt`) and press ⌃⌥T. While "Translating…" shows,
  press ⌃⌥T again within 3 s.
- Expected:
  - one bubble that changes to "Cancelled.";
  - nothing pasted, and the old clipboard back.
- Measure the time from the second press to "Cancelled.": M15 notes it can take up to about 5 s.
  Record it. If over 3 s, add a defect with a suggested change, e.g. notify before the cancel
  request.

**K7 — Cleanup from Hammerspoon.**
- For every run in K4–K6, `llmtr log` shows `cursor agent <id6> deleted` from a separate PID within
  about a minute. This proves the detached child survives the Hammerspoon task ending.
- Then run the listing snippet above: expect `llmtr agents left: 0` (wait up to 2 minutes).
- If agents are left, run `llmtr cursor-cleanup` by hand and record whether that removes them.

**K8 — Bad key message.** In Terminal:
`echo "Dzień dobry" | CURSOR_API_KEY=not-a-real-key llmtr translate --stdin`.
- Expect `Cursor rejected the API key. Create a new one in Cursor Dashboard → API Keys.`. This also
  confirms the env var wins over the Keychain.

**K9 — Ollama unaffected.** Set `engine = "ollama"`, or remove the line, after asking.
- **[user]** ⌃⌥T on a short Polish sentence in Notes.
- The log line shows `engine=ollama` and the configured translategemma model. The result is
  correct, as in M12.

**K10 — Restore.** Ask the user, then do the following and record what was kept and what was
restored:
- `engine` stays `"cursor"` or `"ollama"` in their config, as they choose;
- the Keychain item is kept, or removed with `security delete-generic-password -s llmtr-cursor`;
- llmtr stays installed.

**K11 — README check.** Did the README "Cursor engine (optional)" steps for macOS work as written?
List any step that was missing, wrong or unclear, each with a suggested wording.

## Files you may change

`docs/tasks/M16-mac-cursor.result.md` only.

## Done when

1. K1–K11 each have a status and a note. K2 may be "skipped" if the Keychain item already existed.
2. Every FAIL and PARTIAL has exact steps, the message or output seen, and a suggested fix (file
   and change), so the orchestrator can write a fix task without asking.
3. K7 ends with 0 `llmtr-` agents left.
4. The result file is written and committed on `task/M16-mac-cursor`, and the branch is pushed;
   `git status` shows only the result file changed.

Stop as soon as these hold. If something blocks the rest (e.g. K4 can never read the key), record
it, run what does not depend on it (K8, K9, K10, K11), and finish.

## Reruns

- An item may be repeated **at most 3 times** for the **same problem**, and the session may restart
  or `--continue` **at most once**.
- Record every repeat under "Reruns": item, why, what changed. Write "Reruns: none" if there were
  none.
- A flaky item that needs a retry to pass is **PARTIAL**, not PASS.

## Hand-back

Result file sections:
- **Environment:** versions, `git log -1` of `main`, Hammerspoon version.
- **Results:** a table K1–K11.
- **Runs:** table from K5.
- **Timings:** K3–K6.
- **Dialogs:** exact texts, especially the Keychain dialog.
- **Defects:** one per FAIL or PARTIAL, with a suggested fix.
- **Reruns.**
- **Restored state.**
- **Verdict:** ready / ready with minor fixes / not ready.

Commit on `task/M16-mac-cursor` (prefix `M16-mac-cursor:`; end the message with a
`Co-Authored-By` line naming the model you actually run as). Then **push only that branch**:
`git push -u origin task/M16-mac-cursor`. Never push `main`.
