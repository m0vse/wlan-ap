#!/bin/sh
# Read-only installed-firmware handoff check. Never performs a second upgrade.
set -eu
set +x
OEM_HERE=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
OEM_SYS_ROOT=
OEM_BUNDLE=$OEM_HERE
OEM_RELEASE_PIN=RELEASE_PIN_NOT_CONFIGURED
[ "${1:-}" != --help ] || { printf '%s\n' 'Usage: cambium-ab-ready [--release-dir DIR --release-pin SHA256]';exit 0; }
while [ "$#" -gt 0 ]; do
 [ "$#" -ge 2 ] || exit 2
 case "$1" in --release-dir) OEM_BUNDLE=$2;; --release-pin) OEM_RELEASE_PIN=$2;; *) exit 2;; esac
 shift 2
done
[ "${#OEM_RELEASE_PIN}" = 64 ] || exit 1
case "$OEM_RELEASE_PIN" in *[!0-9a-f]*) exit 1;; esac
[ -d "$OEM_BUNDLE" ] && [ ! -L "$OEM_BUNDLE" ] && [ "$(readlink -f "$OEM_BUNDLE")" = "$OEM_BUNDLE" ] || exit 1
[ -f "$OEM_BUNDLE/SHA256SUMS" ] && [ ! -L "$OEM_BUNDLE/SHA256SUMS" ] || exit 1
[ "$(sha256sum < "$OEM_BUNDLE/SHA256SUMS" | awk '{print $1}')" = "$OEM_RELEASE_PIN" ] || exit 1
awk 'NF!=2 || length($1)!=64 || $1~/[^0-9a-f]/ || $2!~/^[A-Za-z0-9_.\/-]+$/ || $2~/^\// || $2~/(^|\/)\.\.?(\/|$)/ || seen[$2]++ {bad=1} END{exit bad || NR<4}' "$OEM_BUNDLE/SHA256SUMS" || exit 1
while read -r digest name; do
 [ -f "$OEM_BUNDLE/$name" ] && [ ! -L "$OEM_BUNDLE/$name" ] && [ "$(readlink -f "$OEM_BUNDLE/$name")" = "$OEM_BUNDLE/$name" ] || exit 1
done < "$OEM_BUNDLE/SHA256SUMS"
(cd "$OEM_BUNDLE" && sha256sum -c SHA256SUMS >/dev/null 2>&1) || exit 1
for name in lib/common.sh recognition.tsv; do
 awk -v name="$name" '$2==name {n++} END{exit n!=1}' "$OEM_BUNDLE/SHA256SUMS" || exit 1
done
. "$OEM_BUNDLE/lib/common.sh"
member=$(oem_bundle_member lib/protection.sh) || exit 1
. "$member"
[ -r "$OEM_SYS_ROOT/etc/openwrt_release" ] || exit 1
oem_detect || exit 1
OEM_MODEL_MAP=upgrade-models.tsv OEM_ADAPTER_PREFIX=upgrade-
oem_release_check || { printf 'Sysupgrade readiness: unsupported or not released for this model/version.\n';exit 1; }
member=$(oem_bundle_member "adapters/upgrade-$OEM_ADAPTER.sh") || exit 1
. "$member"
command -v oem_upgrade_inspect >/dev/null || exit 1
OEM_UPGRADE_STATUS=unsupported OEM_UPGRADE_REASON=not-checked
oem_upgrade_inspect || { printf 'Sysupgrade readiness check failed; no changes made.\n';exit 1; }
case "$OEM_UPGRADE_STATUS" in ready|onboarded|unsupported) ;; *) exit 1;; esac
case "$OEM_UPGRADE_REASON" in *[!A-Za-z0-9._:/' '-]*) exit 1;; esac
printf 'Sysupgrade readiness: %s; %s\n' "$OEM_UPGRADE_STATUS" "$OEM_UPGRADE_REASON"
[ "$OEM_UPGRADE_STATUS" = ready ]
