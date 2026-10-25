#!/bin/bash
# M8-spike S5: llmtr-like flow without a model; keystrokes via osascript/System Events.
# save clipboard -> clear -> [delay] -> Cmd+C -> poll (max 1 s) -> upper-case -> pbcopy -> Cmd+V
# -> 0.3 s -> restore. Also S8: bundle id of the frontmost app and how long the query takes.
# Usage: s5_flow.sh <combo> <hotkey-epoch-seconds> <press|release> [start_delay_s]
source "$(dirname "$0")/common.sh"
combo=$1 t_key=$2 mode=$3 delay=${4:-0}
t0=$(now)
old=$(clip_get)
clip_clear
[[ "$delay" != 0 ]] && sleep "$delay"

keystroke() {
	/usr/bin/osascript -e "tell application \"System Events\" to keystroke \"$1\" using command down" 2>&1
}

err=$(keystroke c) || log "cmd+c osascript error: $err"
t_copy=$(now)
text=
for _ in $(seq 50); do
	text=$(clip_get)
	[[ -n "$text" ]] && break
	sleep 0.02
done
t_got=$(now)
if [[ -z "$text" ]]; then
	clip_set "$old"
	/usr/bin/osascript -e 'display notification "Nothing copied (S5)" with title "llmtr spike"'
	log "FAIL combo=$combo mode=$mode delay=$delay nothing copied after $(elapsed "$t_copy" "$t_got")s; front=$(frontmost)"
	exit 2
fi
result=$(printf '%s' "$text" | upper)
clip_set "$result"
err=$(keystroke v) || log "cmd+v osascript error: $err"
t_paste=$(now)
sleep 0.3
clip_set "$old"
restored=$([[ "$(clip_get)" == "$old" ]] && echo yes || echo NO)
t_f0=$(now)
front=$(frontmost)
t_f1=$(now)
log "OK combo=$combo mode=$mode delay=$delay copied=${#text}ch" \
	"start=$(elapsed "$t_key" "$t0")s copy_wait=$(elapsed "$t_copy" "$t_got")s" \
	"hotkey_to_paste=$(elapsed "$t_key" "$t_paste")s restored=$restored" \
	"front=$front front_query=$(elapsed "$t_f0" "$t_f1")s"
