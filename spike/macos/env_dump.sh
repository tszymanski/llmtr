#!/bin/bash
# M8-spike S4: dump the environment Hammerspoon's hs.task gives a child, and test whether
# pbcopy/pbpaste keep Polish diacritics with that environment and with LANG set.
source "$(dirname "$0")/common.sh"
out=${SPIKE_LOG%/*}/hs_env.txt
{
	echo "== env =="
	env | sort
	echo "== which =="
	for c in uv llmtr ollama brew pbcopy osascript; do
		printf '%s: %s\n' "$c" "$(command -v "$c" || echo MISSING)"
	done
	text='zażółć gęślą jaźń'
	echo "== diacritics, inherited env (LANG=${LANG:-unset}) =="
	clip_set "$text"
	got=$(clip_get)
	[[ "$got" == "$text" ]] && echo OK || echo "MISMATCH: $got"
	echo "== diacritics, LANG=en_US.UTF-8 =="
	printf '%s' "$text" | LANG=en_US.UTF-8 /usr/bin/pbcopy
	got=$(LANG=en_US.UTF-8 /usr/bin/pbpaste)
	[[ "$got" == "$text" ]] && echo OK || echo "MISMATCH: $got"
} >"$out" 2>&1
log "env dumped to $out"
# Leave the text copied with the inherited (no-LANG) environment, for a cross-process check.
clip_set 'zażółć gęślą jaźń'
