#!/bin/sh
# Source-preserving Jaguar OEM test return; never retire/reset certificates.
oem_restore_jaguar_member() { oem_bundle_member "profiles/$OEM_MODEL/restore/$1"; }
oem_restore_jaguar_physical_profile() {
 case "$OEM_SOURCE_SLOT" in 0|1) ;;*) return 1;;esac
 oem_restore_jaguar_member "mtd-slot$OEM_SOURCE_SLOT.tsv"
}
oem_restore_jaguar_load() {
 local file
 file=$(oem_bundle_member adapters/jaguar.sh) && . "$file" || return 1
 file=$(oem_bundle_member adapters/required-source.sh) && . "$file"
}
oem_restore_jaguar_ubi() (
 local node found= count=0
 for node in "$OEM_SYS_ROOT"/sys/class/ubi/ubi*/mtd_num;do
  [ -r "$node" ] && [ "$(cat "$node")" = "$1" ] || continue
  found=${node%/mtd_num};found=${found##*/};count=$((count+1))
 done
 [ "$count" -le 1 ] || exit 1
 [ "$count" = 0 ] || printf '%s\n' "$found"
)
oem_restore_jaguar_inspect() {
 local file release contract status field value arg attachment= rootarg= label index header factory
 OEM_SERIAL= OEM_SOURCE_RELEASE= OEM_SOURCE_SLOT= OEM_TARGET_SLOT=
 oem_restore_jaguar_load && oem_jaguar_table && oem_jaguar_config || return 1
 file=$(oem_restore_jaguar_member source-sets/runtime-implementation.set) || return 1
 oem_required_source_check "$file" "$OEM_SYS_ROOT" /etc/openwrt_release sh awk sed grep cmp dd head sha256sum tar fw_printenv fw_setenv cambium-ab-status ubimkvol ubirmvol ubirsvol ubiupdatevol || return 1
 file=$(oem_restore_jaguar_member source-contract) || return 1
 [ "$(wc -l < "$file")" -eq 2 ] || return 1
 release=$(sed -n '1p' "$file");contract=$(sed -n '2p' "$file");oem_hex64 "$contract" || return 1
 OEM_SOURCE_RELEASE=$(awk -F= '$1=="DISTRIB_TIP_VERSION" {v=$2;gsub(/^\047|\047$/,"",v);n++} END{if(n!=1 || v!~/^[A-Za-z0-9._~-]+$/)exit 1;print v}' "$OEM_SYS_ROOT/etc/openwrt_release") || return 1
 [ "$release" = "$OEM_SOURCE_RELEASE" ] && [ "$release" = "$OEM_SUPPORTED_RELEASE" ] || return 1
 status=$(cambium-ab-status) || return 1
 for field in family model mode running confirmed state;do
  value=$(printf '%s\n' "$status" | awk -v key="$field" 'index($0,key "=")==1 {v=substr($0,length(key)+2);n++}END{if(n!=1)exit 1;print v}') || return 1
  case "$field" in
   family) [ "$value" = jaguar ] || return 1;;model) [ "$value" = "$OEM_MODEL" ] || return 1;;
   mode) [ "$value" = ab ] || return 1;;state) [ "$value" = confirmed ] || return 1;;
   running) case "$value" in 0|1) OEM_SOURCE_SLOT=$value;;*) return 1;;esac;;
   confirmed) [ "$value" = "$OEM_SOURCE_SLOT" ] || return 1;;
  esac
 done
 OEM_TARGET_SLOT=$((1-OEM_SOURCE_SLOT))
 for arg in $(cat "$OEM_SYS_ROOT/proc/cmdline");do
  case "$arg" in ubi.mtd=*) [ -z "$attachment" ] || return 1;attachment=${arg#ubi.mtd=};;root=*) [ -z "$rootarg" ] || return 1;rootarg=${arg#root=};;esac
 done
 label=rootfs;[ "$OEM_SOURCE_SLOT" = 0 ] || label=rootfs_1
 [ "$attachment" = "$label" ] || return 1
 RJ_SOURCE_MTD=$(oem_physical_index "$OEM_SYS_ROOT/sys/class/mtd" "$label") || return 1
 label=rootfs;[ "$OEM_TARGET_SLOT" = 0 ] || label=rootfs_1
 RJ_TARGET_MTD=$(oem_physical_index "$OEM_SYS_ROOT/sys/class/mtd" "$label") || return 1
 [ "$RJ_SOURCE_MTD" != "$RJ_TARGET_MTD" ] || return 1
 RJ_SOURCE_UBI=$(oem_restore_jaguar_ubi "$RJ_SOURCE_MTD") && RJ_TARGET_UBI=$(oem_restore_jaguar_ubi "$RJ_TARGET_MTD") || return 1
 [ -n "$RJ_SOURCE_UBI" ] || return 1
 [ "$rootarg" = "/dev/ubiblock${RJ_SOURCE_UBI#ubi}_1" ] || return 1
 for label in "$RJ_SOURCE_UBI" "$RJ_TARGET_UBI";do
  [ -n "$label" ] || continue
  [ "$(cat "$OEM_SYS_ROOT/sys/class/ubi/$label/eraseblock_size")" = 126976 ] && [ "$(cat "$OEM_SYS_ROOT/sys/class/ubi/$label/min_io_size")" = 2048 ] || return 1
 done
 . "$OEM_SYS_ROOT/lib/functions/system.sh" || return 1
 OEM_SERIAL=$(get_mac_label_dt | tr -d ':' | tr 'A-F' 'a-f') || return 1
 index=$(oem_physical_index "$OEM_SYS_ROOT/sys/class/mtd" mfginfo) || return 1
 header=$(oem_read_hex "$OEM_SYS_ROOT/dev/mtd${index}ro" 6) || return 1
 [ "$header" = 05ca01000c00 ] || return 1
 factory=$(dd if="$OEM_SYS_ROOT/dev/mtd${index}ro" bs=1 skip=6 count=12 2>/dev/null | tr 'A-F' 'a-f') || return 1
 [ "$factory" = "$OEM_SERIAL" ] || return 1
 [ "$(cat "$OEM_SYS_ROOT/tmp/sysinfo/board_name")" = "cambiumnetworks,$(printf '%s' "$OEM_MODEL" | tr 'A-Z' 'a-z')" ] || return 1
 oem_jaguar_env_read | awk -F= '$1~/^jaguar_(installer_(target|job|image)|storage_pending|oem_restore_(target|state))$/ {if(NF!=2 || length($2) || seen[$1]++)bad=1} END{exit bad}' || return 1
 oem_context_check
}
oem_restore_jaguar_boot_check() {
 local file pin source current stable
 oem_context_check || return 1
 [ "$(oem_jaguar_env_value image)" = "$OEM_SOURCE_SLOT" ] &&
  [ "$(oem_jaguar_env_value jaguar_ab_confirmed)" = "$OEM_SOURCE_SLOT" ] || return 1
 file=$(oem_restore_jaguar_member "source-boot$OEM_SOURCE_SLOT.sha256") || return 1
 [ "$(wc -l < "$file")" -eq 1 ] || return 1
 pin=$(cat "$file");oem_hex64 "$pin" || return 1
 source=$(oem_jaguar_env_value "jaguar_boot$OEM_SOURCE_SLOT") || return 1
 [ "$(printf '%s' "$source" | sha256sum | awk '{print $1}')" = "$pin" ] || return 1
 current=$(oem_jaguar_env_value bootcmd) || return 1
 case "$current" in
  "run jaguar_boot$OEM_SOURCE_SLOT") ;;
  "run jaguar_stable$OEM_SOURCE_SLOT")
   stable=$(oem_jaguar_env_value "jaguar_stable$OEM_SOURCE_SLOT") || return 1
   [ "$stable" = "run jaguar_boot$OEM_SOURCE_SLOT; run jaguar_boot$OEM_TARGET_SLOT" ] ||
    [ "$stable" = "run jaguar_boot$OEM_SOURCE_SLOT" ] || return 1;;
  *) return 1;;
 esac
}
oem_restore_jaguar_files() {
 case "$OEM_MODEL" in
  XV2-2|XV2-2T1) printf 'lib/firmware/IPQ6018/WIFI_FW/bdwlan.b13.stock 65536\n';;
  XE3-4) printf 'lib/firmware/IPQ6018/WIFI_FW/bdwlan.b10-puma 65536\nlib/firmware/qcn9000/WIFI_FW/bdwlan.bab-puma 131072\n';;
  *) return 1;;
 esac
}
# Existing tar bytes, never regenerated MANIFEST or donor data. Unknown length,
# header type or path is not permission to shrink this raw archive volume.
oem_restore_jaguar_vault_capture() (
 local device=$1 output=$2 blocks=$3 offset=0 bytes header zero name prefix kind octal size entries src expected entry value count file
 case "$blocks" in 1|2|3|4|5|6|7|8) ;;*) exit 1;;esac
 bytes=$((blocks*126976));header=$output.header;entries=$output.entries
 [ ! -e "$output" ] && [ ! -e "$output.dir" ] || exit 1
 umask 077;: > "$entries" || exit 1
 dd if=/dev/zero of="$header" bs=512 count=1 2>/dev/null || exit 1
 zero=$(oem_sha "$header") || exit 1
 while [ "$((offset+1024))" -le "$bytes" ];do
  dd if="$device" of="$header" bs=512 skip="$((offset/512))" count=1 2>/dev/null || exit 1
  [ "$(wc -c < "$header")" -eq 512 ] || exit 1
  if [ "$(oem_sha "$header")" = "$zero" ];then
   dd if="$device" of="$header" bs=512 skip="$((offset/512+1))" count=1 2>/dev/null || exit 1
   [ "$(wc -c < "$header")" -eq 512 ] && [ "$(oem_sha "$header")" = "$zero" ] || exit 1
   offset=$((offset+1024));break
  fi
  name=$(dd if="$header" bs=1 count=100 2>/dev/null | tr -d '\000') || exit 1
  prefix=$(dd if="$header" bs=1 skip=345 count=155 2>/dev/null | tr -d '\000') || exit 1
  [ -z "$prefix" ] || name=$prefix/$name
  name=${name%/}
  case "$name" in ''|/*|*[!A-Za-z0-9_./-]*) exit 1;;esac
  printf '%s\n' "$name" | awk '$0~/(^|\/)\.\.?($|\/)/ {bad=1}END{exit bad}' || exit 1
  kind=$(dd if="$header" bs=1 skip=156 count=1 2>/dev/null | tr -d '\000') || exit 1
  case "$kind" in ''|0|5) ;;*) exit 1;;esac
  expected=0
  if [ "$name" = MANIFEST ];then [ "$kind" != 5 ] || exit 1;expected=1
  else
   while read -r src size;do
    if [ "$name" = "files/$src" ] && [ "$kind" != 5 ];then expected=1;fi
    case "files/$src" in "$name/"*) [ "$kind" = 5 ] && expected=1;;esac
   done <<EOF_VAULT_FILES
$(oem_restore_jaguar_files)
EOF_VAULT_FILES
  fi
  [ "$expected" = 1 ] || exit 1
  printf '%s\n' "$name" >> "$entries" || exit 1
  octal=$(dd if="$header" bs=1 skip=124 count=12 2>/dev/null | tr -d '\000 ' | sed 's/^0*//') || exit 1
  [ -n "$octal" ] || octal=0
  case "$octal" in *[!0-7]*) exit 1;;esac
  [ "${#octal}" -le 7 ] || exit 1
  size=$((0$octal));[ "$size" -le "$bytes" ] || exit 1
  [ "$kind" != 5 ] || [ "$size" = 0 ] || exit 1
  offset=$((offset+512+((size+511)/512)*512))
 done
 [ "$offset" -gt 1024 ] && [ "$offset" -le "$bytes" ] && [ "$(oem_sha "$header")" = "$zero" ] || exit 1
 awk 'seen[$0]++ {bad=1}END{exit bad}' "$entries" || exit 1
 head -c "$offset" "$device" > "$output" && [ "$(wc -c < "$output")" -eq "$offset" ] || exit 1
 tar -tf "$output" >/dev/null 2>&1 && mkdir -m 700 "$output.dir" && tar -xf "$output" -C "$output.dir" || exit 1
 file=$output.dir/MANIFEST
 [ -f "$file" ] && [ ! -L "$file" ] || exit 1
 for entry in format board sku art_sha256;do
  value=$(awk -v key="$entry" '$1==key {if(NF!=2)bad=1;v=$2;n++}END{if(bad || n!=1)exit 1;print v}' "$file") || exit 1
  case "$entry" in
   format) [ "$value" = 1 ] || exit 1;;
   board) [ "$value" = "cambiumnetworks,$(printf '%s' "$OEM_MODEL" | tr 'A-Z' 'a-z')" ] || exit 1;;
   sku) [ "$value" = "$OEM_SKU" ] || exit 1;;
   art_sha256) [ "$value" = "$RJ_ART_PIN" ] || exit 1;;
  esac
 done
 count=0
 while read -r src size;do
  entry=$(awk -v src="$src" '$1=="file" && $2==src {if(NF!=4)bad=1;print;n++}END{if(bad || n!=1)exit 1}' "$file") || exit 1
  set -- $entry;[ "$3" = "$size" ] && oem_hex64 "$4" || exit 1
  [ -f "$output.dir/files/$src" ] && [ ! -L "$output.dir/files/$src" ] &&
   [ "$(wc -c < "$output.dir/files/$src")" -eq "$size" ] && [ "$(oem_sha "$output.dir/files/$src")" = "$4" ] || exit 1
  count=$((count+1))
 done <<EOF_VAULT_FILES
