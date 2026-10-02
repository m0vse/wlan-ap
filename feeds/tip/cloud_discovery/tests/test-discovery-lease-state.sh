#!/bin/sh
# Execute actual state-transition and lease notification methods without daemon
# startup, real ubus, credentials, networking or filesystem mutations.
set -eu
ucode=${1:?native ucode binary}
daemon=${2:?shipped discovery daemon}
work=$(mktemp -d /tmp/openwifi-discovery-state.XXXXXX)
trap 'rm -rf "$work"' EXIT HUP INT TERM
cat > "$work/test.uc" <<'UCODE'
const DISCOVER=0, VALIDATING=1, ONLINE=2, OFFLINE=3, ORPHAN=4;
const LOG_INFO=0;
let state, offline_time, orphan_time, validate_time;
let discovery_block_list=[], discovery_method=0;
let fs={unlink: function() { die('persistent/transient state deleted on lease loss'); }};
function ulog() {};
function gateway_write() { die('gateway changed on lease loss'); };
function gateway_load() { die('gateway consulted before handling lease loss'); };
function dhcp_restart() { die('DHCP restarted on lease loss'); };
function discovery_state_write() { die('discovery state persisted on lease loss'); };
function readjsonfile() { return {lease:false}; };
UCODE
sed -n '/^function set_state(set) {/,/^function discover_dhcp()/p' "$daemon" | sed '$d' >> "$work/test.uc"
printf 'let methods = {\n' >> "$work/test.uc"
sed -n '/^\trenew: {/,/^\tonline: {/p' "$daemon" | sed '$d' >> "$work/test.uc"
printf '};\n' >> "$work/test.uc"
cat >> "$work/test.uc" <<'UCODE'
for (let previous in [ONLINE, VALIDATING, OFFLINE, DISCOVER]) {
    state=previous;
    methods.renew.call({});
    let expected=(previous==ONLINE || previous==VALIDATING) ? OFFLINE : previous;
    if (state!=expected)
        die('incorrect lease-loss transition');
}
print('PASS: four actual lease-loss state transitions preserve gateway/credentials and do not restart DHCP\n');
UCODE
"$ucode" "$work/test.uc"
