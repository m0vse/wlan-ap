#!/bin/sh
# Execute the shipped helper with filesystem paths redirected and ubus stubbed.
# No DHCP packets, host networking, EST, or AP operations are performed.
set -eu
export interface=up0v0
ucode=${1:?native ucode executable}
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")/../files" && pwd)
fixture=$(mktemp -d /tmp/openwifi-discovery-test.XXXXXX)
mkdir -p "$fixture/tmp" "$fixture/etc/ucentral"
cp "$source_dir/usr/share/ucentral/discovery_policy.uc" "$fixture/"
cp "$source_dir/etc/ucentral/discovery-policy.json" "$fixture/etc/ucentral/"
sed -e "s|/tmp/|$fixture/tmp/|g" -e "s|/etc/|$fixture/etc/|g" \
    -e "s|from 'ubus'|from './ubus.uc'|" \
    "$source_dir/usr/share/ucentral/cloud_discovery.uc" > "$fixture/helper.uc"
printf '%s\n' 'import * as fs from "fs";' \
    "export function connect() { return { call: function() { fs.writefile('$fixture/tmp/renew-called', 'yes'); } }; };" > "$fixture/ubus.uc"
assert_selected() {
    "$ucode" -e 'import * as fs from "fs"; let c=json(fs.readfile(ARGV[0])); if(c.dhcp_server != ARGV[1] || c.dhcp_port != 15002 || c.no_validation != false) die("bad selection\n");' "$fixture/tmp/cloud.json" "${1:-openwifi.wlan.local}"
}
assert_rejected() {
    "$ucode" -e 'import * as fs from "fs"; let c=json(fs.readfile(ARGV[0])); if(!c.lease || c.dhcp_server != null || c.dhcp_port != null) die("bad rejection\n");' "$fixture/tmp/cloud.json"
}
printf '%s' '192.0.2.1' > "$fixture/tmp/dhcp-option-138"
printf '%s' 'openwifi.wlan.local:15002' > "$fixture/tmp/dhcp-option-224"
"$ucode" "$fixture/helper.uc" bound
assert_selected
interface=secondary "$ucode" "$fixture/helper.uc" deconfig
assert_selected
"$ucode" "$fixture/helper.uc" deconfig
"$ucode" -e 'import * as fs from "fs"; let c=json(fs.readfile(ARGV[0])); if(c.lease != false || c.dhcp_server != null || c.dhcp_port != null || c.lease_interface != "up0v0") die("stale lease/hint\n");' "$fixture/tmp/cloud.json"
test ! -e "$fixture/tmp/dhcp-option-138"
test ! -e "$fixture/tmp/dhcp-option-224"
test -s "$fixture/tmp/renew-called"
"$ucode" "$fixture/helper.uc" bound
assert_selected
"$ucode" "$fixture/helper.uc" release
"$ucode" -e 'import * as fs from "fs"; if(json(fs.readfile(ARGV[0])).lease != false) die("release retained lease\n");' "$fixture/tmp/cloud.json"
"$ucode" "$fixture/helper.uc" bound
assert_selected
: > "$fixture/tmp/dhcp-option-138"
: > "$fixture/tmp/dhcp-option-224"
"$ucode" "$fixture/helper.uc" renew
assert_selected
test -s "$fixture/tmp/renew-called"
printf '%s' 'https://unapproved.example/path' > "$fixture/tmp/dhcp-option-224"
"$ucode" "$fixture/helper.uc" bound
assert_selected
printf '%s' 'other.example:15002' > "$fixture/tmp/dhcp-option-224"
"$ucode" "$fixture/helper.uc" bound
assert_selected other.example
printf '%s' 'https://invalid.example/path' > "$fixture/tmp/dhcp-option-224"
printf '%s' '{broken' > "$fixture/etc/ucentral/discovery-policy.json"
"$ucode" "$fixture/helper.uc" bound
assert_rejected
printf '%s' 'null' > "$fixture/etc/ucentral/discovery-policy.json"
"$ucode" "$fixture/helper.uc" bound
assert_rejected
mv "$fixture/etc/ucentral/discovery-policy.json" "$fixture/policy.disabled"
"$ucode" "$fixture/helper.uc" bound
assert_rejected
printf '%s\n' "12 actual helper cases passed; retained fixtures: $fixture"
