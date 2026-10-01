#!/bin/sh
# Patch backups under init.d are executable services to OpenWrt's installer.
set -eu
[ "$#" -gt 0 ] || { echo "Usage: $0 tree..." >&2; exit 2; }
report=$(mktemp)
trap 'rm -f "$report"' EXIT HUP INT TERM
for tree do
	[ -d "$tree" ] || { echo "Missing tree: $tree" >&2; exit 2; }
	find "$tree" \( -path '*/etc/init.d/*' -o -path '*/etc/rc.d/*' \) \
		\( -name '*.orig' -o -name '*.rej' -o -name '*.bak' -o -name '*~' \) \
		-print >> "$report"
done
if [ -s "$report" ]; then
	echo 'Refusing firmware with init-script backup files or boot entries:' >&2
	cat "$report" >&2
	exit 1
fi
