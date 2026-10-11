#!/bin/sh
# OEM Sage transaction orchestration. Loaded by an authenticated source runner,
# not an admission authority or independently deployable production installer.
# The sealed runner supplies cos_admit, cos_authenticate, cos_source_check,
# cos_refuse_pending, cos_recovery, cos_boot_preflight and cos_arm callbacks.
# They must be reviewed together with this library and both sibling libraries.
# cos_admit establishes trusted OW_EXPECT_* and CSP_FS_MTD; source check verifies
# live factory identity/source bank; recovery preserves this AP's unique data.
# Boot preflight is read-only and MUST refuse an unqualified boot adapter.
# cos_arm alone publishes pending metadata and the recoverable one-shot selector,
# using a reviewed environment transaction, readback and persistent OEM fallback.
# No callback may enroll, generate keys/CSR or silently reformat a pending job.

# The incoming existing 75_certificates preinit producer allocates the shared
# 20-LEB volume without deleting/resizing another volume. A fresh factory OEM
# migration admits only an absent store; an existing store needs a separately
# qualified identity-preserving lifecycle, never automatic clearing.
cos_certificate_capacity() {
    local node free current
    for node in "${CSP_SYS:-/sys/class/ubi}/ubi0_"*/name; do
        [ -r "$node" ] || continue
        [ "$(cat "$node")" != certificates ] || return 1
    done
    free=$(csp_read ubi0 avail_eraseblocks) || return 1
    csp_number "$free" && [ "$free" -le 1024 ] || return 1
    if [ "$1" = before ]; then
        current=$(csp_read ubi0_$CSP_ROOT_ID reserved_ebs) || return 1
        csp_number "$current" || return 1
        [ "$((free + current + CSP_OVERLAY_LEBS))" -ge 372 ]
    else
        [ "$free" -ge 20 ]
    fi
}
cos_fail() { echo 'OEM Sage transaction refused.' >&2; return 1; }
cos_install() (
    local image=$1 kernel=$2 root=$3 settings=$4 mountpoint= volume= node count=0
    [ "$#" = 4 ] || exit 2
    # Callbacks come from the authenticated runner, never from staged settings.
    for node in cos_admit cos_authenticate cos_source_check cos_refuse_pending cos_recovery cos_boot_preflight cos_arm; do
        command -v "$node" >/dev/null 2>&1 || exit 1
    done
    cos_admit "$image" || exit 1
    [ "${OW_EXPECT_FAMILY:-}" = sage ] &&
    [ "${OW_EXPECT_OPERATION:-}" = production-oem-migration ] || exit 1
    case "${OW_EXPECT_MODEL:-}" in E410|E410B) ;; *) exit 1 ;; esac
    case "${OW_EXPECT_SOURCE:-}:${OW_EXPECT_TARGET:-}" in 0:1|1:0) ;; *) exit 1 ;; esac
    # All qualification/authentication/source/tool/boot checks precede backup,
    # directory creation or destructive inactive-bank work.
    cos_authenticate "$image" "$kernel" "$root" || exit 1
    cos_source_check && cos_refuse_pending && cos_boot_preflight || exit 1
    OW_STAGE_ADMISSION=qualified
    ow_settings_tree "$settings" && ow_settings_context "$image" || exit 1
    CSP_ACTIVE=$OW_EXPECT_SOURCE
    CSP_WRITE_ADMISSION=qualified
    CSP_ROOT_RESIZE_MODE=recreate
    csp_payload_check "$kernel" "$root" 285 squashfs || exit 1
    [ "$CSP_TARGET" = "$OW_EXPECT_TARGET" ] && cos_certificate_capacity before || exit 1
    for node in mount umount rmdir mktemp sync ubirmvol ubimkvol ubiupdatevol; do
        command -v "$node" >/dev/null 2>&1 || exit 1
    done
    cos_recovery || exit 1
    # Recheck mutable source/pending state immediately before the writer. A
    # qualified runner must hold exclusive execution for the full transaction.
    cos_source_check && cos_refuse_pending || exit 1
    csp_stage_pair "$kernel" "$root" 285 squashfs || exit 1
    # Keep the already reviewed incoming preinit producer's 20-LEB capacity.
    cos_certificate_capacity after || exit 1
    # Independent final readback is required before settings publication.
    csp_readback "$kernel" "${CSP_DEV:-/dev}/ubi0_$((2 * OW_EXPECT_TARGET))" &&
    csp_readback "$root" "${CSP_DEV:-/dev}/ubi0_$((2 * OW_EXPECT_TARGET + 1))" || exit 1
    for node in "${CSP_SYS:-/sys/class/ubi}/ubi0_"*; do
        [ -r "$node/name" ] || continue
        [ "$(cat "$node/name")" = "rootfs_data$OW_EXPECT_TARGET" ] || continue
        volume=${node##*/}; count=$((count + 1))
    done
    [ "$count" = 1 ] || exit 1
    OW_EXPECT_TARGET_VOLUME=$volume
    OW_EXPECT_TARGET_MTD=$CSP_FS_MTD
    umask 077
    mountpoint=$(mktemp -d /tmp/cambium-oem-settings.XXXXXX) || exit 1
    trap '[ -z "$mountpoint" ] || { umount "$mountpoint" 2>/dev/null; rmdir "$mountpoint" 2>/dev/null; }' EXIT
    trap 'exit 1' HUP INT TERM
    mount -t ubifs "${CSP_DEV:-/dev}/$volume" "$mountpoint" || exit 1
    ow_settings_stage_overlay "$settings" "$image" "$mountpoint" && sync || exit 1
    umount "$mountpoint" && rmdir "$mountpoint" || exit 1
    mountpoint=
    # No selector or pending transaction is written until both payload and
    # settings are durable, read back, and the target overlay is unmounted.
    cos_source_check && cos_refuse_pending && cos_boot_preflight || exit 1
    cos_arm "$image" || exit 1
    printf 'candidate_staged=%s\nreboot_required=yes\n' "$OW_EXPECT_TARGET"
)
