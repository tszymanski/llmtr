#!/bin/bash
# M8-spike S4: started by a Hammerspoon hotkey; logs which combo fired and the start latency.
# Usage: s4_hotkey.sh <combo> <hotkey-epoch-seconds> <press|release>
source "$(dirname "$0")/common.sh"
t_start=$(now)
log "combo=$1 mode=$3 latency=$(elapsed "$2" "$t_start")s"
