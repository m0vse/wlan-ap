#!/bin/sh
# Thor integration pieces for the one shared installer. No standalone entrypoint.
# The owner still supplies exact-version inspection, complete physical profile,
# OEM-volume conversion, vault/FORMAT2 staging and the reviewed boot armer.
# These helpers neither admit a release nor erase, create, resize or arm a bank.

oem_thor_local_payload() {
    local thor_role=$1 thor_manifest thor_row thor_relative thor_bytes thor_digest thor_file
    case "$thor_role" in kernel|rootfs) ;; *) return 1 ;; esac
    thor_manifest=$(oem_bundle_member profiles/XV3-8/payloads.tsv) || return 1
    # Two exact role/file/byte-count/digest rows, all authenticated by the bundle.
    awk -F '\t' 'NF!=4 || $1!~/^(kernel|rootfs)$/ || seen[$1]++ ||
      $2!~/^payloads\/XV3-8\/(kernel|rootfs)\.bin$/ ||
      $2!="payloads/XV3-8/" $1 ".bin" || $3!~/^[1-9][0-9]*$/ ||
      $3>100663296 || length($4)!=64 || $4~/[^0-9a-f]/ {bad=1}
      END{exit bad || NR!=2}' "$thor_manifest" || return 1
    thor_row=$(awk -F '\t' -v role="$thor_role" '$1==role {print $2, $3, $4}' "$thor_manifest") || return 1
    read -r thor_relative thor_bytes thor_digest <<EOF
$thor_row
EOF
    thor_file=$(oem_bundle_member "$thor_relative") || return 1
    [ "$(wc -c < "$thor_file")" -eq "$thor_bytes" ] && [ "$(oem_sha "$thor_file")" = "$thor_digest" ] || return 1
    THOR_PAYLOAD_FILE=$thor_file
    THOR_PAYLOAD_BYTES=$thor_bytes
    THOR_PAYLOAD_SHA=$thor_digest
}

oem_thor_target_node() {
    local thor_node=${OEM_SYS_ROOT:-}/dev/${OEM_TARGET_UBI}_$1
    [ -c "$thor_node" ] && [ ! -L "$thor_node" ] || return 1
    printf '%s\n' "$thor_node"
}

oem_thor_update_existing_child() {
    local thor_role=$1 thor_child thor_plan thor_node thor_actual
    [ "${OEM_SKU:-}:${OEM_MODEL:-}" = 00000013:XV3-8 ] || return 1
    case "${OEM_SOURCE_SLOT:-}:${OEM_TARGET_SLOT:-}" in 0:1|1:0) ;; *) return 1 ;; esac
    case "${OEM_SOURCE_MTD:-}:${OEM_TARGET_MTD:-}" in *[!0-9:]*|:*) return 1 ;; esac
    [ -n "$OEM_SOURCE_MTD" ] && [ -n "$OEM_TARGET_MTD" ] &&
        [ "$OEM_SOURCE_MTD" != "$OEM_TARGET_MTD" ] || return 1
    case "${OEM_TARGET_UBI:-}" in ubi[0-9]*) ;; *) return 1 ;; esac
    case "${OEM_TARGET_UBI#ubi}" in ''|*[!0-9]*) return 1 ;; esac
    case "$thor_role" in kernel) thor_child=0 ;; rootfs) thor_child=1 ;; *) return 1 ;; esac
    # All input bytes are local and pinned before any child update. No fetch.
    oem_thor_local_payload kernel && oem_thor_local_payload rootfs &&
        oem_thor_local_payload "$thor_role" || return 1
    [ -d "$OEM_WORK" ] && [ ! -L "$OEM_WORK" ] || return 1
    thor_plan=$OEM_WORK/thor-child-plan.tsv
    printf 'ubi-update\t%s\t%s\t%s\n' "$OEM_TARGET_MTD" "$thor_child" "$thor_role" > "$thor_plan" || return 1
    oem_write_boundary "$OEM_PROTECTED_RANGES" "$thor_plan" || return 1
    oem_ubi_child_check "${OEM_SYS_ROOT:-}/sys/class/ubi" "$OEM_TARGET_MTD" "$OEM_TARGET_UBI" "$thor_child" "$thor_role" || return 1
    thor_node=$(oem_thor_target_node "$thor_child") || return 1
    printf '%s\t%s\n' "$thor_role" writing >> "$OEM_WORK/thor-child-journal.tsv" || return 1
    if ! ubiupdatevol "$thor_node" "$THOR_PAYLOAD_FILE"; then
        printf '%s\t%s\n' "$thor_role" write-failed >> "$OEM_WORK/thor-child-journal.tsv"
        return 1
    fi
    if ! oem_ubi_child_check "${OEM_SYS_ROOT:-}/sys/class/ubi" "$OEM_TARGET_MTD" "$OEM_TARGET_UBI" "$thor_child" "$thor_role"; then
        printf '%s\t%s\n' "$thor_role" metadata-failed >> "$OEM_WORK/thor-child-journal.tsv"
        return 1
    fi
    thor_actual=$(head -c "$THOR_PAYLOAD_BYTES" "$thor_node" | sha256sum | awk '{print $1}') || return 1
    if [ "$thor_actual" != "$THOR_PAYLOAD_SHA" ]; then
        printf '%s\t%s\n' "$thor_role" readback-failed >> "$OEM_WORK/thor-child-journal.tsv"
        return 1
    fi
    printf '%s\t%s\n' "$thor_role" verified >> "$OEM_WORK/thor-child-journal.tsv"
}
