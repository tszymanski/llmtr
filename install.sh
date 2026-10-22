#!/usr/bin/env bash
# Install (or uninstall) llmtr: the CLI via `uv tool install`, and five GNOME custom shortcuts.
#
# Run as your normal user (not root); this script never calls sudo itself. For ydotool (needed
# for the keystroke-based copy/paste flow; without it llmtr falls back to clipboard-only mode),
# either run scripts/install-ydotool.sh yourself first, or pass --with-ydotool to have this
# script run it for you (that script uses sudo internally). Safe to re-run: re-running updates
# llmtr's own shortcut entries in place instead of duplicating them.
#
# Usage:
#   ./install.sh                installs llmtr and registers the five shortcuts
#   ./install.sh --with-ydotool also runs scripts/install-ydotool.sh first if needed
#   ./install.sh --dry-run      print every command instead of running it
#   ./install.sh --uninstall    remove llmtr's shortcuts and the uv tool (keeps config, ydotool)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MEDIA_KEYS_SCHEMA="org.gnome.settings-daemon.plugins.media-keys"
BASE_PATH="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"

# Parallel arrays: one entry per shortcut.
SLOTS=(translate fix tone tone-next tone-show)
NAMES=("llmtr translate" "llmtr fix" "llmtr tone" "llmtr tone --next" "llmtr tone --show")
ARGS=("translate" "fix" "tone" "tone --next" "tone --show")
BINDINGS=(
    "<Super><Alt>t" "<Super><Alt>g" "<Super><Alt>r" "<Shift><Super><Alt>r" "<Shift><Super><Alt>t"
)

DRY_RUN=false
UNINSTALL=false
WITH_YDOTOOL=false

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        --uninstall) UNINSTALL=true ;;
        --with-ydotool) WITH_YDOTOOL=true ;;
        *)
            echo "install.sh: unknown option: $arg" >&2
            exit 2
            ;;
    esac
done

# Runs (or, in --dry-run, prints) a mutating command. Read-only lookups bypass this and always
# run for real, since they are needed to decide what to print.
run() {
    if "$DRY_RUN"; then
        printf '+'
        printf ' %q' "$@"
        printf '\n'
    else
        "$@"
    fi
}

llmtr_path_for_slot() {
    printf '%s/llmtr-%s/\n' "$BASE_PATH" "$1"
}

llmtr_paths() {
    for slot in "${SLOTS[@]}"; do
        llmtr_path_for_slot "$slot"
    done
}

current_keybinding_paths() {
    gsettings get "$MEDIA_KEYS_SCHEMA" custom-keybindings 2>/dev/null \
        | grep -o "'[^']*'" | tr -d "'" || true
}

# Existing custom-keybinding paths that are not one of llmtr's own five, i.e. other apps'
# shortcuts that must survive an install/uninstall untouched.
other_keybinding_paths() {
    local -a llmtr=()
    while IFS= read -r p; do llmtr+=("$p"); done < <(llmtr_paths)
    while IFS= read -r p; do
        [[ -z "$p" ]] && continue
        local skip=false
        for lp in "${llmtr[@]}"; do
            [[ "$p" == "$lp" ]] && skip=true && break
        done
        "$skip" || printf '%s\n' "$p"
    done < <(current_keybinding_paths)
}

