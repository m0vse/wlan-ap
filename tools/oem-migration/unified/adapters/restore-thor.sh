#!/bin/sh
# Test-return writer: retain the running OpenWiFi bank and both identity
# children. No whole-bank format, factory reset or OEM confirmation here.
oem_restore_thor_load() {
    local thor_member
    thor_member=$(oem_bundle_member adapters/thor.sh) || return 1
    . "$thor_member" || return 1
    thor_member=$(oem_bundle_member runtime/cambium-ab.sh) || return 1
    CAMBIUM_AB_MODULES=$OEM_WORK/no-autoload-modules
    . "$thor_member" || return 1
    thor_member=$(oem_bundle_member runtime/cambium-ab-thor.sh) || return 1
    . "$thor_member" || return 1
}

oem_restore_inspect() {
    local thor_release thor_art thor_node thor_env thor_line
    OEM_SERIAL= OEM_SOURCE_RELEASE= OEM_SOURCE_SLOT= OEM_TARGET_SLOT=
    [ "${OEM_FAMILY:-}:${OEM_MODEL:-}:${OEM_SKU:-}" = thor:XV3-8:00000013 ] || return 1
    oem_restore_thor_load || return 1
    thor_release=$(awk -F= '$1=="DISTRIB_TIP_VERSION" {v=$2;gsub(/^\047|\047$/,"",v);n++}END{if(n!=1 || v!~/^[A-Za-z0-9._~-]+$/)exit 1;print v}' "${OEM_SYS_ROOT:-}/etc/openwrt_release") || return 1
    [ "$thor_release" = thor-2026.10.05.8 ] && [ "$OEM_SUPPORTED_RELEASE" = "$thor_release" ] || return 1
    AB_PROC_MTD=${OEM_SYS_ROOT:-}/proc/mtd AB_CMDLINE=${OEM_SYS_ROOT:-}/proc/cmdline AB_DT=${OEM_SYS_ROOT:-}/proc/device-tree
    AB_UBI_SYS=${OEM_SYS_ROOT:-}/sys/class/ubi AB_MTD_SYS=${OEM_SYS_ROOT:-}/sys/class/mtd AB_DEV=${OEM_SYS_ROOT:-}/dev
    board_name() { printf 'cambiumnetworks,xv3-8\n'; }
    ab_identity && ab_converted || return 1
    tr '\000' '\n' < "$AB_DT/compatible" | grep -x 'cambiumnetworks,xv3-8' >/dev/null || return 1
    OEM_SOURCE_SLOT=$AB_ACTIVE OEM_TARGET_SLOT=$AB_TARGET OEM_SOURCE_MTD=$AB_ACTIVE_MTD OEM_TARGET_MTD=$AB_TARGET_MTD
    OEM_SOURCE_RELEASE=$thor_release
    thor_art=$(oem_physical_index "$AB_MTD_SYS" 0:ART) || return 1
    thor_node=$(oem_thor_art_node "$thor_art") || return 1
    OEM_SERIAL=$(od -An -v -tx1 -j64 -N6 "$thor_node" | tr -d ' \n') || return 1
    thor_env=$(oem_physical_index "$AB_MTD_SYS" 0:APPSBLENV) || return 1
    THOR_ENV_CONFIG=${OEM_SYS_ROOT:-}/tmp/cambium-ab-fw_env.config
    [ -f "$THOR_ENV_CONFIG" ] && [ ! -L "$THOR_ENV_CONFIG" ] || return 1
    thor_line=$(awk '!/^#/ && NF {print}' "$THOR_ENV_CONFIG") || return 1
    case "$thor_line" in "/dev/mtd$thor_env 0x0 0x10000 0x10000 1"|"/dev/mtd$thor_env 0x0 0x00010000 0x00010000 1") ;; *) return 1 ;; esac
    AB_ENV_CONFIG=$THOR_ENV_CONFIG
    oem_context_check
}

oem_restore_thor_payloads() {
    THOR_OEM_KERNEL=$(oem_bundle_member payloads/XV3-8/oem/kernel.bin) &&
        THOR_OEM_ROOT=$(oem_bundle_member payloads/XV3-8/oem/rootfs.bin) || return 1
    [ "$(wc -c < "$THOR_OEM_KERNEL")" -eq 3905000 ] &&
        [ "$(oem_sha "$THOR_OEM_KERNEL")" = 9650712dc69a82342ebe2dee753110805dd6154024f305db80ae91d1165a93aa ] &&
        [ "$(wc -c < "$THOR_OEM_ROOT")" -eq 40233806 ] &&
        [ "$(oem_sha "$THOR_OEM_ROOT")" = 75bc545a6cad4fb66642798194318be02a32cf21cd4cd07caf08a75da48a3214 ]
}

