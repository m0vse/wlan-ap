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
export PATH=$work/bin:$PATH TEST_CALLS=$work/calls TEST_LABEL=AA:BB:CC:DD:EE:FF
sh "$work/identity.sh"
grep -Fxq 'set system.@system[-1].mac=AA:BB:CC:DD:EE:FF' "$work/calls"
grep -Fxq 'set system.@system[-1].hostname=aabbccddeeff' "$work/calls"
grep -Fxq 'set ucentral.config.serial=aabbccddeeff' "$work/calls"
for TEST_LABEL in '' 'AA:BB:CC:DD:EE' 'invalid-label'; do
 export TEST_LABEL
 : > "$work/calls"
 if sh "$work/identity.sh"; then exit 1; fi
 test ! -s "$work/calls"
done
echo 'PASS: factory-label identity produces MAC/hostname/serial; absent or invalid labels fail before UCI changes'
