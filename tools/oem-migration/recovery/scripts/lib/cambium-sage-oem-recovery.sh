#!/bin/sh
# Recoverable operator-led OEM activation using the existing native A/B design.
# Source boot command pin comes from the independently qualified source tuple,
# never from hashing a downloaded/observed command and approving it itself.
csr_boot_preflight() {
    local idx product boot
    [ "${CSR_RECOVERY_BOOT_QUALIFIED:-}" = qualified ] &&
    [ "${CSR_OEM_DEFAULTS_QUALIFIED:-}" = qualified ] && [ "${CSR_MODEL:-}" = E410 ] || return 1
    csr_digest "${CSR_SOURCE_BOOT_PIN:-}" || return 1
    idx=$(csr_mtd_index mfginfo) || return 1
    product=$(tr '\000' '\n' < "${CSR_DEV:-/dev}/mtd${idx}ro" | sed -n 's/.*\(PL-E410XXX[A-B]-[A-Z][A-Z]\).*/\1/p') || return 1
    [ "$product" = PL-E410XXXA-EU ] || return 1
    idx=$(csr_mtd_index '0:APPSBL') || return 1
    [ "$(csr_mtd_geometry '0:APPSBL')" = '00080000 00010000' ] &&
    csr_is_device "${CSR_DEV:-/dev}/mtd${idx}ro" &&
    [ "$(csr_hash "${CSR_DEV:-/dev}/mtd${idx}ro")" = 066bfcc317291b23e44bd42f1d10c4d08ca82ded6ca05abd15f5da280ae4dba1 ] || return 1
    case "${CSR_ACTIVE:-}" in 0|1) ;; *) return 1 ;; esac
    boot=$(fw_printenv -c "$CSR_ENV_CONFIG" -n "sage_boot$CSR_ACTIVE" 2>/dev/null) || return 1
    [ -n "$boot" ] &&
    [ "$(printf '%s' "$boot" | sha256sum | awk '{print $1}')" = "$CSR_SOURCE_BOOT_PIN" ] || return 1
    for boot in fw_setenv fw_printenv mktemp rmdir rm sync; do command -v "$boot" >/dev/null 2>&1 || return 1; done
}
csr_configuration_empty_check() {
    [ "$(csr_hash "${CSR_DEV:-/dev}/mtd${CSR_CONFIG_MTD}ro")" = 71189f7fb6aed638640078fba3a35fda6c39c8962e74dcc75935aac948da9063 ] &&
    [ "$(head -c "$CSR_NVRAM_BYTES" "${CSR_DEV:-/dev}/ubi0_4" | sha256sum | awk '{print $1}')" = "$CSR_EMPTY_NVRAM_SHA" ]
}
csr_arm_oem() (
    local work target trial key value
    CSR_ALLOW_CHANGED_ENV=0
    csr_preflight && csr_boot_preflight && csr_configuration_empty_check || exit 1
    target=$((1 - CSR_ACTIVE))
    trial="setenv bootcmd run sage_boot$CSR_ACTIVE && setenv image $CSR_ACTIVE && setenv sage_ab_state trial-started && saveenv && run sage_boot$target; run sage_boot$CSR_ACTIVE"
    umask 077
    work=$(mktemp -d /tmp/cambium-oem-recovery-arm.XXXXXX) || exit 1
    trap 'rm -f "$work/metadata"; rmdir "$work"' EXIT
    {
        # Keep the exact qualified native source boot command unchanged.
        printf 'sage_boot%s setenv image %s; bootipq\n' "$target" "$target"
        printf 'sage_stable%s run sage_boot%s\n' "$CSR_ACTIVE" "$CSR_ACTIVE"
        printf 'sage_stable%s run sage_boot%s; run sage_boot%s\n' "$target" "$target" "$CSR_ACTIVE"
        printf 'sage_ab_version 1\nsage_ab_confirmed %s\nsage_ab_target %s\nsage_ab_state armed\nsage_oem_fallback %s\n' "$CSR_ACTIVE" "$target" "$target"
    } > "$work/metadata" || exit 1
    fw_setenv -c "$CSR_ENV_CONFIG" -s "$work/metadata" && sync || exit 1
    while read -r key value; do
        [ "$(fw_printenv -c "$CSR_ENV_CONFIG" -n "$key" 2>/dev/null)" = "$value" ] || exit 1
    done < "$work/metadata"
    csr_boot_preflight || exit 1
    # Source boot remains the default until the last checked selector write.
    fw_setenv -c "$CSR_ENV_CONFIG" bootcmd "$trial" && sync || exit 1
    [ "$(fw_printenv -c "$CSR_ENV_CONFIG" -n bootcmd 2>/dev/null)" = "$trial" ] || exit 1
    printf 'oem_candidate_armed=%s\nreboot_required=yes\n' "$target"
)
csr_restore_oem() (
    # Source caller fixes live roots and holds exclusive execution. Both exact
    # reset and boot/defaults admission are checked before any candidate write.
    CSR_ALLOW_CHANGED_ENV=0
    csr_preflight payload-only && csr_boot_preflight || exit 1
    CSP_WRITE_ADMISSION=qualified
    CSP_ROOT_RESIZE_MODE=${CSR_ROOT_RESIZE_MODE:-resize}
    csp_stage_pair "$CSR_KERNEL" "$CSR_ROOT" 372 ubifs || exit 1
    csr_reset_shared && csr_arm_oem || exit 1
    # Host verifies actual OEM boot/reset/network/root access before separately
    # invoking csr_apply_oem_defaults. No automatic confirmation or reboot.
)
