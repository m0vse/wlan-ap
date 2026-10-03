#!/bin/bash
set -euo pipefail
task_tree=${1:?dedicated wlan-ap root}
task_revision=${2:?exact TIP revision}
task_image=$task_tree/openwrt/bin/targets/qualcommax/ipq50xx/openwrt-qualcommax-ipq50xx-cambiumnetworks_cheetah-persistent-squashfs-sysupgrade.bin
task_extract=$(mktemp -d /tmp/cheetah-image-check.XXXXXX)
tar -xf "$task_image" -C "$task_extract"
"$task_tree/openwrt/staging_dir/host/bin/unsquashfs4" -excludes -d "$task_extract/rootfs" "$task_extract/sysupgrade-cambiumnetworks_cheetah/root" dev/console >/dev/null
root=$task_extract/rootfs
"$task_tree/scripts/check-init-backups.sh" "$root"
task_entries=$(find "$root/etc/rc.d" -name 'S*network*' -printf '%f\n' | grep '^S[0-9][0-9]network')
test "$task_entries" = S20network
test "$(readlink "$root/etc/rc.d/S20network")" = ../init.d/network
grep -Fq "$task_revision" "$root/etc/openwrt_release"
test ! -e "$root/etc/uci-defaults/17_cheetah_bridge_section"
test ! -e "$task_tree/openwrt/package/network/config/netifd/patches/301-bridge-no-default-pvid.patch"
! grep -q 'vlan_filtering' "$root/usr/share/ucentral/templates/base.uc"
grep -Fq '/usr/libexec/ucentral-network || return 1' "$root/etc/init.d/network"
grep -q 'ucentral-network.ready' "$root/etc/init.d/dnsmasq"
test -x "$root/usr/libexec/ucentral-network"
test -x "$root/etc/init.d/ucentral-network"
identity=$root/etc/uci-defaults/19_cambium_openwifi_identity
for model in xv2-21x xv2-22h xv2-23t; do
 fixture=$task_extract/identity-$model
 mkdir "$fixture"
 CAMBIUM_BOARD_NAME=cambiumnetworks,$model UCENTRAL_DIR="$fixture" sh "$identity"
 test "$(cat "$fixture/compatible")" = cambium_$model
done
mkdir "$task_extract/identity-unknown"
CAMBIUM_BOARD_NAME=cambiumnetworks,e600 UCENTRAL_DIR="$task_extract/identity-unknown" sh "$identity"
test ! -e "$task_extract/identity-unknown/compatible"
UCENTRAL_DIR="$task_extract/identity-xv2-21x" sh -c '. "$1"; for model in xv2-21x xv2-22h xv2-23t; do AB_QUALIFIED=0; ab_cheetah_board "cambiumnetworks,$model"; case "$model:$AB_QUALIFIED" in xv2-21x:1|xv2-22h:0|xv2-23t:0) ;; *) exit 1 ;; esac; done' sh "$root/lib/functions/cambium-ab-cheetah.sh"
sh "$(dirname "$0")/test-rtty.sh" "$root/etc/init.d/rtty"
test -f "$root/lib/preinit/75_certificates"
grep -q 'certificates' "$root/lib/upgrade/cambium-ab.sh"
test -f "$root/lib/functions/cambium-ab-cheetah.sh"
grep -q 'AB_CERTIFICATE_LEBS=20' "$root/lib/functions/cambium-ab-cheetah.sh"
test -f "$root/lib/upgrade/cambium-ab-certificates.sh"
grep -q 'ab_certificate_validate_snapshot' "$root/lib/upgrade/cambium-ab.sh"
grep -q 'ab_certificate_export' "$root/lib/upgrade/platform.sh"
grep -q 'RAMFS_COPY_DATA=' "$root/lib/upgrade/cambium-ab-certificates.sh"
grep -q 'get_mac_label' "$root/etc/uci-defaults/99-ucentral-hostname"
sh "$(dirname "$0")/test-hostname.sh" "$root/etc/uci-defaults/99-ucentral-hostname"
test -f "$root/etc/ucentral/discovery-policy.json"
test -f "$root/usr/share/ucentral/discovery_policy.uc"
test ! -e "$root/etc/ucentral/key.pem"
test ! -e "$root/etc/ucentral/cert.pem"
test ! -e "$root/etc/ucentral/operational.pem"
test ! -e "$root/certificates/key.pem"
test ! -e "$root/certificates/cert.pem"
. "$root/etc/openwrt_release"
printf 'FULL_REVISION=%s\n' "$DISTRIB_TIP"
stat -c 'SIZE=%s' "$task_image"
sha256sum "$task_image"
printf 'VERIFIED_EXTRACT=%s\n' "$task_extract"
echo 'PASS: full rootfs startup guards, identity, qualification, RTTY and certificate storage'
