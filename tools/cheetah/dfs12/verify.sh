#!/bin/bash
set -euo pipefail
base=/home/phil/openwifi-cheetah-build
tree=$base/wlan-ap
mkdir -p "$base/dfs12/payload/modules"
bash "$base/verify-image.sh" "$tree" cheetah-2026.10.02.12 > "$base/dfs12/image-verification.log"
extract=$(sed -n 's/^VERIFIED_EXTRACT=//p' "$base/dfs12/image-verification.log")
root=$extract/rootfs
printf '%s\n' "$root" > "$base/dfs12/ROOT"
image=$base/dfs12/cambium_xv2-21x-cheetah-2026.10.02.12-sysupgrade.bin
cp "$tree/openwrt/bin/targets/qualcommax/ipq50xx/openwrt-qualcommax-ipq50xx-cambiumnetworks_cheetah-persistent-squashfs-sysupgrade.bin" "$image"
export PATH=$base/fit-verification/bin:$PATH
CHEETAH_FLAVOR=persistent sh "$base/fit-verification/verify-family-fit.sh" "$extract/sysupgrade-cambiumnetworks_cheetah/kernel" > "$base/dfs12/fit-verification.log"
python3 "$base/verify-hardware-fit.py" "$extract/sysupgrade-cambiumnetworks_cheetah/kernel" > "$base/dfs12/hardware-fit.json"
python3 "$base/audit-kernel-headers.py" "$tree/openwrt" > "$base/dfs12/kernel-header-audit.json"
sh "$base/test-target-permissions.sh" "$root" "$root/lib/upgrade/cambium-ab-certificates.sh" > "$base/dfs12/target-utility-tests.log"
export OW_DFS_TARGET_ROOT=$root OW_DFS_SOURCE=$base/dfs12-source OW_DFS_IMAGE=$image OW_DFS_QEMU=/usr/bin/qemu-aarch64
python3 "$base/test-built-image.py" > "$base/dfs12/built-image-tests.json"
python3 "$base/test-target-cli.py" > "$base/dfs12/target-cli-tests.json"
cp "$root/lib/functions/cambium-ab.sh" "$base/dfs12/payload/cambium-ab.sh"
cp "$root/lib/functions/cambium-ab-cheetah.sh" "$base/dfs12/payload/modules/cambium-ab-cheetah.sh"
cp "$root/lib/upgrade/cambium-ab.sh" "$base/dfs12/payload/cambium-ab-upgrade.sh"
cp "$root/lib/upgrade/cambium-ab-certificates.sh" "$base/dfs12/payload/cambium-ab-certificates.sh"
cp "$root/lib/upgrade/platform.sh" "$base/dfs12/payload/platform.sh"
python3 "$base/dfs12/adapt-tests.py"
python3 "$base/dfs12/test-validator.py" > "$base/dfs12/managed11-validator-tests.json"
python3 "$base/dfs12/test-ram-copy.py" > "$base/dfs12/ram-copy-tests.json"
sha256sum "$image"
echo 'PASS: Cheetah .12 root/FIT/hardware/header/runtime/validator/RAM fixtures'
