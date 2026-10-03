#!/bin/sh
# Source-only replay in a fresh private directory; never edits retained builds.
set -eu
archive=$1
patches=$2
fixture=$(mktemp -d /tmp/openwifi-schema-series.XXXXXX)
tar -xf "$archive" --strip-components=1 -C "$fixture"
for p in "$patches"/*.patch; do
	patch -d "$fixture" -p1 -F0 --batch < "$p"
done
printf 'Full schema series -F0 PASS: %s\n' "$fixture"