array_literal() {
    if [[ $# -eq 0 ]]; then
        printf '[]'
        return
    fi
    local joined=""
    for p in "$@"; do
        [[ -n "$joined" ]] && joined+=","
        joined+="'$p'"
    done
    printf '[%s]' "$joined"
}

check_requirements() {
    command -v uv >/dev/null 2>&1 || {
        echo "install.sh: missing required tool: uv" >&2
        exit 1
    }
    command -v ollama >/dev/null 2>&1 \
        || echo "note: ollama not found on PATH (llmtr needs a running Ollama server)." >&2
    { command -v wl-copy >/dev/null 2>&1 && command -v wl-paste >/dev/null 2>&1; } \
        || command -v xclip >/dev/null 2>&1 \
        || echo "note: neither wl-clipboard nor xclip found on PATH (llmtr needs one)." >&2
    command -v notify-send >/dev/null 2>&1 \
        || echo "note: notify-send not found on PATH (llmtr's notifications will be silent)." >&2
}

ydotool_ready() {
    local version major
    # ydotool 1.0.4 has no --version/-V flag of its own; only the daemon reports a version
    # (`ydotoold -V` -> "v1.0.4-0-g57ba7d0"). Ubuntu's old 0.1.8 package ships no ydotoold at
    # all, so requiring ydotoold on PATH also rules that package out.
    command -v ydotoold >/dev/null 2>&1 || return 1
    version="$(ydotoold -V 2>&1 | grep -oE 'v[0-9]+' | head -n1 || true)"
    [[ -n "$version" ]] || return 1
    major="${version#v}"
    [[ "$major" -ge 1 ]] || return 1
    systemctl --user is-active ydotoold.service >/dev/null 2>&1 \
        || [[ -S "${XDG_RUNTIME_DIR:-}/.ydotool_socket" ]] || return 1
}

check_ydotool() {
    if command -v ydotool >/dev/null 2>&1 && ydotool_ready; then
        return
    fi
    if "$WITH_YDOTOOL"; then
        echo "==> ydotool >= 1.0 with the ydotoold user service not found; installing it"
        run bash "$SCRIPT_DIR/scripts/install-ydotool.sh"
    else
        echo "note: ydotool >= 1.0 with the ydotoold user service is not set up." >&2
        echo "      Run scripts/install-ydotool.sh (or re-run with --with-ydotool)." >&2
        echo "      Without it, llmtr falls back to clipboard-only mode." >&2
    fi
}

# The absolute path of the installed llmtr: GNOME custom keybindings run without the user's
# shell PATH, so ~/.local/bin (uv's default tool bin dir) may not be visible to them.
resolve_llmtr_bin() {
    local bin tool_bin_dir
    bin="$(command -v llmtr 2>/dev/null || true)"
    if [[ -z "$bin" ]]; then
        tool_bin_dir="$(uv tool dir --bin 2>/dev/null || true)"
        [[ -z "$tool_bin_dir" ]] && tool_bin_dir="$HOME/.local/bin"
        bin="$tool_bin_dir/llmtr"
    fi
    if ! "$DRY_RUN" && [[ ! -x "$bin" ]]; then
        echo "install.sh: could not find the installed llmtr binary (looked at $bin)" >&2
        exit 1
    fi
    printf '%s' "$bin"
}

install_cli() {
    echo "==> Installing llmtr with uv tool install"
    run uv tool install --force --reinstall "$SCRIPT_DIR"
}

uninstall_cli() {
    echo "==> Uninstalling the llmtr uv tool"
    run uv tool uninstall llmtr
}

register_shortcuts() {
    local llmtr_bin
    llmtr_bin="$(resolve_llmtr_bin)"
    echo "==> Registering GNOME shortcuts for $llmtr_bin"

    local -a others=() llmtr=()
    while IFS= read -r p; do [[ -n "$p" ]] && others+=("$p"); done < <(other_keybinding_paths)
    while IFS= read -r p; do llmtr+=("$p"); done < <(llmtr_paths)

    run gsettings set "$MEDIA_KEYS_SCHEMA" custom-keybindings \
        "$(array_literal "${others[@]}" "${llmtr[@]}")"

    for i in "${!SLOTS[@]}"; do
        local path="${llmtr[$i]}"
        local schema="${MEDIA_KEYS_SCHEMA}.custom-keybinding:${path}"
        run gsettings set "$schema" name "${NAMES[$i]}"
        run gsettings set "$schema" command "${llmtr_bin} ${ARGS[$i]}"
        run gsettings set "$schema" binding "${BINDINGS[$i]}"
    done
}

uninstall_shortcuts() {
    echo "==> Removing llmtr's GNOME shortcuts"
    local -a others=()
    while IFS= read -r p; do [[ -n "$p" ]] && others+=("$p"); done < <(other_keybinding_paths)
    run gsettings set "$MEDIA_KEYS_SCHEMA" custom-keybindings "$(array_literal "${others[@]}")"
    while IFS= read -r path; do
        run gsettings reset-recursively "${MEDIA_KEYS_SCHEMA}.custom-keybinding:${path}"
    done < <(llmtr_paths)
}

if "$UNINSTALL"; then
    uninstall_shortcuts
    uninstall_cli
    exit 0
fi

check_requirements
check_ydotool
install_cli
register_shortcuts
echo "OK: llmtr installed. Shortcuts: Super+Alt+T translate, Super+Alt+G fix, Super+Alt+R tone,"
echo "    Shift+Super+Alt+R next tone, Shift+Super+Alt+T show tone."