oem_restore_boot_preflight() {
    local thor_stored thor_expected
    oem_thor_environment > "$OEM_WORK/thor-restore-env-check" || return 1
    [ "$(ab_getenv changing_bootcmd)" = 1 ] &&
        [ "$(ab_getenv thor_ab_confirmed)" = "$OEM_SOURCE_SLOT" ] &&
        [ "$(ab_getenv thor_ab_state)" = confirmed ] || return 1
    case "$(ab_getenv bootcmd)" in "run thor_stable$OEM_SOURCE_SLOT"|"run thor_boot$OEM_SOURCE_SLOT") ;; *) return 1 ;; esac
    thor_expected=$(ab_thor_boot_command "$OEM_SOURCE_SLOT") || return 1
    thor_stored=$(ab_getenv "thor_boot$OEM_SOURCE_SLOT") || return 1
    case "$thor_expected" in 'aq_load_fw; '*) thor_expected="aq_load_fw && ${thor_expected#aq_load_fw; }" ;; esac
    [ "$thor_stored" = "$thor_expected" ] || [ "$thor_stored" = "aq_load_fw; ${thor_expected#aq_load_fw && }" ] || return 1
    awk -F= '$1~/^thor_installer_/ || $1~/^thor_restore_/ {if(length(substr($0,index($0,"=")+1)))bad=1}END{exit bad}' "$OEM_WORK/thor-restore-env-check" || return 1
    OEM_BOOT_PRIOR_SLOT=$OEM_SOURCE_SLOT OEM_BOOT_TARGET_SLOT=$OEM_TARGET_SLOT
    OEM_BOOT_MODE=persist-prior-before-load OEM_BOOT_WATCHDOG=manual-reset
}

oem_restore_preflight() {
    local thor_profile thor_name thor_id thor_file thor_n thor_tool thor_ubi
    oem_restore_thor_payloads && oem_restore_boot_preflight || return 1
    thor_profile=$(oem_bundle_member "profiles/XV3-8/mtd-openwifi-slot$OEM_TARGET_SLOT.tsv") || return 1
    OEM_PROTECTED_RANGES=$OEM_WORK/thor-restore-ranges.tsv OEM_WRITE_PLAN=$OEM_WORK/thor-restore-plan.tsv
    oem_physical_inventory "$thor_profile" "${OEM_SYS_ROOT:-}/sys/class/mtd" "$OEM_PROTECTED_RANGES" || return 1
    thor_n=0; OEM_TARGET_UBI=
    for thor_file in "$AB_UBI_SYS"/ubi[0-9]*/mtd_num; do
        [ -r "$thor_file" ] || continue
        if [ "$(cat "$thor_file")" = "$OEM_TARGET_MTD" ]; then
            thor_ubi=${thor_file%/mtd_num}; OEM_TARGET_UBI=${thor_ubi##*/}; thor_n=$((thor_n+1))
        fi
    done
    [ "$thor_n" -le 1 ] || return 1
    if [ "$thor_n" = 1 ]; then
    oem_bank_idle_check "$AB_UBI_SYS" "$AB_DEV" "${OEM_SYS_ROOT:-}/proc" "$OEM_TARGET_MTD" "$OEM_TARGET_UBI" no || return 1
    # Only the original five native children; private certificate/vault bytes
    # are preserved in place, never captured to the critical HTTP relay.
    [ "$(ls "$AB_UBI_SYS/${OEM_TARGET_UBI}_"*/name | wc -l)" -eq 5 ] || return 1
    for thor_id in 0 1 2 3 4; do
        case "$thor_id" in 0) thor_name=kernel ;; 1) thor_name=rootfs ;; 2) thor_name=rootfs_data ;; 3) thor_name=cambium_device_data ;; 4) thor_name=certificates ;; esac
        oem_ubi_child_check "$AB_UBI_SYS" "$OEM_TARGET_MTD" "$OEM_TARGET_UBI" "$thor_id" "$thor_name" || return 1
        oem_thor_target_node "$thor_id" >/dev/null || return 1
    done
    [ "$(cat "$AB_UBI_SYS/${OEM_TARGET_UBI}_0/reserved_ebs")" -ge 31 ] &&
        [ "$(cat "$AB_UBI_SYS/${OEM_TARGET_UBI}_3/reserved_ebs")" -eq 8 ] &&
        [ "$(cat "$AB_UBI_SYS/${OEM_TARGET_UBI}_4/reserved_ebs")" -eq 20 ] || return 1
    # Removing only inactive firmware overlay releases space without shrinking
    # a formatted UBIFS filesystem or touching either identity child.
    [ $(( $(cat "$AB_UBI_SYS/${OEM_TARGET_UBI}_0/reserved_ebs") + 317 + 8 + 20 )) -le 724 ] || return 1
    fi
    {
        printf 'ubi-update\t%s\t0\tkernel\nubi-update\t%s\t1\tubi_rootfs\nubi-resize\t%s\t1\tubi_rootfs\nubi-remove\t%s\t2\trootfs_data\n' "$OEM_TARGET_MTD" "$OEM_TARGET_MTD" "$OEM_TARGET_MTD" "$OEM_TARGET_MTD"
        printf 'environment-fields\t%s\tfields\tpreserve-unlisted\n' "$(oem_physical_index "$AB_MTD_SYS" 0:APPSBLENV)"
    } > "$OEM_WRITE_PLAN" || return 1
    oem_write_boundary "$OEM_PROTECTED_RANGES" "$OEM_WRITE_PLAN" || return 1
    for thor_tool in ubiattach ubiupdatevol ubirmvol ubirsvol ubirename fw_printenv fw_setenv sync cmp head; do command -v "$thor_tool" >/dev/null 2>&1 || return 1; done
}

