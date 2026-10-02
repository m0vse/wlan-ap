#!/bin/sh
set -eu
repo=/home/phil/openwifi-sage-build/wlan-ap
status_file=/home/phil/openwifi-sage-build/sage-2026.10.02.6-build.exit
trap 'status=$?; printf "%s\n" "$status" > "$status_file"' EXIT
cd "$repo/openwrt"
test "$(scripts/getver.sh wlan-ap-version)" = sage-2026.10.02.6
test "$(sed -n 's/^PKG_RELEASE:=//p' package/feeds/target_ipq40xx/cambium-ab/Makefile)" = 17
"$repo/scripts/check-init-backups.sh" package "$repo/feeds"
make package/base-files/clean
make package/feeds/target_ipq40xx/cambium-ab/clean
nice -n 10 make -j4 V=s
