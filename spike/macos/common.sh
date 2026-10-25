#!/bin/bash
# M8-spike shared helpers, sourced by the other spike scripts.

# Hammerspoon children get no LANG; without a UTF-8 locale pbcopy/pbpaste garble Polish (S4).
export LC_CTYPE=UTF-8

SPIKE_LOG=${SPIKE_LOG:-${XDG_STATE_HOME:-$HOME/.local/state}/llmtr-spike/spike.log}
mkdir -p "${SPIKE_LOG%/*}"

now() { /usr/bin/perl -MTime::HiRes=time -e 'printf "%.6f\n", time'; }
elapsed() { /usr/bin/perl -e "printf '%.2f', $2 - $1"; }
log() { printf '%s [%s] %s\n' "$(date '+%H:%M:%S')" "${0##*/}" "$*" >>"$SPIKE_LOG"; }

# Prints the clipboard exactly (keeps trailing newlines).
clip_get() {
	local s
	s=$(/usr/bin/pbpaste; printf x)
	printf '%s' "${s%x}"
}
clip_set() { printf '%s' "$1" | /usr/bin/pbcopy; }
clip_clear() { /usr/bin/pbcopy </dev/null; }

upper() { /usr/bin/perl -CSD -pe '$_ = uc'; }

frontmost() {
	/usr/bin/osascript -e 'tell application "System Events" to get bundle identifier of first application process whose frontmost is true' 2>&1
}
