#!/bin/sh
# Manual migration of a qualified, converted Cambium OpenWrt XV3-8.
# Default --check has no flash writes. Phil controls --install execution.
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
mode=${1:---check}
case "$mode" in --check|--install) ;; *) echo 'Usage: thor-sysinstall.sh --check|--install' >&2; exit 2 ;; esac
requested=${2:---auto}
case "$requested" in --auto|--stock|--openwifi) ;; *) exit 2 ;; esac
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
image_name=$(cat "$here/IMAGE")
case "$image_name" in ''|*/*|*..*) echo 'Invalid bundled image name' >&2; exit 1 ;; esac
image=$here/$image_name
(cd "$here" && sha256sum -c SHA256SUMS)
. "$here/source-set-check.sh"
. "$here/minimum-release-contract.sh"
. "$here/runtime-implementation-contract.sh"
. "$here/source-route.sh"
approved_metadata=$(ow_thor_metadata_fingerprint) || exit 1
route=$(ow_thor_route "$here") || { echo 'Unknown or mixed outgoing source tuple' >&2; exit 1; }
[ "$(ow_thor_metadata_fingerprint)" = "$approved_metadata" ] || exit 1
[ "$requested" = --auto ] || [ "$requested" = "--$route" ] || { echo 'Requested route does not match verified source' >&2; exit 1; }
sh "$here/prepare-upgrader.sh" --check "$image" "$route"
# Frozen OpenWiFi defaults SAVE_CONFIG=0 even for -T; explicitly guard the
# configuration that the preserving -f route will restore. No UCI edits.
if [ "$route" = openwifi ]; then
 uci -q export system >/dev/null || { echo 'Cannot validate preserving-route system configuration' >&2; exit 1; }
 compat=$(uci -q get 'system.@system[0].compat_version') || compat=
 case "$compat" in ''|1.0) ;; *) echo 'Preserving-route compatibility must be default/explicit 1.0' >&2; exit 1 ;; esac
fi
if [ "$route" = openwifi ] && { [ -L /etc/ucentral/ucentral.active ] || [ -e /etc/ucentral/ucentral.active ]; }; then
 active=$(readlink -f /etc/ucentral/ucentral.active)
 case "$active" in /etc/ucentral/*|/rom/etc/ucentral/ucentral.cfg.0000000001) ;; *) echo 'Unsupported active document path; refusing migration' >&2; exit 1 ;; esac
 [ -f "$active" ] && [ -s "$active" ] || { echo 'Saved active document is empty/dangling; refusing migration' >&2; exit 1; }
fi
# Keep metadata/config compatibility checks in the default read-only path.
# Do not force a compatibility override or change UCI/config-shadow fences.
if [ "$route" = stock ]; then sysupgrade --no-provisioning -n -T "$image"; else sysupgrade -T "$image"; fi
[ "$mode" = --install ] || exit 0

# Preserve the complete existing sysupgrade set plus all managed identity,
# saved document and shadow baseline files on the OpenWiFi route only.
if [ "$route" = openwifi ]; then
work=$(mktemp -d /tmp/thor-openwifi-install.XXXXXX)
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
fi

# Update only the outgoing updater files, verify every byte, then run the
# normal platform/metadata preflight with the corrected stage2 policy.
sh "$here/prepare-upgrader.sh" --install "$image" "$route"
sh "$here/prepare-upgrader.sh" --verify-installed "$image" "$route"
if [ "$route" = stock ]; then sysupgrade --no-provisioning -n -T "$image"; else sysupgrade -T "$image"; fi
[ "$(ow_thor_metadata_fingerprint)" = "$approved_metadata" ] || { echo "Release metadata changed; refusing flash" >&2; exit 1; }
[ "$(ow_thor_route "$here")" = "$route" ] || exit 1
echo 'Starting operator-authorized A/B trial; running bank remains the rollback bank.'
if [ "$route" = stock ]; then
 echo 'Clean migration: no legacy identity/configuration imported; OpenWiFi starts unprovisioned.'
 sysupgrade -v --no-provisioning -n "$image"
else
 sysupgrade -v -f "$work/preserved.tgz" "$image"
fi
