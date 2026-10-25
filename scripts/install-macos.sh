#!/usr/bin/env bash
# Install (or uninstall) llmtr on macOS: the CLI via `uv tool install`, and five global shortcuts
# through Hammerspoon (~/.hammerspoon/llmtr.lua plus one `require("llmtr")` line in init.lua).
#
# Normally started by ./install.sh, which hands over here on macOS. User-level: never calls sudo.
# Safe to re-run. It cannot grant the macOS permissions; it opens the Settings panes and prints
# the steps. Needs `uv` (brew install uv) and Hammerspoon (brew install --cask hammerspoon).
# Written for macOS's bash 3.2: no mapfile, no associative arrays.
#
# Usage:
#   ./install.sh                installs llmtr and the Hammerspoon shortcuts
#   ./install.sh --dry-run      print every command instead of running it
#   ./install.sh --uninstall    remove llmtr's Hammerspoon file and line and the uv tool
#                               (keeps config, state and Hammerspoon itself)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
TEMPLATE="$REPO_DIR/macos/llmtr.lua.in"
HS_DIR="$HOME/.hammerspoon"
HS_MODULE="$HS_DIR/llmtr.lua"
HS_INIT="$HS_DIR/init.lua"
REQUIRE_LINE='require("llmtr")'

DRY_RUN=false
UNINSTALL=false

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        --uninstall) UNINSTALL=true ;;
        *)
            echo "install-macos.sh: unknown option: $arg" >&2
            exit 2
            ;;
    esac
done

# Runs (or, in --dry-run, prints) a mutating command.
run() {
    if "$DRY_RUN"; then
        printf '+'
        printf ' %q' "$@"
        printf '\n'
    else
        "$@"
    fi
}

hammerspoon_app() {
    local dir
    for dir in /Applications "$HOME/Applications"; do
        if [[ -d "$dir/Hammerspoon.app" ]]; then
            printf '%s' "$dir/Hammerspoon.app"
            return 0
        fi
    done
    return 1
}

hammerspoon_running() {
    command -v pgrep >/dev/null 2>&1 && pgrep -x Hammerspoon >/dev/null 2>&1
}

check_requirements() {
    if ! command -v uv >/dev/null 2>&1; then
        echo "install-macos.sh: uv is required but not found. Install it with: brew install uv" >&2
        exit 1
    fi
    if ! hammerspoon_app >/dev/null; then
        echo "install-macos.sh: Hammerspoon.app not found in /Applications or ~/Applications." >&2
        echo "Install it with: brew install --cask hammerspoon" >&2
        exit 1
    fi
    command -v ollama >/dev/null 2>&1 \
        || echo "note: ollama not found on PATH (llmtr needs a running Ollama server)." >&2
}

install_cli() {
    echo "==> Installing llmtr with uv tool install"
    run uv tool install --force --reinstall "$REPO_DIR"
}

# The absolute path of the installed llmtr: Hammerspoon's tasks run with a minimal PATH.
resolve_llmtr_bin() {
    local bin_dir bin
    bin_dir="$(uv tool dir --bin 2>/dev/null || true)"
    [[ -n "$bin_dir" ]] || bin_dir="$HOME/.local/bin"
    bin="$bin_dir/llmtr"
    if ! "$DRY_RUN" && [[ ! -x "$bin" ]]; then
        echo "install-macos.sh: could not find the installed llmtr binary (looked at $bin)" >&2
        exit 1
    fi
    printf '%s' "$bin"
}

write_module() {
    local bin content
    bin="$(resolve_llmtr_bin)"
    case "$bin" in
        *'"'* | *'\'*)
            echo "install-macos.sh: unsupported characters in path: $bin" >&2
            exit 1
            ;;
    esac
    echo "==> Writing $HS_MODULE (llmtr at $bin)"
    if "$DRY_RUN"; then
        echo "+ write $HS_MODULE from $TEMPLATE"
        return
    fi
    content="$(cat "$TEMPLATE")"
    mkdir -p "$HS_DIR"
    # Not ${content//@LLMTR_BIN@/"$bin"}: bash <= 4.2 keeps the quotes in the replacement and
    # bash >= 5.2 turns an `&` in it into the match. The placeholder occurs exactly once.
    printf '%s%s%s\n' "${content%%@LLMTR_BIN@*}" "$bin" "${content#*@LLMTR_BIN@}" >"$HS_MODULE"
}

