#!/bin/sh
# Thor integration pieces for the one shared installer. No standalone entrypoint.
# Exact release phases reuse the existing bank allocator, native FORMAT2
# producer/stager and shipped health consumer. Release assembly/publication is
# owned by the shared installer. No AP action or automatic reboot occurs here.

oem_thor_art_node() {
    local thor_art=$1 thor_path=${OEM_SYS_ROOT:-}/dev/mtd${1}ro
    [ -c "$thor_path" ] && [ ! -L "$thor_path" ] || return 1
    printf '%s\n' "$thor_path"
}

oem_thor_bank_offset() {
    local thor_node=${OEM_SYS_ROOT:-}/sys/class/mtd/mtd$1 thor_physical=
    # Older OEM kernels omit sysfs offsets. Reuse the shared unique live
    # kernel-range reader, never partition order or an assumed offset.
    if [ ! -r "$thor_node/offset" ]; then
        thor_physical=$(oem_mtd_domain "$thor_node") || return 1
    fi
    oem_mtd_offset "$thor_node" "$2" target "$thor_physical"
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
    [ "$(oem_thor_bank_offset "$thor_zero" rootfs)" = 0 ] &&
        [ "$(oem_thor_bank_offset "$thor_one" rootfs_1)" = 100663296 ] || return 1
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
    oem_thor_character_matches "$thor_node" "${OEM_SYS_ROOT:-}/sys/class/ubi/${OEM_TARGET_UBI}_$1/dev" || return 1
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

oem_thor_published_image_valid() {
    [ "$#" = 1 ] && [ -f "$1" ] && [ ! -L "$1" ] || return 1
    [ "$(wc -c < "$1")" -eq 29327664 ] &&
        [ "$(oem_sha "$1")" = ef1bbf0fcdc72252df64b3b6944462c7b01eca2d1973a0e1ef8daed00035aae9 ]
}

# Connect the existing immutable FORMAT2 stager to the exact inspected Thor
# context. Caller owns producer/admission, mount/unmount and the final armer.
# No enrollment key is accepted as a process argument or exported here.
oem_thor_stage_native_overlay() {
    local thor_input=$1 thor_image=$2 thor_mount=$3 thor_volume
    [ "${OEM_SKU:-}:${OEM_MODEL:-}" = 00000013:XV3-8 ] || return 1
    # Original reviewed OEM writer: source bank 1, incoming bank 0.
    [ "${OEM_SOURCE_SLOT:-}:${OEM_TARGET_SLOT:-}" = 1:0 ] || return 1
    [ "$OW_EXPECT_SERIAL" = "$OEM_SERIAL" ] &&
        [ "$OW_EXPECT_FAMILY:$OW_EXPECT_MODEL" = thor:XV3-8 ] &&
        [ "$OW_EXPECT_OPERATION" = production-oem-migration ] &&
        [ "$OW_EXPECT_RELEASE" = "$OEM_SOURCE_RELEASE" ] &&
        [ "$OW_EXPECT_SOURCE:$OW_EXPECT_TARGET" = "$OEM_SOURCE_SLOT:$OEM_TARGET_SLOT" ] &&
        [ "$OW_EXPECT_TARGET_MTD" = "$OEM_TARGET_MTD" ] || return 1
    thor_volume=${OEM_TARGET_UBI}_2
    [ "$OW_EXPECT_TARGET_VOLUME" = "$thor_volume" ] || return 1
    oem_thor_published_image_valid "$thor_image" || return 1
    command -v ow_settings_stage_overlay >/dev/null 2>&1 || return 1
    ow_settings_stage_overlay "$thor_input" "$thor_image" "$thor_mount"
}

oem_thor_mtd_target_node() {
    local thor_path=${OEM_SYS_ROOT:-}/dev/mtd$OEM_TARGET_MTD
    [ -c "$thor_path" ] && [ ! -L "$thor_path" ] || return 1
    oem_thor_character_matches "$thor_path" "${OEM_SYS_ROOT:-}/sys/class/mtd/mtd$OEM_TARGET_MTD/dev" || return 1
    printf '%s\n' "$thor_path"
}

oem_thor_character_matches() {
    local thor_expected thor_listing thor_actual
    thor_expected=$(cat "$2") || return 1
    case "$thor_expected" in ''|*[!0-9:]*|:*|*:) return 1 ;; esac
    thor_listing=$(LC_ALL=C ls -ldn "$1") || return 1
    thor_actual=$(printf '%s\n' "$thor_listing" | awk '
      NR==1 && $1~/^c/ && $5~/^[0-9]+,$/ && $6~/^[0-9]+$/ {sub(/,$/,"",$5);v=$5 ":" $6;good=1}
      END{if(NR!=1 || !good)exit 1;print v}') || return 1
    [ "$thor_actual" = "$thor_expected" ]
}

oem_thor_vault_assets_ready() {
    local thor_table thor_src thor_rel thor_bytes thor_sha thor_file
    thor_table=$(oem_bundle_member profiles/XV3-8/vault-assets.tsv) || return 1
    awk -F '\t' 'NF!=4 || seen[$1]++ || $1!~/^lib\/firmware\/(IPQ8074|AR9887)\/[A-Za-z0-9_.\/-]+$/ ||
      $1~/(^|\/)\.\.?(\/|$)/ || $1~/caldata|private|key\.pem/ ||
      $2!~/^payloads\/shared-radio\/[A-Za-z0-9_.-]+$/ ||
      $3!~/^[1-9][0-9]*$/ || $3>1048576 || length($4)!=64 || $4~/[^0-9a-f]/ {bad=1}
      END{exit bad || NR<1}' "$thor_table" || return 1
    while IFS="$(printf '\t')" read -r thor_src thor_rel thor_bytes thor_sha; do
        thor_file=$(oem_bundle_member "$thor_rel") || return 1
        [ "$(wc -c < "$thor_file")" -eq "$thor_bytes" ] && [ "$(oem_sha "$thor_file")" = "$thor_sha" ] || return 1
    done < "$thor_table"
}

# Whole-bank preparation reuses the existing current A/B allocator. It is not
# the final migration/arm phase: caller still writes/verifies parts and own
# vault, mounts/stages/verifies FORMAT2, unmounts and runs the reviewed armer.
oem_thor_prepare_native_layout() (
    local thor_image=$1 thor_core thor_writer thor_module thor_profile thor_map
    local thor_kernel_bytes thor_root_bytes thor_target_ubi thor_count thor_file thor_kind thor_label
    local thor_limit thor_reason thor_idx thor_before thor_command thor_device thor_rc
    umask 077
    oem_thor_published_image_valid "$thor_image" || exit 1
    # All executable inputs and image/radio objects must already be local.
    thor_core=$(oem_bundle_member runtime/cambium-ab.sh) &&
        thor_writer=$(oem_bundle_member runtime/cambium-ab-upgrade.sh) &&
        thor_module=$(oem_bundle_member runtime/cambium-ab-thor.sh) || exit 1
    oem_thor_local_payload kernel || exit 1
    [ "$THOR_PAYLOAD_BYTES:$THOR_PAYLOAD_SHA" = '14125888:c04f44290a710c169c47886f3a870f630a74a8c3b6e0c203a0e93ccc7411b2c1' ] || exit 1
    thor_kernel_bytes=$THOR_PAYLOAD_BYTES
    oem_thor_local_payload rootfs || exit 1
    [ "$THOR_PAYLOAD_BYTES:$THOR_PAYLOAD_SHA" = '15195136:670029e07e61e956c9b5788ca8fae36f7e05511fbf1f55183d32ecad528e17a3' ] || exit 1
    thor_root_bytes=$THOR_PAYLOAD_BYTES
    # Owner's exact model/revision radio map is staged before preparation.
    oem_thor_vault_assets_ready || exit 1
    thor_profile=$(oem_bundle_member profiles/XV3-8/mtd-slot0.tsv) || exit 1
    oem_adapter_inspect && oem_context_check || exit 1
    [ "$OEM_SOURCE_RELEASE:$OEM_SOURCE_SLOT:$OEM_TARGET_SLOT" = 7.2-r1:1:0 ] || exit 1
    [ -d "$OEM_WORK" ] && [ ! -L "$OEM_WORK" ] || exit 1
    thor_map=$OEM_WORK/thor-format-physical.tsv
    oem_physical_inventory "$thor_profile" "${OEM_SYS_ROOT:-}/sys/class/mtd" "$thor_map" || exit 1
    awk -F '\t' -v src="$OEM_SOURCE_MTD" -v dst="$OEM_TARGET_MTD" '
      $1==src {s++;if($2!=100663296 || $3!=100663296 || $4!="active-oem" || $5!="nand0")bad=1}
      $1==dst {d++;if($2!=0 || $3!=100663296 || $4!="target" || $5!="nand0")bad=1}
      END{exit bad || s!=1 || d!=1}' "$thor_map" || exit 1
    [ "$(cat "$OEM_WORK/critical/OFFDEVICE_VERIFIED")" = "$(oem_sha "$OEM_WORK/critical/SHA256SUMS")" ] || exit 1
    (cd "$OEM_WORK/critical" && sha256sum -c SHA256SUMS >/dev/null 2>&1) || exit 1
    # Source-only persistence may rewrite ENV encoding without changing its
    # unrelated fields. Use the full saved semantic snapshot in a transaction.
    if [ -f "$OEM_WORK/thor-env-before" ]; then oem_thor_critical_check || exit 1; fi
    # Unique metadata remains exact; a backup is never permission to overwrite it.
    while IFS="$(printf '\t')" read -r thor_kind thor_label thor_limit thor_reason; do
        [ "$thor_kind" != ENV ] || [ ! -f "$OEM_WORK/thor-env-before" ] || continue
        thor_idx=$(oem_physical_index "${OEM_SYS_ROOT:-}/sys/class/mtd" "$thor_label") || exit 1
        [ "$(oem_sha "$OEM_WORK/critical/$thor_kind.bin")" = "$(oem_sha "${OEM_SYS_ROOT:-}/dev/mtd${thor_idx}ro")" ] || exit 1
    done < "$(oem_bundle_member profiles/XV3-8/critical.tsv)"
    thor_target_ubi=; thor_count=0
    for thor_file in "${OEM_SYS_ROOT:-}"/sys/class/ubi/ubi[0-9]*/mtd_num; do
        [ -r "$thor_file" ] || continue
        if [ "$(cat "$thor_file")" = "$OEM_TARGET_MTD" ]; then
            thor_target_ubi=${thor_file%/mtd_num}; thor_target_ubi=${thor_target_ubi##*/}; thor_count=$((thor_count+1))
        fi
    done
    # Metadata attachment is authorized only after full local staging,
    # verified backup and durable source persistence. Inspect every volume
    # before any format; existing identity or unknown children refuse erase.
    if [ "$thor_count" = 0 ]; then
        [ -f "$OEM_WORK/thor-env-before" ] || exit 1
        oem_thor_target_attachment after-source-save || exit 1
        thor_target_ubi=$OEM_TARGET_UBI; thor_count=1
    fi
    [ "$thor_count" = 1 ] || exit 1
    oem_ubi_child_check "${OEM_SYS_ROOT:-}/sys/class/ubi" "$OEM_TARGET_MTD" "$thor_target_ubi" 0 kernel &&
        oem_ubi_child_check "${OEM_SYS_ROOT:-}/sys/class/ubi" "$OEM_TARGET_MTD" "$thor_target_ubi" 1 ubi_rootfs || exit 1
    thor_count=0
    for thor_file in "${OEM_SYS_ROOT:-}"/sys/class/ubi/"$thor_target_ubi"_*/name; do
        [ -r "$thor_file" ] || continue
        thor_count=$((thor_count+1))
    done
    [ "$thor_count" = 2 ] || exit 1
    oem_bank_idle_check "${OEM_SYS_ROOT:-}/sys/class/ubi" "${OEM_SYS_ROOT:-}/dev" "${OEM_SYS_ROOT:-}/proc" "$OEM_TARGET_MTD" "$thor_target_ubi" no || exit 1
    oem_thor_mtd_target_node >/dev/null || exit 1
    CAMBIUM_AB_LIB=$thor_core
    CAMBIUM_AB_MODULES=$OEM_WORK/no-autoload-modules
    CAMBIUM_AB_CERTIFICATE_LIB=${OEM_WORK}/absent-certificate-export-library
    . "$thor_core"; . "$thor_writer"; . "$thor_module"
    ab_thor_board cambiumnetworks,xv3-8 || exit 1
    AB_FAMILY=thor AB_ACTIVE=$OEM_SOURCE_SLOT AB_TARGET=$OEM_TARGET_SLOT
    AB_TARGET_MTD=$OEM_TARGET_MTD AB_ACTIVE_MTD=$OEM_SOURCE_MTD
    AB_DEV=${OEM_SYS_ROOT:-}/dev AB_UBI_SYS=${OEM_SYS_ROOT:-}/sys/class/ubi
    AB_MTD_SYS=${OEM_SYS_ROOT:-}/sys/class/mtd
    [ $(( $(ab_lebs "$thor_kernel_bytes") + $(ab_lebs "$thor_root_bytes") + 8 + 20 + 67 )) -le 724 ] || exit 1
    # Scoped wrapper: original allocator body is unchanged. Every persistent
    # operation is constrained to the same checked physical target and UBI.
    ab_step() {
        local thor_desc=$1 thor_cmd thor_ubi_now thor_n thor_p
        shift; thor_cmd=$1; shift
        oem_adapter_inspect && oem_context_check || return 1
        [ "$OEM_SOURCE_SLOT:$OEM_TARGET_SLOT:$OEM_SOURCE_MTD:$OEM_TARGET_MTD" = "$AB_ACTIVE:$AB_TARGET:$AB_ACTIVE_MTD:$AB_TARGET_MTD" ] || return 1
        oem_physical_inventory "$thor_profile" "${OEM_SYS_ROOT:-}/sys/class/mtd" "$thor_map" || return 1
        case "$thor_cmd" in
        ubidetach|ubiattach) [ "$#:$1:$2" = "2:-m:$AB_TARGET_MTD" ] || return 1 ;;
        ubiformat)
            [ "$#:$1:$2:$3" = "3:$AB_DEV/mtd$AB_TARGET_MTD:-y:-q" ] &&
                oem_thor_mtd_target_node >/dev/null || return 1 ;;
        ubimkvol|ab_ubi_node)
            thor_ubi_now=; thor_n=0
            for thor_p in "$AB_UBI_SYS"/ubi[0-9]*/mtd_num; do
                [ -r "$thor_p" ] || continue
                if [ "$(cat "$thor_p")" = "$AB_TARGET_MTD" ]; then
                    thor_ubi_now=${thor_p%/mtd_num}; thor_ubi_now=${thor_ubi_now##*/}; thor_n=$((thor_n+1))
                fi
            done
            [ "$thor_n" = 1 ] && [ "$thor_ubi_now" = "$AB_TARGET_UBI" ] || return 1
            if [ "$thor_cmd" = ab_ubi_node ]; then
                case "$1" in "$thor_ubi_now"|"${thor_ubi_now}_0"|"${thor_ubi_now}_1"|"${thor_ubi_now}_2"|"${thor_ubi_now}_3"|"${thor_ubi_now}_4") ;; *) return 1 ;; esac
            else
                [ "$1" = "$AB_DEV/$thor_ubi_now" ] &&
                    oem_thor_character_matches "$1" "$AB_UBI_SYS/$thor_ubi_now/dev" || return 1
            fi ;;
        *) return 1 ;;
        esac
        printf '%s\twriting\n' "$thor_cmd" >> "$OEM_WORK/thor-layout-journal.tsv" || return 1
        "$thor_cmd" "$@" >> "$OEM_WORK/thor-layout.log" 2>&1; thor_rc=$?
        [ "$thor_rc" = 0 ] || { printf '%s\tfailed\n' "$thor_cmd" >> "$OEM_WORK/thor-layout-journal.tsv"; return "$thor_rc"; }
        printf '%s\tverified-command\n' "$thor_cmd" >> "$OEM_WORK/thor-layout-journal.tsv"
    }
    ab_prepare_bank "$thor_kernel_bytes" "$thor_root_bytes" || exit 1
    [ "$(cat "$AB_UBI_SYS/${AB_TARGET_UBI}_3/reserved_ebs")" = 8 ] &&
        [ "$(cat "$AB_UBI_SYS/${AB_TARGET_UBI}_4/reserved_ebs")" = 20 ] || exit 1
    printf '%s\n' "$AB_TARGET_UBI"
)

