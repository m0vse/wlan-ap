#!/bin/sh
# Check only. No installer, mount, source-store edit or upgrade entry point.
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
[ "$#" = 0 ] || { echo 'usage: sh ./check.sh (no install mode)' >&2; exit 2; }
bundle=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
die() { echo "REFUSE: $*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || die 'root required'
(cd "$bundle" && sha256sum -c SHA256SUMS) || die 'bundle checksum mismatch'
. "$bundle/source-set-check.sh"
. "$bundle/minimum-release-contract.sh"
. "$bundle/runtime-implementation-contract.sh"
ow_release_contract_check "$bundle/release-contract-policy" '' || die 'release metadata not qualified'
ow_runtime_contract_check "$bundle/source-sets/runtime-implementation.set" '' || die 'unknown runtime implementation'
for path in /lib/*.sh /lib/functions/*.sh /lib/upgrade/*.sh; do
 [ -e "$path" ] || [ -L "$path" ] || continue
 grep -Fxq "$path" "$bundle/source-sets/required-paths" || die 'unexpected wildcard-loaded script'
done
ow_source_set_matches "$bundle/source-sets/outgoing-tip-2026.10.02.1.set" "$bundle/source-sets/required-paths" '' || die 'unknown .1 updater source tuple'
[ "$(sha256sum < /usr/share/ucentral/cmd_upgrade.uc | cut -d' ' -f1)" = e3db102971239f319ce0f4b9f58bd852c3ff4361421c7357732438a1b55b6c25 ] || die 'unknown managed upgrade command'
[ ! -e /root/sage-upgrader-transaction ] && [ ! -L /root/sage-upgrader-transaction ] || die 'pending bridge transaction requires separate recovery'
# Only now source authenticated outgoing .1 code. Bind every fixture hook.
CAMBIUM_AB_LIB=/lib/functions/cambium-ab.sh
CAMBIUM_AB_MODULES=/lib/functions
CAMBIUM_SAGE_LIB=/lib/functions/cambium-sage.sh
AB_PROC_MTD=/proc/mtd AB_CMDLINE=/proc/cmdline AB_DT=/proc/device-tree
AB_UBI_SYS=/sys/class/ubi AB_MTD_SYS=/sys/class/mtd AB_DEV=/dev
AB_SYS_MODULE=/sys/module AB_BOARD_DATA=/usr/sbin/cambium-board-data
AB_CERTIFICATE_STORE=/certificates AB_CERTIFICATE_RUNTIME=/etc/ucentral
AB_PROC_MOUNTS=/proc/mounts AB_CERTIFICATE_OWNER=0
set +u
. /lib/functions/system.sh
. /lib/upgrade/cambium-ab.sh
ab_upgrade_preflight || die 'identity, layout or trial-state preflight failed'
[ "$AB_FAMILY" = sage ] && [ "$AB_LAYOUT" = pair ] && [ "$AB_QUALIFIED" = 1 ] || die 'unqualified Sage pair'
[ "$(ab_getenv sage_ab_confirmed)" = "$AB_ACTIVE" ] &&
 [ "$(ab_getenv sage_ab_state)" = confirmed ] || die 'running slot is not confirmed'
. "$bundle/compatibility-check.sh"
sage_configuration_preservation_check || die 'configuration compatibility is not 1.0'
# Shared-store check's content helpers: inspection only, no export/import.
ab_certificate_lebs() { echo 0; }
ab_certificate_tree_safe() {
 [ ! -L "$1" ] && [ -d "$1" ] || return 1
 [ -z "$(find "$1" ! -type f ! -type d -print)" ] || return 1
 (cd "$1" && find . -print) | LC_ALL=C awk '/[^A-Za-z0-9_.\/-]/ {bad=1} END {exit bad}'
}
. "$bundle/shared-store-check.sh"
sage_shared_store_check || die 'shared store mount, geometry, privacy or current identity differs'
# Startup must not replace a restored operational credential with stale data.
for file in /etc/ucentral/*.pem /etc/ucentral/*.ca; do
 [ -e "$file" ] || [ -L "$file" ] || continue
 [ -f "$file" ] && [ ! -L "$file" ] || die 'unsafe runtime credential'
 stored=/certificates/${file##*/}
 [ -f "$stored" ] && [ ! -L "$stored" ] && cmp -s "$file" "$stored" || die "durable credential differs: ${file##*/}"
done
for name in "linux$AB_TARGET" "rootfs$AB_TARGET" "rootfs_data$AB_TARGET"; do
 vol=$(ab_ubi_volume "$AB_ACTIVE_UBI" "$name") || die 'target volume absent'
 reserved=$(cat "$AB_UBI_SYS/$vol/reserved_ebs")
 [ "$(cat "$AB_UBI_SYS/$vol/usable_eb_size")" = 126976 ] || die 'target geometry differs'
 case "$reserved" in ''|*[!0-9]*) die 'invalid target capacity' ;; esac
 case "$name" in linux*) minimum=34 ;; rootfs_data*) minimum=67 ;; rootfs*) minimum=305 ;; esac
 [ "$reserved" -ge "$minimum" ] || die "target capacity too small: $name"
done
echo "PASS: authenticated Sage .1 source/runtime, confirmed $AB_MODEL slot $AB_ACTIVE, compatibility, shared durable credentials and target capacities."
echo 'Check only: no mount, allocation, source-store edit, bridge install, bank write or reboot. Normal UI .3 image validation and human trial are still required.'
