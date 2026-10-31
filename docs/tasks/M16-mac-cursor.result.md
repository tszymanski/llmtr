# M16-mac-cursor — result

Mac acceptance of the Cursor engine (M15), run interactively with the user on 2026-10-31,
16:50–17:45 local time. Worker: Claude Code session on the Mac (Opus 5.5), normal permission
mode, no sandbox.

## Environment

| Item | Value |
| --- | --- |
| Machine | MacBook Pro M1, 16 GB (arm64) |
| macOS | 27.0.1 (26A434) |
| `main` | `069cea8 Orchestrator: M16-mac-cursor contract (Cursor engine acceptance on the Mac)` |
| llmtr | 0.1.0, `uv tool install` from the clone; tool venv runs Homebrew Python **3.14.7** |
| uv | 0.13.5 (Homebrew) |
| Hammerspoon | 1.1.1 |
| Ollama | 0.40.9 (`translategemma:12b`, `gemma3:12b`, `gemma3:latest`) |
| Cursor model | `gpt-5.4-nano` (default `cursor.model`) |
| Notify backend | `auto` (Hammerspoon bubbles) |

State before the task: `~/.config/llmtr/config.toml` held only `[notify] backend = "auto"`
(no `engine`); no Keychain item `llmtr-cursor` (`security find-generic-password -s llmtr-cursor`
exit 44); no key file; `~/.hammerspoon/llmtr.lua` from M12, `init.lua` = `require("llmtr")`.
`CURSOR_API_KEY` not set. Backups were kept outside the repo until K10.

## Results

| Item | Status | Note |
| --- | --- | --- |
| K1 Update and install | PASS | `./install.sh` exit 0; `llmtr --help` lists `cursor-cleanup`; `translate --help` shows `--engine {ollama,cursor}`; user reloaded the Hammerspoon config. |
| K2 No key yet | PARTIAL | Terminal and ⌃⌥T both give exit 1 / the key-missing bubble, selection and clipboard unchanged; but the message shows the **absolute** home path, not `~` (D1). |
| K3 Keychain item | PASS | User added the item with the README command; check without `-w` → exit 0; `llmtr translate --stdin` via config engine → "Hello, how are you?" in 5.62 s. |
| K4 Keychain from Hammerspoon | PASS | **No Keychain dialog**, neither on the first nor the second ⌃⌥T; selection replaced; `engine=cursor`, 6.11 s and 9.98 s. `security` is found from the Hammerspoon child. |
| K5 Modes and apps | PASS | 4/4 runs correct, 5.51–10.28 s; bubble body `gpt-5.4-nano (Cursor)`; clipboard restored in each run (see Runs). |
| K6 Cancel | PASS | One bubble → "Cancelled."; nothing pasted; clipboard byte-identical; second press → job end **0.76 s**; cancel `POST` succeeded. |
| K7 Cleanup from Hammerspoon | PASS | 11/11 agents have `cursor agent <id6> deleted` from a separate PID, 3–37 s after the run; listing: `llmtr agents left: 0 []`. |
| K8 Bad key message | PASS | Exact text `Cursor rejected the API key. Create a new one in Cursor Dashboard → API Keys.`, exit 1, 0.41 s; env var wins over the Keychain. |
| K9 Ollama unaffected | PASS | `engine = "ollama"`: ⌃⌥T in Notes → "Thank you for the quick response and assistance.", `model=translategemma:12b engine=ollama`, 16.38 s (cold load); bubble body `translategemma:12b`; clipboard restored. |
| K10 Restore | PASS | User's choice: `engine = "ollama"` kept, Keychain item kept, llmtr stays installed (see Restored state). |
| K11 README check | PARTIAL | Steps work as written, but `engine` misplaced under a section is silently ignored (D2) and key replace/removal is not documented (D3). |

## Runs

K4–K6 from the Hammerspoon shortcuts, engine `cursor`, model `gpt-5.4-nano`. Times from
`llmtr log` (`duration`); "deleted after" = cleanup line time − run line time.