# Shared dispatcher phases. All code/payload members are authenticated locally.
oem_thor_forward_load() {
    local thor_member
    thor_member=$(oem_bundle_member lib/cambium-installer-settings.sh) || return 1
    . "$thor_member" || return 1
    for thor_member in runtime/cambium-ab.sh runtime/cambium-ab-upgrade.sh runtime/cambium-ab-thor.sh adapters/thor-handoff.sh; do
        oem_bundle_member "$thor_member" >/dev/null || return 1
    done
    THOR_IMAGE=$(oem_bundle_member payloads/XV3-8/image.bin) || return 1
    oem_thor_published_image_valid "$THOR_IMAGE" || return 1
}

oem_thor_environment() (
    set +x; set +a
    local thor_snapshot
    thor_snapshot=$(fw_printenv -c "$THOR_ENV_CONFIG" 2>&1) || exit 1
    printf '%s\n' "$thor_snapshot" | awk '
      {k=$0;sub(/=.*/,"",k);if(index($0,"=")==0 || k!~/^[A-Za-z0-9_]+$/ || seen[k]++)bad=1}
      END{exit bad || !seen["image"] || !seen["bootcmd"]}' || exit 1
    printf '%s\n' "$thor_snapshot"
)

# Direct raw-MTD users are checked before attachment can change UBI metadata.
# Resolve named aliases and device numbers; this is the same target-only idle
# boundary used after attachment, not a new source admission requirement.
oem_thor_raw_target_idle() (
    local thor_proc=${OEM_SYS_ROOT:-}/proc thor_dev=${OEM_SYS_ROOT:-}/dev
    local thor_sys=${OEM_SYS_ROOT:-}/sys/class thor_n=$OEM_TARGET_MTD
    local thor_table thor_path thor_link thor_fd thor_number thor_numbers= thor_listing
    [ -r "$thor_proc/mounts" ] && [ -r "$thor_proc/self/mountinfo" ] || exit 1
    for thor_path in "$thor_sys/mtd/mtd$thor_n/dev" "$thor_sys/mtd/mtd${thor_n}ro/dev" "$thor_sys/block/mtdblock$thor_n/dev"; do
        [ -r "$thor_path" ] || continue
        thor_number=$(cat "$thor_path") || exit 1
        printf '%s\n' "$thor_number" | awk 'NR!=1 || $0!~/^[0-9]+:[0-9]+$/ {bad=1}END{exit bad}' || exit 1
        thor_numbers="$thor_numbers $thor_number"
        if [ "$thor_path" = "$thor_sys/mtd/mtd$thor_n/dev" ]; then
            thor_numbers="$thor_numbers ${thor_number%:*}:$((${thor_number#*:}+1))"
        fi
    done
    awk -v numbers="$thor_numbers" 'BEGIN{n=split(numbers,a," ");for(i=1;i<=n;i++)wanted[a[i]]=1} wanted[$3]{bad=1}END{exit bad}' "$thor_proc/self/mountinfo" || exit 1
    while read -r thor_path thor_table; do
        case "$thor_path" in
            "mtd:$(cat "$thor_sys/mtd/mtd$thor_n/name")") exit 1 ;;
            /*) thor_link=$(readlink -f "$thor_path" 2>/dev/null) || thor_link=$thor_path ;;
            *) continue ;;
        esac
        case "$thor_link" in "$thor_dev/mtd$thor_n"|"$thor_dev/mtd${thor_n}ro"|"$thor_dev/mtdblock$thor_n") exit 1 ;; esac
    done < "$thor_proc/mounts"
    for thor_fd in "$thor_proc"/[0-9]*/fd/*; do
        [ -L "$thor_fd" ] || continue
        thor_link=$(readlink "$thor_fd") || exit 1
        case "$thor_link" in
            /*) thor_path=$(readlink -f "$thor_fd" 2>/dev/null) || thor_path=$thor_link
                case "$thor_path" in "$thor_dev/mtd$thor_n"|"$thor_dev/mtd${thor_n}ro"|"$thor_dev/mtdblock$thor_n") exit 1 ;; esac ;;
        esac
        [ -n "$thor_numbers" ] || continue
        thor_listing=$(LC_ALL=C ls -Lldn "$thor_fd" 2>/dev/null) || exit 1
        thor_number=$(printf '%s\n' "$thor_listing" | awk 'NR==1 && $1~/^[cb]/ && $5~/^[0-9]+,$/ && $6~/^[0-9]+$/ {sub(/,$/,"",$5);print $5 ":" $6}') || exit 1
        [ -n "$thor_number" ] || continue
        case " $thor_numbers " in *" $thor_number "*) exit 1 ;; esac
    done
)

# Preflight remains read-only. Attachment of a currently unattached inactive
# bank occurs only inside the authorized transaction, after backup/source save.
oem_thor_target_attachment() {
    local thor_allow=${1:-no} thor_file thor_n=0 thor_ubi=
    for thor_file in "${OEM_SYS_ROOT:-}"/sys/class/ubi/ubi[0-9]*/mtd_num; do
        [ -r "$thor_file" ] || continue
        if [ "$(cat "$thor_file")" = "$OEM_TARGET_MTD" ]; then
            thor_ubi=${thor_file%/mtd_num}; thor_ubi=${thor_ubi##*/}; thor_n=$((thor_n+1))
        fi
    done
    if [ "$thor_n" = 0 ]; then
        [ "$thor_allow" = after-source-save ] || return 2
        oem_thor_critical_check && oem_thor_mtd_target_node >/dev/null && oem_thor_raw_target_idle || return 1
        awk -F '\t' -v dst="$OEM_TARGET_MTD" -v src="$OEM_SOURCE_MTD" '
          $1==dst {d++;if($4!="target")bad=1} $1==src {s++;if($4!="active-oem")bad=1}
          END{exit bad || d!=1 || s!=1}' "$OEM_PROTECTED_RANGES" || return 1
        printf 'ubiattach-inventory\twriting\n' >> "$OEM_WORK/thor-layout-journal.tsv" || return 1
        ubiattach -m "$OEM_TARGET_MTD" >> "$OEM_WORK/thor-layout.log" 2>&1 || return 1
        oem_thor_target_attachment no || return 1
        printf 'ubiattach-inventory\tverified-command\n' >> "$OEM_WORK/thor-layout-journal.tsv"
        return $?
    fi
    [ "$thor_n" = 1 ] || return 1
    OEM_TARGET_UBI=$thor_ubi
}

