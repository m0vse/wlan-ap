#!/bin/sh
# Current qualified b6 OpenWiFi -> retained OEM, once. Both banks untouched.
# OpenWrt functions/system.sh and its UCI/JSON libraries do not support nounset.
set -e
[ "$*" = 'arm --yes' ] || { echo 'Usage: enter-oem-once.sh arm --yes' >&2;exit 2; }
kit=$(CDPATH= cd -- "$(dirname "$0")" && pwd -P)
. /lib/functions/system.sh
CAMBIUM_AB_MODULES=$kit/modules
CAMBIUM_AB_LIB=$kit/shared/cambium-ab.sh
. "$CAMBIUM_AB_LIB"
. "$kit/shared/cambium-ab-upgrade.sh"
prove_source() {
 ab_identity && [ "$AB_FAMILY:$AB_MODEL:$AB_SKU" = miami:X7-35X:0000002c ] || return 1
 [ ! -e /proc/device-tree/cambium-platform/storage-policy ] &&
 [ -z "$(ab_getenv miami_ab_version)" ] || return 1
 grep -q "TIP-devel-b6d1a26f'" /etc/openwrt_release || return 1
 ab_miami_storage_context && ab_miami_upgrade_geometry &&
 ab_miami_certificate_mount && ab_miami_readiness_identity && ab_miami_native_connected || return 1
 prior=$(ab_miami_slot_command "$AB_ACTIVE" legacy)
 [ "$(ab_getenv miami_persistent_restore)" = 'setenv bootcount 0 && setenv bootcmd bootipq && setenv changing_bootcmd && saveenv' ] &&
 [ "$(ab_getenv miami_persistent_slot)" = "$AB_ACTIVE" ] &&
 [ "$(ab_getenv miami_persistent_load)" = "$prior; reset" ] || return 1
 case "$(ab_getenv bootcmd):$(ab_getenv image)" in
 "run miami_persistent_restore && run miami_persistent_load || bootipq:$AB_TARGET") ;;
 "run miami_boot$AB_ACTIVE:$AB_ACTIVE") [ "$(ab_getenv miami_boot$AB_ACTIVE)" = "$prior" ] || return 1;;
 *) return 1;;
 esac
 [ "$(ab_getenv changing_bootcmd)" = 1 ] || return 1
 case "$AB_ACTIVE" in
 0) kernel_sha=9c22c101aad1325ca0e1cfac9c52a3d84b3c3a5bfc46a99667dc491c3765712b;;
 1) kernel_sha=dcf685056218b88a8685ea2c60c8cc0fceef5a39dcc168691541f9fb90e4a255;;
 esac
 volume=$(ab_ubi_volume "$AB_ACTIVE_UBI" kernel)
 actual=$(head -c 4855880 "/dev/$volume" | sha256sum)
 [ "${actual%% *}" = "$kernel_sha" ] || return 1
 volume=$(ab_ubi_volume "$AB_ACTIVE_UBI" rootfs)
 actual=$(head -c 22502074 "/dev/$volume" | sha256sum)
 [ "${actual%% *}" = 1ecd75a5487c1a014d05adce627bf746b163df7b3f275deff258c77d9564dae9 ]
}
[ -z "$(ab_getenv miami_oem_once_state)" ] || { echo 'Existing OEM-entry attempt must be inspected first' >&2;exit 1; }
prove_source || exit 1
# Cancel OEM's pending bank switch without changing the verified selector.
selector=$(ab_getenv image) || exit 1
ab_setenv bootcount 0
counter=$(ab_getenv bootcount) || exit 1
current=$(ab_getenv image) || exit 1
[ "$counter" = 0 ] && [ "$current" = "$selector" ] || exit 1
# Durable working source first. The later one-shot prefix saves this again.
ab_setenv "miami_boot$AB_ACTIVE" "$prior"
ab_setenv bootcmd "run miami_boot$AB_ACTIVE"
ab_setenv image "$AB_ACTIVE"
sync
[ "$(ab_getenv bootcmd)" = "run miami_boot$AB_ACTIVE" ] &&
[ "$(ab_getenv image)" = "$AB_ACTIVE" ] || exit 1
batch=$(mktemp /tmp/miami-oem-once.XXXXXX)
trap 'rm -f "$batch"' EXIT
printf 'miami_oem_once_source %s\nmiami_oem_once_target %s\nmiami_oem_once_state prepared\nmiami_oem_once_source_release b6d1a26f\n' "$AB_ACTIVE" "$AB_TARGET" > "$batch"
ab_setenv_batch "$batch"
once="if setenv bootcount 0 && setenv bootcmd run miami_boot$AB_ACTIVE && setenv image $AB_ACTIVE && setenv miami_oem_once_state started && saveenv; then setenv image $AB_TARGET && setenv bootcount 0 && bootipq; run miami_boot$AB_ACTIVE; fi"
# Repeat source/pair/geometry/identity just before the last arming write.
prove_source || exit 1
ab_setenv bootcmd "$once"
[ "$(ab_getenv bootcmd)" = "$once" ] || exit 1
sync
echo 'One retained-OEM boot armed; working OpenWiFi is saved first as the fallback. No reboot or firmware write performed.'
