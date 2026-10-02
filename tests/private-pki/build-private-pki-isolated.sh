#!/bin/sh
# Run by sudo unshare --mount --net; every build write goes to private upper.
set -eu
test_root=${1:?private fixture directory}
source_root=/home/phil/openwifi-thor-build/wlan-ap
case "$test_root" in /tmp/private-pki-package-build.*) ;; *) exit 2 ;; esac
[ "$(dirname "$test_root")" = /tmp ] && [ -d "$test_root" ] && [ ! -L "$test_root" ] || exit 2
# Refuse accidental direct execution in the caller's mount/network namespace.
for test_namespace in mnt net; do
 [ "$(readlink /proc/self/ns/$test_namespace)" != "$(readlink /proc/$PPID/ns/$test_namespace)" ] || exit 2
done
mount --make-rprivate /
# fakeroot uses local IPC over loopback; no external interface exists here.
ip link set lo up
# Protect all absolute references back to existing family builds in namespace.
mount --bind /home/phil /home/phil
mount -o remount,bind,ro /home/phil
mkdir -p "$test_root/upper" "$test_root/work" "$test_root/tree"
mount -t overlay overlay -o "lowerdir=$source_root,upperdir=$test_root/upper,workdir=$test_root/work" "$test_root/tree"
trap 'umount "$test_root/tree"' 0 HUP INT TERM
mkdir -p "$test_root/tree/openwrt/feeds/tip/ucentral-private-pki"
cp -a "$test_root/input/ucentral-private-pki/." "$test_root/tree/openwrt/feeds/tip/ucentral-private-pki/"
[ -L "$test_root/tree/openwrt/package/feeds/tip/ucentral-private-pki" ] || ln -s ../../../feeds/tip/ucentral-private-pki "$test_root/tree/openwrt/package/feeds/tip/ucentral-private-pki"
chown -R phil:phil "$test_root/upper"
set +e
runuser -u phil -- make -C "$test_root/tree/openwrt/package/feeds/tip/ucentral-private-pki" TOPDIR="$test_root/tree/openwrt" -j2 compile CONFIG_PACKAGE_ucentral-private-pki=m V=s > "$test_root/build-package.log" 2>&1
result=$?
set -e
mkdir -p "$test_root/artifacts"
find "$test_root/tree/openwrt/bin" -name 'ucentral-private-pki*.apk' -exec cp '{}' "$test_root/artifacts/" ';'
printf '%s\n' "$result" > "$test_root/result"
tail -50 "$test_root/build-package.log"
exit "$result"