| # | Run | Where | Result | Time | Agent | Deleted after |
| --- | --- | --- | --- | --- | --- | --- |
| K3 | CLI `translate --stdin`, PL sentence | Terminal | "Hello, how are you?" | 5.62 s | bc-9ee | 33 s |
| K4a | ⌃⌥T PL→EN, short sentence | Notes | replaced, correct | 6.11 s | bc-b90 | 34 s |
| K4b | ⌃⌥T PL→EN, second press check | Notes | replaced, correct | 9.98 s | bc-fd6 | 5 s |
| K5.1 | ⌃⌥T PL→EN, `pl_paragraph.txt` | Notes | full EN translation; clipboard byte-identical | 5.51 s | bc-86b | 32 s |
| K5.2 | ⌃⌥T EN→PL, `en_paragraph.txt` | VS Code | PL, diacritics intact (ą ć ę ł ń ó ś ż all present); clipboard byte-identical | 10.28 s | bc-698 | 32 s |
| K5.3 | ⌃⌥G fix, "…do skelpu… chlep…" | Notes | "Wczoraj poszedłem do sklepu i kupiłem świeży chleb oraz mleko." Only the two typos changed | 6.86 s | bc-f96 | 37 s |
| K5.4 | ⌃⌥R tone, preset `team` | Notes | formal PL → "Hej! Jutro spotykamy się o 14:00. Daj proszę znać, czy będziesz."; clipboard restored | 6.02 s | bc-273 | 33 s |
| — | ⌃⌥G fix, wrong key, cancelled by user | Notes | cancelled | 5.27 s | bc-aab | 6 s |
| — | ⌃⌥G fix, wrong key, cancelled by user | Notes | cancelled (cancel `POST` → `HTTPStatusError`, ignored by design) | 6.38 s | bc-170 | 33 s |
| — | ⌃⌥R tone, repeat | Notes | ok | 10.94 s | bc-f41 | 32 s |
| K6 | ⌃⌥T `en_long.txt`, cancelled | Notes | "Cancelled.", nothing pasted, clipboard byte-identical | 2.64 s | bc-420 | 3 s |

All runs are within M14's 6–14 s, and three are faster (5.5–6.0 s). Bubbles seen:
"Translating PL → EN…", "Fixing grammar…" and "Rewriting: team…", each with the body
`gpt-5.4-nano (Cursor)`. One bubble per run.

Cursor usage: 11 agents created, plus 1 rejected request (K8) and one listing. That is within the
~20 budget.

The two wrong-key ⌃⌥G runs and the repeat ⌃⌥R run were user actions: the user pressed the wrong
shortcut, cancelled it and tried again. They are not reruns of a failing item. They also show
cancel working for `fix` from Hammerspoon.

## Timings

| Item | Value |
| --- | --- |
| K2 key missing (shortcut) | 0.44 s to the error |
| K3 CLI translate | 5.62 s (wall 5.80 s) |
| K4 shortcut translate | 6.11 s, 9.98 s |
| K5 | 5.51 / 10.28 / 6.86 / 6.02 s (median 6.44 s) |
| K6 cancel | first press 0.00 s; "Translating…" sent 0.54 s; second press 1.92 s; cleanup child spawned 2.65 s; job ended (`outcome=cancelled`, "Cancelled.") 2.68 s → **second press to "Cancelled." ≈ 0.76 s**; user saw it as "1 or 2 s" |
| K7 delete in the detached child | 3–37 s after the run (11/11) |
| K8 bad key | 0.41 s |
| K9 Ollama translate | 16.38 s (includes the cold model load) |

K6 was measured with a process watcher (`ps` polled every 50 ms; new `llmtr` processes and
`open hammerspoon://llmtr…` calls timestamped) plus the log line. M15's warning of up to ~5 s did
not happen here, because the cancel `POST` answered quickly.

## Dialogs

- **Keychain:** **none.** No dialog in K4 (two runs), the K5/K6 runs or the uv-run listing. The
  item was created by `/usr/bin/security`, which is therefore in its access list, and llmtr reads
  it through `security` as well.
- **`security add-generic-password … -w` (K3):** it prompted for the key in the user's own
  Terminal. The user reported no output besides the prompts. The exact prompt wording was not
  captured (macOS normally shows `password data for new item:` and
  `retype password for new item:`).
- **System dialogs:** none. The permissions from M12 were still in place, and `install.sh` only
  opened the three Settings panes.
- **Bubbles (exact):**
  - K2: title `Hammerspoon`, body `No Cursor API key. Put it in /Users/<user>/.config/llmtr/cursor-api-key (mode 600) or in the Keychain as llmtr-cursor.`
    The absolute path wraps the bubble to five lines.
  - K4/K5: `Translating PL → EN…` / `gpt-5.4-nano (Cursor)`, `Fixing grammar…` /
    `gpt-5.4-nano (Cursor)`, `Rewriting: team…` / `gpt-5.4-nano (Cursor)`.
  - K6: one bubble, `Translating EN → PL…` → `Cancelled.`
  - K9: `Translating PL → EN…` / `translategemma:12b`.

## Defects

**D1 (K2, minor): key-missing message shows the absolute home path.**
- Steps:
  1. No `CURSOR_API_KEY`, no Keychain item, no key file.
  2. Run `echo "Dzień dobry" | llmtr translate --engine cursor --stdin`, or press ⌃⌥T with
     `engine = "cursor"`.
- Seen: `No Cursor API key. Put it in /Users/<user>/.config/llmtr/cursor-api-key (mode 600) or in the Keychain as llmtr-cursor.`
  The log line has the same text, with `~` only because of our own redaction.
- Expected (architecture §23.5 and the contract): `… Put it in ~/.config/llmtr/cursor-api-key …`.
- Impact:
  - the bubble wraps to five lines;
  - the username ends up in screenshots and bug reports.
