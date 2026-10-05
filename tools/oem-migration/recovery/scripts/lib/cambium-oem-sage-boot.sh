#!/bin/sh
# Native Sage A/B boot contract for a qualified OEM source runner. No stock
# loader, no trial-mode admission escape, and no automatic reboot.
# Trusted source qualification supplies COS_ENV_CONFIG, COS_OEM_BOOT_COMMAND,
# COS_BOOT_QUALIFIED and COS_TARGET_FIT after matching the actual signed FIT.
# COS_OEM_BOOT_COMMAND must be the reviewed original source-bank command,
# including source image selection. Never render an OpenWiFi command for OEM.
cos_boot_preflight() {
    [ "${COS_BOOT_QUALIFIED:-}" = qualified ] || return 1
    [ -r "${COS_ENV_CONFIG:-}" ] && [ ! -L "$COS_ENV_CONFIG" ] || return 1
    case "$OW_EXPECT_MODEL:${COS_TARGET_FIT:-}" in
        E410:config@5|E410B:config@17) ;; *) return 1 ;;
    esac
    case "$OW_EXPECT_SOURCE:$OW_EXPECT_TARGET" in 0:1|1:0) ;; *) return 1 ;; esac
    [ -n "${COS_OEM_BOOT_COMMAND:-}" ] || return 1
    # The source capability contract owns this exact command. Require the
    # original command's source bank selection, not a user-provided script.
    [ "$COS_OEM_BOOT_COMMAND" = "setenv image $OW_EXPECT_SOURCE; bootipq" ] || return 1
    for COS_CHECK_TOOL in fw_printenv fw_setenv mktemp chmod rm rmdir sync; do
        command -v "$COS_CHECK_TOOL" >/dev/null 2>&1 || return 1
    done
    [ "$(fw_printenv -c "$COS_ENV_CONFIG" -n image 2>/dev/null)" = "$OW_EXPECT_SOURCE" ] || return 1
    [ "$(fw_printenv -c "$COS_ENV_CONFIG" -n bootcmd 2>/dev/null)" = bootipq ] || return 1
}
cos_native_target_command() {
    local slot=$OW_EXPECT_TARGET id=$((2 * OW_EXPECT_TARGET + 1))
    printf '%s\n' "setenv image $slot; setenv bootargs mtdparts=spi0.1:128M(fs) ubi.mtd=fs ubi.block=0,rootfs$slot root=/dev/ubiblock0_$id rootfstype=squashfs ro rootwait fstools_overlay_name=rootfs_data$slot cambium_sage_slot=$slot clk_ignore_unused; nand device 1 && setenv mtdids nand1=nand1 && setenv mtdparts mtdparts=nand1:0x8000000@0x0(fs) && ubi part fs && ubi read 0x84000000 linux$slot && bootm 0x84000000#$COS_TARGET_FIT"
}
cos_arm() (
    local image=$1 work target trial key value
    cos_boot_preflight && ow_settings_context "$image" || exit 1
    target=$(cos_native_target_command) || exit 1
    trial="setenv bootcmd run sage_stable$OW_EXPECT_SOURCE; setenv image $OW_EXPECT_SOURCE; setenv sage_ab_state trial-started; saveenv; run sage_boot$OW_EXPECT_TARGET; run sage_boot$OW_EXPECT_SOURCE"
    umask 077
    work=$(mktemp -d /tmp/cambium-oem-arm.XXXXXX) || exit 1
    trap 'rm -f "$work/environment"; rmdir "$work"' EXIT
    # Metadata/boot definitions first; original bootcmd remains bootipq until
    # the last write. Incoming guard sees the existing native acceptance state.
    {
        printf 'sage_boot%s %s\n' "$OW_EXPECT_SOURCE" "$COS_OEM_BOOT_COMMAND"
        printf 'sage_boot%s %s\n' "$OW_EXPECT_TARGET" "$target"
        printf 'sage_stable%s run sage_boot%s; run sage_boot%s\n' "$OW_EXPECT_SOURCE" "$OW_EXPECT_SOURCE" "$OW_EXPECT_TARGET"
        printf 'sage_stable%s run sage_boot%s; run sage_boot%s\n' "$OW_EXPECT_TARGET" "$OW_EXPECT_TARGET" "$OW_EXPECT_SOURCE"
        printf 'sage_ab_version 1\n'
        printf 'sage_ab_confirmed %s\nsage_ab_target %s\nsage_ab_state armed\n' "$OW_EXPECT_SOURCE" "$OW_EXPECT_TARGET"
        printf 'sage_installer_target %s\nsage_installer_job %s\nsage_installer_image %s\n' "$OW_EXPECT_TARGET" "$OW_EXPECT_JOB" "$OW_IMAGE"
    } > "$work/environment" || exit 1
    chmod 600 "$work/environment" || exit 1
    fw_setenv -c "$COS_ENV_CONFIG" -s "$work/environment" && sync || exit 1
    while read -r key value; do
        [ "$(fw_printenv -c "$COS_ENV_CONFIG" -n "$key" 2>/dev/null)" = "$value" ] || exit 1
    done < "$work/environment"
    # Never activate after a failed metadata readback. The first candidate boot
    # durably restores the source fallback before loading the candidate kernel.
    fw_setenv -c "$COS_ENV_CONFIG" bootcmd "$trial" && sync || exit 1
    [ "$(fw_printenv -c "$COS_ENV_CONFIG" -n bootcmd 2>/dev/null)" = "$trial" ] || exit 1
)
