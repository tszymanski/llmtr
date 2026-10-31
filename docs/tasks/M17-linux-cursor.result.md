# M17-linux-cursor — result

Linux acceptance of the Cursor engine (M15 + M16-fix1). It ran interactively with the user on
2026-10-31, 21:24–21:58 local time. Worker: a Claude Code session on the host (Opus 5.5), normal
permission mode, no sandbox.

## Environment

| Item | Value |
| --- | --- |
| Host | Ubuntu 25.10, kernel 6.17.0-41, GNOME Shell 49.0 on Wayland, RTX 5060 Ti 16 GB |
| `main` | `41e42cf Orchestrator: M16-fix1 merged, log updated` |
| llmtr | 0.1.0, `./install.sh` from the worktree (`uv tool install`); tool venv Python 3.13.7 |
| uv | 0.12.22 |
| Ollama | 0.30.11 on `localhost:11434` (`translategemma:12b`) |
| Desktop tools | `ydotoold` user service, `wl-clipboard` 2.2.1, `libnotify-bin` 0.8.6 (`notify-send`) |
| Apps | gedit, VS Code 1.109.0, Firefox 158.0 |
| Cursor model | `gpt-5.4-nano` (default `cursor.model`) |

State before the task:
- `~/.config/llmtr/config.toml`: the M2 example config with three tone presets and no `engine`
  line. A backup was kept outside the repo until L11.
- Key file `~/.config/llmtr/cursor-api-key`: `600`, 70 bytes. `CURSOR_API_KEY` not set.
- `ydotoold`: active and enabled.
- Shortcuts: the five llmtr entries, Super+Alt+T/G/R and Shift+Super+Alt+R/T.
- Tone: `team`.
- Cursor agents: `llmtr agents left: 0 []`.

## Results

| Item | Status | Note |
| --- | --- | --- |
| L1 Update and install | PASS | `./install.sh` exit 0. `llmtr --help`: "…with a local Ollama model or a Cursor cloud agent (--engine cursor)…" (O2 fixed) and lists `cursor-cleanup`. `translate --help` shows `--engine {ollama,cursor}`. `gsettings` still shows Super+Alt+T/G/R (+ Shift+Super+Alt+R/T). |
| L2 Missing key | PASS | Terminal: exact `No Cursor API key. Put it in ~/.config/llmtr/cursor-api-key (mode 600).`, exit 1. `~` is shown (D1 fixed), with no Keychain text. Super+Alt+T: same bubble, 0.60–0.74 s; gedit text and clipboard unchanged. |
| L3 Readable key file | PASS | Exact bubble `Cursor API key file is readable by others. Run: chmod 600 ~/.config/llmtr/cursor-api-key`, 0.63 s. No agent in the log, so the key was not read. Mode back to `600`. |
| L4 `engine` in the wrong place | PARTIAL | Terminal and shortcut both report the error naming `notify.engine` (D2 fixed). But the message starts with the **absolute** config path, and the collapsed GNOME bubble cuts off before the fix and cannot be expanded (D4). |
| L5 Key file from a GNOME shortcut | PASS | Selection replaced. `engine=cursor`, 6.33 s, `agent=a0d4e3` (no `bc-`, O1 fixed). The key file was read from the shortcut process. |
| L6 Modes and apps | PASS | 4/4 correct, 6.11–8.52 s. Bubble body `gpt-5.4-nano (Cursor)`. Clipboard restored each time. VS Code stood in for Slack (not installed), see Deviations. |
| L7 Cancel | PASS | One bubble → `Cancelled.`. Nothing pasted, clipboard byte-identical. Second press → job end **≈0.79 s** (user saw about 1 s). |
| L8 Clipboard-only fallback | PASS | With `ydotoold` stopped: `Result copied. Press Ctrl+V to paste.`; Ctrl+V pasted "Please send a quick reply by Friday." Log `keystrokes=False`. `ydotoold` was started again and is active. |
| L9 Cleanup from GNOME | PASS | 12/12 agents have `cursor agent <id> deleted` from a separate PID, 10–56 s after their run. Listing: `llmtr agents left: 0 []`. `llmtr cursor-cleanup` was not needed. |
| L10 Bad key and Ollama | PASS | Exact `Cursor rejected the API key. Create a new one in Cursor Dashboard → API Keys.`, exit 1, 0.41 s. With `engine = "ollama"`: Super+Alt+T in gedit gives `model=translategemma:12b engine=ollama`, 11.68 s (cold load), with a correct result. |
| L11 Restore and README check | PARTIAL | State restored as the user chose (see Restored state). README Linux steps worked as written, but the key-file command fails without `~/.config/llmtr/` (D5) and the clipboard-only order is easy to get wrong (D6). |

