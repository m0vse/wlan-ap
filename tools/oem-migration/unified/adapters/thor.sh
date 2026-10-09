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
    # Unique metadata remains exact; a backup is never permission to overwrite it.
    while IFS="$(printf '\t')" read -r thor_kind thor_label thor_limit thor_reason; do
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
    # Unknown/unattached and resumed OW/identity-containing targets are not
    # reformatted. Caller must establish a safe inventory/resume first.
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
