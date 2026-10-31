# llmtr — approved proposal (2026-10-03)

Source of truth for scope and decisions. Mirrors the reviewed proposal doc:
https://claude.ai/code/artifact/a102dc3b-5655-44fe-a856-479048ed7feb

## Goal

`llmtr` is a small Python CLI. GNOME shortcuts call it. It takes the selected text, sends it to the
local Ollama server and replaces the selection with the result.

Modes:

| Mode | What it does | Default model |
| --- | --- | --- |
| `translate` | PL↔EN, direction detected automatically (Polish in → English out, otherwise → Polish) | `translategemma:12b` (`--quality` → `translategemma:27b`) |
| `fix` | Grammar and spelling only, same language, keep meaning and formatting | `gemma3` (M5: Bielik rejected — translated Polish in 30% of samples) |
| `tone` | Rewrite in the current tone preset, same language | `gemma3:12b` (M5b, user decision 2026-10-04: formal Polish 100% vs 77% register; ~6 s reload when alternating with translate on 16 GB) |

Out of scope for v1: GUI windows, diff view, history browser, cloud APIs, Windows/macOS, streaming
into the active window, languages other than PL and EN, non-text clipboard content (images and
files are not translated, saved or restored — confirmed by the user 2026-10-04).

**2026-10-22:** macOS is now in scope as v2 — see [macOS support (v2)](#macos-support-v2).

**2026-10-29:** a Cursor Cloud Agents engine is being evaluated (spike only) — see
[Cursor engine (v3, spike)](#cursor-engine-v3-spike).

## User flow

1. Select text in any app.
2. Press a shortcut: `Super+Alt+T` translate, `Super+Alt+G` fix, `Super+Alt+R` rewrite in the
   current tone, `Super+Alt+Shift+R` switch to the next tone preset.
3. `llmtr` saves the current clipboard, sends the configured **copy key** through `ydotool`, and
   reads the copied text with `wl-paste`.
4. Notification: "Translating…" + model name (`notify-send`).
5. `llmtr` puts the result on the clipboard (`wl-copy`), sends the configured **paste key**, which
   replaces the selection, then restores the old clipboard.
6. If `ydotool` is unavailable, the result stays on the clipboard and the notification says
   "Press Ctrl+V".

A second press while a job runs cancels it (single-run lock). The last result is kept in
`~/.cache/llmtr/last.txt`.

### Copy/paste keys

These are keys `llmtr` **sends** after its own shortcut is pressed — never triggers. A normal
Ctrl+C/Ctrl+V by the user never starts a translation. Default `ctrl+c` / `ctrl+v`; optional per-app
overrides:

```toml
[keys]
copy = "ctrl+c"
paste = "ctrl+v"

[[keys.override]]
app = ["org.gnome.Terminal", "kitty"]
copy = "ctrl+shift+c"
paste = "ctrl+shift+v"
```

GNOME on Wayland does not expose the focused window class to scripts. Overrides need a Shell
extension (e.g. Window Calls) or a D-Bus call that M3 tests; without one only the default pair is
used. `wl-paste --primary` hung on this machine, so the flow copies with a key.

**Decision 2026-10-04:** v1 targets GUI apps only and does **not** depend on Window Calls; only the
default `ctrl+c` / `ctrl+v` pair is used. Future terminal support: install the Window Calls
extension (https://github.com/ickyicky/window-calls), read the focused window's `wm_class` via
`gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell/Extensions/Windows
--method org.gnome.Shell.Extensions.Windows.List`, and enable `[[keys.override]]` for terminals
(`ctrl+shift+c` / `ctrl+shift+v`). The override code path can stay, inactive without the extension.

### Tone (option A)

- Current tone stored in `~/.local/state/llmtr/state.toml`.
- `Super+Alt+R` rewrites in the current tone; `Super+Alt+Shift+R` cycles to the next preset and
  shows its name in a notification.
- v1 ships one preset, the default: **`team` — informal team message**: casual and friendly, short
  sentences, first names, no stiff formulas, same language as the input.
- More presets live in `config.toml` as name + instruction; cycling works once there are two.
- **2026-10-04:** user config has three presets: `team`, `formal`, `concise` (instructions in
  `~/.config/llmtr/config.toml`). `Shift+Super+Alt+T` → `llmtr tone --show` shows the current
  tone (`Tone: formal (2/3)` + instruction) without changing it.
- **Finding for M5:** `gemma3` sometimes ignores "never translate" (formal tone turned Polish into
  English and added a subject line). Spelling out "Write in the SAME language as the input" and "no
  subject/greeting/signature" in the preset instruction fixed it in a spot check. M5 should move
  this into `TONE_SYSTEM_PROMPT_TEMPLATE` and measure it.

## Architecture

```
GNOME shortcut ──runs──▶ llmtr CLI ──HTTP /api/chat──▶ Ollama :11434
                           │  cli.py          mode dispatch, lock, cancel
                           │  prompts.py      prompt builders per mode/model
                           │  ollama_client.py POST, stream=false, keep_alive
                           │  config.py       config.toml + state.toml
                           │  clipboard.py    wl-copy / wl-paste (xclip fallback)
                           │  keys.py         ydotool copy/paste keystrokes
                           │  notify.py       notify-send
                           ▼
                        clipboard / notifications
```

The desktop side and the model side never talk directly; only `llmtr` touches both, so a model or
clipboard tool can be swapped in one module. Final module boundaries are set in M1
(`docs/architecture.md`).

## Model notes

`translategemma` is translation-only and expects this exact prompt, then **two blank lines**, then
the text:

> You are a professional {SOURCE_LANG} ({SOURCE_CODE}) to {TARGET_LANG} ({TARGET_CODE}) translator.
> Your goal is to accurately convey the meaning and nuances of the original {SOURCE_LANG} text while
> adhering to {TARGET_LANG} grammar, vocabulary, and cultural sensitivities. Produce only the
> {TARGET_LANG} translation, without any additional explanations or commentary. Please translate the
> following {SOURCE_LANG} text into {TARGET_LANG}:

Measured 2026-10-03 on RTX 5060 Ti 16 GB, temperature 0, 4K context:

| Case | 27b (s) | 12b (s) |
| --- | --- | --- |
| PL→EN sentence, cold start | 9.6 | 4.6 |
| PL→EN sentence, loaded | 2.4 | 0.7 |
| PL→EN paragraph (60 words) | 10.4 | 2.3 |
| EN→PL paragraph (70 words) | 16.3 | 3.5 |
| EN→PL long text (220 words) | 34.6 | 7.0 |
| Output tokens/s | 9 | 49 |

27b spills 19% to CPU; 12b runs 100% on GPU. Use `keep_alive` to avoid the cold start.

Installed models: `translategemma:12b`, `translategemma:27b`, `gemma3`, `Bielik-tansleter`,
`SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0`.

## Orchestration approach

The orchestrator (main Claude Code session, on the host) owns the plan, writes task contracts in
`docs/tasks/`, and merges. It does not write feature code. Workers run in Docker Sandboxes (`sbx`)
on a private clone of the repo.

| Agent | Owns | Hands back |
| --- | --- | --- |
| Orchestrator | plan, task contracts, merge order | merged `main`, status per milestone |
| Architect | module boundaries, interfaces, config schema | `docs/architecture.md`, typed stubs |
| Core worker | `ollama_client.py`, `prompts.py`, language detection | code + unit tests (Ollama mocked) |
| Desktop worker | `clipboard.py`, `keys.py`, `notify.py`, lock/cancel | code + tests with fake backends |
| Integration worker | `cli.py`, `install.sh`, GNOME shortcuts, README | working CLI, install script |
| Reviewer | review against the contract | pass, or fixes back to the worker |
| Evaluator | quality on real models | score table per model and mode |

- **Hand-off contract:** goal, files the worker may touch, interface to match, commands that must
  pass, out of scope. A worker that needs to cross its file boundary reports back instead.
- **Review loop:** a failed review goes back to the same worker at most twice, then to the
  orchestrator to re-scope. Nothing merges without green tests.
- **Log:** time, tokens and review rounds per task in `docs/orchestration-log.md`.

### Sandboxes

- Network: start from deny-all; allow only the Anthropic API + login hosts, `pypi.org`,
  `files.pythonhosted.org`, and `localhost:11434` (Ollama). Inside a sandbox, code calls
  `http://host.docker.internal:11434`; the proxy rewrites it to the host's localhost.
- Workers test with Ollama mocked; only the integration smoke test and the evaluator call the real
  server.
- Clipboard/notifications cannot be tested inside a sandbox; the desktop worker uses fakes and the
  real check runs on the host.
- Fallback: plain `docker run` with only the clone mounted, running `claude -p <task file>`.

## Milestones

1. **M0 — Setup.** git, uv project, ruff + pytest, task files, `sbx` test sandbox runs `pytest` and
   reaches Ollama. Check: `uv run pytest` passes inside a sandbox.
2. **M1 — Architecture.** Interfaces + config schema; user approves `docs/architecture.md`.
3. **M2 — Core (parallel with M3).** Ollama client, prompt builders, language detection. Check: unit
   tests pass; manual PL→EN run works.
4. **M3 — Desktop (parallel with M2).** Clipboard, keys via `ydotool`, `notify-send`, lock with
   cancel. Check: copy/process/paste works in gedit and Firefox (on the host).
5. **M4 — Integration.** `llmtr` CLI, `install.sh` (GNOME custom shortcuts via `gsettings`, ydotool
   udev rule + user service), README. Check: fresh install gives four working shortcuts.
6. **M5 — Evaluation.** ~20 PL/EN samples per mode across translategemma 12b/27b, gemma3, Bielik.
   Check: score + latency table; defaults confirmed.

## macOS support (v2)

Decisions by the user, 2026-10-22 and (after the M8 spike) 2026-10-25. Status: **done, closed by the
user 2026-10-27.** All milestones below are merged, M12 acceptance passed on the test Mac, and CI is
green on Linux and macOS (Python 3.13 and 3.14). Task records: `docs/tasks/M8-*` to `M13-*`; timing,
review rounds and lessons: `docs/orchestration-log.md`.

### Goal

The same five shortcuts and the same flow as on Linux (copy → model → paste, cancel on second press,
tone presets, clipboard-only fallback, log), on Apple silicon Macs. Only the desktop layer and the
installer change; `prompts.py`, `ollama_client.py`, `engine.py`, `langdetect.py`, `config.py`,
`lock.py` and `log.py` are shared. M8: the existing suite already passes on macOS (309 tests).

Test Mac: MacBook Pro M1, 16 GB, macOS 27.0.1. Target apps: Electron apps (Teams, VS Code; Slack is
not installed), browsers, native apps, Terminal/iTerm — all of them, which rules out macOS Services
as the main path.

### Decisions

| Topic | Decision |
| --- | --- |
| Approach | **Option A**: same flow as Linux, global shortcuts from a hotkey tool. Rejected: Shortcuts.app (hotkeys can't be installed by a script, minimal PATH); macOS Services (no Electron apps, no cancel) — possible later extra for native apps, as it only needs `--stdin`. |
| Hotkey tool | **Hammerspoon** (free, MIT, `brew install --cask hammerspoon`). `install.sh` writes `~/.hammerspoon/llmtr.lua` and adds one `require("llmtr")` line to `init.lua` (idempotent, keeps the user's own config; creates `init.lua` if there is none). |
| Default shortcuts | **⌃⌥** (Ctrl+Opt): ⌃⌥T translate, ⌃⌥G fix, ⌃⌥R tone, ⇧⌃⌥R tone --next, ⇧⌃⌥T tone --show. Same letters as Linux. M8: no conflicts in Teams, Chrome, VS Code, Notes, Terminal. |
| Binding trigger | **On key release, no start delay** (M8: the press binding fails while the letter key is still down; a still-held ⌃⌥ or Caps is harmless). |
| Keystrokes | **`osascript` → System Events, called from `llmtr`** (M8 S5), so the whole flow stays in shared Python. Documented fallback: `hs.eventtap.keyStroke` from Lua (S6, same speed, Accessibility only). |
| Notifications | **`hs.notify`** (shows as Hammerspoon, "Translating…" can be withdrawn/replaced) through a `hammerspoon://llmtr?…` URL event; **fallback `osascript display notification`** (shows as "Script Editor", cannot be replaced). User decision 2026-10-25. |
| Caps Lock | User's own Mac only: Karabiner-Elements maps Caps Lock (held) → ⌃⌥, tap alone = Caps Lock. **Not** part of `install.sh`; README gets an optional section with the rule and the setup from M8 (below). |
| Copy/paste keys | `cmd+c` / `cmd+v` (also work in Terminal and iTerm, so `[[keys.override]]` is not needed on macOS; M8 S8). |
| Models | Shipped defaults unchanged; the user keeps `gemma3:12b` for tone on the Mac and accepts the M1 speed (2026-10-25). |
| Python | No `.python-version` pin: code targets 3.13, CI tests 3.13 and 3.14, uv may pick either (2026-10-25). |

### Desktop layer on macOS

| Job | Linux (v1) | macOS (v2) |
| --- | --- | --- |
| Global shortcut | GNOME `gsettings` | Hammerspoon `hs.hotkey.bind(mods, key, nil, fn)` (release) → `hs.task` runs `llmtr` **by absolute path** (`hs.task` children get `PATH=/usr/bin:/bin:/usr/sbin:/sbin`) |
| Clipboard | `wl-copy` / `wl-paste` | `/usr/bin/pbcopy` / `/usr/bin/pbpaste`, **always with `LC_CTYPE=UTF-8`** in their env (Hammerspoon children have no locale; Polish text is garbled otherwise). Empty clipboard or an image → empty output |
| Copy/paste keystrokes | `ydotool` | `/usr/bin/osascript` → System Events `keystroke "c" using command down` |
| Notifications | `notify-send` | `hs.notify` via URL event; fallback `osascript display notification` |
| Modifier release | key-up for Super/Alt + `start_delay` | release binding, no delay |
| Secure Input | — | detected as "nothing copied" (existing check); then `ioreg -l -w 0` (`kCGSSessionSecureInputPID`) names the app in the message |
| Config/state/cache | XDG paths | same XDG paths (`~/.config/llmtr/…`), not `~/Library` |

Measured in M8 without a model: hotkey → paste 0.43–0.50 s. The platform is chosen once, at
startup, from `sys.platform`; the exact module split is the Architect's call in M9.

### Permissions (macOS 27.0.1, all for Hammerspoon only)

1. Privacy & Security → **Accessibility** (titled "Device Control and Data Access" on macOS 27):
   Hammerspoon on. Without it `osascript` fails with "osascript is not allowed to send keystrokes
   (1002)"; no `osascript` entry is needed.
2. Privacy & Security → **Automation** → Hammerspoon → System Events on. A dialog asks on the first
   ⌘C ("“Hammerspoon” wants access to control “System Events”"); the installer can trigger it.
3. **Notifications** → Hammerspoon → Allow notifications, then restart Hammerspoon (no prompt is
   shown; only for `hs.notify`).

The shortcuts themselves need no permission. The installer opens the right Settings panes and
explains the steps; it cannot grant them. Without 1–2 the copy keystroke fails with a message that
names the missing Hammerspoon setting (**not** a clipboard-only fallback, which would process stale
clipboard text; M9 deviation, user approved 2026-10-25). Clipboard-only ("Press ⌘V") still applies
when the paste fails or `osascript` is missing.

### Karabiner setup (for the README, from M8)

On the test Mac the rule was enabled but silently did nothing until:
1. Driver extension allowed (Login Items & Extensions → Driver Extensions).
2. Input Monitoring: add **`Karabiner-Core-Service`** by hand (+ → ⌘⇧G →
   `/Library/Application Support/org.pqrs/Karabiner-Elements/Karabiner-Core-Service.app`), then
   restart Karabiner-Elements (Karabiner 16; older versions used `karabiner_grabber`/`_observer`).
3. Devices → Apple Internal Keyboard → Modify events on.
4. ISO keyboards: Devices → "Swap ISO layout-specific keys" on, or `` ` ``/`~` produce `§`.
5. Check in Karabiner-EventViewer: Caps held + T shows `left_control`, `left_option`, then `t`.

### Models on a 16 GB M1 (measured in M8)

Unified memory; the GPU gets about 2/3 (~10.7 GB). Generation is memory-bandwidth bound (~68 GB/s).

| Model | Size | On the test Mac |
| --- | --- | --- |
| `translategemma:12b` | ~8 GB | 7.7 tokens/s; sentence 3.5 s loaded, paragraph 12–21 s, long text (220 words) 51–55 s, cold +14 s |
| `gemma3:12b` (tone) | ~8 GB | 7.8 tokens/s; tone paragraph 9–15 s loaded; really rewrites |
| `gemma3` 4b (fix) | ~3.4 GB | 22.7 tokens/s; 4–7 s; barely changes the tone (so not used for tone) |
| `translategemma:27b` (`--quality`) | ~17 GB | does not fit; `--quality` is not usable on this Mac |

**Only one model stays loaded**, even translategemma 12b + gemma3 4b: every switch between
translate and tone/fix reloads (+6–8 s for translate, +4 s for 4b, +9 s for 12b). With 10–50 s jobs,
a visible "Translating…" notification and a working cancel matter more than on Linux.

### Testing

- Sandboxes run Linux: macOS backends are built there and unit-tested with fakes (no real
  `osascript`/`pbcopy`), as the Linux desktop layer was. One test must check that the clipboard
  backend sets `LC_CTYPE=UTF-8` even when `os.environ` has no locale.
- CI adds a `macos-latest` test job, so the unit tests also run on macOS.
- Real desktop checks run on the test Mac (user acceptance), by an interactive Claude Code session
  there; it pushes its `task/<id>` branch to GitHub and the orchestrator reviews and squash-merges.

### Milestones (v2)

All done. Each line: what it delivered, then the result.

7. **M8 — macOS spike** (Mac, interactive) — **done 2026-10-25.** Hotkeys, keystrokes, clipboard,
   permissions and model speed measured on the real Mac; found the locale bug in Hammerspoon
   children and the need for release bindings.
8. **M9 — Architecture update** — **done 2026-10-25**, approved by the user. Platform layer and
   macOS interfaces (`docs/architecture.md` §11–22); permission failure is an error, not a
   clipboard-only fallback.
9. **M10 — macOS desktop backends** — **done 2026-10-25.** pbcopy/pbpaste, osascript keystrokes,
   Hammerspoon notifications, probes; fake-based tests.
10. **M11 — macOS install + docs** — **done 2026-10-26** (1 fix round: bash 3.2 broke the Lua file).
    `scripts/install-macos.sh`, `macos/llmtr.lua.in`, README macOS section, CI `test-macos`.
    Follow-ups: **M11-fix1** (Linux installer tests forced to Linux on the macOS runner),
    **M11-fix2** (empty arrays under `set -u` on bash < 4.4 wiped the GNOME keybinding list).
11. **M12 — Mac acceptance** — **done 2026-10-26**: 12 PASS, 1 PARTIAL. Follow-ups: **M12-fix1**
    (Accessibility message names "Device Control and Data Access" on macOS 27, uv_build range,
    README) and **M12-fix2** (cancel shows one bubble after all; README wording).
12. **M13 — Backends cleanup** — **done 2026-10-26.** `cli.py` gets its desktop and notifier from
    `backends.py` on both platforms.

Possible later work (not planned): macOS Services as an extra for native apps, more language pairs,
a smaller translate model for the M1.

### Risks (macOS)

- **Speed on M1:** 12–21 s per translated paragraph (bandwidth bound); accepted by the user.
  Mitigation: notification, cancel, `keep_alive`.
- **Permissions:** three manual steps; a missed one must give a clear message, not a silent failure.
- **Locale/PATH in Hammerspoon children:** absolute tool paths and `LC_CTYPE=UTF-8` (M8 bug).
- **Existing Hammerspoon config:** the installer only adds one `require` line and its own file.
- **macOS updates:** M8 ran on 27.0.1; Settings names already differ from older macOS.

## Cursor engine (v3, spike)

Opened by the user 2026-10-28. Status: **M14 spike done 2026-10-31 (verdict: go, as an opt-in engine); M15 merged 2026-10-31; Linux hotkey and Mac checks pending.**

### Goal

Support a user who may use **only Cursor and the Cursor API**, with Ollama and other cloud LLMs
forbidden. llmtr would send the selected text to the Cursor Cloud Agents REST API v1
(`https://api.cursor.com/v1`) as a no-repo agent and paste the answer. Ollama stays the default
engine. The selected text leaves the machine, which reverses the local-only premise for this
engine, so the README must say so.

### Decisions so far (user, 2026-10-29)

| Topic | Decision |
| --- | --- |
| API | Cursor Cloud Agents REST API v1 at `https://api.cursor.com`. Rejected for now: Cursor CLI (`agent -p`), legacy v0 API. |
| Order | Measure first (M14 spike), then design the engine from the findings (M15). |
| API key | Never in `config.toml`, never in a sandbox. Storage method decided after M14. |

### Milestones (v3)

13. **M14 — Cursor spike** (host, interactive, user's API key) — **done 2026-10-31.** No-repo
    agents work: fresh agent + stream gives 5.8–13.9 s per call (`gpt-5.4-nano` fastest), output
    clean, no tool use. Needs Cursor "Privacy Mode" (storage on), not "Privacy Mode (Legacy)".
    `DELETE` is slow (median 11.7 s), so cleanup must run after the paste. `sbx` blocks
    `api.cursor.com`. Findings and the M15 recommendation: `docs/tasks/M14-cursor-spike.result.md`.
14. **M15 — Cursor engine** (sbx worker, fakes only) — contract `docs/tasks/M15-cursor-engine.md`.
    Opt-in `engine = "cursor"`, default model `gpt-5.4-nano`; fresh no-repo agent per call, SSE
    stream, delete in a detached child after the paste, hourly sweep of leftover `llmtr-` agents;
    key from `CURSOR_API_KEY`, the macOS Keychain (`llmtr-cursor`) or a `0600` file; README privacy
    note (user decisions 2026-10-31). **Merged 2026-10-31:** 601 tests; real-API test and a CLI
    translate pass on the host, agents deleted in the background ~30 s later. Pending: Linux hotkey
. **M16 — Mac acceptance of the Cursor engine** (Mac, interactive) — contract
    `docs/tasks/M16-mac-cursor.md`. Keychain lookup from a Hammerspoon child (PATH, Keychain
    dialog), the detached cleanup child, notifications, cancel, error messages, Ollama unaffected,
    README steps.

### Risks (Cursor)

- **Latency:** every call may start a cloud agent; there are no published startup times.
- **Agent with tools:** selected text could steer the agent (prompt injection). The prompt frames
  the text as data; M14 tests it.
- **Rate limit:** 20 requests per minute by default, and one call takes several requests.
- **Leftovers and cost:** every call creates an agent that must be deleted, and usage is billed to
  the user's Cursor plan.
- **Privacy:** the text is sent to Cursor's cloud.

## Risks

- **Wayland keystrokes:** `ydotool` is not installed; it needs `ydotoold` and write access to
  `/dev/uinput` (root-only now). `install.sh` adds a udev rule and a user service. Clipboard-only
  fallback always works.
- **Latency:** 12b: 2–4 s per paragraph, ~7 s long text. Mitigation: `keep_alive`, notification,
  cancel.
- **Model chatter:** general models add preambles ("Here is the corrected text:"). Mitigation: strict
  system prompts, temperature 0, a post-filter that strips preambles.
- **translategemma for fix/tone:** trained only to translate; if M5 shows same-language
  "translation" fixes grammar well, the second model can be dropped.
