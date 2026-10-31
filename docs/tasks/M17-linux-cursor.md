# Task M17-linux-cursor — Cursor engine acceptance on the Linux host

Role: **Linux acceptance worker**: a Claude Code session on the **host**, run **interactively with
the user present** (normal permission mode, no sandbox). It mirrors M16 on the Mac, so both
platforms are tested the same way.

Setup: the orchestrator prepares a worktree `../llmtr-m17` on branch `task/M17-linux-cursor` from
`main`, after M16-fix1 is merged.

Read first:
- `CLAUDE.md`;
- `docs/proposal.md` ("Cursor engine (v3, spike)");
- `README.md`, sections "Install", "Cursor engine (optional)", "Troubleshooting" and "Uninstall":
  the user follows them as a new user would;
- `docs/architecture.md` §3 and §23;
- `docs/tasks/M16-mac-cursor.result.md`, for the format and the Mac numbers to compare with.

Host: Ubuntu 25.10, GNOME on Wayland, RTX 5060 Ti 16 GB, Ollama on `localhost:11434`. The
shortcuts are Super+Alt+T (translate), Super+Alt+G (fix) and Super+Alt+R (tone). Keystrokes go
through `ydotool`, notifications through `notify-send`, and the clipboard through
`wl-copy`/`wl-paste`. The Cursor key file `~/.config/llmtr/cursor-api-key` (mode 600) already
exists from M14.

## Goal

Prove that the Cursor engine works on the Linux desktop when started by the GNOME shortcuts, with
the M16-fix1 changes in place. Linux-specific points:
- the key file read from a GNOME shortcut process (no shell environment), with its
  missing/insecure messages;
- the detached `llmtr cursor-cleanup` child started from a GNOME shortcut;
- `ydotool` paste, `notify-send` bubbles and the clipboard-only fallback with this engine;
- the README steps for Linux.

**This is acceptance, not development.** Do not change `src/`, `tests/`, `scripts/`, `install.sh`,
`macos/` or `README.md`. Every defect goes into the result file with exact steps, the output seen
and a suggested fix.

## Ground rules

- **The API key.** The worker never prints, `cat`s, logs or echoes the key, and never puts it on a
  command line.
  - To check the file, use only `stat -c '%a %s' ~/.config/llmtr/cursor-api-key`.
  - L2 and L3 change the file's name or mode, never its content. Ask before each change, and put
    it back right after.
- **Public repo.** Committed files must contain:
  - no key, account e-mail, user or team name, username, absolute home path or session
    scratchpad path (use `~`);
  - agent and run ids only in their short form, as logged.
- **Budget.** About 20 Cursor runs in total. Ask the user before going over 30.
- **Ask before changes.** Ask before every change to `~/.config/llmtr/config.toml`, the key file,
  `ydotoold` or the GNOME shortcuts. Never use `sudo`.
- **[user]** steps: say exactly what to select and press and what should happen, wait, then record
  what happened, with the exact notification texts.
- **Restore later.** Before L1, note the state you will change (config, key file mode, `ydotoold`
  state), so L11 can restore what the user wants.
- **Timings** in seconds with two decimals, from `llmtr log` (`duration`, `engine=`, `agent=`).

**Listing agents without printing the key.** Run from the worktree; it prints only counts and
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

**L1 — Update and install.**
- `git log -1 --oneline`.
- Run `./install.sh` from the worktree, as the README says. Afterwards:
  - `llmtr --help` names Cursor (M16-fix1 O2) and lists `cursor-cleanup`;
  - `llmtr translate --help` shows `--engine`;
  - the GNOME shortcuts are still Super+Alt+T, G and R (`gsettings` list).

**L2 — Missing key.**
- Rename the key file to `cursor-api-key.m17bak`, after asking.
- Terminal: `echo "Dzień dobry" | llmtr translate --engine cursor --stdin`. Expect exit ≠ 0 and
  exactly `No Cursor API key. Put it in ~/.config/llmtr/cursor-api-key (mode 600).`: with `~`
  (D1 fixed) and no Keychain text on Linux.
- Set `engine = "cursor"` on the **first line** of `config.toml`, after asking.
- **[user]** In gedit, select text and press Super+Alt+T. Expect the same message as a
  notification, and the clipboard unchanged.
- Rename the file back.

**L3 — Readable key file.**
- `chmod 644` the key file, after asking.
- **[user]** Press Super+Alt+T in gedit. Expect
  `Cursor API key file is readable by others. Run: chmod 600 ~/.config/llmtr/cursor-api-key`, with
  the key file not read (no agent in the log).
- `chmod 600` again, then confirm with `stat` (expect `600`).

**L4 — `engine` in the wrong place (D2).**
- Move the `engine` line below an existing `[section]`, after asking.
- Terminal: `echo "Dzień dobry" | llmtr translate --stdin`. Expect the config error that names
  `<table>.engine` and says to put `engine` above any `[section]`.
