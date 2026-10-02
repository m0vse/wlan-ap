#!/bin/sh
# Manual update of exact Sage OpenWiFi Oct2.1 E410/E410B only.
# Converted stock OpenWrt (DSA/config1.1) is not approved by this bundle.
# Default --check has no flash writes. Phil controls --install execution.
set -eu
mode=${1:---check}
case "$mode" in --check|--install) ;; *) echo 'Usage: sage-sysinstall.sh --check|--install' >&2; exit 2 ;; esac
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
image_name=$(cat "$here/IMAGE")
case "$image_name" in ''|*/*|*..*) echo 'Invalid bundled image name' >&2; exit 1 ;; esac
image=$here/$image_name
(cd "$here" && sha256sum -c SHA256SUMS)
if [ "$mode" = --install ]; then
 # Explicit installation permits recovery of our own approved pending journal.
 sh "$here/prepare-upgrader.sh" --recover "$image"
fi
sh "$here/prepare-upgrader.sh" --check "$image"
if [ -L /etc/ucentral/ucentral.active ] || [ -e /etc/ucentral/ucentral.active ]; then
 active=$(readlink -f /etc/ucentral/ucentral.active)
 case "$active" in /etc/ucentral/*|/rom/etc/ucentral/ucentral.cfg.0000000001) ;; *) echo 'Unsupported active document path; refusing migration' >&2; exit 1 ;; esac
 [ -f "$active" ] && [ -s "$active" ] || { echo 'Saved active document is empty/dangling; refusing migration' >&2; exit 1; }
fi
[ "$mode" = --install ] || exit 0

# Preserve the complete existing sysupgrade set plus all managed identity,
# saved document and shadow baseline files. Never use sysupgrade -n here.
work=$(mktemp -d /tmp/sage-openwifi-install.XXXXXX)
chmod 700 "$work"
mkdir "$work/archive"
sysupgrade -b "$work/existing.tgz"
tar -xzf "$work/existing.tgz" -C "$work/archive"
mkdir -p "$work/archive/etc"
for path in /etc/config /etc/config-shadow /etc/ucentral; do
 [ ! -d "$path" ] || cp -a "$path" "$work/archive/etc/"
done
(cd "$work/archive" && tar -czf "$work/preserved.tgz" .)
chmod 600 "$work/preserved.tgz"

# Update only the outgoing updater files, verify every byte, then run the
# normal platform/metadata preflight with the corrected stage2 policy.
sh "$here/prepare-upgrader.sh" --install "$image"
sh "$here/prepare-upgrader.sh" --verify-installed "$image"
sysupgrade -T "$image"
echo 'Starting operator-authorized A/B trial; running bank remains the rollback bank.'
sysupgrade -v -f "$work/preserved.tgz" "$image"
