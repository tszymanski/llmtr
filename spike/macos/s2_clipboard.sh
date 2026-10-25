#!/bin/bash
# M8-spike S2: pbcopy/pbpaste round trips with timings (seconds, two decimals).
set -u

now() { perl -MTime::HiRes=time -e 'printf "%.6f\n", time'; }
elapsed() { perl -e "printf '%.2f', $2 - $1"; }

roundtrip() {
	local name=$1 text=$2 t0 t1 t2 got
	t0=$(now)
	printf '%s' "$text" | pbcopy
	t1=$(now)
	got=$(pbpaste; printf x)
	got=${got%x}
	t2=$(now)
	if [[ "$got" == "$text" ]]; then res=OK; else res=MISMATCH; fi
	printf '%-12s %-8s chars=%-5s pbcopy=%ss pbpaste=%ss\n' \
		"$name" "$res" "${#text}" "$(elapsed "$t0" "$t1")" "$(elapsed "$t1" "$t2")"
}

roundtrip diacritics 'zażółć gęślą jaźń ZAŻÓŁĆ GĘŚLĄ JAŹŃ'
roundtrip multiline $'line one\nline two\n\n\tindented line\nlast'
roundtrip emoji '👍 🇵🇱 👨‍👩‍👧 ✅ done'
roundtrip 8000chars "$(perl -e 'print "abcdefghij" x 800')"

# Empty clipboard.
pbcopy </dev/null
out=$(pbpaste)
echo "empty: exit=$? bytes=${#out}"

# Does pbcopy return at once and leave no process holding the pipe?
t0=$(now)
printf 'x' | pbcopy &
pid=$!
wait "$pid"
t1=$(now)
echo "pbcopy background wait=$(elapsed "$t0" "$t1")s leftover=$(pgrep -x pbcopy || echo none)"
# A captured-stdout call must not hang (wl-copy would).
t0=$(now)
captured=$(printf 'y' | pbcopy 2>&1)
t1=$(now)
echo "pbcopy via \$(...) returned in $(elapsed "$t0" "$t1")s output='${captured}'"