oem_restore_recovery() { oem_adapter_recovery; }

oem_restore_thor_boundary() {
    local thor_profile
    thor_profile=$(oem_bundle_member "profiles/XV3-8/mtd-openwifi-slot$OEM_TARGET_SLOT.tsv") || return 1
    oem_physical_inventory "$thor_profile" "$AB_MTD_SYS" "$OEM_PROTECTED_RANGES" &&
        oem_write_boundary "$OEM_PROTECTED_RANGES" "$OEM_WRITE_PLAN" &&
        oem_bank_idle_check "$AB_UBI_SYS" "$AB_DEV" "${OEM_SYS_ROOT:-}/proc" "$OEM_TARGET_MTD" "$OEM_TARGET_UBI" no &&
        oem_thor_critical_check || return 1
    if [ -f "$OEM_WORK/thor-restore-identities-before" ]; then
        oem_restore_thor_identity_snapshot > "$OEM_WORK/thor-restore-identities-after" &&
            cmp -s "$OEM_WORK/thor-restore-identities-before" "$OEM_WORK/thor-restore-identities-after"
    fi
}

oem_restore_thor_identity_snapshot() {
    local thor_id thor_name thor_node thor_hash
    for thor_id in 3 4; do
        case "$thor_id" in 3) thor_name=cambium_device_data ;; 4) thor_name=certificates ;; esac
        oem_ubi_child_check "$AB_UBI_SYS" "$OEM_TARGET_MTD" "$OEM_TARGET_UBI" "$thor_id" "$thor_name" || return 1
        thor_node=$(oem_thor_target_node "$thor_id") && thor_hash=$(oem_sha "$thor_node") || return 1
        printf '%s\t%s\t%s\n' "$thor_id" "$(cat "$AB_UBI_SYS/${OEM_TARGET_UBI}_$thor_id/reserved_ebs")" "$thor_hash" || return 1
    done
}