## Runs

These runs used the GNOME shortcuts with engine `cursor` and model `gpt-5.4-nano`. Times come from
`llmtr log` (`duration`). "Deleted after" is the cleanup line time minus the run line time; every
delete came from a different PID than the run.

| # | Run | Where | Result | Time | Agent | Deleted after |
| --- | --- | --- | --- | --- | --- | --- |
| L5 | Super+Alt+T PL→EN, short sentence (69 chars) | gedit | replaced, correct; clipboard restored | 6.33 s | a0d4e3 | 32 s |
| — | Super+Alt+T PL→EN, "Dzień dobry, jak się masz?" (user extra) | gedit | ok | 6.92 s | a3f0ff | 32 s |
| — | same (user extra) | gedit | ok | 7.30 s | 520743 | 35 s |
| — | same (user extra) | gedit | ok | 6.02 s | a0579c | 32 s |
| L6.1 | Super+Alt+T PL→EN, `pl_paragraph.txt` | VS Code (for Slack) | full, correct EN paragraph; clipboard restored | 7.62 s | b22dd1 | 32 s |
| L6.2 | Super+Alt+T EN→PL, `en_paragraph.txt` | Firefox `<textarea>` | PL, diacritics intact (ą ć ę ł ń ó ś ż present; no word needed ź); clipboard restored | 8.10 s | 948c37 | 32 s |
| L6.3 | Super+Alt+G fix, "…do skelpu… chlep…" | gedit | "Wczoraj poszedłem do sklepu i kupiłem świeży chleb oraz mleko." Only the two typos changed | 6.11 s | c81092 | 32 s |
| L6.4 | Super+Alt+R tone, preset `team`, formal PL | VS Code (for Slack) | "Hej! Jutro spotykamy się o 14:00. Dajcie znać, czy będziecie obecni." Same language; clipboard restored | 8.52 s | cb2c76 | 31 s |
| — | Super+Alt+T `en_long.txt`, not cancelled (user set-up slip, undone) | gedit | full PL translation | 13.35 s | ba3227 | 56 s |
| L7 | Super+Alt+T `en_long.txt`, cancelled | gedit | `Cancelled.`, nothing pasted, clipboard byte-identical | 3.62 s | 6a1a37 | 32 s |
| — | Super+Alt+T, no ydotool, pressed before Ctrl+C (user slip) | gedit | translated the old clipboard (`en_long.txt`), `Result copied…` | 7.38 s | a77b7f | 10 s |
| L8 | Super+Alt+T, no ydotool, after Ctrl+C | gedit | `Result copied. Press Ctrl+V to paste.`; Ctrl+V pasted "Please send a quick reply by Friday." | 5.53 s | 1f08e3 | 33 s |

All runs are inside the README's "about 6–14 s". The L6 runs (6.1–8.5 s, median 7.86 s) are a
little slower than the Mac's L6 equivalent, K5 (5.5–10.3 s, median 6.44 s), and within M14's
5.8–13.9 s.

Cursor usage: 12 agents created, plus 1 rejected request (L10) and 2 listings. That is within the
~20 budget.

The four "—" rows were user actions:
- three extra short translations;
- one long translation where the user forgot the second press and undid it;
- one press before Ctrl+C in L8.

None of them repeats a failing item.

## Timings

