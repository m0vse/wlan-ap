#!/bin/sh

set -eu

upgrade=$1

require() {
	grep -Fq "$1" "$upgrade" || {
		echo "ucentral-schema: managed upgrade invariant missing: $1" >&2
		exit 1
	}
}

# These trees are restored into the inactive overlay before init starts.
# Keeping both is what guarantees that netifd sees the controller-rendered
# bridge VLAN filtering and management interface before starting DHCP.
require '"/etc/config", "/etc/config-shadow"'
require 'fs.readlink("/etc/ucentral/ucentral.active")'
require "push(archive_cmdline, '/etc/ucentral/ucentral.active', active_config)"
require 'sysupgrade -f /upgrade.tgz'
require '"/etc/ucentral/discovery-policy.json"'

# A single shadow file creates the directory and makes zzz-ucentral skip its
# initialization while leaving the rest of the rendered configuration absent.
if grep -Fq '"/etc/config-shadow/ucentral"' "$upgrade"; then
	echo 'ucentral-schema: partial config-shadow preservation is unsafe' >&2
	exit 1
fi