oem_adapter_preflight() {
    local thor_profile thor_source thor_tool thor_ubi thor_n thor_file
    oem_thor_forward_load && oem_adapter_inspect && oem_context_check || return 1
    [ "$OEM_SOURCE_RELEASE:$OEM_SOURCE_SLOT:$OEM_TARGET_SLOT" = 7.2-r1:1:0 ] || return 1
    thor_source=$(oem_bundle_member profiles/XV3-8/source.tsv) || return 1
    oem_source_identifiers_check "${OEM_SYS_ROOT:-}/etc/version" "$thor_source" || return 1
    THOR_SOURCE_CONTRACT=$(oem_sha "$thor_source") || return 1
    oem_thor_local_payload kernel && oem_thor_local_payload rootfs && oem_thor_vault_assets_ready || return 1
    thor_profile=$(oem_bundle_member profiles/XV3-8/mtd-slot0.tsv) || return 1
    OEM_PROTECTED_RANGES=$OEM_WORK/thor-ranges.tsv OEM_WRITE_PLAN=$OEM_WORK/thor-write-plan.tsv
    oem_physical_inventory "$thor_profile" "${OEM_SYS_ROOT:-}/sys/class/mtd" "$OEM_PROTECTED_RANGES" || return 1
    {
        printf 'ubi-update\t%s\t0\tkernel\nubi-update\t%s\t1\trootfs\nubi-update\t%s\t3\tcambium_device_data\n' "$OEM_TARGET_MTD" "$OEM_TARGET_MTD" "$OEM_TARGET_MTD"
        printf 'ubi-create\t%s\t2\trootfs_data\nubi-create\t%s\t4\tcertificates\n' "$OEM_TARGET_MTD" "$OEM_TARGET_MTD"
        printf 'environment-fields\t%s\tfields\tpreserve-unlisted\n' "$(oem_physical_index "${OEM_SYS_ROOT:-}/sys/class/mtd" 0:APPSBLENV)"
    } > "$OEM_WRITE_PLAN" || return 1
    oem_write_boundary "$OEM_PROTECTED_RANGES" "$OEM_WRITE_PLAN" || return 1
    thor_n=0; thor_ubi=
    for thor_file in "${OEM_SYS_ROOT:-}"/sys/class/ubi/ubi[0-9]*/mtd_num; do
        [ -r "$thor_file" ] || continue
        if [ "$(cat "$thor_file")" = "$OEM_TARGET_MTD" ]; then
            thor_ubi=${thor_file%/mtd_num}; thor_ubi=${thor_ubi##*/}; thor_n=$((thor_n+1))
        fi
    done
    [ "$thor_n" -le 1 ] || return 1
    if [ "$thor_n" = 1 ]; then
    oem_bank_idle_check "${OEM_SYS_ROOT:-}/sys/class/ubi" "${OEM_SYS_ROOT:-}/dev" "${OEM_SYS_ROOT:-}/proc" "$OEM_TARGET_MTD" "$thor_ubi" no || return 1
    oem_ubi_child_check "${OEM_SYS_ROOT:-}/sys/class/ubi" "$OEM_TARGET_MTD" "$thor_ubi" 0 kernel &&
        oem_ubi_child_check "${OEM_SYS_ROOT:-}/sys/class/ubi" "$OEM_TARGET_MTD" "$thor_ubi" 1 ubi_rootfs || return 1
    [ "$(ls "${OEM_SYS_ROOT:-}/sys/class/ubi/${thor_ubi}_"*/name | wc -l)" -eq 2 ] || return 1
    fi
    oem_thor_environment | awk -F= '$1~/^thor_(installer_|migration_|ab_)/ && length(substr($0,index($0,"=")+1)) {bad=1}END{exit bad}' || return 1
    for thor_tool in ubiattach ubidetach ubiformat ubimkvol ubiupdatevol fw_printenv fw_setenv mount umount tar sync cmp head od sha256sum; do
        command -v "$thor_tool" >/dev/null 2>&1 || return 1
    done
}

oem_adapter_boot_preflight() {
    [ "$(fw_printenv -c "$THOR_ENV_CONFIG" -n bootcmd)" = 'aq_load_fw&&bootipq' ] &&
        [ "$(fw_printenv -c "$THOR_ENV_CONFIG" -n image)" = "$OEM_SOURCE_SLOT" ] || return 1
    OEM_BOOT_PRIOR_SLOT=$OEM_SOURCE_SLOT OEM_BOOT_TARGET_SLOT=$OEM_TARGET_SLOT
    OEM_BOOT_MODE=persist-prior-before-load OEM_BOOT_WATCHDOG=manual-reset
}

oem_adapter_recovery() {
    local thor_plan
    thor_plan=$(oem_bundle_member profiles/XV3-8/critical.tsv) || return 1
    OEM_RECOVERY_DIR=$OEM_WORK/critical
    oem_backup_capture "$thor_plan" "${OEM_SYS_ROOT:-}/sys/class/mtd" "${OEM_SYS_ROOT:-}/dev" "$OEM_RECOVERY_DIR" && oem_backup_upload "$OEM_RECOVERY_DIR"
}

oem_thor_critical_check() {
    local thor_kind thor_label thor_limit thor_reason thor_idx thor_plan thor_expected thor_live
    [ "$(cat "$OEM_WORK/critical/OFFDEVICE_VERIFIED")" = "$(oem_sha "$OEM_WORK/critical/SHA256SUMS")" ] || return 1
    (cd "$OEM_WORK/critical" && sha256sum -c SHA256SUMS >/dev/null 2>&1) || return 1
    thor_plan=$(oem_bundle_member profiles/XV3-8/critical.tsv) || return 1
    while IFS="$(printf '\t')" read -r thor_kind thor_label thor_limit thor_reason; do
        [ "$thor_kind" != ENV ] || continue
        thor_idx=$(oem_physical_index "${OEM_SYS_ROOT:-}/sys/class/mtd" "$thor_label") || return 1
        thor_expected=$(oem_sha "$OEM_WORK/critical/$thor_kind.bin") &&
            thor_live=$(oem_sha "${OEM_SYS_ROOT:-}/dev/mtd${thor_idx}ro") || return 1
        oem_hex64 "$thor_expected" && oem_hex64 "$thor_live" && [ "$thor_expected" = "$thor_live" ] || return 1
    done < "$thor_plan"
    oem_thor_environment > "$OEM_WORK/thor-env-after" || return 1
    oem_env_preserved "$OEM_WORK/thor-env-before" "$OEM_WORK/thor-env-after" "$OEM_WORK/thor-env-allowed"
}

oem_thor_environment_batch() {
    local thor_name thor_value
    fw_setenv -c "$THOR_ENV_CONFIG" -s "$1" && sync || return 1
    while read -r thor_name thor_value; do
        [ "$(fw_printenv -c "$THOR_ENV_CONFIG" -n "$thor_name")" = "$thor_value" ] || return 1
    done < "$1"
    oem_thor_critical_check
}

# Exact existing .8 vault ABI; only shared BDF bytes and own ART hash.
oem_thor_build_vault() {
    local thor_table thor_src thor_rel thor_bytes thor_sha thor_file thor_art thor_art_hash thor_dir
    thor_table=$(oem_bundle_member profiles/XV3-8/vault-assets.tsv) || return 1
    [ "$(wc -l < "$thor_table")" -eq 1 ] || return 1
    [ "$(cut -f1,3,4 "$thor_table")" = "$(printf 'lib/firmware/IPQ8074/WIFI_FW/bdwlan.b215.accton\t131072\t831633e2451a456f3f71d4ad49429f519c0148ba1a37312e74e30533ce8adfab')" ] || return 1
    oem_thor_vault_assets_ready || return 1
    thor_dir=$OEM_WORK/thor-vault
    [ ! -e "$thor_dir" ] && mkdir -m 700 "$thor_dir" || return 1
    while IFS="$(printf '\t')" read -r thor_src thor_rel thor_bytes thor_sha; do
        thor_file=$(oem_bundle_member "$thor_rel") || return 1
        mkdir -p "$thor_dir/files/${thor_src%/*}" && cp "$thor_file" "$thor_dir/files/$thor_src" || return 1
    done < "$thor_table"
    thor_art=$(oem_physical_index "${OEM_SYS_ROOT:-}/sys/class/mtd" 0:ART) || return 1
    thor_file=$(oem_thor_art_node "$thor_art") || return 1
    thor_art_hash=$(oem_sha "$thor_file") || return 1
    {
        printf 'format 1\nboard cambiumnetworks,xv3-8\nsku 00000013\nart_sha256 %s\nnvram_sha256_at_capture unknown\nsource verified-vendor-7.2-r1\n' "$thor_art_hash"
        printf 'file lib/firmware/IPQ8074/WIFI_FW/bdwlan.b215.accton 131072 831633e2451a456f3f71d4ad49429f519c0148ba1a37312e74e30533ce8adfab\n'
    } > "$thor_dir/MANIFEST" || return 1
    (cd "$thor_dir" && tar -cf "$OEM_WORK/thor-vault.tar" MANIFEST files) || return 1
    [ "$(wc -c < "$OEM_WORK/thor-vault.tar")" -le 1015808 ]
}

oem_thor_forward_write_boundary() {
    local thor_profile thor_source thor_serial=$OEM_SERIAL thor_parent=$OEM_TARGET_MTD thor_active=$OEM_SOURCE_MTD thor_ubi=$OEM_TARGET_UBI thor_id thor_name
    oem_adapter_inspect && oem_context_check || return 1
    [ "$OEM_SERIAL:$OEM_SOURCE_MTD:$OEM_TARGET_MTD:$OEM_SOURCE_SLOT:$OEM_TARGET_SLOT" = "$thor_serial:$thor_active:$thor_parent:1:0" ] || return 1
    thor_source=$(oem_bundle_member profiles/XV3-8/source.tsv) || return 1
    oem_source_identifiers_check "${OEM_SYS_ROOT:-}/etc/version" "$thor_source" || return 1
    thor_profile=$(oem_bundle_member profiles/XV3-8/mtd-slot0.tsv) || return 1
    oem_physical_inventory "$thor_profile" "${OEM_SYS_ROOT:-}/sys/class/mtd" "$OEM_PROTECTED_RANGES" &&
        oem_write_boundary "$OEM_PROTECTED_RANGES" "$OEM_WRITE_PLAN" && oem_thor_critical_check || return 1
    [ "$OEM_TARGET_UBI" = "$thor_ubi" ] &&
        [ "$(ls "${OEM_SYS_ROOT:-}/sys/class/ubi/${thor_ubi}_"*/name | wc -l)" -eq 5 ] || return 1
    for thor_id in 0 1 2 3 4; do
        case "$thor_id" in 0) thor_name=kernel ;; 1) thor_name=rootfs ;; 2) thor_name=rootfs_data ;; 3) thor_name=cambium_device_data ;; 4) thor_name=certificates ;; esac
        oem_ubi_child_check "${OEM_SYS_ROOT:-}/sys/class/ubi" "$OEM_TARGET_MTD" "$thor_ubi" "$thor_id" "$thor_name" || return 1
    done
    oem_bank_idle_check "${OEM_SYS_ROOT:-}/sys/class/ubi" "${OEM_SYS_ROOT:-}/dev" "${OEM_SYS_ROOT:-}/proc" "$OEM_TARGET_MTD" "$thor_ubi" no
}