| Item | Value |
| --- | --- |
| L2 key missing (shortcut) | 0.59 / 0.60 / 0.68 / 0.74 s to the error |
| L3 key insecure (shortcut) | 0.63 s |
| L5 shortcut translate | 6.33 s (the user felt 2–3 s, counted from the bubble, which appears after the copy step) |
| L6 | 7.62 / 8.10 / 6.11 / 8.52 s (median 7.86 s) |
| Long text (221 words), not cancelled | 13.35 s |
| L7 cancel | first press 21:51:39.49; second press 42.33; second process exits 42.42; cleanup child spawned 43.00; `outcome=cancelled` logged 43.12; first process exits 43.17 → **second press to "Cancelled." ≈ 0.79 s** |
| L8 fallback | 5.53 s |
| L9 delete in the detached child | 10–56 s after the run (12/12); 11 of 12 within 35 s |
| L10 bad key | 0.41 s |
| L10 Ollama translate | 11.68 s (includes the cold load of `translategemma:12b`) |

L7 was measured with a process watcher, which polled `pgrep` every 50 ms and timestamped new and
exiting `llmtr` processes, plus the log lines.

## Notifications

All bubbles carry the app name `llmtr`.

- L2: `No Cursor API key. Put it in ~/.config/llmtr/cursor-api-key (mode 600).` It fits on one
  line.
- L3: `Cursor API key file is readable by others. Run: chmod 600 ~/.config/llmtr/cursor-api-key`.
- L4, collapsed and not expandable: `Config error in /home/<user>/.config/llmtr/config.toml: 'engine' must b…`.
  The terminal shows the full text: `Config error in /home/<user>/.config/llmtr/config.toml: 'engine' must be a top-level key: put it above any [section] (found as notify.engine)`.
- L5/L6 progress bubbles, each with the body `gpt-5.4-nano (Cursor)`:
  - `Translating PL → EN…`;
  - `Translating EN → PL…`;
  - `Fixing grammar…`;
  - `Rewriting: team…`.
- L7: one bubble, `Translating EN → PL…`, which changed to `Cancelled.`
- L8: `Result copied. Press Ctrl+V to paste.`
- L10 (terminal): `Cursor rejected the API key. Create a new one in Cursor Dashboard → API Keys.`
- L10 (Ollama): `Translating PL → EN…` / `translategemma:12b`.

## Defects

M16's D1 (absolute path in the key messages), D2 (misplaced `engine` silently ignored) and O1/O2
are confirmed fixed on Linux. New findings:

**D4 (L4, minor): the config error shows the absolute home path, and the bubble hides the fix.**
- Steps:
  1. Put `engine = "cursor"` at the end of `config.toml`, below `[notify]`.
  2. Run `echo "Dzień dobry" | llmtr translate --stdin`, or press Super+Alt+T.
- Seen: `Config error in /home/<user>/.config/llmtr/config.toml: 'engine' must be a top-level key: put it above any [section] (found as notify.engine)`.
  - GNOME shows the bubble collapsed as `Config error in /home/<user>/.config/llmtr/config.toml: 'engine' must b…`.
  - The user could not expand it.
  - The log line has `~` only because the logger redacts it.
- Impact:
  - the actionable part ("put it above any [section]") is not visible from the shortcut;
  - the username ends up in screenshots.
  - This affects every `ConfigError`, not only `engine`.
- Suggested fix:
  - In `src/llmtr/errors.py`, `ConfigError.__init__`: build the message with the existing
    `display_path(path)`, i.e. `f"Config error in {display_path(path)}: {problem}"`. Keep
    `self.path` absolute.
  - Add a test with `HOME` set to a tmp directory.
  - Optionally, for this case, put the fix first, e.g. summary `Config error: put 'engine' on the
    first line of config.toml` with the details in the body.

**D5 (L11, minor): the README key-file command fails for a new user without a config directory.**
- Steps: on a machine where `~/.config/llmtr/` does not exist yet (the README makes
  `config.toml` optional), run the README's
  `install -m 600 /dev/null ~/.config/llmtr/cursor-api-key`.
- Expected failure: `install: cannot create regular file …: No such file or directory`. `install`
  without `-D` does not create parent directories.
  - Not run on the host, because the directory exists here. This is the documented behaviour of
    GNU `install`.
