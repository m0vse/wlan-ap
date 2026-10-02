#!/bin/sh
# Run only in a private root mount namespace; no AP/service/network operations.
set -eu
root=$1
qemu=$2
package=$3
fixtures=$4
work=$5
mount --make-rprivate /
mount -t tmpfs tmpfs /etc
mount -t tmpfs tmpfs /usr/share
mount -t tmpfs tmpfs /usr/libexec
mkdir -p /etc/ucentral /usr/share/ucentral
cp "$fixtures/gateway.json" /etc/ucentral/gateway.json
cp "$package/files/usr/share/ucentral/"*.uc /usr/share/ucentral/
for source in "$package/files/usr/bin/cloud_discovery" "$package/files/usr/bin/est_client" /usr/share/ucentral/cloud_discovery.uc "$fixtures/policy-probe.uc"; do
 "$qemu" -L "$root" "$root/usr/bin/ucode" -L "$root/usr/lib/ucode" -c -o "$work/$(basename "$source").ucb" "$source"
done
# Actual CLI dispatch and complete target imports, not extracted functions.
set +e
"$qemu" -L "$root" "$root/usr/bin/ucode" -L "$root/usr/lib/ucode" "$package/files/usr/bin/est_client" reenroll > "$work/missing-leaf.log" 2>&1
status=$?
set -e
test "$status" = 1
grep -q 'Operational certificate was not found' "$work/missing-leaf.log"
cp "$fixtures/private-guard" /usr/libexec/ucentral-private-pki
chmod 0755 /usr/libexec/ucentral-private-pki
for source in est_client cloud_discovery; do
 set +e
 "$qemu" -L "$root" "$root/usr/bin/ucode" -L "$root/usr/lib/ucode" "$package/files/usr/bin/$source" reenroll > "$work/$source-guard.log" 2>&1
 status=$?
 set -e
 test "$status" = 1
 test ! -s "$work/$source-guard.log"
done
echo 'PASS: four complete target compilations, actual missing-leaf CLI error and two preserved private-guard refusals'
