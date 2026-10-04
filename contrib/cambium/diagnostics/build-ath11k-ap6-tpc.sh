#!/bin/bash
# Diagnostic only: replay exact canonical Kbuild commands, restore all inputs.
set -euo pipefail
patch_file="${1:?Provide the AP TPC diagnostic patch path}"
root=/home/phil/openwifi-jaguar-build/wlan-ap/openwrt
linux="$root/build_dir/target-aarch64_cortex-a53_musl/linux-qualcommax_ipq60xx"
backports="$linux/mac80211-regular/backports-6.18.7"
driver="$backports/drivers/net/wireless/ath/ath11k"
toolchain="$root/staging_dir/toolchain-aarch64_cortex-a53_gcc-14.3.0_musl/bin"
export PATH="$toolchain:$PATH" STAGING_DIR="$root/staging_dir"
work=$(mktemp -d /tmp/xe34-ap-tpc-diagnostic.XXXXXX)
mkdir "$work/original"
for name in mac.c mac.o ath11k.o ath11k.ko; do
    cp -p "$driver/$name" "$work/original/$name"
done
if [ -f "$driver/.mac.o.d" ]; then
    cp -p "$driver/.mac.o.d" "$work/original/.mac.o.d"
fi
(cd "$driver"; sha256sum mac.c mac.o ath11k.o ath11k.ko) > "$work/original.sha256"
restore() {
    for name in mac.c mac.o ath11k.o ath11k.ko; do
        cp -p "$work/original/$name" "$driver/$name"
    done
    if [ -f "$work/original/.mac.o.d" ]; then
        cp -p "$work/original/.mac.o.d" "$driver/.mac.o.d"
    fi
    (cd "$driver"; sha256sum -c "$work/original.sha256")
}
trap restore EXIT
patch -p1 -F0 --batch --dry-run -d "$backports" < "$patch_file"
patch -p1 -F0 --batch -d "$backports" < "$patch_file"
cp -p "$driver/mac.c" "$work/mac.patched.c"
replay() {
    local command
    command=$(sed -n '1s/^.* := //p' "$driver/.$1.cmd")
    test -n "$command"
    # GNU make decodes Kbuild's savedcmd escaping exactly as in original build.
    printf 'saved := %s\n.PHONY: replay\nreplay:\n\t$(saved)\n' "$command" |
        make --no-print-directory -C "$linux/linux-6.12.85" -f - replay
}
replay mac.o
replay ath11k.o
replay ath11k.ko
cp -p "$driver/ath11k.ko" "$work/ath11k-ap-tpc.ko"
cp -p "$work/original/ath11k.ko" "$work/ath11k-original-stripped.ko"
export CROSS="$toolchain/aarch64-openwrt-linux-musl-"
sh "$root/scripts/strip-kmod.sh" "$work/ath11k-ap-tpc.ko"
sh "$root/scripts/strip-kmod.sh" "$work/ath11k-original-stripped.ko"
sha256sum "$work/ath11k-ap-tpc.ko" "$work/ath11k-original-stripped.ko"
aarch64-openwrt-linux-musl-readelf -p .modinfo "$work/ath11k-ap-tpc.ko"
cmp <(aarch64-openwrt-linux-musl-readelf -p .modinfo "$work/ath11k-ap-tpc.ko") <(aarch64-openwrt-linux-musl-readelf -p .modinfo "$work/ath11k-original-stripped.ko")
printf 'DIAGNOSTIC_DIR=%s\n' "$work"