oem_thor_write_vault() {
    local thor_node thor_sha
    oem_ubi_child_check "${OEM_SYS_ROOT:-}/sys/class/ubi" "$OEM_TARGET_MTD" "$OEM_TARGET_UBI" 3 cambium_device_data &&
        oem_write_boundary "$OEM_PROTECTED_RANGES" "$OEM_WRITE_PLAN" || return 1
    thor_node=$(oem_thor_target_node 3) || return 1
    thor_sha=$(oem_sha "$OEM_WORK/thor-vault.tar") || return 1
    ubiupdatevol "$thor_node" "$OEM_WORK/thor-vault.tar" || return 1
    [ "$(head -c "$(wc -c < "$OEM_WORK/thor-vault.tar")" "$thor_node" | sha256sum | awk '{print $1}')" = "$thor_sha" ] &&
        oem_ubi_child_check "${OEM_SYS_ROOT:-}/sys/class/ubi" "$OEM_TARGET_MTD" "$OEM_TARGET_UBI" 3 cambium_device_data
}

oem_thor_stage_handoff() {
    local thor_mnt=$1 thor_file thor_dest
    thor_file=$(oem_bundle_member adapters/thor-handoff.sh) || return 1
    thor_dest=$thor_mnt/upper/lib/functions/cambium-ab-thor-handoff.sh
    [ ! -e "$thor_dest" ] && [ ! -L "$thor_dest" ] || return 1
    [ ! -L "$thor_mnt/upper/lib" ] && [ ! -L "$thor_mnt/upper/lib/functions" ] || return 1
    mkdir -p "$thor_mnt/upper/lib/functions" && chmod 755 "$thor_mnt/upper/lib" "$thor_mnt/upper/lib/functions" || return 1
    cp "$thor_file" "$thor_dest" && chmod 644 "$thor_dest" && cmp -s "$thor_file" "$thor_dest"
}

