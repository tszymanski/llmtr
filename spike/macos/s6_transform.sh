#!/bin/bash
# M8-spike S6: transform step only. Hammerspoon has cleared the clipboard and sent Cmd+C;
# this waits for the copied text (max 1 s), upper-cases it into the clipboard and exits 0.
# Exit 2 = nothing copied. Hammerspoon sends Cmd+V and restores the clipboard.
source "$(dirname "$0")/common.sh"
text=
for _ in $(seq 50); do
	text=$(clip_get)
	[[ -n "$text" ]] && break
	sleep 0.02
done
[[ -z "$text" ]] && exit 2
clip_set "$(printf '%s' "$text" | upper)"
