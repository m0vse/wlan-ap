#!/bin/sh
# Execute the actual naming function and consume its output with real libuci.
# No host network/service/device changes occur.
set -eu
schema=${1:?prepared schema source}
ucode=${2:?native ucode binary}
uci=${3:?native uci binary}
work=$(mktemp -d /tmp/openwifi-udevstats-sections.XXXXXX)
trap 'rm -rf "$work"' EXIT HUP INT TERM
mkdir "$work/config" "$work/state"
: > "$work/config/udevstats"
sed -n '/function normalize_section_name(port) {/,/^\t}/p' \
    "$schema/renderer/templates/interface/bridge-vlan.uc" > "$work/names.uc"
grep -q 'function normalize_section_name' "$work/names.uc"
cat >> "$work/names.uc" <<'UCODE'
let seen = {};
for (let port in ['lan-multigig', 'lan.1', 'lan_1', 'lan-1', 'lan1', 'eth0', 'dev_65746830']) {
    let section = normalize_section_name(port);
    if (!match(section, /^[A-Za-z0-9_]+$/) || seen[section])
        die('invalid or colliding section ID');
    seen[section] = true;
    print(`set udevstats.${section}=device\n`);
    print(`set udevstats.${section}.name='${port}'\n`);
    print(`add_list udevstats.${section}.vlan='0'\n`);
}
UCODE
"$ucode" "$work/names.uc" > "$work/batch"
"$uci" -c "$work/config" -t "$work/state" batch < "$work/batch" 2> "$work/errors"
test ! -s "$work/errors"
for port in lan-multigig lan.1 lan_1 lan-1 lan1 eth0 dev_65746830; do
    section=$("$ucode" -e 'print("dev_", hexenc(ARGV[0]));' "$port")
    test "$("$uci" -c "$work/config" -t "$work/state" get "udevstats.$section.name")" = "$port"
    test "$("$uci" -c "$work/config" -t "$work/state" get "udevstats.$section.vlan")" = 0
done
echo 'PASS: seven distinct UCI section IDs accepted; exact device names and VLAN list preserved'