ensure_require() {
    echo "==> Ensuring $REQUIRE_LINE in $HS_INIT"
    if [[ -f "$HS_INIT" ]] && grep -qxF "$REQUIRE_LINE" "$HS_INIT"; then
        echo "    already there"
        return
    fi
    if "$DRY_RUN"; then
        echo "+ append $REQUIRE_LINE to $HS_INIT"
        return
    fi
    mkdir -p "$HS_DIR"
    # Keep the user's content; make sure our line starts on its own line.
    if [[ -s "$HS_INIT" && -n "$(tail -c1 "$HS_INIT")" ]]; then
        printf '\n' >>"$HS_INIT"
    fi
    printf '%s\n' "$REQUIRE_LINE" >>"$HS_INIT"
}

start_hammerspoon() {
    if hammerspoon_running; then
        echo "==> Hammerspoon is already running: choose 'Reload Config' in its menu bar menu."
    else
        echo "==> Starting Hammerspoon"
        run open -a Hammerspoon
    fi
}

open_settings() {
    echo "==> Opening the System Settings panes you need"
    run open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
    run open "x-apple.systempreferences:com.apple.preference.security?Privacy_Automation"
    run open "x-apple.systempreferences:com.apple.Notifications-Settings.extension"
    cat <<'TEXT'

Permissions (llmtr cannot grant them; all are for Hammerspoon):
  1. Privacy & Security > Accessibility (called "Device Control and Data Access" on macOS 27):
     turn Hammerspoon on.
  2. Privacy & Security > Automation > Hammerspoon: turn System Events on. A dialog
     ("Hammerspoon" wants access to control "System Events") appears at the first copy; Allow.
  3. Notifications > Hammerspoon: Allow notifications, then restart Hammerspoon.

Shortcuts: Ctrl+Opt+T translate, Ctrl+Opt+G fix, Ctrl+Opt+R tone,
           Shift+Ctrl+Opt+R next tone, Shift+Ctrl+Opt+T show tone.
TEXT
}

remove_require() {
    [[ -f "$HS_INIT" ]] || return 0
    grep -qxF "$REQUIRE_LINE" "$HS_INIT" || return 0
    echo "==> Removing $REQUIRE_LINE from $HS_INIT"
    if "$DRY_RUN"; then
        echo "+ remove $REQUIRE_LINE from $HS_INIT"
        return
    fi
    # Through a temp file, not $(...): that would drop the user's trailing blank lines. Copied
    # back with cat so the file itself (maybe a symlink) is rewritten in place and an init.lua
    # holding only our line stays (empty).
    grep -vxF "$REQUIRE_LINE" "$HS_INIT" >"$HS_INIT.tmp" || true
    cat "$HS_INIT.tmp" >"$HS_INIT"
    rm -f "$HS_INIT.tmp"
}

uninstall() {
    echo "==> Removing llmtr's Hammerspoon file and line"
    remove_require
    run rm -f "$HS_MODULE"
    if command -v uv >/dev/null 2>&1; then
        echo "==> Uninstalling the llmtr uv tool"
        run uv tool uninstall llmtr
    else
        echo "note: uv not found; the llmtr uv tool was not uninstalled." >&2
    fi
    echo "OK: removed. Choose 'Reload Config' in Hammerspoon. Config, state and Hammerspoon are kept."
}

if "$UNINSTALL"; then
    uninstall
    exit 0
fi

check_requirements
install_cli
write_module
ensure_require
start_hammerspoon
open_settings
echo "OK: llmtr installed."
