#!/bin/bash
set -euo pipefail
task_base=/home/phil/openwifi-gambit-build
task_tree=$task_base/wlan-ap
task_openwrt=$task_tree/openwrt
test "$(cat "$task_base/build.exit")" = 0
test "$(cat "$task_base/final-build.exit")" = 0
task_image=$task_openwrt/bin/targets/ath79/nand/openwrt-ath79-nand-cambiumnetworks_gambit-persistent-squashfs-sysupgrade.bin
test -s "$task_image"
task_extract=$(mktemp -d /tmp/gambit-openwifi-image-check.XXXXXX)
tar -xf "$task_image" -C "$task_extract"
task_payload=$task_extract/sysupgrade-cambiumnetworks_gambit-persistent
test -s "$task_payload/kernel"
test -s "$task_payload/root"
"$task_openwrt/staging_dir/host/bin/unsquashfs4" -excludes -d "$task_extract/rootfs" "$task_payload/root" dev/console >/dev/null
python3 "$task_base/gambit-packaged-audit.py" "$task_extract/rootfs" "$task_extract/packaged-audit.json"
"$task_tree/scripts/check-init-backups.sh" "$task_extract/rootfs"
task_entries=$(find "$task_extract/rootfs/etc/rc.d" -name 'S*network*' -printf '%f\n' | grep '^S[0-9][0-9]network')
test "$task_entries" = S20network
test "$(readlink "$task_extract/rootfs/etc/rc.d/S20network")" = ../init.d/network
test -s "$task_extract/rootfs/etc/ucentral/discovery-policy.json"
test -s "$task_extract/rootfs/etc/uci-defaults/19_cambium_openwifi_identity"
test ! -e "$task_extract/rootfs/etc/uci-defaults/12_gambit_recovery"
grep -Fq 'AB_CERTIFICATE_LEBS=20' "$task_extract/rootfs/lib/functions/cambium-ab-gambit.sh"
grep -Fq 'AB_CERTIFICATE_POLICY_VERSION=1' "$task_extract/rootfs/lib/upgrade/cambium-ab.sh"
grep -Fq 'AB_CERTIFICATE_CONTENT_VERSION=1' "$task_extract/rootfs/lib/upgrade/cambium-ab-certificates.sh"
grep -Fq 'platform_pre_upgrade()' "$task_extract/rootfs/lib/upgrade/platform.sh"
grep -Fq 'AB_ACTIVE_UBI' "$task_extract/rootfs/usr/bin/mount_certs"
task_sections_root=$(mktemp -d /tmp/gambit-packaged-sections.XXXXXX)
ln -s "$task_extract/rootfs/usr/share/ucentral" "$task_sections_root/renderer"
sh "$task_tree/feeds/ucentral/ucentral-schema/scripts/test-udevstats-sections.sh" "$task_sections_root" "$task_openwrt/staging_dir/hostpkg/bin/ucode" /tmp/openwifi-native-uci.KOZSBq/bin/uci
sh "$task_base/gambit-real-uci.sh" "$task_openwrt" /tmp/openwifi-native-uci.KOZSBq "$task_base/renderer-fixtures" "$task_extract/rootfs"
cmp "$task_openwrt/package/cambium/cambium-ab/files/cambium-ab-guard" "$task_extract/rootfs/usr/sbin/cambium-ab-guard"
cmp "$task_openwrt/package/cambium/cambium-ab/files/cambium-ab.sh" "$task_extract/rootfs/lib/functions/cambium-ab.sh"
cmp "$task_openwrt/package/cambium/cambium-ab/files/cambium-ab-upgrade.sh" "$task_extract/rootfs/lib/upgrade/cambium-ab.sh"
cmp "$task_openwrt/package/cambium/cambium-ab/files/cambium-ab-certificates.sh" "$task_extract/rootfs/lib/upgrade/cambium-ab-certificates.sh"
cmp "$task_openwrt/package/cambium/cambium-gambit-support/files/cambium-ab-gambit.sh" "$task_extract/rootfs/lib/functions/cambium-ab-gambit.sh"
cmp "$task_openwrt/package/boot/uboot-tools/uboot-envtools/files/ath79" "$task_extract/rootfs/etc/uci-defaults/30_uboot-envtools"
cmp "$task_tree/feeds/tip/certificates/files/usr/bin/mount_certs" "$task_extract/rootfs/usr/bin/mount_certs"
task_kernel=$task_openwrt/build_dir/target-mips_24kc_musl/linux-ath79_nand/linux-6.12.85
test -s "$task_kernel/.config"
for task_symbol in LEDS_GPIO CPU_BIG_ENDIAN CPU_MIPS32_R2 MTD_NAND_AR934X MTD_NAND_ECC_SW_HAMMING NVMEM NVMEM_LAYOUTS MTD_UBI MTD_UBI_BLOCK; do
    grep -qx "CONFIG_$task_symbol=y" "$task_kernel/.config"
done
grep -qx 'CONFIG_INITRAMFS_SOURCE=""' "$task_kernel/.config"
grep -Rq 'nvmem_mac_base_hex_read' "$task_kernel/drivers/nvmem"
test -s "$task_kernel/drivers/mtd/nand/raw/ar934x_nand.o"
python3 "$task_openwrt/cambium/scripts/verify-gambit.py" persistent "$task_payload/kernel"
GAMBIT_GUARD_TEST_FILE="$task_extract/rootfs/usr/sbin/cambium-ab-guard" sh "$task_openwrt/cambium/tests/cambium-ab-routing.sh"
task_discovery_test=$(mktemp -d /tmp/gambit-packaged-discovery.XXXXXX)
mkdir "$task_discovery_test/tests" "$task_discovery_test/files"
cp "$task_tree/feeds/tip/cloud_discovery/tests/"* "$task_discovery_test/tests/"
ln -s "$task_extract/rootfs/usr" "$task_discovery_test/files/usr"
ln -s "$task_extract/rootfs/etc" "$task_discovery_test/files/etc"
"$task_openwrt/staging_dir/hostpkg/bin/ucode" "$task_discovery_test/tests/test-discovery-policy.uc"
sh "$task_discovery_test/tests/test-discovery-helper.sh" "$task_openwrt/staging_dir/hostpkg/bin/ucode"
sh "$task_discovery_test/tests/test-discovery-lease-state.sh" "$task_openwrt/staging_dir/hostpkg/bin/ucode" "$task_extract/rootfs/usr/bin/cloud_discovery"
python3 "$task_base/gambit-component-tests.py" "$task_extract/rootfs"
grep -E 'DISTRIB_(DESCRIPTION|TIP|REVISION)' "$task_extract/rootfs/etc/openwrt_release"
stat -c 'SIZE=%s' "$task_image"
sha256sum "$task_image"
echo "VERIFIED_EXTRACT=$task_extract"
echo 'PASS: static image and component checks; hardware and private enrollment remain separate gates'

sh "$task_base/gambit-target-utilities.sh" "$task_extract/rootfs"