oem_thor_arm_forward() {
    local thor_core thor_module thor_boot thor_batch thor_trial
    oem_thor_critical_check && oem_adapter_boot_preflight || return 1
    thor_core=$(oem_bundle_member runtime/cambium-ab.sh) && thor_module=$(oem_bundle_member runtime/cambium-ab-thor.sh) || return 1
    CAMBIUM_AB_MODULES=$OEM_WORK/no-autoload-modules
    . "$thor_core"; . "$thor_module"
    ab_thor_board cambiumnetworks,xv3-8 || return 1
    thor_boot=$(ab_thor_boot_command "$OEM_TARGET_SLOT") || return 1
    case "$thor_boot" in 'aq_load_fw; '*) thor_boot="aq_load_fw && ${thor_boot#aq_load_fw; }" ;; 'aq_load_fw && '*) ;; *) return 1 ;; esac
    thor_batch=$OEM_WORK/thor-arm.tsv
    {
        printf 'changing_bootcmd 1\nthor_boot%s setenv image %s && aq_load_fw && bootipq\n' "$OEM_SOURCE_SLOT" "$OEM_SOURCE_SLOT"
        printf 'thor_boot%s %s\nthor_stable%s run thor_boot%s; run thor_boot%s\n' "$OEM_TARGET_SLOT" "$thor_boot" "$OEM_TARGET_SLOT" "$OEM_TARGET_SLOT" "$OEM_SOURCE_SLOT"
        printf 'thor_migration_oem_slot %s\nthor_ab_confirmed %s\nthor_ab_state armed\nthor_ab_target %s\n' "$OEM_SOURCE_SLOT" "$OEM_SOURCE_SLOT" "$OEM_TARGET_SLOT"
        printf 'thor_installer_target %s\nthor_installer_job %s\nthor_installer_image %s\n' "$OEM_TARGET_SLOT" "$OW_EXPECT_JOB" "$(oem_sha "$THOR_IMAGE")"
    } > "$thor_batch" || return 1
    oem_thor_environment_batch "$thor_batch" || return 1
    # The prior-only default is durable before the candidate load, exactly
    # once. No converted flag is manufactured for the retained OEM bank.
    thor_trial=$(ab_trial_command "$OEM_SOURCE_SLOT" "$OEM_TARGET_SLOT") || return 1
    [ "$thor_trial" = "setenv bootcmd run thor_boot$OEM_SOURCE_SLOT && setenv image $OEM_SOURCE_SLOT && setenv thor_ab_state trial-started && saveenv && run thor_boot$OEM_TARGET_SLOT; run thor_boot$OEM_SOURCE_SLOT" ] || return 1
    printf 'bootcmd %s\n' "$thor_trial" > "$thor_batch" || return 1
    if ! oem_thor_environment_batch "$thor_batch"; then
        printf 'bootcmd aq_load_fw&&bootipq\nimage %s\n' "$OEM_SOURCE_SLOT" > "$thor_batch"
        oem_thor_environment_batch "$thor_batch" || :
        return 1
    fi
}

