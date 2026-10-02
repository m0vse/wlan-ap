#!/bin/sh
# Execute the shipped helper with filesystem paths redirected and ubus stubbed.
# No DHCP packets, host networking, EST, or AP operations are performed.
set -eu
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
    "$ucode" -e 'import * as fs from "fs"; let c=json(fs.readfile(ARGV[0])); if(c.dhcp_server != "openwifi.shinesystems.co.uk" || c.dhcp_port != 15002 || c.no_validation != false) die("bad selection\n");' "$fixture/tmp/cloud.json"
}
assert_rejected() {
    "$ucode" -e 'import * as fs from "fs"; let c=json(fs.readfile(ARGV[0])); if(!c.lease || c.dhcp_server != null || c.dhcp_port != null) die("bad rejection\n");' "$fixture/tmp/cloud.json"
}
printf '%s' '192.0.2.1' > "$fixture/tmp/dhcp-option-138"
printf '%s' 'openwifi.shinesystems.co.uk:15002' > "$fixture/tmp/dhcp-option-224"
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
printf '%s' '{broken' > "$fixture/etc/ucentral/discovery-policy.json"
"$ucode" "$fixture/helper.uc" bound
assert_rejected
printf '%s' 'null' > "$fixture/etc/ucentral/discovery-policy.json"
"$ucode" "$fixture/helper.uc" bound
assert_rejected
mv "$fixture/etc/ucentral/discovery-policy.json" "$fixture/policy.disabled"
"$ucode" "$fixture/helper.uc" bound
assert_rejected
printf '%s\n' "6 actual helper cases passed; retained fixtures: $fixture"