- Suggested fix in README "Cursor engine (optional)" → "API key, Linux": put
  `mkdir -p ~/.config/llmtr` on the line before the `install` command.

**D6 (L8/L11, documentation): the clipboard-only order is easy to get wrong.**
- Steps:
  1. Stop `ydotoold`.
  2. Select text and press Super+Alt+T **before** Ctrl+C.
- Seen: llmtr translates whatever was on the clipboard before (here a 1324-character text from an
  earlier step). It sent that text to Cursor and showed `Result copied. Press Ctrl+V to paste.`.
  This is the designed behaviour, but with the Cursor engine an unrelated old clipboard leaves the
  machine.
- Suggested fix in README "Requirements" (ydotool bullet) and in "Troubleshooting":
  - Change "you copy by hand, trigger the shortcut, then paste by hand" to *"press Ctrl+C first,
    then the shortcut, then Ctrl+V; the shortcut uses whatever is on the clipboard"*.
  - In "Cursor engine (optional)", add *"Without ydotool, the shortcut sends the current
    clipboard."*

### Observations (no status impact)

- **O6. Slack not on the host.** The contract's Slack runs (L6.1, L6.4) used VS Code, which is
  also an Electron app.
- **O7. Stale ydotool socket.** After `systemctl --user stop ydotoold`, the socket file
  `$XDG_RUNTIME_DIR/.ydotool_socket` stays. llmtr still detected the daemon as unavailable and
  fell back cleanly (`keystrokes=False`), with no "Could not send keystrokes" error.
- **O8. Cleanup time follows the run.** The long-text agent was deleted after 56 s; all others
  took 10–35 s. This is within "a few seconds to a minute" in the README.

## Deviations

- Slack runs were done in VS Code (O6), with the user's agreement.
- The Firefox text area was a local `data:text/html` page with a `<textarea>`, not a website.

## Reruns

Reruns: none. Every item was recorded on its first try. The extra runs in the Runs table were user
actions, not repeats of a failing item:
- three extra short translations in L5;
- a long translation without the second press before L7;
- a press before Ctrl+C in L8.

L2's shortcut was pressed a fourth time only because the user's screenshot had replaced the
clipboard, which made the clipboard check impossible. The result did not change.

## Restored state

| Item | State after the task | User's choice |
| --- | --- | --- |
| `~/.config/llmtr/config.toml` | `engine = "ollama"` on the first line; the rest is byte-identical to the backup | keep `ollama` |
| Key file | `600`, 70 bytes (as before); never read by the worker | unchanged |
| `ydotoold` | active (enabled) | as before |
| llmtr | installed from `41e42cf`; the five GNOME shortcuts unchanged | keep |
| Tone | `team` | unchanged |
| Cursor agents | `llmtr agents left: 0 []` | — |

## Verdict

**Ready with minor fixes.** The Linux-specific risks all passed when started from GNOME shortcuts:
- the key file is read from the shortcut process, and the missing/insecure messages are exact,
  with `~`;
- the detached `cursor-cleanup` child outlives the shortcut process: 12/12 agents deleted, and 0
  left;
- `ydotool` paste, `notify-send` bubbles and the clipboard-only fallback work with this engine;
- cancel takes about 0.8 s;
- Ollama is unaffected.

D4–D6 are a message path and wording fix plus two README lines.

## Mac vs Linux

| | Mac (M16) | Linux (M17) |
| --- | --- | --- |
| Modes run (K5 / L6) | 5.51–10.28 s, median 6.44 s | 6.11–8.52 s, median 7.86 s |
| Short sentence from the shortcut | 6.11 / 9.98 s | 6.02–7.30 s (4 runs) |
| Cancel, second press → "Cancelled." | ≈0.76 s | ≈0.79 s |
| Cleanup in the detached child | 11/11, 3–37 s | 12/12, 10–56 s |
| Agents left | 0 | 0 |
| Key source | Keychain, no dialog | `0600` file, read from the GNOME shortcut |
| Key-missing message | absolute path (D1) | `~` (fixed) |
| Misplaced `engine` | silently ignored (D2) | reported, but the bubble hides the fix (D4) |
| Bad key | 0.41 s | 0.41 s |