- Suggested fix:
  - In `src/llmtr/errors.py`, have `CursorKeyMissing.__init__` (and `CursorKeyInsecure`) show the
    path with the home directory collapsed to `~`, e.g. a helper
    `_tilde(path) = "~/" + str(path.relative_to(Path.home()))` when the path is under home.
  - Keep `self.path` absolute.
  - Add a test in `tests/test_errors.py` (or the cursor_key tests) with `HOME` set to a tmp
    directory.

**D2 (K11, minor): `engine` placed under a section is silently ignored.**
- Steps:
  1. Start from an existing config that ends with `[notify]\nbackend = "auto"`.
  2. Append `engine = "cursor"` at the end, as a new user easily does.
  3. Run `echo "Dzień dobry" | CURSOR_API_KEY=not-a-real-key llmtr --config <that file> translate --stdin`.
- Seen: `Good morning.`, exit 0, log `model=translategemma:12b … engine=ollama`. TOML reads the key
  as `notify.engine`, and unknown keys are ignored (`config.py` docstring at line 376).
- Impact: no privacy leak, since the text stays local. But for a Cursor-only user, where Ollama is
  forbidden or absent, the result is a confusing Ollama error or an unexpected Ollama run.
- Suggested fix:
  - README "Cursor engine (optional)" → "Config.": add *"`engine` is a top-level key: put it on
    the first line of `config.toml`, above any `[section]`."*
  - Optionally, in `src/llmtr/config.py`, raise `ConfigError` (or log a warning) when a known
    top-level key such as `engine` appears inside another table, e.g. `notify.engine`. Add a test.

**D3 (K11, minor): README has no macOS step to replace or remove the Keychain key.**
- Seen:
  - Running the README `security add-generic-password …` a second time, e.g. after revoking a key,
    fails because the item already exists.
  - Uninstall (`./install.sh --uninstall` and the "Uninstall" section) does not mention the
    Keychain item or the key file.
- Suggested fix, in README "API key, macOS", after the command: *"To replace the key later, add
  `-U`: `security add-generic-password -U -s llmtr-cursor -a "$USER" -w`. To remove it:
  `security delete-generic-password -s llmtr-cursor`."* In "Uninstall", add *"The Cursor key stays
  in the Keychain (`llmtr-cursor`) or in `~/.config/llmtr/cursor-api-key`; remove it as shown in
  "Cursor engine (optional)", and revoke it in Cursor Dashboard → API Keys."*

### Observations (no status impact)

- **O1. Short agent id keeps the `bc-` prefix.** `_short()` in `src/llmtr/cursor_client.py` takes
  the first 6 characters (`bc-9ee`), so only 3 hex characters tell agents apart. Suggestion: strip
  a leading `bc-` before taking 6 characters, or take 9.
- **O2. Outdated top-level help.** `llmtr --help` still says "…with a local Ollama model". Suggestion:
  "…with a local Ollama model or a Cursor cloud agent (`--engine cursor`)" in `src/llmtr/cli.py`.
- **O3. Tool venv uses Python 3.14.** `uv tool install` picked Homebrew Python 3.14.7, while the
  project targets 3.13. Everything worked. If 3.13 should be enforced, `install.sh` /
  `scripts/install-macos.sh` could pass `--python 3.13`.
- **O4. Full agent id in the cleanup child's argv.** The full id is visible in `ps`
  (`-m llmtr cursor-cleanup bc-…`). It is not a secret, so no change is needed. Noted because the
  log deliberately shortens it.
- **O5. M15 open issues confirmed on the real Mac.**
  - #3: `GET /v1/agents?includeArchived=true&limit=100` works and the response key is `items`; the
    sweep ran with `0 leftover`.
  - #4: no `/usr/bin/security` change is needed.
  - #5: cancel took ≈0.8 s.

## Reruns

Reruns: none. Every item passed or was recorded on its first try. The extra ⌃⌥G and ⌃⌥R runs in
the Runs table were user key mistakes, not repeats of a failing item. The K11 config probe was
run twice only because macOS has no `timeout` command (exit 127 before llmtr started).

## Restored state

| Item | State after the task | User's choice |
| --- | --- | --- |
| `~/.config/llmtr/config.toml` | `engine = "ollama"` on the first line, then the original `[notify] backend = "auto"` | keep `ollama` |
| Keychain item `llmtr-cursor` | present (exit 0 without `-w`) | keep |
| llmtr | installed (new version from `069cea8`), `~/.hammerspoon/llmtr.lua` rewritten by `install.sh` | keep |
| Cursor agents | `llmtr agents left: 0` | — |
| Clipboard | test text from K9 restored | — |

## Verdict

**Ready with minor fixes.** The Mac-only risks all passed on the real machine:
- the Keychain lookup from a Hammerspoon child works, with no dialog;
- the detached cleanup child outlives the Hammerspoon task, 11/11 agents deleted;
- cancel shows "Cancelled." in about 0.8 s, with one bubble and the clipboard restored;
- Ollama is unaffected.

D1–D3 are wording and documentation fixes: an absolute path in one message, a silently ignored
misplaced `engine` key, and the missing key replace/remove steps.
