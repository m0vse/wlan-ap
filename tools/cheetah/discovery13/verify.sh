#!/bin/bash
set -euo pipefail
base=/home/phil/openwifi-cheetah-build
tree=$base/wlan-ap
out=$base/discovery13
mkdir -p "$out"
bash "$base/verify-image.sh" "$tree" cheetah-2026.10.02.13 > "$out/image-verification.log"
extract=$(sed -n 's/^VERIFIED_EXTRACT=//p' "$out/image-verification.log")
root=$extract/rootfs
printf '%s\n' "$root" > "$out/ROOT"
cp "$tree/openwrt/bin/targets/qualcommax/ipq50xx/openwrt-qualcommax-ipq50xx-cambiumnetworks_cheetah-persistent-squashfs-sysupgrade.bin" "$out/cambium_xv2-21x-cheetah-2026.10.02.13-sysupgrade.bin"
export PATH=$base/fit-verification/bin:$PATH
CHEETAH_FLAVOR=persistent sh "$base/fit-verification/verify-family-fit.sh" "$extract/sysupgrade-cambiumnetworks_cheetah/kernel" > "$out/fit-verification.log"
python3 "$base/verify-hardware-fit.py" "$extract/sysupgrade-cambiumnetworks_cheetah/kernel" > "$out/hardware-fit.json"
python3 "$out/check-image.py" "$root" "$tree" > "$out/extracted-package-tests.json"
work=$(mktemp -d /tmp/cheetah-discovery13-target.XXXXXX)
sudo -n unshare -m -- sh "$tree/tests/discovery-renewal-r6/test-target-package.sh" "$root" /usr/bin/qemu-aarch64 "$tree/feeds/tip/cloud_discovery" "$tree/tests/discovery-renewal-r6/target-fixtures" "$work" > "$out/target-package-tests.log"
export OW_TEST_UCODE=$tree/openwrt/staging_dir/hostpkg/bin/ucode
python3 "$base/test-managed-upgrade-command.py" /tmp/cheetah-image-check.c1ktu4/rootfs > "$out/managed12-command-tests.json"
python3 "$out/adapt-tests.py"
python3 "$out/test-validator.py" > "$out/managed12-validator-tests.json"
python3 "$out/test-ram-copy.py" > "$out/ram-copy-tests.json"
"$tree/openwrt/staging_dir/host/bin/fwtool" -q -i "$out/image-metadata.json" "$out/cambium_xv2-21x-cheetah-2026.10.02.13-sysupgrade.bin"
echo 'PASS: extracted discovery6 exact source, target runtime, .12 managed path and RAM/model controls'