oem_adapter_migrate() (
    set +x; set +a
    unset credential
    local credential=$1 thor_job thor_mount thor_rc thor_image_sha
    umask 077
    oem_adapter_preflight && oem_adapter_boot_preflight || exit 1
    oem_thor_environment > "$OEM_WORK/thor-env-before" || exit 1
    printf '%s\n' bootcmd image changing_bootcmd thor_boot0 thor_boot1 thor_stable0 thor_stable1 thor_migration_oem_slot thor_ab_confirmed thor_ab_state thor_ab_target thor_installer_target thor_installer_job thor_installer_image > "$OEM_WORK/thor-env-allowed" || exit 1
    oem_thor_critical_check && oem_thor_build_vault || exit 1
    thor_job=$(oem_read_hex "${OEM_SYS_ROOT:-}/dev/urandom" 32) || exit 1
    oem_hex64 "$thor_job" || exit 1
    thor_image_sha=$(oem_sha "$THOR_IMAGE") || exit 1
    OW_EXPECT_SERIAL=$OEM_SERIAL OW_EXPECT_FAMILY=thor OW_EXPECT_MODEL=XV3-8
    OW_EXPECT_OPERATION=production-oem-migration OW_EXPECT_RELEASE=$OEM_SOURCE_RELEASE
    OW_EXPECT_CONTRACT=$THOR_SOURCE_CONTRACT OW_EXPECT_SOURCE=$OEM_SOURCE_SLOT OW_EXPECT_TARGET=$OEM_TARGET_SLOT OW_EXPECT_JOB=$thor_job
    OW_STAGE_ADMISSION=qualified
    {
        printf 'format\t2\nserial\t%s\nfamily\tthor\nmodel\tXV3-8\nsource_operation\tproduction-oem-migration\nsource_release\t%s\nsource_contract_sha256\t%s\nsource_slot\t%s\ntarget_slot\t%s\nimage_sha256\t%s\njob_id\t%s\n' "$OEM_SERIAL" "$OEM_SOURCE_RELEASE" "$THOR_SOURCE_CONTRACT" "$OEM_SOURCE_SLOT" "$OEM_TARGET_SLOT" "$thor_image_sha" "$thor_job"
    } > "$OEM_WORK/thor-binding.tsv" || exit 1
    printf '{"server":"%s:18443","tls_ca":"/etc/ssl/certs/ca-certificates.crt"}\n' "$OEM_CONTROLLER" > "$OEM_WORK/thor-est.json" || exit 1
    printf '{"server":"%s","port":15002,"cert":"/etc/ucentral/operational.pem","ca":"/etc/ssl/certs/ca-certificates.crt","hostname_validate":1}\n' "$OEM_CONTROLLER" > "$OEM_WORK/thor-gateway.json" || exit 1
    chmod 600 "$OEM_WORK/thor-binding.tsv" "$OEM_WORK/thor-est.json" "$OEM_WORK/thor-gateway.json" || exit 1
    ow_settings_prepare "$OEM_WORK/thor-binding.tsv" "$OEM_WORK/thor-est.json" "$OEM_WORK/thor-gateway.json" "$credential" "$OEM_WORK/thor-seed" || exit 1
    credential=
    # Persist and read back the actual working OEM source, before any erase.
    printf 'bootcmd aq_load_fw&&bootipq\nimage %s\n' "$OEM_SOURCE_SLOT" > "$OEM_WORK/thor-source.tsv" || exit 1
    oem_thor_environment_batch "$OEM_WORK/thor-source.tsv" || exit 1
    OEM_TARGET_UBI=$(oem_thor_prepare_native_layout "$THOR_IMAGE") || exit 1
    oem_thor_forward_write_boundary && oem_thor_update_existing_child kernel &&
        oem_thor_forward_write_boundary && oem_thor_update_existing_child rootfs &&
        oem_thor_forward_write_boundary && oem_thor_write_vault || exit 1
    OW_SETTINGS_SYS=${OEM_SYS_ROOT:-}/sys/class/ubi OW_SETTINGS_DEV=${OEM_SYS_ROOT:-}/dev OW_SETTINGS_MOUNTS=${OEM_SYS_ROOT:-}/proc/mounts OW_SETTINGS_OWNER=0
    OW_EXPECT_TARGET_MTD=$OEM_TARGET_MTD OW_EXPECT_TARGET_VOLUME=${OEM_TARGET_UBI}_2
    thor_mount=$OEM_WORK/thor-overlay
    mkdir -m 700 "$thor_mount" || exit 1
    mount -t ubifs "$(oem_thor_target_node 2)" "$thor_mount" || exit 1
    thor_rc=0
    oem_thor_stage_native_overlay "$OEM_WORK/thor-seed" "$THOR_IMAGE" "$thor_mount" && oem_thor_stage_handoff "$thor_mount" && sync || thor_rc=1
    umount "$thor_mount" || exit 1
    [ "$thor_rc" = 0 ] || exit 1
    # Reopen read-only after unmount to prove persisted seed and hook bytes.
    mount -t ubifs -o ro "$(oem_thor_target_node 2)" "$thor_mount" || exit 1
    thor_rc=0
    ow_settings_tree "$thor_mount/upper/root/.cambium-installer-settings" && ow_settings_context "$THOR_IMAGE" &&
        cmp -s "$OEM_WORK/thor-seed/files.sha256" "$thor_mount/upper/root/.cambium-installer-settings/files.sha256" &&
        cmp -s "$(oem_bundle_member adapters/thor-handoff.sh)" "$thor_mount/upper/lib/functions/cambium-ab-thor-handoff.sh" || thor_rc=1
    umount "$thor_mount" && sync || exit 1
    [ "$thor_rc" = 0 ] && oem_thor_forward_write_boundary && oem_thor_arm_forward || exit 1
    printf 'handoff=one-shot-armed\nonboarded=not-yet-verified\nsysupgrade_ready=not-yet-verified\n'
)
