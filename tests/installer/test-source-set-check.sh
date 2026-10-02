#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$here/source-set-check.sh"
work=$(mktemp -d /tmp/openwifi-source-set-test.XXXXXX)
trap 'rm -rf "$work"' EXIT HUP INT TERM
mkdir -p "$work/root/lib/functions" "$work/root/lib/upgrade"
printf 'reviewed core\n' > "$work/root/lib/functions/cambium-ab.sh"
printf '%s\n' /lib/functions/cambium-ab.sh /lib/upgrade/cambium-ab-certificates.sh > "$work/paths"
digest=$(sha256sum < "$work/root/lib/functions/cambium-ab.sh"); digest=${digest%% *}
printf '%s %s\n- %s\n' "$digest" /lib/functions/cambium-ab.sh /lib/upgrade/cambium-ab-certificates.sh > "$work/set"
ow_source_set_matches "$work/set" "$work/paths" "$work/root"
reject() { if ow_source_set_matches "$work/set" "$work/paths" "$work/root"; then echo "FAIL: $1" >&2; exit 1; fi; }
cp "$work/set" "$work/good"
printf 'changed\n' >> "$work/root/lib/functions/cambium-ab.sh"
reject modified
printf 'reviewed core\n' > "$work/root/lib/functions/cambium-ab.sh"
printf 'unexpected\n' > "$work/root/lib/upgrade/cambium-ab-certificates.sh"
reject expected-absence
rm "$work/root/lib/upgrade/cambium-ab-certificates.sh"
head -n 1 "$work/good" > "$work/set"
reject missing-record
cp "$work/good" "$work/set"
head -n 1 "$work/good" >> "$work/set"
reject duplicate
printf '%s /lib/../secret\n- /lib/upgrade/cambium-ab-certificates.sh\n' "$digest" > "$work/set"
reject traversal
cp "$work/good" "$work/set"
mv "$work/root/lib/functions/cambium-ab.sh" "$work/core"
ln -s "$work/core" "$work/root/lib/functions/cambium-ab.sh"
reject symlink
: > "$work/set"
reject empty
echo 'PASS: reviewed tuple accepted; modified/absent/missing/duplicate/traversal/symlink/empty refused'
