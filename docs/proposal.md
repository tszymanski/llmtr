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
