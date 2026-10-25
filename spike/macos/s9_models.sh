#!/bin/bash
# M8-spike S9: model latency on the Mac through the CLI's engine-only mode (--stdin).
# Prints one line per call: case, mode, model, seconds, output words; plus `ollama ps` snapshots.
# Usage: s9_models.sh [latency|tone|switch|all]   (run from the repo root)
set -u
source "$(dirname "$0")/common.sh"
T="$(dirname "$0")/texts"
TRANSLATE=translategemma:12b

stop_all() {
	ollama ps | awk 'NR > 1 { print $1 }' | while read -r m; do ollama stop "$m"; done
	sleep 1
}
ps_line() { ollama ps | awk 'NR > 1 { printf "%s %s %s %s %s | ", $1, $3, $4, $5, $6 }'; echo; }

call() { # case mode model file
	local case=$1 mode=$2 model=$3 file=$4 t0 t1 out
	t0=$(now)
	out=$(uv run llmtr "$mode" --stdin --model "$model" <"$file")
	t1=$(now)
	printf '%-28s %-9s %-20s %6ss  out=%sw\n' "$case" "$mode" "$model" "$(elapsed "$t0" "$t1")" \
		"$(printf '%s' "$out" | wc -w | tr -d ' ')"
	printf '%s\n' "$out" >>"${SPIKE_LOG%/*}/s9_outputs.txt"
}

tokens_per_s() { # model file: one direct /api/generate call, prints output tokens/s
	/usr/bin/perl -MJSON::PP -e '
		local $/; open my $f, "<", $ARGV[1] or die; my $t = <$f>;
		print encode_json({model => $ARGV[0], prompt => $t, stream => JSON::PP::false,
			options => {temperature => 0}});' "$1" "$2" |
		curl -s http://localhost:11434/api/generate -d @- |
		/usr/bin/perl -MJSON::PP -e 'local $/; my $r = decode_json(<STDIN>);
			printf "%s eval_count=%d tokens/s=%.1f load=%.2fs\n", $r->{model}, $r->{eval_count},
			$r->{eval_count} / ($r->{eval_duration} / 1e9), $r->{load_duration} / 1e9;'
}

latency() {
	echo "== uv run overhead =="
	t0=$(now); uv run llmtr --help >/dev/null; t1=$(now); echo "uv run llmtr --help: $(elapsed "$t0" "$t1")s"
	echo "== translate, $TRANSLATE =="
	stop_all
	call "PL->EN sentence cold" translate $TRANSLATE "$T/pl_sentence.txt"
	ps_line
	for i in 1 2 3; do call "PL->EN sentence loaded #$i" translate $TRANSLATE "$T/pl_sentence.txt"; done
	for i in 1 2; do call "PL->EN paragraph 56w #$i" translate $TRANSLATE "$T/pl_paragraph.txt"; done
	for i in 1 2; do call "EN->PL paragraph 71w #$i" translate $TRANSLATE "$T/en_paragraph.txt"; done
	for i in 1 2; do call "EN->PL long 221w #$i" translate $TRANSLATE "$T/en_long.txt"; done
	tokens_per_s $TRANSLATE "$T/en_long.txt"
	ps_line
}

tone() {
	for m in gemma3:12b gemma3; do
		echo "== tone/fix, $m =="
		stop_all
		call "tone EN paragraph cold" tone "$m" "$T/en_paragraph.txt"
		ps_line
		for i in 1 2; do call "tone EN paragraph loaded #$i" tone "$m" "$T/en_paragraph.txt"; done
		call "tone PL paragraph loaded" tone "$m" "$T/pl_paragraph.txt"
		call "fix PL paragraph loaded" fix "$m" "$T/pl_paragraph.txt"
		tokens_per_s "$m" "$T/en_paragraph.txt"
	done
}

switch() {
	for m in gemma3:12b gemma3; do
		echo "== switch cost: translate -> tone($m) -> translate -> tone($m) =="
		stop_all
		call "translate (cold)" translate $TRANSLATE "$T/pl_paragraph.txt"; ps_line
		call "tone" tone "$m" "$T/en_paragraph.txt"; ps_line
		call "translate again" translate $TRANSLATE "$T/pl_paragraph.txt"; ps_line
		call "tone again" tone "$m" "$T/en_paragraph.txt"; ps_line
	done
}

what=${1:-all}
case $what in
latency) latency ;;
tone) tone ;;
switch) switch ;;
all) latency; tone; switch ;;
*) echo "usage: $0 [latency|tone|switch|all]" >&2; exit 2 ;;
esac
