#!/bin/sh
set -eu
script=${1:?factory identity script}
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT HUP INT TERM
mkdir "$work/bin"
printf 'get_mac_label() { printf "%%s" "$TEST_LABEL"; }\n' > "$work/system.sh"
sed "s|/lib/functions/system.sh|$work/system.sh|" "$script" > "$work/identity.sh"
printf '#!/bin/sh\nprintf "%%s\\n" "$*" >> "$TEST_CALLS"\n' > "$work/bin/uci"
printf '#!/bin/sh\nexit 0\n' > "$work/bin/logger"
chmod +x "$work/bin/uci" "$work/bin/logger"
export PATH=$work/bin:$PATH TEST_CALLS=$work/calls
# The initializer is shared: every family's supplied factory label must remain
# the MAC source for both lowercase hostname and serial. These are synthetic
# labels; this verifies normalization, not physical label discovery.
for family in sage jaguar cheetah thor gambit; do
 case "$family" in
 sage) TEST_LABEL=02:10:AA:BB:CC:01 ;;
 jaguar) TEST_LABEL=02:20:aa:bb:cc:02 ;;
 cheetah) TEST_LABEL=02:30:Aa:bB:Cc:03 ;;
 thor) TEST_LABEL=02:40:AA:bb:CC:04 ;;
 gambit) TEST_LABEL=02:50:aa:BB:cc:05 ;;
 esac
 export TEST_LABEL
 : > "$work/calls"
 sh "$work/identity.sh"
 expected=$(printf '%s' "$TEST_LABEL" | tr -d : | tr '[:upper:]' '[:lower:]')
 grep -Fxq "set system.@system[-1].mac=$TEST_LABEL" "$work/calls"
 grep -Fxq "set system.@system[-1].hostname=$expected" "$work/calls"
 grep -Fxq "set ucentral.config.serial=$expected" "$work/calls"
 [ "$(wc -l < "$work/calls" | tr -d ' ')" = 3 ]
done
for TEST_LABEL in '' 'AA:BB:CC:DD:EE' 'invalid-label'; do
 export TEST_LABEL
 : > "$work/calls"
 if sh "$work/identity.sh"; then exit 1; fi
 test ! -s "$work/calls"
done
echo 'PASS: five family label-normalization cases preserve MAC/hostname/serial identity; three invalid labels fail before UCI changes'
