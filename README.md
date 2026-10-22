# llmtr

A small command-line tool for GNOME on Wayland: select some text anywhere, press a shortcut, and
`llmtr` translates it (PL↔EN), fixes its grammar, or rewrites its tone — using a local Ollama
model — then pastes the result back over the selection.

## What it does

| Shortcut | Command | What happens |
| --- | --- | --- |
| `Super+Alt+T` | `llmtr translate` | Translate the selection. Polish in → English out, anything else → Polish. |
| `Super+Alt+G` | `llmtr fix` | Fix grammar and spelling only, same language, same meaning and formatting. |
| `Super+Alt+R` | `llmtr tone` | Rewrite the selection in the current tone preset (same language). |
| `Shift+Super+Alt+R` | `llmtr tone --next` | Switch to the next tone preset and show its name (no text is processed). |
| `Shift+Super+Alt+T` | `llmtr tone --show` | Show the current tone preset's name and instruction (no text is processed). |

A second press of a shortcut while a job is running cancels it. If `ydotool` isn't set up, the
result is left on the clipboard instead of being pasted automatically, with a notification
reminding you to press Ctrl+V. Only plain text is handled — images and files on the clipboard are
left untouched.

## Requirements

- Linux with GNOME on Wayland (uses `gsettings` custom shortcuts).
- [uv](https://docs.astral.sh/uv/) — used to install and run the CLI.
- A running [Ollama](https://ollama.com) server with the models you plan to use pulled, e.g.:
  ```bash
  ollama pull translategemma:12b
  ollama pull gemma3
  ollama pull gemma3:12b
  ```
  `tone` defaults to `gemma3:12b` for better formal Polish; alternating it with `translate` costs
  about a 6 s model reload on a 16 GB GPU.
- `wl-clipboard` (`wl-copy`/`wl-paste`) or `xclip`, and `notify-send` (usually part of
  `libnotify-bin`).
- `ydotool` ≥ 1.0 with the `ydotoold` user service, for automatic copy/paste keystrokes. Without
  it, llmtr still works in clipboard-only mode (you copy by hand, trigger the shortcut, then
  paste by hand).

## Install

```bash
# 1. Set up ydotool (needs sudo once, for a udev rule and a systemd user service):
./scripts/install-ydotool.sh
# ...or let install.sh do it for you:
./install.sh --with-ydotool

# 2. Install the CLI and register the five GNOME shortcuts:
./install.sh
```

`install.sh` is idempotent: re-running it updates llmtr's own shortcuts in place rather than
duplicating them, and leaves any other app's custom shortcuts untouched. It never calls `sudo`
itself; only `scripts/install-ydotool.sh` does (and only when you run it, directly or via
`--with-ydotool`).

Other `install.sh` flags:

```bash
./install.sh --dry-run      # print every command instead of running it
./install.sh --uninstall    # remove llmtr's shortcuts and the uv tool; keeps config and ydotool
```

## Config

Copy [`config.example.toml`](config.example.toml) to `~/.config/llmtr/config.toml` (or
`$XDG_CONFIG_HOME/llmtr/config.toml`) and edit what you need — every key is optional and falls
back to the default shown in the example. It covers the Ollama connection, the model used per
mode, the PL/EN language pair, the copy/paste keys (plus optional per-app overrides, which need
the "Window Calls" GNOME Shell extension), tone presets, and whether progress notifications are
shown.

State (the current tone preset) lives in `~/.local/state/llmtr/state.toml`; the last result is
cached in `~/.cache/llmtr/last.txt`. All of these respect the usual `XDG_*` environment variables.

## Tone presets

`[[tone.preset]]` entries add presets after the built-in `team` preset (a preset named `team`
replaces the built-in one in place):

```toml
[[tone.preset]]
name = "formal"
instruction = "Formal business email: polite, complete sentences, no slang."

[[tone.preset]]
name = "concise"
instruction = "As short as possible: cut every word that isn't needed."
```

- `llmtr tone` rewrites the selection in the current preset.
- `llmtr tone --next` cycles to the next preset (wrapping around) and shows its name — no text is
  processed.
- `llmtr tone --show` shows the current preset's name and instruction without changing it or
  touching any text — e.g. `Tone: formal (2/3)` with the instruction as the notification body.
  `llmtr tone --show --stdin` prints the same information (`formal (2/3): <instruction>`) to
  stdout instead. `--show` and `--next` can't be combined.

## Manual use: `--stdin`

Every mode accepts `--stdin`, which reads text from stdin and prints the result to stdout —
no clipboard, keystrokes, lock or notifications involved. Useful for checking a model or prompt
without touching the desktop:

```bash
echo "Dzień dobry, jak się masz?" | llmtr translate --stdin
echo "This have a typo in it." | llmtr fix --stdin
echo "hey can u send me the report" | llmtr tone --stdin
llmtr translate --quality --stdin < long_text.txt     # use translategemma:27b
llmtr translate --model translategemma:27b --stdin < long_text.txt
```

`llmtr tone --next --stdin` is a usage error (exit 2): switching presets doesn't process text.

## Troubleshooting

- **Where's the log?** Every run writes one line to `~/.local/state/llmtr/llmtr.log`
  (`$XDG_STATE_HOME/llmtr/llmtr.log`), rotated at 1 MB with one backup. `llmtr log` prints the
  path and the last 20 lines; `llmtr log --tail 50` prints more. Errors are logged with the full
  traceback and the hidden `detail` the notification doesn't show (e.g. which tool failed and
  why). The log never contains the selected text, the model's output, or clipboard contents —
  only their lengths. Disable it with `[log] enabled = false`, or raise/lower verbosity with
  `[log] level` (`"debug" | "info" | "error"`) or the `LLMTR_LOG_LEVEL` env var.
- **"Could not send keystrokes. Is ydotoold running?"** — `ydotool` is installed but the daemon
  isn't reachable. Check `systemctl --user status ydotoold.service` and that
  `$XDG_RUNTIME_DIR/.ydotool_socket` exists; re-run `./scripts/install-ydotool.sh` if needed.
- **Nothing happens, or the result stays on the clipboard with a "Press Ctrl+V" notification** —
  `ydotool` isn't installed or the socket isn't set up; this is the expected clipboard-only
  fallback, not an error. Paste manually, or install ydotool for the automatic flow.
- **"Can't reach Ollama at .../is it running?"** — start Ollama (`ollama serve`, or check your
  install's service) and confirm the URL in your config / `OLLAMA_HOST` matches where it's
  listening.
- **"Model X is not installed. Run: ollama pull X"** — pull the model it names, or point
  `[models]` in your config at one you already have.
- **Shortcuts don't fire** — open GNOME Settings → Keyboard → View and Customize Shortcuts →
  Custom Shortcuts and confirm the five `llmtr ...` entries are there with the expected bindings;
  re-run `./install.sh` to re-register them.
- **"Unexpected error — see ..."** — a bug, not one of the known failure modes above. Run
  `llmtr log` to see the traceback and open an issue with it.

## Uninstall

```bash
./install.sh --uninstall
```

Removes llmtr's five GNOME shortcuts and the `uv tool`-installed CLI. Your config, state and
cache files, and any ydotool installation, are left alone — remove
`~/.config/llmtr`/`~/.local/state/llmtr`/`~/.cache/llmtr` and run `./scripts/install-ydotool.sh`'s
undo steps manually if you want those gone too.