- **[user]** Press Super+Alt+T: the same message as a notification.
- Put the line back on the first line.

**L5 — Key file from a GNOME shortcut.** **[user]** In gedit, select a short Polish sentence and
press Super+Alt+T.
- The selection is replaced by the English text.
- The log shows `engine=cursor`, the time, and a short agent id without `bc-` (M16-fix1 O1).
- This proves the shortcut process reads the key file with no shell environment.

**L6 — Modes and apps.** **[user]**, with the shortcut and the Cursor engine:

| Run | Where | What to check |
| --- | --- | --- |
| Super+Alt+T PL→EN, a paragraph (`spike/macos/texts/pl_paragraph.txt`) | Slack | Selection replaced, old clipboard restored afterwards |
| Super+Alt+T EN→PL, a paragraph (`spike/macos/texts/en_paragraph.txt`) | Firefox (a text area) | Polish diacritics intact (ąęłóżźćńś) |
| Super+Alt+G fix, a Polish sentence with two typos | gedit | Typos fixed, nothing else changed |
| Super+Alt+R tone, current preset | Slack | Rewritten in the preset's tone, same language |

Table each run with its result and time, and compare with M16 on the Mac (5.5–10.3 s) and with M14.
Record the progress notification's summary and body; expect `gpt-5.4-nano (Cursor)` as the body.

**L7 — Cancel.** **[user]**
- Select the long text (`spike/macos/texts/en_long.txt`) in gedit and press Super+Alt+T. While
  "Translating…" shows, press Super+Alt+T again within 3 s.
- Expected:
  - "Cancelled.";
  - nothing pasted, and the old clipboard back.
- Time from the second press to "Cancelled.", from the log and the user's view. The Mac took about
  0.8 s.

**L8 — Clipboard-only fallback.**
- Stop `ydotoold` (`systemctl --user stop ydotoold`), after asking.
- **[user]** Copy a Polish sentence with Ctrl+C, then press Super+Alt+T. Expect the notification
  `Result copied. Press Ctrl+V to paste.`; Ctrl+V pastes the English text.
- Start `ydotoold` again and check it is active.

**L9 — Cleanup from GNOME.**
- For every Cursor run in L5–L8, `llmtr log` shows `cursor agent <id> deleted` from a separate PID
  within about a minute. This proves the detached child survives the shortcut process ending.
- Then run the listing snippet: expect `llmtr agents left: 0` (wait up to 2 minutes).
- If agents are left, run `llmtr cursor-cleanup` and record whether that removes them.

**L10 — Bad key and Ollama.**
- Terminal: `echo "Dzień dobry" | CURSOR_API_KEY=not-a-real-key llmtr translate --stdin`. Expect
  `Cursor rejected the API key. Create a new one in Cursor Dashboard → API Keys.`.
- Set `engine = "ollama"`, or remove the line, after asking.
- **[user]** Press Super+Alt+T on a short Polish sentence in gedit. The log shows `engine=ollama`
  and `translategemma:12b`, and the result is correct.

**L11 — Restore and README check.**
- Ask the user, then record:
  - which `engine` stays in the config;
  - that the key file is unchanged (`stat`: `600`, same size as before);
  - that `ydotoold` is active;
  - that llmtr is installed.
- Did the README Linux steps work as written, including the M16-fix1 additions (top-level `engine`
  note, uninstall note)? List anything missing, wrong or unclear, with a suggested wording.

## Files you may change

`docs/tasks/M17-linux-cursor.result.md` only.

## Done when

1. L1–L11 each have a status and a note.
2. Every FAIL and PARTIAL has exact steps, the message or output seen, and a suggested fix (file
   and change).
3. L9 ends with 0 `llmtr-` agents left, and L11 confirms the key file and `ydotoold` are as before.
4. The result file is written and committed on `task/M17-linux-cursor`; `git status` shows only
   the result file changed. **Do not push.** The orchestrator merges from the local branch.

Stop as soon as these hold. If something blocks the rest, record it, run what does not depend on
it, restore the state (L11), and finish.

## Reruns

- An item may be repeated **at most 3 times** for the **same problem**, and the session may restart
  or `--continue` **at most once**.
- Record every repeat under "Reruns": item, why, what changed. Write "Reruns: none" if there were
  none.
- A flaky item that needs a retry to pass is **PARTIAL**, not PASS.

## Hand-back

Result file sections, as in M16:
- **Environment.**
- **Results:** a table L1–L11.
- **Runs:** table from L6.
- **Timings.**
- **Notifications:** exact texts.
- **Defects.**
- **Reruns.**
- **Restored state.**
- **Verdict:** ready / ready with minor fixes / not ready.
- **Mac vs Linux:** a short comparison with M16 (times, cancel, cleanup).

Commit on `task/M17-linux-cursor` (prefix `M17-linux-cursor:`; end the message with a
`Co-Authored-By` line naming the model you actually run as).