$(oem_restore_jaguar_files)
EOF_VAULT_FILES
 [ "$(awk '$1=="file" {n++}END{print n+0}' "$file")" = "$count" ] || exit 1
 printf '%s\t%s\n' "$offset" "$(oem_sha "$output")"
)
oem_restore_inspect() { oem_restore_jaguar_inspect; }
oem_restore_boot_preflight() {
 oem_restore_jaguar_boot_check || return 1
 OEM_BOOT_PRIOR_SLOT=$OEM_SOURCE_SLOT OEM_BOOT_TARGET_SLOT=$OEM_TARGET_SLOT
 OEM_BOOT_MODE=persist-prior-before-load OEM_BOOT_WATCHDOG=manual-reset
}
oem_restore_jaguar_public_payload_check() {
 [ "$(oem_sha "$RJ_KERNEL")" = "$RJ_KERNEL_PIN" ] && [ "$(oem_sha "$RJ_ROOT")" = "$RJ_ROOT_PIN" ] &&
  [ "$(oem_sha "$RJ_SHARED")" = "$RJ_SHARED_PIN" ]
}
oem_restore_jaguar_payload_check() {
 oem_restore_jaguar_public_payload_check && [ "$(oem_sha "$RJ_VAULT_COPY")" = "$RJ_VAULT_PIN" ]
}
oem_restore_jaguar_plan() {
 local label
 : > "$OEM_WRITE_PLAN" || return 1
 for label in '0 kernel' '1 rootfs' '2 rootfs_data';do set -- $label;printf 'ubi-remove\t%s\t%s\t%s\n' "$RJ_TARGET_MTD" "$1" "$2" >> "$OEM_WRITE_PLAN" || return 1;done
 printf 'ubi-create\t%s\t0\tkernel\nubi-create\t%s\t1\tubi_rootfs\nubi-update\t%s\t0\tkernel\nubi-update\t%s\t1\tubi_rootfs\nenvironment-fields\t%s\tfields\tpreserve-unlisted\n' "$RJ_TARGET_MTD" "$RJ_TARGET_MTD" "$RJ_TARGET_MTD" "$RJ_TARGET_MTD" "$OEM_JAGUAR_ENV_MTD" >> "$OEM_WRITE_PLAN"
}
# No target UBI yet: prove exact physical target and no direct mounted/open
# aliases. Standard attachment is permitted only later, after consent and the
# source-only default has been persisted/read back. It can write UBI metadata.
oem_restore_jaguar_unattached_check() (
 local file node path flags found
 found=$(oem_restore_jaguar_ubi "$RJ_TARGET_MTD") || exit 1
 [ -z "$found" ] || exit 1
 file=$(oem_restore_jaguar_physical_profile) || exit 1
 oem_physical_inventory "$file" "$OEM_SYS_ROOT/sys/class/mtd" "$OEM_PROTECTED_RANGES" && oem_write_boundary "$OEM_PROTECTED_RANGES" "$OEM_WRITE_PLAN" || exit 1
 flags=$(cat "$OEM_SYS_ROOT/sys/class/mtd/mtd$RJ_TARGET_MTD/flags") || exit 1
 printf '%s\n' "$flags" | awk 'NR!=1 || $0!~/^([0-9]+|0x[0-9a-fA-F]+)$/ {bad=1}END{exit bad}' || exit 1
 [ "$((flags&0x400))" -ne 0 ] || exit 1
 for file in "$OEM_SYS_ROOT/proc/mounts" "$OEM_SYS_ROOT/proc/self/mountinfo";do
  [ -r "$file" ] || exit 1
  grep -E "(^|[[:space:]])($OEM_SYS_ROOT)?/dev/mtd(block)?${RJ_TARGET_MTD}(ro)?([[:space:]]|$)" "$file" >/dev/null && exit 1
 done
 for node in "$OEM_SYS_ROOT"/proc/[0-9]*/fd/*;do
  [ -L "$node" ] || continue
  path=$(readlink "$node") || exit 1
  case "$path" in "$OEM_SYS_ROOT/dev/mtd$RJ_TARGET_MTD"|"$OEM_SYS_ROOT/dev/mtd${RJ_TARGET_MTD}ro"|"$OEM_SYS_ROOT/dev/mtdblock$RJ_TARGET_MTD") exit 1;;esac
 done
)
oem_restore_preflight() {
 local file pin label index id name reclaim=0 blocks free captured directory
 oem_jaguar_table && oem_context_check && oem_restore_jaguar_boot_check || return 1
 file=$(oem_restore_jaguar_member operator-artifact-pins) || return 1
 [ "$(wc -l < "$file")" -eq 3 ] || return 1
 RJ_KERNEL_PIN=$(sed -n '1p' "$file");RJ_ROOT_PIN=$(sed -n '2p' "$file");RJ_SHARED_PIN=$(sed -n '3p' "$file")
 for pin in "$RJ_KERNEL_PIN" "$RJ_ROOT_PIN" "$RJ_SHARED_PIN";do oem_hex64 "$pin" || return 1;done
 RJ_KERNEL=$(oem_bundle_member "payloads/$OEM_MODEL/oem/kernel.itb") && RJ_ROOT=$(oem_bundle_member "payloads/$OEM_MODEL/oem/rootfs.squashfs") && RJ_SHARED=$(oem_bundle_member "payloads/$OEM_MODEL/oem/shared.json") || return 1
 [ "$(oem_sha "$RJ_KERNEL")" = "$RJ_KERNEL_PIN" ] && [ "$(oem_sha "$RJ_ROOT")" = "$RJ_ROOT_PIN" ] && [ "$(oem_sha "$RJ_SHARED")" = "$RJ_SHARED_PIN" ] || return 1
 [ "$(oem_read_hex "$RJ_KERNEL" 4)" = d00dfeed ] && [ "$(head -c 4 "$RJ_ROOT")" = hsqs ] || return 1
 RJ_KERNEL_LEBS=$((($(wc -c < "$RJ_KERNEL")+126975)/126976));RJ_ROOT_LEBS=$((($(wc -c < "$RJ_ROOT")+126975)/126976))
 [ "$RJ_KERNEL_LEBS:$RJ_ROOT_LEBS" = 32:337 ] || return 1
 file=$(oem_restore_jaguar_member oem-release) || return 1
 [ "$(wc -l < "$file")" -eq 1 ] && [ "$(cat "$file")" = 7.2-r1 ] || return 1
 file=$(oem_restore_jaguar_physical_profile) || return 1
 OEM_PROTECTED_RANGES=$OEM_WORK/jaguar-restore-ranges.tsv;OEM_WRITE_PLAN=$OEM_WORK/jaguar-restore-plan.tsv
 oem_physical_inventory "$file" "$OEM_SYS_ROOT/sys/class/mtd" "$OEM_PROTECTED_RANGES" || return 1
 awk -F '\t' -v source="$RJ_SOURCE_MTD" -v target="$RJ_TARGET_MTD" -v env="$OEM_JAGUAR_ENV_MTD" '$1==source {if($4!="active-oem")bad=1;s++}$1==target {if($4!="target")bad=1;t++}$1==env {if($4!="environment")bad=1;e++}$4=="target" && $1!=target {bad=1}END{exit bad || s!=1 || t!=1 || e!=1}' "$OEM_PROTECTED_RANGES" || return 1
 for index in "$RJ_SOURCE_MTD" "$RJ_TARGET_MTD";do
  [ "$(cat "$OEM_SYS_ROOT/sys/class/mtd/mtd$index/type")" = nand ] && [ "$(cat "$OEM_SYS_ROOT/sys/class/mtd/mtd$index/size")" = "$OEM_JAGUAR_BANK" ] && [ "$(cat "$OEM_SYS_ROOT/sys/class/mtd/mtd$index/erasesize")" = 131072 ] && [ "$(cat "$OEM_SYS_ROOT/sys/class/mtd/mtd$index/writesize")" = 2048 ] || return 1
 done
 for label in 0:ART mfginfo;do
  index=$(oem_physical_index "$OEM_SYS_ROOT/sys/class/mtd" "$label") || return 1
  case "$label" in 0:ART) RJ_ART_MTD=$index;RJ_ART_PIN=$(oem_sha "$OEM_SYS_ROOT/dev/mtd${index}ro");;esac
 done
 oem_hex64 "$RJ_ART_PIN" || return 1
 for id in 0 1 2 3 4;do
  case "$id" in 0) name=kernel;;1) name=rootfs;;2) name=rootfs_data;;3) name=cambium_device_data;;4) name=certificates;;esac
  oem_ubi_child_check "$OEM_SYS_ROOT/sys/class/ubi" "$RJ_SOURCE_MTD" "$RJ_SOURCE_UBI" "$id" "$name" || return 1
 done
 directory=$(mktemp -d "$OEM_WORK/return-vault.XXXXXX") || return 1
 blocks=$(cat "$OEM_SYS_ROOT/sys/class/ubi/${RJ_SOURCE_UBI}_3/reserved_ebs") || return 1
 oem_restore_jaguar_vault_capture "$OEM_SYS_ROOT/dev/${RJ_SOURCE_UBI}_3" "$directory/source.tar" "$blocks" >/dev/null || return 1
 oem_restore_jaguar_plan || return 1
 if [ -z "$RJ_TARGET_UBI" ];then
  command -v ubiattach >/dev/null 2>&1 && oem_restore_jaguar_unattached_check && oem_restore_jaguar_public_payload_check
  return $?
 fi
 for id in 0 1 2 3 4;do
  case "$id" in 0) name=kernel;;1) name=rootfs;;2) name=rootfs_data;;3) name=cambium_device_data;;4) name=certificates;;esac
  oem_ubi_child_check "$OEM_SYS_ROOT/sys/class/ubi" "$RJ_TARGET_MTD" "$RJ_TARGET_UBI" "$id" "$name" || return 1
  [ "$(cat "$OEM_SYS_ROOT/sys/class/ubi/${RJ_TARGET_UBI}_$id/type")" = dynamic ] || return 1
  [ "$(cat "$OEM_SYS_ROOT/sys/class/ubi/${RJ_TARGET_UBI}_$id/usable_eb_size")" = 126976 ] || return 1
  case "$id" in 0|1|2) blocks=$(cat "$OEM_SYS_ROOT/sys/class/ubi/${RJ_TARGET_UBI}_$id/reserved_ebs") || return 1;reclaim=$((reclaim+blocks));;esac
 done
 [ "$(cat "$OEM_SYS_ROOT/sys/class/ubi/${RJ_TARGET_UBI}_4/reserved_ebs")" = 20 ] || return 1
 RJ_CERT_GEOMETRY=$(oem_restore_jaguar_certificate_geometry) || return 1
 RJ_CERT_PIN=$(oem_sha "$OEM_SYS_ROOT/dev/${RJ_TARGET_UBI}_4") || return 1
 RJ_VAULT_LEBS=$(cat "$OEM_SYS_ROOT/sys/class/ubi/${RJ_TARGET_UBI}_3/reserved_ebs") || return 1
 RJ_VAULT_COPY=$directory/target.tar
 captured=$(oem_restore_jaguar_vault_capture "$OEM_SYS_ROOT/dev/${RJ_TARGET_UBI}_3" "$RJ_VAULT_COPY" "$RJ_VAULT_LEBS") || return 1
 RJ_VAULT_BYTES=$(printf '%s\n' "$captured" | cut -f1);RJ_VAULT_PIN=$(printf '%s\n' "$captured" | cut -f2)
 oem_hex64 "$RJ_VAULT_PIN" || return 1
 RJ_VAULT_TARGET_LEBS=$RJ_VAULT_LEBS
 free=$(cat "$OEM_SYS_ROOT/sys/class/ubi/$RJ_TARGET_UBI/avail_eraseblocks") || return 1
 case "$free:$reclaim" in *[!0-9:]*) return 1;;esac
 if [ "$((free+reclaim))" -lt "$((RJ_KERNEL_LEBS+RJ_ROOT_LEBS))" ];then
  [ "$OEM_MODEL" = XV2-2 ] || return 1
  RJ_VAULT_TARGET_LEBS=$(((RJ_VAULT_BYTES+126975)/126976))
  [ "$RJ_VAULT_TARGET_LEBS" -ge 1 ] && [ "$RJ_VAULT_TARGET_LEBS" -lt "$RJ_VAULT_LEBS" ] &&
   [ "$((free+reclaim+RJ_VAULT_LEBS-RJ_VAULT_TARGET_LEBS))" -ge "$((RJ_KERNEL_LEBS+RJ_ROOT_LEBS))" ] || return 1
 fi
 [ "$RJ_VAULT_TARGET_LEBS" = "$RJ_VAULT_LEBS" ] || printf 'ubi-resize\t%s\t3\tcambium_device_data\n' "$RJ_TARGET_MTD" >> "$OEM_WRITE_PLAN" || return 1
 oem_restore_jaguar_live yes && oem_restore_jaguar_payload_check
}
oem_restore_jaguar_certificate_geometry() (
 local field value
 for field in name reserved_ebs usable_eb_size type alignment data_bytes;do
  value=$(cat "$OEM_SYS_ROOT/sys/class/ubi/${RJ_TARGET_UBI}_4/$field") || exit 1
  printf '%s=%s\n' "$field" "$value"
 done
)
oem_restore_jaguar_live() (
 local file flags blocks
 file=$(oem_restore_jaguar_physical_profile) || exit 1
 oem_physical_inventory "$file" "$OEM_SYS_ROOT/sys/class/mtd" "$OEM_PROTECTED_RANGES" && oem_write_boundary "$OEM_PROTECTED_RANGES" "$OEM_WRITE_PLAN" || exit 1
 flags=$(cat "$OEM_SYS_ROOT/sys/class/mtd/mtd$RJ_TARGET_MTD/flags") || exit 1
 printf '%s\n' "$flags" | awk 'NR!=1 || $0!~/^([0-9]+|0x[0-9a-fA-F]+)$/ {bad=1}END{exit bad}' || exit 1
 [ "$((flags&0x400))" -ne 0 ] && [ "$(cat "$OEM_SYS_ROOT/sys/class/ubi/$RJ_TARGET_UBI/ro_mode")" = 0 ] || exit 1
 oem_bank_idle_check "$OEM_SYS_ROOT/sys/class/ubi" "$OEM_SYS_ROOT/dev" "$OEM_SYS_ROOT/proc" "$RJ_TARGET_MTD" "$RJ_TARGET_UBI" "${1:-no}" || exit 1
 oem_ubi_child_check "$OEM_SYS_ROOT/sys/class/ubi" "$RJ_TARGET_MTD" "$RJ_TARGET_UBI" 4 certificates &&
  [ "$(cat "$OEM_SYS_ROOT/sys/class/ubi/${RJ_TARGET_UBI}_4/type")" = dynamic ] &&
  [ "$(cat "$OEM_SYS_ROOT/sys/class/ubi/${RJ_TARGET_UBI}_4/reserved_ebs")" = 20 ] &&
  [ "$(oem_restore_jaguar_certificate_geometry)" = "$RJ_CERT_GEOMETRY" ] &&
  [ "$(oem_sha "$OEM_SYS_ROOT/dev/${RJ_TARGET_UBI}_4")" = "$RJ_CERT_PIN" ] || exit 1
 oem_ubi_child_check "$OEM_SYS_ROOT/sys/class/ubi" "$RJ_TARGET_MTD" "$RJ_TARGET_UBI" 3 cambium_device_data || exit 1
 [ "$(cat "$OEM_SYS_ROOT/sys/class/ubi/${RJ_TARGET_UBI}_3/type")" = dynamic ] || exit 1
 [ "$(cat "$OEM_SYS_ROOT/sys/class/ubi/${RJ_TARGET_UBI}_3/usable_eb_size")" = 126976 ] || exit 1
 blocks=$(cat "$OEM_SYS_ROOT/sys/class/ubi/${RJ_TARGET_UBI}_3/reserved_ebs") || exit 1
 [ "$blocks" = "$RJ_VAULT_LEBS" ] || [ "$blocks" = "$RJ_VAULT_TARGET_LEBS" ] || exit 1
 [ "$(head -c "$RJ_VAULT_BYTES" "$OEM_SYS_ROOT/dev/${RJ_TARGET_UBI}_3" | sha256sum | awk '{print $1}')" = "$RJ_VAULT_PIN" ]
)
oem_restore_jaguar_write_check() (
 local op=$1 id=$2 name=$3 create=${4:-0}
 oem_restore_jaguar_live && oem_restore_jaguar_payload_check || exit 1
 awk -F '\t' -v op="$op" -v parent="$RJ_TARGET_MTD" -v id="$id" -v name="$name" '$1==op && $2==parent && $3==id && $4==name {n++}END{exit n!=1}' "$OEM_WRITE_PLAN" || exit 1
 if [ "$create" = 1 ];then [ ! -e "$OEM_SYS_ROOT/sys/class/ubi/${RJ_TARGET_UBI}_$id" ]
 else oem_ubi_child_check "$OEM_SYS_ROOT/sys/class/ubi" "$RJ_TARGET_MTD" "$RJ_TARGET_UBI" "$id" "$name";fi
)
oem_restore_recovery() {
 local file
 file=$(oem_restore_jaguar_member critical-backup.tsv) || return 1
 OEM_RECOVERY_DIR=$OEM_WORK/critical
 oem_backup_capture "$file" "$OEM_SYS_ROOT/sys/class/mtd" "$OEM_SYS_ROOT/dev" "$OEM_RECOVERY_DIR" && oem_backup_upload "$OEM_RECOVERY_DIR"
}
oem_restore_jaguar_snapshot() (
 local index offset bytes role domain id name blocks hash ubi
 while IFS="$(printf '\t')" read -r index offset bytes role domain;do
  case "$role" in identity|bootcode) hash=$(oem_sha "$OEM_SYS_ROOT/dev/mtd${index}ro") && oem_hex64 "$hash" || exit 1;printf 'mtd%s %s\n' "$index" "$hash";;esac
 done < "$OEM_PROTECTED_RANGES"
 for ubi in "$RJ_SOURCE_UBI" "$RJ_TARGET_UBI";do
  [ -n "$ubi" ] || continue
  [ "${1:-}" != source-only ] || [ "$ubi" = "$RJ_SOURCE_UBI" ] || continue
  for id in 0 1 2 3 4;do
   [ "$ubi" = "$RJ_SOURCE_UBI" ] || [ "$id" = 4 ] || continue
   name=$(cat "$OEM_SYS_ROOT/sys/class/ubi/${ubi}_$id/name") && blocks=$(cat "$OEM_SYS_ROOT/sys/class/ubi/${ubi}_$id/reserved_ebs") || exit 1
   if [ "$ubi" = "$RJ_SOURCE_UBI" ];then oem_ubi_child_check "$OEM_SYS_ROOT/sys/class/ubi" "$RJ_SOURCE_MTD" "$ubi" "$id" "$name" || exit 1;fi
   case "$id" in 2|4) hash=mutable-no-installer-writes;;*) hash=$(oem_sha "$OEM_SYS_ROOT/dev/${ubi}_$id") || exit 1;;esac
   [ "$ubi:$id" != "$RJ_TARGET_UBI:4" ] || hash=$(oem_sha "$OEM_SYS_ROOT/dev/${ubi}_$id") || exit 1
   printf '%s_%s %s %s %s\n' "$ubi" "$id" "$name" "$blocks" "$hash"
  done
 done
)
oem_restore_jaguar_preserved() {
 oem_restore_jaguar_snapshot > "$OEM_WORK/return-after" && cmp -s "$OEM_WORK/return-before" "$OEM_WORK/return-after" &&
  oem_jaguar_env_read > "$OEM_WORK/return-env-after" && oem_env_preserved "$OEM_WORK/return-env-before" "$OEM_WORK/return-env-after" "$OEM_WORK/return-env-allowed"
}
oem_restore_jaguar_staged_check() (
 local id name file blocks
 oem_restore_jaguar_payload_check && oem_restore_jaguar_live || exit 1
 for id in 0 1;do
  case "$id" in 0) name=kernel;file=$RJ_KERNEL;blocks=$RJ_KERNEL_LEBS;;1) name=ubi_rootfs;file=$RJ_ROOT;blocks=$RJ_ROOT_LEBS;;esac
  oem_ubi_child_check "$OEM_SYS_ROOT/sys/class/ubi" "$RJ_TARGET_MTD" "$RJ_TARGET_UBI" "$id" "$name" &&
   [ "$(cat "$OEM_SYS_ROOT/sys/class/ubi/${RJ_TARGET_UBI}_$id/reserved_ebs")" = "$blocks" ] &&
   [ "$(cat "$OEM_SYS_ROOT/sys/class/ubi/${RJ_TARGET_UBI}_$id/usable_eb_size")" = 126976 ] &&
   oem_jaguar_readback "$file" "$OEM_SYS_ROOT/dev/${RJ_TARGET_UBI}_$id" || exit 1
 done
)
oem_restore_jaguar_save_source() (
 local key value
 oem_restore_jaguar_boot_check || exit 1
 umask 077
 # The old OpenWiFi guard may restore its stable wrapper on rollback. Narrow
 # that wrapper too, so it cannot fall through to the unconfirmed OEM bank.
 printf 'jaguar_stable%s run jaguar_boot%s\nbootcmd run jaguar_boot%s\nimage %s\njaguar_oem_restore_target %s\njaguar_oem_restore_state writing\n' "$OEM_SOURCE_SLOT" "$OEM_SOURCE_SLOT" "$OEM_SOURCE_SLOT" "$OEM_SOURCE_SLOT" "$OEM_TARGET_SLOT" > "$OEM_WORK/return-source.env" || exit 1
 fw_setenv -c "$OEM_JAGUAR_ENV_CONFIG" -s "$OEM_WORK/return-source.env" && sync || exit 1
 while read -r key value;do [ "$(oem_jaguar_env_value "$key")" = "$value" ] || exit 1;done < "$OEM_WORK/return-source.env"
)
oem_restore_jaguar_receipt_live() (
 local kind label bytes reason index
 oem_backup_receipt_check "$OEM_RECOVERY_DIR" || exit 1
 while IFS="$(printf '\t')" read -r kind label bytes reason;do
  index=$(oem_physical_index "$OEM_SYS_ROOT/sys/class/mtd" "$label") || exit 1
  [ "$(oem_sha "$OEM_RECOVERY_DIR/$kind.bin")" = "$(oem_sha "$OEM_SYS_ROOT/dev/mtd${index}ro")" ] || exit 1
 done < "$OEM_RECOVERY_DIR/manifest.tsv"
)
oem_restore_migrate() (
 local id name file blocks key value trial context
 context=$(oem_context_fingerprint) || exit 1
 oem_restore_inspect && [ "$(oem_context_fingerprint)" = "$context" ] && oem_restore_preflight && oem_restore_boot_preflight && oem_restore_jaguar_receipt_live || exit 1
 oem_restore_jaguar_snapshot > "$OEM_WORK/return-before" && oem_jaguar_env_read > "$OEM_WORK/return-env-before" || exit 1
 printf '%s\n' bootcmd image jaguar_oem_restore_target jaguar_oem_restore_state jaguar_ab_state jaguar_ab_target "jaguar_oem_boot$OEM_TARGET_SLOT" "jaguar_stable$OEM_SOURCE_SLOT" > "$OEM_WORK/return-env-allowed" || exit 1
 oem_restore_jaguar_public_payload_check && oem_restore_jaguar_save_source || exit 1
 if [ -z "$RJ_TARGET_UBI" ];then
  oem_restore_jaguar_snapshot source-only > "$OEM_WORK/source-before-attach" || exit 1
  oem_restore_jaguar_unattached_check && oem_restore_jaguar_boot_check && oem_restore_jaguar_public_payload_check || exit 1
  ubiattach -m "$RJ_TARGET_MTD" || exit 1
  RJ_TARGET_UBI=$(oem_restore_jaguar_ubi "$RJ_TARGET_MTD") && [ -n "$RJ_TARGET_UBI" ] && [ "$RJ_TARGET_UBI" != "$RJ_SOURCE_UBI" ] || exit 1
  oem_restore_preflight && oem_restore_jaguar_snapshot source-only > "$OEM_WORK/source-after-attach" && cmp -s "$OEM_WORK/source-before-attach" "$OEM_WORK/source-after-attach" || exit 1
  # The target certificate baseline starts AFTER actual attachment discovery;
  # no pre-attach byte/geometry proof is claimed. Erase/resize is still pending.
  oem_restore_jaguar_snapshot > "$OEM_WORK/return-before" || exit 1
 fi
 # The existing shared helper removes only the proved inactive rootfs map.
 # Source-only persistence/readback and discovered vault/cert proof precede it.
 oem_restore_jaguar_payload_check && oem_restore_jaguar_preserved &&
  oem_bank_remove_idle_root_map "$OEM_SYS_ROOT/sys/class/ubi" "$OEM_SYS_ROOT/dev" "$OEM_SYS_ROOT/proc" "$RJ_TARGET_MTD" "$RJ_TARGET_UBI" || exit 1
 if [ "$RJ_VAULT_TARGET_LEBS" != "$RJ_VAULT_LEBS" ];then
  oem_restore_jaguar_write_check ubi-resize 3 cambium_device_data && ubirsvol "$OEM_SYS_ROOT/dev/$RJ_TARGET_UBI" -n 3 -s "$((RJ_VAULT_TARGET_LEBS*126976))" && sync || exit 1
  [ "$(cat "$OEM_SYS_ROOT/sys/class/ubi/${RJ_TARGET_UBI}_3/reserved_ebs")" = "$RJ_VAULT_TARGET_LEBS" ] &&
   [ "$(head -c "$RJ_VAULT_BYTES" "$OEM_SYS_ROOT/dev/${RJ_TARGET_UBI}_3" | sha256sum | awk '{print $1}')" = "$RJ_VAULT_PIN" ] || exit 1
 fi
 for id in 2 1 0;do
  case "$id" in 0) name=kernel;;1) name=rootfs;;2) name=rootfs_data;;esac
  oem_restore_jaguar_write_check ubi-remove "$id" "$name" && ubirmvol "$OEM_SYS_ROOT/dev/$RJ_TARGET_UBI" -n "$id" || exit 1
 done
 for id in 0 1;do
  case "$id" in 0) name=kernel;blocks=$RJ_KERNEL_LEBS;;1) name=ubi_rootfs;blocks=$RJ_ROOT_LEBS;;esac
  oem_restore_jaguar_write_check ubi-create "$id" "$name" 1 && ubimkvol "$OEM_SYS_ROOT/dev/$RJ_TARGET_UBI" -n "$id" -N "$name" -s "$((blocks*126976))" || exit 1
 done
 for id in 0 1;do
  case "$id" in 0) name=kernel;file=$RJ_KERNEL;;1) name=ubi_rootfs;file=$RJ_ROOT;;esac
  oem_restore_jaguar_write_check ubi-update "$id" "$name" && ubiupdatevol "$OEM_SYS_ROOT/dev/${RJ_TARGET_UBI}_$id" "$file" && sync && oem_jaguar_readback "$file" "$OEM_SYS_ROOT/dev/${RJ_TARGET_UBI}_$id" || exit 1
 done
 oem_restore_jaguar_staged_check && oem_restore_jaguar_preserved && oem_restore_jaguar_boot_check || exit 1
 printf 'jaguar_oem_boot%s setenv image %s; bootipq\njaguar_oem_restore_state armed\njaguar_ab_target %s\njaguar_ab_state armed\n' "$OEM_TARGET_SLOT" "$OEM_TARGET_SLOT" "$OEM_TARGET_SLOT" > "$OEM_WORK/return-arm.env" || exit 1
 fw_setenv -c "$OEM_JAGUAR_ENV_CONFIG" -s "$OEM_WORK/return-arm.env" && sync || exit 1
 while read -r key value;do [ "$(oem_jaguar_env_value "$key")" = "$value" ] || exit 1;done < "$OEM_WORK/return-arm.env"
 oem_restore_jaguar_staged_check && oem_restore_jaguar_preserved && oem_restore_jaguar_boot_check || exit 1
 while read -r key value;do [ "$(oem_jaguar_env_value "$key")" = "$value" ] || exit 1;done < "$OEM_WORK/return-arm.env"
 [ "$(oem_jaguar_env_value "jaguar_stable$OEM_SOURCE_SLOT")" = "run jaguar_boot$OEM_SOURCE_SLOT" ] || exit 1
 trial="setenv bootcmd run jaguar_boot$OEM_SOURCE_SLOT && setenv image $OEM_SOURCE_SLOT && setenv jaguar_oem_restore_state trial-started && saveenv && run jaguar_oem_boot$OEM_TARGET_SLOT; run jaguar_boot$OEM_SOURCE_SLOT"
 fw_setenv -c "$OEM_JAGUAR_ENV_CONFIG" bootcmd "$trial" && sync && [ "$(oem_jaguar_env_value bootcmd)" = "$trial" ] || exit 1
 printf 'handoff=one-shot-oem-armed\noem_boot=not-yet-verified\nidentity_retired=no\ndefaults_committed=no\n'
)
