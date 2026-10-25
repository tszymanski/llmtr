# llmtr

A small command-line tool for GNOME on Wayland and macOS: select some text anywhere, press a shortcut, and
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

On macOS the shortcuts are `Ctrl+Opt+T/G/R` (and `Shift+Ctrl+Opt+R/T`) instead of the `Super+Alt`
ones, run through Hammerspoon; see [macOS](#macos).

## Requirements

(Linux; for macOS see [macOS](#macos).)

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

## macOS

Same commands and flow as on Linux, on Apple silicon Macs (tested on macOS 27 with an M1, 16 GB).
Global shortcuts come from [Hammerspoon](https://www.hammerspoon.org); `llmtr` copies and pastes
with `osascript` (System Events), `pbcopy` and `pbpaste`.

| Shortcut | Command |
| --- | --- |
| `Ctrl+Opt+T` | `llmtr translate` |
| `Ctrl+Opt+G` | `llmtr fix` |
| `Ctrl+Opt+R` | `llmtr tone` |
| `Shift+Ctrl+Opt+R` | `llmtr tone --next` |
| `Shift+Ctrl+Opt+T` | `llmtr tone --show` |

The shortcuts fire when you **release** the letter key. A second press while a job runs cancels it.
Copy and paste use `⌘C`/`⌘V` (also in Terminal and iTerm).

### macOS requirements

- [uv](https://docs.astral.sh/uv/): `brew install uv`.
- Hammerspoon: `brew install --cask hammerspoon`, in `/Applications` or `~/Applications`.
- A running Ollama server with your models, as above. With 16 GB only one 12b model stays loaded:
  every switch between translate and tone/fix reloads the model (+6–9 s), and a translated
  paragraph takes 12–21 s. `translategemma:27b` (`--quality`) does not fit.

### macOS install

```bash
./install.sh                # same entry point; on macOS it runs scripts/install-macos.sh
./install.sh --dry-run      # print every command instead of running it
./install.sh --uninstall    # remove llmtr's Hammerspoon file and line and the uv tool
```

The installer is user-level (no `sudo`) and safe to re-run. It installs the CLI with
`uv tool install`, writes `~/.hammerspoon/llmtr.lua` (with the absolute path of `llmtr`), adds one
`require("llmtr")` line to `~/.hammerspoon/init.lua` (created if missing; the rest of your
Hammerspoon config is never touched), starts Hammerspoon and opens the System Settings panes you
need. If Hammerspoon was already running, choose *Reload Config* in its menu bar menu. `--uninstall`
keeps your llmtr config and state and Hammerspoon itself.

### macOS permissions

macOS lets nobody grant these by script, so you do it once. All three are for **Hammerspoon**:

1. **Privacy & Security → Accessibility** (titled **Device Control and Data Access** on macOS 27):
   turn Hammerspoon on. Without it `osascript` fails with "osascript is not allowed to send
   keystrokes (1002)" and `llmtr` tells you to turn Hammerspoon on here. No `osascript` entry is
   needed.
2. **Privacy & Security → Automation → Hammerspoon → System Events**: on. At the first copy macOS
   asks *"“Hammerspoon” wants access to control “System Events”. Allowing control will provide access
   to documents and data in “System Events”, and to perform actions within that app."* — click
   **Allow**. The first press waits while the dialog is open.
3. **Notifications → Hammerspoon**: *Allow notifications*, then **restart Hammerspoon** (no prompt is
   shown; only needed for the notification bubbles).

The shortcuts themselves need no permission. A missing Accessibility or Automation grant is reported
on the first press with a notification naming the setting; llmtr does not fall back to the
clipboard there, because it would process stale clipboard text.

### macOS notifications

By default `llmtr` shows its messages through Hammerspoon, as one bubble per run: "Translating…" is
replaced by the result or the error and disappears a few seconds after the run. If no Hammerspoon
bubbles appear (Notifications not allowed, or you prefer not to), set in
`~/.config/llmtr/config.toml`:

```toml
[notify]
backend = "osascript"   # "auto" (default, = hammerspoon on macOS) | "hammerspoon" | "osascript"
```

`osascript` bubbles show as "Script Editor" and cannot be replaced. The key is ignored on Linux.

### Caps Lock as Ctrl+Opt (optional, Karabiner-Elements)

Not part of the installer. With [Karabiner-Elements](https://karabiner-elements.pqrs.org) you can
hold Caps Lock instead of `Ctrl+Opt` (a tap alone is still Caps Lock). Add this under
*Complex Modifications → Add your own rule*:

```json
{
  "description": "Caps Lock held → Ctrl+Option (tap = Caps Lock)",
  "manipulators": [
    {
      "from": { "key_code": "caps_lock", "modifiers": { "optional": ["any"] } },
      "to": [{ "key_code": "left_control", "modifiers": ["left_option"] }],
      "to_if_alone": [{ "key_code": "caps_lock" }],
      "type": "basic"
    }
  ]
}
```

If the rule is enabled but Caps Lock keeps toggling (Karabiner gives no warning):

1. Allow the driver extension (System Settings → General → Login Items & Extensions → Driver
   Extensions).
2. Privacy & Security → Input Monitoring: add **`Karabiner-Core-Service`** by hand (**+** → `⌘⇧G` →
   `/Library/Application Support/org.pqrs/Karabiner-Elements/Karabiner-Core-Service.app`), switch it
   on, then restart Karabiner-Elements. (Karabiner 16; older versions used `karabiner_grabber` and
   `karabiner_observer`.)
3. Karabiner Settings → Devices → your keyboard (e.g. Apple Internal Keyboard): *Modify events* on.
4. ISO keyboards: Devices → *Swap ISO layout-specific keys* on, or `` ` ``/`~` produce `§`.
5. Check in Karabiner-EventViewer: Caps held + `T` must show `left_control` and `left_option`, then `t`.

### macOS troubleshooting

- **Start with `llmtr log`.** The log at `~/.local/state/llmtr/llmtr.log` is the diagnosis path:
  Hammerspoon does not show `llmtr`'s output.
- **"Nothing copied: secure input is active in …"** — the app (often a browser with a focused
  password field, or a password manager) turned on Secure Input, which blocks the copy keystroke.
  Leave the field or close the app that holds it.
- **"No text selected"** — nothing was selected, or the app ignored `⌘C`.
- **Polish letters come out garbled** — report it with `llmtr log`; `llmtr` runs `pbcopy` and
  `pbpaste` with `LC_CTYPE=UTF-8` because Hammerspoon's children have no locale.
- **Shortcut does nothing** — check that Hammerspoon is running and reload its config; open
  *Console* in its menu and look for errors from `llmtr.lua`. Another app may own the same shortcut.
- **No bubbles** — see macOS notifications above (Allow notifications, restart Hammerspoon, or use
  `backend = "osascript"`).
- **Removing everything** — `./install.sh --uninstall`; then delete `~/.config/llmtr`,
  `~/.local/state/llmtr`, `~/.cache/llmtr` if you want those gone too.

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
