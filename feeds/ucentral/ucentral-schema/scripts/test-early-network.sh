#!/bin/sh
# Component tests execute the actual patched schema code with side effects
# mocked. Network namespace tests below exercise Linux, not AP hardware.
set -eu
source_dir=${1:?patched schema source}
ucode_bin=${2:?host ucode}
test_dir=$(mktemp -d)
trap 'rm -rf "$test_dir"' EXIT

{
    printf '%s\n' 'for (let c in [[true, [], true, true], [false, [], true, false], [true, ["[E] bad"], true, false], [true, [], false, false]]) {
let ARGV = ["saved.json", "--boot"]; let inputjson = {}; let logs = []; let boot_render = true;
let schemareader = { validate: () => { push(logs, ...c[1]); return c[0] ? {} : null; } };
let renderer = {render: () => "batch", write_files: () => c[2]};
let ready = false; let commands = [];
let fs = {writefile: (path, data) => { if (path == "/tmp/ucentral-network.ready") ready = true; return length(data); } };
let staging = {foreach: () => {}, delete: () => {}, commit: () => {}};
let require = () => ({cursor: () => staging});
let system = cmd => { push(commands, cmd); return 0; };
let actual_exit = null; let exit = code => { actual_exit = code; };
let warn = () => {}; let print = () => {};
try {'
    awk '/^if \(boot_render\) \{/ { output = 1 } output { print } output && /^}$/ { exit }' "$source_dir/renderer/ucentral.uc"
    printf '%s\n' '} catch (e) { die("unexpected exception: " + e); }
assert(actual_exit == (c[3] ? 0 : 1), "wrong boot exit");
assert(ready == c[3], "invalid boot marked ready");
for (let cmd in commands) assert(!match(cmd, /init.d|reload_config|ifup|udhcpc/), "boot render activated networking");
if (!c[0] || length(c[1])) assert(!length(commands), "invalid config had side effects");
} print("4 boot render acceptance/fail-closed cases passed\n");'
} | "$ucode_bin" -

# Render the real bridge templates with the real ethernet/UCI helper library.
{
    printf 'import * as helpers from "%s/renderer/libs/uci_helpers.uc";\n' "$source_dir"
    printf 'import { create_ethernet } from "%s/renderer/libs/ethernet.uc";\n' "$source_dir"
    printf 'import * as schema from "%s/schemareader.uc";\n' "$source_dir"
    printf 'let root = "%s/renderer/templates/";\n' "$source_dir"
    printf '%s\n' '
let capab = {platform: "ap", network: {wan: ["lan1"]}};
let ethernet = create_ethernet(capab, null, null);
let base = render(root + "base.uc", {...helpers, capab, board: {}});
assert(index(base, "network.up.vlan_filtering=\u00271\u0027") >= 0, "up filtering not explicit");
assert(index(base, "network.down.vlan_filtering=\u00271\u0027") >= 0, "down filtering not explicit");
for (let c in [[37, "tagged", ":t"], [203, "un-tagged", ""], [4090, "un-tagged", ""]]) {
 let input = {uuid: 2, interfaces: [{name: "Management", role: "upstream", vlan: {id: c[0]}, ethernet: [{"select-ports": ["WAN"], "vlan-tag": c[1]}], ipv4: {addressing: "dynamic"}}]};
 if (c[0] == 4090) delete input.interfaces[0].vlan;
 let logs = []; let state = schema.validate(input, logs);
 assert(state && !length(logs), "fixture rejected: " + join("; ", logs));
 let interface = state.interfaces[0]; interface.index = 0;
 interface.vlan ??= {id: 0, dyn_id: 4090};
 let name = ethernet.calculate_name(interface);
 let output = render(root + "interface/bridge-vlan.uc", {...helpers, ethernet, interface, name, eth_ports: {lan1: c[1]}, this_vid: c[0], bridgedev: "up", swconfig: null});
 assert(index(output, "network.@bridge-vlan[-1].vlan=" + c[0]) >= 0, "wrong VLAN");
 assert(index(output, "lan1" + c[2]) >= 0, "wrong tagging");
 assert(index(output, "network.@device[-1].vid=" + c[0]) >= 0, "management device wrong VLAN");
}
print("3 configured tagged/native VLAN template cases passed\n");'
} | "$ucode_bin" -

grep -Fq 'START=18' "$source_dir/early-network/ucentral-network.init"
grep -Fq 'preinit_ip_config() { return 0; }' "$source_dir/early-network/15_ucentral_no_preinit_network"
grep -Fq '/usr/libexec/ucentral-network || return 1' "$source_dir/early-network/network"
for f in ucentral-network ucentral-network.init 15_ucentral_no_preinit_network network; do
    sh -n "$source_dir/early-network/$f"
done
printf '%s\n' 'Startup order, preinit suppression and shell syntax checks passed'
