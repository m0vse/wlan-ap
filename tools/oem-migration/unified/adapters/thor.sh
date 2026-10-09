#!/bin/sh
# Thor integration pieces for the one shared installer. No standalone entrypoint.
# Inspection reads actual source fields; the owner supplies the released exact
# version row, full physical profile, OEM-volume conversion, vault/FORMAT2
# staging and reviewed boot armer.
# These helpers neither admit a release nor erase, create, resize or arm a bank.

oem_thor_art_node() {
    local thor_art=$1 thor_path=${OEM_SYS_ROOT:-}/dev/mtd${1}ro
    [ -c "$thor_path" ] && [ ! -L "$thor_path" ] || return 1
    printf '%s\n' "$thor_path"
}

oem_adapter_inspect() {
    local thor_root=${OEM_SYS_ROOT:-} thor_source_name thor_source_mtd thor_target_mtd
    local thor_zero thor_one thor_ubi thor_count thor_node thor_art thor_art_file thor_serial
    local thor_config= thor_next thor_file thor_env thor_cmdline thor_env_config thor_release thor_slot thor_env_dump
    OEM_SERIAL= OEM_SOURCE_RELEASE= OEM_SOURCE_SLOT= OEM_TARGET_SLOT=
    OEM_SOURCE_MTD= OEM_TARGET_MTD= THOR_ACTIVE_UBI= THOR_ENV_CONFIG=
    [ "${OEM_SKU:-}:${OEM_MODEL:-}" = 00000013:XV3-8 ] || return 1
    [ ! -e "$thor_root/etc/openwrt_release" ] || return 1
    thor_release=$(oem_read_release "$thor_root/etc/version") || return 1
    thor_zero=$(oem_physical_index "$thor_root/sys/class/mtd" rootfs) &&
        thor_one=$(oem_physical_index "$thor_root/sys/class/mtd" rootfs_1) || return 1
    [ "$thor_zero" != "$thor_one" ] || return 1
    for thor_node in "$thor_zero" "$thor_one"; do
        [ "$(cat "$thor_root/sys/class/mtd/mtd$thor_node/type")" = nand ] &&
        [ "$(cat "$thor_root/sys/class/mtd/mtd$thor_node/size")" = 100663296 ] &&
        [ "$(cat "$thor_root/sys/class/mtd/mtd$thor_node/erasesize")" = 131072 ] &&
        [ "$(cat "$thor_root/sys/class/mtd/mtd$thor_node/writesize")" = 2048 ] || return 1
    done
    [ "$(cat "$thor_root/sys/class/mtd/mtd$thor_zero/offset")" = 0 ] &&
        [ "$(cat "$thor_root/sys/class/mtd/mtd$thor_one/offset")" = 100663296 ] || return 1
    thor_cmdline=$(cat "$thor_root/proc/cmdline") || return 1
    thor_source_name=$(printf '%s\n' "$thor_cmdline" | awk '{for(i=1;i<=NF;i++)if($i~/^ubi.mtd=/){n++;v=substr($i,9)}}END{if(n!=1)exit 1;print v}') || return 1
    case "$thor_source_name" in
    rootfs) thor_slot=0; thor_source_mtd=$thor_zero; thor_target_mtd=$thor_one ;;
    rootfs_1) thor_slot=1; thor_source_mtd=$thor_one; thor_target_mtd=$thor_zero ;;
    *) return 1 ;;
    esac
    thor_count=0; thor_ubi=
    for thor_file in "$thor_root"/sys/class/ubi/ubi[0-9]*/mtd_num; do
        [ -r "$thor_file" ] || continue
        if [ "$(cat "$thor_file")" = "$thor_source_mtd" ]; then
            thor_ubi=${thor_file%/mtd_num}; thor_ubi=${thor_ubi##*/}; thor_count=$((thor_count+1))
        fi
    done
    [ "$thor_count" = 1 ] || return 1
    [ "$(cat "$thor_root/sys/class/ubi/$thor_ubi/eraseblock_size")" = 126976 ] &&
        [ "$(cat "$thor_root/sys/class/ubi/$thor_ubi/min_io_size")" = 2048 ] || return 1
    oem_ubi_child_check "$thor_root/sys/class/ubi" "$thor_source_mtd" "$thor_ubi" 0 kernel &&
        oem_ubi_child_check "$thor_root/sys/class/ubi" "$thor_source_mtd" "$thor_ubi" 1 ubi_rootfs || return 1
    printf '%s\n' "$thor_cmdline" | awk -v ubi="$thor_ubi" '{for(i=1;i<=NF;i++)if($i~/^root=/){n++;v=substr($i,6)}}END{exit n!=1 || (v!="mtd:ubi_rootfs" && v!=ubi ":ubi_rootfs" && v!="/dev/ubiblock" substr(ubi,4) "_1")}' || return 1
    thor_env=$(oem_physical_index "$thor_root/sys/class/mtd" 0:APPSBLENV) || return 1
    [ "$(cat "$thor_root/sys/class/mtd/mtd$thor_env/type")" = nor ] &&
        [ "$(cat "$thor_root/sys/class/mtd/mtd$thor_env/size")" = 65536 ] || return 1
    for thor_file in "$thor_root/etc/fw_env.config" "$thor_root/tmp/fw_env.config"; do
        [ -r "$thor_file" ] || continue
        thor_next=$(awk '!/^#/ && NF{print}' "$thor_file") || return 1
        [ -z "$thor_config" ] || [ "$thor_config" = "$thor_next" ] || return 1
        thor_config=$thor_next; thor_env_config=$thor_file
    done
    [ -n "$thor_config" ] || return 1
    set -- $thor_config
    [ "$#" = 4 ] || [ "$#" = 5 ] || return 1
    [ "$1" = "/dev/mtd$thor_env" ] || return 1
    case "$2:$3:$4:${5:-1}" in 0x0:0x10000:0x10000:1|0x0:0x00010000:0x00010000:1) ;; *) return 1 ;; esac
    # Capture warnings with the whole ENV response: a bad-CRC fallback may
    # otherwise return apparently valid compiled image/bootcmd defaults.
    thor_env_dump=$(fw_printenv -c "$thor_env_config" 2>&1) || return 1
    printf '%s\n' "$thor_env_dump" | awk '
      {key=$0;sub(/=.*/,"",key);if(index($0,"=")==0 || key!~/^[A-Za-z0-9_]+$/ || seen[key]++)bad=1}
      END{exit bad || !seen["image"] || !seen["bootcmd"]}' || return 1
    [ "$(printf '%s\n' "$thor_env_dump" | sed -n 's/^image=//p')" = "$thor_slot" ] &&
        [ "$(printf '%s\n' "$thor_env_dump" | sed -n 's/^bootcmd=//p')" = 'aq_load_fw&&bootipq' ] || return 1
    thor_env_dump=
    thor_art=$(oem_physical_index "$thor_root/sys/class/mtd" 0:ART) || return 1
    [ "$(cat "$thor_root/sys/class/mtd/mtd$thor_art/type")" = nor ] &&
        [ "$(cat "$thor_root/sys/class/mtd/mtd$thor_art/size")" = 262144 ] || return 1
    thor_art_file=$(oem_thor_art_node "$thor_art") || return 1
    thor_serial=$(od -An -v -tx1 -j64 -N6 "$thor_art_file" | tr -d ' \n') || return 1
    case "$thor_serial" in ''|*[!0-9a-f]*|000000000000|ffffffffffff) return 1 ;; esac
    [ "${#thor_serial}" = 12 ] || return 1
    # Factory base MAC is at ART 0x40 on exact XV3-8; no radio-MAC inference.
    OEM_SERIAL=$thor_serial; OEM_SOURCE_RELEASE=$thor_release; OEM_SOURCE_SLOT=$thor_slot
    OEM_SOURCE_MTD=$thor_source_mtd; OEM_TARGET_MTD=$thor_target_mtd
    OEM_TARGET_SLOT=$((1-OEM_SOURCE_SLOT)); THOR_ACTIVE_UBI=$thor_ubi; THOR_ENV_CONFIG=$thor_env_config
}

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
