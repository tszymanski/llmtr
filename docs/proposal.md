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

Decisions by the user, 2026-10-22. Status: **approved 2026-10-22**; M8 spike next.

### Goal

The same five shortcuts and the same flow as on Linux (copy → model → paste, cancel on second press,
tone presets, clipboard-only fallback, log), on Apple silicon Macs. Only the desktop layer and the
installer change; `prompts.py`, `ollama_client.py`, `engine.py`, `langdetect.py`, `config.py`,
`lock.py` and `log.py` are shared.

Test Mac: MacBook Pro M1, 16 GB, macOS 27.0.1. Target apps: Electron apps (Slack, Teams, VS Code),
browsers, native apps, Terminal/iTerm — all of them, which rules out macOS Services as the main path.

### Decisions

| Topic | Decision |
| --- | --- |
| Approach | **Option A**: same flow as Linux, global shortcuts from a hotkey tool. Rejected: Shortcuts.app (hotkeys can't be installed by a script, minimal PATH); macOS Services (no Electron apps, no cancel) — possible later extra for native apps, as it only needs `--stdin`. |
| Hotkey tool | **Hammerspoon** (free, MIT, `brew install --cask hammerspoon`). `install.sh` writes `~/.hammerspoon/llmtr.lua` and adds one `require("llmtr")` line to `init.lua` (idempotent, keeps the user's own config). |
| Default shortcuts | **⌃⌥** (Ctrl+Opt): ⌃⌥T translate, ⌃⌥G fix, ⌃⌥R tone, ⇧⌃⌥R tone --next, ⇧⌃⌥T tone --show. Same letters as Linux. |
| Caps Lock | User's own Mac only: Karabiner-Elements maps Caps Lock (held) → ⌃⌥, so Caps+T/G/R use the defaults with no llmtr config change. **Not** part of `install.sh`; README gets an optional section with the Karabiner rule and its setup (driver extension allowed in Login Items & Extensions, Input Monitoring for `karabiner_grabber`/`karabiner_observer`, Devices → Modify events: without these the rule silently does nothing). |
| Copy/paste keys | `cmd+c` / `cmd+v` (also work in Terminal and iTerm, so `[[keys.override]]` is not needed on macOS). |

### Desktop layer on macOS

| Job | Linux (v1) | macOS (v2) |
| --- | --- | --- |
| Global shortcut | GNOME `gsettings` | Hammerspoon `hs.hotkey.bind` → `hs.task` runs `llmtr` by absolute path |
| Clipboard | `wl-copy` / `wl-paste` | `pbcopy` / `pbpaste` (built in) |
| Copy/paste keystrokes | `ydotool` | `osascript` → System Events `keystroke "c" using command down` (built in; needs Accessibility) |
| Notifications | `notify-send` | `osascript -e 'display notification …'` (built in; cannot replace or close "Translating…") |
| Modifier release | key-up for Super/Alt + `start_delay` | fire the Hammerspoon binding on key **release**, so ⌃⌥ is up before ⌘C is sent |
| Config/state/cache | XDG paths | same XDG paths (`~/.config/llmtr/…`), not `~/Library` |

The platform is chosen once, at startup, from `sys.platform`; the exact module split (one module per
platform or a backend per existing module) is the Architect's call in M8.

### Permissions

macOS requires the user to grant **Accessibility** to Hammerspoon once, by hand, in System Settings →
Privacy & Security. `osascript` runs as Hammerspoon's child, so the permission should carry over —
the spike must confirm this. The installer opens the right Settings pane and explains the step; it
cannot grant it. Without the permission `llmtr` falls back to clipboard-only ("Press ⌘V"), as on
Linux without `ydotool`.

### Models on a 16 GB M1

Unified memory; by default the GPU gets about 2/3 of it (~10–11 GB).

| Model | Size (Q4) | On the test Mac |
| --- | --- | --- |
| `translategemma:12b` | ~8 GB | fits |
| `gemma3:12b` (tone default) | ~8 GB | fits, but not together with translategemma 12b → reload on every switch |
| `gemma3` 4b (fix default) | ~3.3 GB | fits next to translategemma 12b |
| `translategemma:27b` (`--quality`) | ~17 GB | does not fit; `--quality` is not usable on this Mac |

The spike measures real latency; if 12b is too slow or the tone↔translate reload hurts, the user's
config (not the shipped defaults) switches tone to `gemma3` 4b.

### Testing

- Sandboxes run Linux: macOS backends are built there and unit-tested with fakes (no real
  `osascript`/`pbcopy`), as the Linux desktop layer was.
- CI adds a `macos-latest` test job, so the unit tests also run on macOS.
- Real desktop checks run on the test Mac (user acceptance), with a checklist per milestone.

### Milestones (v2)

7. **M8 — macOS spike** (on the test Mac, by an interactive Claude Code session there with the
   user; no sandbox, since it must test the real desktop; it pushes `task/M8-spike` to GitHub and
   the orchestrator reviews it). A short script and checklist: Hammerspoon hotkey →
   shell command, `osascript` keystroke with Accessibility granted to Hammerspoon only,
   `pbcopy`/`pbpaste` round trip, notification, release-triggered binding, Ollama latency for
   12b/4b and the tone↔translate reload. Check: results file with pass/fail per item and timings.
8. **M9 — Architecture update.** Platform layer, macOS backend interfaces, installer split,
   updated `docs/architecture.md`; user approves.
9. **M10 — macOS desktop backends.** Clipboard, keys, notify, focused app on macOS, with fake-based
   tests. Check: unit tests pass on Linux and on the CI macOS runner.
10. **M11 — macOS install + docs.** `install.sh` on macOS (uv tool, Hammerspoon config, Settings
    pane, `--uninstall`), README macOS section incl. the optional Karabiner rule, CI macOS job.
    Check: fresh install on the test Mac gives five working shortcuts.
11. **M12 — Mac acceptance.** User checklist in Slack, a browser, Notes and Terminal; cancel;
    clipboard-only fallback without Accessibility; model defaults confirmed for 16 GB.

### Risks (macOS)

- **Accessibility/TCC:** if the permission does not carry over from Hammerspoon to `osascript`,
  keystrokes fail. Mitigation: spike first; fallback is Hammerspoon sending the keys itself
  (`hs.eventtap.keyStroke`) or clipboard-only.
- **Secure Input:** password fields and Terminal's "Secure Keyboard Entry" block synthetic
  keystrokes. Mitigation: clipboard-only fallback with a clear notification.
- **Existing Hammerspoon config:** the installer only adds one `require` line and its own file.
- **Memory and speed on 16 GB M1:** see the model table; measured in M8.
- **macOS 27 changes:** new release; the spike runs on 27.0.1 before any build.

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