oem_restore_migrate() (
    local thor_node thor_bytes thor_sha thor_batch thor_prior thor_trial
    umask 077
    oem_restore_inspect && oem_restore_preflight || exit 1
    oem_thor_environment > "$OEM_WORK/thor-env-before" || exit 1
    printf '%s\n' bootcmd image thor_restore_prior thor_restore_oem thor_restore_state thor_restore_target > "$OEM_WORK/thor-env-allowed" || exit 1
    oem_thor_critical_check || exit 1
    # Read back the working source default before changing the inactive bank.
    printf 'bootcmd run thor_boot%s\nimage %s\n' "$OEM_SOURCE_SLOT" "$OEM_SOURCE_SLOT" > "$OEM_WORK/thor-restore-source.tsv" || exit 1
    oem_thor_environment_batch "$OEM_WORK/thor-restore-source.tsv" || exit 1
    oem_thor_target_attachment after-source-save && oem_restore_preflight || exit 1
    oem_restore_thor_identity_snapshot > "$OEM_WORK/thor-restore-identities-before" || exit 1
    oem_restore_thor_boundary && oem_ubi_child_check "$AB_UBI_SYS" "$OEM_TARGET_MTD" "$OEM_TARGET_UBI" 2 rootfs_data || exit 1
    ubirmvol "$AB_DEV/$OEM_TARGET_UBI" -n 2 || exit 1
    [ ! -e "$AB_UBI_SYS/${OEM_TARGET_UBI}_2" ] || exit 1
    oem_restore_thor_boundary && oem_ubi_child_check "$AB_UBI_SYS" "$OEM_TARGET_MTD" "$OEM_TARGET_UBI" 1 rootfs || exit 1
    # Exact ID/name transition; no global rename or whole-bank format.
    ubirename "$AB_DEV/$OEM_TARGET_UBI" rootfs ubi_rootfs || exit 1
    oem_restore_thor_boundary && oem_ubi_child_check "$AB_UBI_SYS" "$OEM_TARGET_MTD" "$OEM_TARGET_UBI" 1 ubi_rootfs || exit 1
    ubirsvol "$AB_DEV/$OEM_TARGET_UBI" -n 1 -s 40251392 || exit 1
    [ "$(cat "$AB_UBI_SYS/${OEM_TARGET_UBI}_1/reserved_ebs")" = 317 ] || exit 1
    for thor_node in 0 1; do
        oem_restore_thor_boundary || exit 1
        if [ "$thor_node" = 0 ]; then
            oem_ubi_child_check "$AB_UBI_SYS" "$OEM_TARGET_MTD" "$OEM_TARGET_UBI" 0 kernel || exit 1
            thor_bytes=3905000 thor_sha=9650712dc69a82342ebe2dee753110805dd6154024f305db80ae91d1165a93aa
            thor_batch=$THOR_OEM_KERNEL
        else
            oem_ubi_child_check "$AB_UBI_SYS" "$OEM_TARGET_MTD" "$OEM_TARGET_UBI" 1 ubi_rootfs || exit 1
            thor_bytes=40233806 thor_sha=75bc545a6cad4fb66642798194318be02a32cf21cd4cd07caf08a75da48a3214
            thor_batch=$THOR_OEM_ROOT
        fi
        thor_prior=$(oem_thor_target_node "$thor_node") || exit 1
        ubiupdatevol "$thor_prior" "$thor_batch" || exit 1
        [ "$(head -c "$thor_bytes" "$thor_prior" | sha256sum | awk '{print $1}')" = "$thor_sha" ] || exit 1
    done
    oem_restore_thor_boundary && oem_restore_boot_preflight || exit 1
    thor_prior=$(ab_getenv "thor_boot$OEM_SOURCE_SLOT") || exit 1
    thor_batch=$OEM_WORK/thor-restore-arm.tsv
    {
        printf 'thor_restore_prior %s\nthor_restore_oem setenv image %s && aq_load_fw && bootipq\n' "$thor_prior" "$OEM_TARGET_SLOT"
        printf 'thor_restore_state armed\nthor_restore_target %s\n' "$OEM_TARGET_SLOT"
    } > "$thor_batch" || exit 1
    oem_thor_environment_batch "$thor_batch" || exit 1
    thor_trial="setenv bootcmd run thor_restore_prior && setenv image $OEM_SOURCE_SLOT && setenv thor_restore_state trial-started && saveenv && run thor_restore_oem; run thor_restore_prior"
    printf 'bootcmd %s\n' "$thor_trial" > "$thor_batch" || exit 1
    if ! oem_thor_environment_batch "$thor_batch"; then
        printf 'bootcmd run thor_boot%s\nimage %s\n' "$OEM_SOURCE_SLOT" "$OEM_SOURCE_SLOT" > "$thor_batch"
        oem_thor_environment_batch "$thor_batch" || :
        exit 1
    fi
    printf 'handoff=one-shot-oem-armed\noem_boot=not-yet-verified\ndefaults_committed=no\n'
)
