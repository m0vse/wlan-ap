#!/bin/sh
# Exact Jaguar OEM inspection. No stock sysupgrade source is silently admitted
# as an OEM writer. Publication must supply the closed bank/payload/BDF tuple.
oem_jaguar_member() { oem_bundle_member "profiles/$OEM_MODEL/$1"; }
oem_jaguar_table() {
 case "$OEM_FAMILY:$OEM_MODEL:$OEM_SKU" in
  jaguar:XV2-2:00000014) OEM_JAGUAR_BANK=54525952 OEM_JAGUAR_FIT=config@cp01-c1 OEM_JAGUAR_LEBS=392;;
  jaguar:XV2-2T1:0000001f) OEM_JAGUAR_BANK=100663296 OEM_JAGUAR_FIT=config@cp01-c1-2 OEM_JAGUAR_LEBS=724;;
  jaguar:XE3-4:00000020) OEM_JAGUAR_BANK=100663296 OEM_JAGUAR_FIT=config@cp01-c3-xv3-4 OEM_JAGUAR_LEBS=724;;
  *) oem_fail 'this Jaguar model/SKU has no exact OEM adapter'; return 1;;
 esac
}
oem_jaguar_env_read() (
 set +x; set +a; unset oem_private_environment_blob
 oem_private_environment_blob=$(fw_printenv -c "$OEM_JAGUAR_ENV_CONFIG" 2>&1) || exit 1
 printf '%s\n' "$oem_private_environment_blob" | awk '
  {i=index($0,"=");key=substr($0,1,i-1);if(!i || key!~/^[A-Za-z0-9_#.-]+$/ || seen[key]++)bad=1}
  END{exit bad || NR<1}' || exit 1
 printf '%s\n' "$oem_private_environment_blob"
)
oem_jaguar_env_value() {
 oem_jaguar_env_read | awk -v key="$1" '{i=index($0,"=");if(substr($0,1,i-1)==key){value=substr($0,i+1);n++}} END{if(n!=1)exit 1;print value}'
}
oem_jaguar_config() {
 local file text normalized= index offset size erase sectors
 index=$(oem_physical_index "$OEM_SYS_ROOT/sys/class/mtd" 0:APPSBLENV) || return 1
 OEM_JAGUAR_ENV_MTD=$index
 for file in "$OEM_SYS_ROOT/etc/fw_env.config" "$OEM_SYS_ROOT/tmp/fw_env.config"; do
  [ -r "$file" ] || continue
  [ ! -L "$file" ] || return 1
  text=$(awk '!/^#/ && NF {sub(/[[:space:]]*#.*/,"");if(NF) print}' "$file") || return 1
  [ "$(printf '%s\n' "$text" | wc -l)" -eq 1 ] || return 1
  [ -z "$normalized" ] || [ "$normalized" = "$text" ] || return 1
  normalized=$text OEM_JAGUAR_ENV_CONFIG=$file
 done
 [ -n "$normalized" ] || return 1
 set -- $normalized
 [ "$#" -ge 3 ] && [ "$#" -le 5 ] && [ "$1" = "/dev/mtd$index" ] || return 1
 offset=$2 size=$3 erase=${4:-65536} sectors=${5:-1}
 case "$offset" in 0|0x0|0x00|0x0000) ;; *) return 1;; esac
 for text in "$size" "$erase"; do case "$text" in 65536|0x10000|0x00010000) ;; *) return 1;; esac; done
 [ "$sectors" = 1 ] && [ "$(cat "$OEM_SYS_ROOT/sys/class/mtd/mtd$index/size")" = 65536 ] && [ "$(cat "$OEM_SYS_ROOT/sys/class/mtd/mtd$index/type")" = nor ]
}
oem_adapter_inspect() {
 local product label rootarg= attachment= argument index header serial state
 OEM_SERIAL= OEM_SOURCE_RELEASE= OEM_SOURCE_SLOT= OEM_TARGET_SLOT=
 oem_jaguar_table && oem_jaguar_config || return 1
 [ ! -e "$OEM_SYS_ROOT/etc/openwrt_release" ] || return 1
 OEM_SOURCE_RELEASE=$(oem_read_release "$OEM_SYS_ROOT/etc/version") || return 1
 product=$(awk -F= '$1=="PRODUCT" {v=$2;n++} END{if(n!=1)exit 1;print v}' "$OEM_SYS_ROOT/etc/version") || return 1
 [ "$product" = jaguar ] && [ "$OEM_SOURCE_RELEASE" = 7.2-r1 ] || { oem_fail 'Jaguar OEM source is not the reviewed 7.2-r1 baseline'; return 1; }
 oem_jaguar_env_read >/dev/null || return 1
 [ "$(oem_jaguar_env_value bootcmd)" = bootipq ] || return 1
 for argument in $(cat "$OEM_SYS_ROOT/proc/cmdline"); do
  case "$argument" in root=*) [ -z "$rootarg" ] || return 1; rootarg=${argument#root=};; ubi.mtd=*) [ -z "$attachment" ] || return 1; attachment=${argument#ubi.mtd=};; esac
 done
 case "$rootarg" in mtd:ubi_rootfs|ubi0:ubi_rootfs|/dev/ubiblock0_1) ;; *) return 1;; esac
 case "$attachment" in rootfs) OEM_SOURCE_SLOT=0;; rootfs_1) OEM_SOURCE_SLOT=1;; *) return 1;; esac
 OEM_TARGET_SLOT=$((1-OEM_SOURCE_SLOT))
 [ "$(oem_jaguar_env_value image)" = "$OEM_SOURCE_SLOT" ] || return 1
 OEM_JAGUAR_SOURCE_MTD=$(oem_physical_index "$OEM_SYS_ROOT/sys/class/mtd" "$attachment") || return 1
 if [ "$OEM_TARGET_SLOT" = 0 ]; then label=rootfs; else label=rootfs_1; fi
 OEM_JAGUAR_TARGET_MTD=$(oem_physical_index "$OEM_SYS_ROOT/sys/class/mtd" "$label") || return 1
 [ "$OEM_JAGUAR_SOURCE_MTD" != "$OEM_JAGUAR_TARGET_MTD" ] || return 1
 for index in "$OEM_JAGUAR_SOURCE_MTD" "$OEM_JAGUAR_TARGET_MTD"; do
  [ "$(cat "$OEM_SYS_ROOT/sys/class/mtd/mtd$index/type")" = nand ] && [ "$(cat "$OEM_SYS_ROOT/sys/class/mtd/mtd$index/size")" = "$OEM_JAGUAR_BANK" ] && [ "$(cat "$OEM_SYS_ROOT/sys/class/mtd/mtd$index/erasesize")" = 131072 ] && [ "$(cat "$OEM_SYS_ROOT/sys/class/mtd/mtd$index/writesize")" = 2048 ] || return 1
 done
 for state in "rootfs:0" "rootfs_1:$OEM_JAGUAR_BANK"; do
  label=${state%%:*}; index=$(oem_physical_index "$OEM_SYS_ROOT/sys/class/mtd" "$label") || return 1
  [ "$(cat "$OEM_SYS_ROOT/sys/class/mtd/mtd$index/offset")" = "${state#*:}" ] || return 1
 done
 [ "$(cat "$OEM_SYS_ROOT/sys/class/ubi/ubi0/mtd_num")" = "$OEM_JAGUAR_SOURCE_MTD" ] && [ "$(cat "$OEM_SYS_ROOT/sys/class/ubi/ubi0/eraseblock_size")" = 126976 ] && [ "$(cat "$OEM_SYS_ROOT/sys/class/ubi/ubi0/min_io_size")" = 2048 ] || return 1
 oem_ubi_child_check "$OEM_SYS_ROOT/sys/class/ubi" "$OEM_JAGUAR_SOURCE_MTD" ubi0 0 kernel && oem_ubi_child_check "$OEM_SYS_ROOT/sys/class/ubi" "$OEM_JAGUAR_SOURCE_MTD" ubi0 1 ubi_rootfs || return 1
 index=$(oem_physical_index "$OEM_SYS_ROOT/sys/class/mtd" mfginfo) || return 1
 [ "$(cat "$OEM_SYS_ROOT/sys/class/mtd/mtd$index/size")" = 65536 ] || return 1
 if command -v hexdump >/dev/null 2>&1; then
  header=$(head -c 6 "$OEM_SYS_ROOT/dev/mtd${index}ro" | hexdump -v -e '1/1 "%02x"') || return 1
 else
  header=$(od -An -tx1 -N6 "$OEM_SYS_ROOT/dev/mtd${index}ro" | tr -d ' \n') || return 1
 fi
 [ "$header" = 05ca01000c00 ] || { oem_fail 'Jaguar manufacturing label format is not recognized'; return 1; }
 serial=$(dd if="$OEM_SYS_ROOT/dev/mtd${index}ro" bs=1 skip=6 count=12 2>/dev/null | tr 'A-F' 'a-f') || return 1
 case "$serial" in ''|*[!0-9a-f]*|000000000000|ffffffffffff) return 1;; esac
 [ "${#serial}" = 12 ] || return 1
 case "$(printf '%s' "$serial" | cut -c2)" in 1|3|5|7|9|b|d|f) return 1;; esac
 OEM_SERIAL=$serial
 # A complete read prevents missing-key errors from hiding unreadable ENV.
 oem_jaguar_env_read | awk -F= '$1=="changing_bootcmd" || $1~/^jaguar_(installer_(target|job|image)|storage_pending|ab_version)$/ {if(NF!=2 || length($2) || seen[$1]++)bad=1} END{exit bad}' || return 1
 oem_context_check
}
oem_adapter_preflight() {
 local profile member pin label index
 oem_jaguar_table && oem_context_check || return 1
 member=$(oem_jaguar_member source-sets/runtime-implementation.set) || return 1
 profile=$(oem_bundle_member adapters/required-source.sh) || return 1
 . "$profile" || return 1
 oem_required_source_check "$member" "$OEM_SYS_ROOT" /etc/version sh awk sed grep cmp dd head sha256sum fw_printenv fw_setenv ubiattach ubiupdatevol ubimkvol ubirmvol mount umount tar || return 1
 member=$(oem_jaguar_member source-contract) || return 1
 [ "$(wc -l < "$member")" -eq 2 ] && [ "$(sed -n '1p' "$member")" = "$OEM_SOURCE_RELEASE" ] || return 1
 OEM_JAGUAR_CONTRACT=$(sed -n '2p' "$member");oem_hex64 "$OEM_JAGUAR_CONTRACT" || return 1
 member=$(oem_jaguar_member operator-artifact-pins) || return 1
 [ "$(wc -l < "$member")" -eq 3 ] || return 1
 OEM_JAGUAR_IMAGE_PIN=$(sed -n '1p' "$member") OEM_JAGUAR_KERNEL_PIN=$(sed -n '2p' "$member") OEM_JAGUAR_ROOT_PIN=$(sed -n '3p' "$member")
 for pin in "$OEM_JAGUAR_IMAGE_PIN" "$OEM_JAGUAR_KERNEL_PIN" "$OEM_JAGUAR_ROOT_PIN";do oem_hex64 "$pin" || return 1;done
 OEM_JAGUAR_IMAGE=$(oem_bundle_member "payloads/$OEM_MODEL/image.bin") &&
  OEM_JAGUAR_KERNEL=$(oem_bundle_member "payloads/$OEM_MODEL/kernel.itb") &&
  OEM_JAGUAR_ROOT=$(oem_bundle_member "payloads/$OEM_MODEL/rootfs.squashfs") || return 1
 [ "$(oem_sha "$OEM_JAGUAR_IMAGE")" = "$OEM_JAGUAR_IMAGE_PIN" ] && [ "$(oem_sha "$OEM_JAGUAR_KERNEL")" = "$OEM_JAGUAR_KERNEL_PIN" ] && [ "$(oem_sha "$OEM_JAGUAR_ROOT")" = "$OEM_JAGUAR_ROOT_PIN" ] || return 1
 member=$(oem_jaguar_member fit.tsv) || return 1
 awk -F '\t' -v hash="$OEM_JAGUAR_KERNEL_PIN" -v model="$OEM_MODEL" -v sku="$OEM_SKU" -v fit="$OEM_JAGUAR_FIT" \
  'NF!=4 || $1!=hash || $2!=model || $3!=sku || $4!=fit {bad=1} END{exit bad || NR!=1}' "$member" || return 1
 profile=$(oem_jaguar_member mtd.tsv) || return 1
 OEM_PROTECTED_RANGES=$OEM_WORK/jaguar-ranges.tsv OEM_WRITE_PLAN=$OEM_WORK/jaguar-write-plan.tsv
 oem_physical_inventory "$profile" "$OEM_SYS_ROOT/sys/class/mtd" "$OEM_PROTECTED_RANGES" || return 1
 awk -F '\t' -v active="$OEM_JAGUAR_SOURCE_MTD" -v target="$OEM_JAGUAR_TARGET_MTD" -v env="$OEM_JAGUAR_ENV_MTD" \
  '$1==active {if($4!="active-oem")bad=1;a++} $1==target {if($4!="target")bad=1;t++} $1==env {if($4!="environment")bad=1;e++} $4=="target" && $1!=target {bad=1} END{exit bad || a!=1 || t!=1 || e!=1}' "$OEM_PROTECTED_RANGES" || return 1
 for label in 0:ART mfginfo 0:APPSBLENV;do
  index=$(oem_physical_index "$OEM_SYS_ROOT/sys/class/mtd" "$label") || return 1
  case "$label" in 0:ART) OEM_JAGUAR_ART_MTD=$index;;mfginfo) OEM_JAGUAR_MFG_MTD=$index;;esac
 done
 : > "$OEM_WRITE_PLAN" || return 1
 printf 'ubi-remove\t%s\t0\tkernel\nubi-remove\t%s\t1\tubi_rootfs\n' "$OEM_JAGUAR_TARGET_MTD" "$OEM_JAGUAR_TARGET_MTD" >> "$OEM_WRITE_PLAN"
 for label in '0 kernel' '1 rootfs' '2 rootfs_data' '3 cambium_device_data' '4 certificates';do
  set -- $label
  printf 'ubi-create\t%s\t%s\t%s\n' "$OEM_JAGUAR_TARGET_MTD" "$1" "$2" >> "$OEM_WRITE_PLAN" || return 1
  case "$1" in 0|1|3) printf 'ubi-update\t%s\t%s\t%s\n' "$OEM_JAGUAR_TARGET_MTD" "$1" "$2" >> "$OEM_WRITE_PLAN";;esac
 done
 printf 'environment-fields\t%s\tfields\tpreserve-unlisted\n' "$OEM_JAGUAR_ENV_MTD" >> "$OEM_WRITE_PLAN" || return 1
 oem_write_boundary "$OEM_PROTECTED_RANGES" "$OEM_WRITE_PLAN" && oem_jaguar_payload_capacity && oem_jaguar_assets_check || return 1
 profile=$(oem_bundle_member lib/cambium-installer-settings.sh) || return 1
 . "$profile" || return 1
 oem_adapter_boot_preflight
}
oem_adapter_recovery() {
 local plan
 plan=$(oem_jaguar_member critical-backup.tsv) || return 1
 OEM_RECOVERY_DIR=$OEM_WORK/critical
 oem_backup_capture "$plan" "$OEM_SYS_ROOT/sys/class/mtd" "$OEM_SYS_ROOT/dev" "$OEM_RECOVERY_DIR" && oem_backup_upload "$OEM_RECOVERY_DIR"
}

oem_jaguar_payload_capacity() {
 local kernel root magic
 kernel=$(wc -c < "$OEM_JAGUAR_KERNEL") && root=$(wc -c < "$OEM_JAGUAR_ROOT") || return 1
 case "$kernel:$root" in *[!0-9[:space:]:]*|0:*|*:0) return 1;;esac
 if command -v hexdump >/dev/null 2>&1;then magic=$(head -c 4 "$OEM_JAGUAR_KERNEL" | hexdump -v -e '1/1 "%02x"')
 else magic=$(od -An -tx1 -N4 "$OEM_JAGUAR_KERNEL" | tr -d ' \n');fi
 [ "$magic" = d00dfeed ] && [ "$(head -c 4 "$OEM_JAGUAR_ROOT")" = hsqs ] || return 1
 OEM_JAGUAR_KERNEL_LEBS=$(((kernel+126975)/126976))
 OEM_JAGUAR_ROOT_LEBS=$(((root+126975)/126976))
 OEM_JAGUAR_DATA_LEBS=$((OEM_JAGUAR_LEBS-OEM_JAGUAR_KERNEL_LEBS-OEM_JAGUAR_ROOT_LEBS-8-20))
 [ "$OEM_JAGUAR_KERNEL_LEBS" -gt 0 ] && [ "$OEM_JAGUAR_ROOT_LEBS" -gt 0 ] && [ "$OEM_JAGUAR_DATA_LEBS" -ge 67 ]
}
oem_jaguar_payload_hash_check() {
 [ "$(oem_sha "$OEM_JAGUAR_IMAGE")" = "$OEM_JAGUAR_IMAGE_PIN" ] &&
  [ "$(oem_sha "$OEM_JAGUAR_KERNEL")" = "$OEM_JAGUAR_KERNEL_PIN" ] &&
  [ "$(oem_sha "$OEM_JAGUAR_ROOT")" = "$OEM_JAGUAR_ROOT_PIN" ] &&
  [ "$(oem_sha "$OEM_WORK/jaguar-vault.tar")" = "$OEM_JAGUAR_VAULT_PIN" ]
}
oem_jaguar_assets_check() {
 local table src size digest file count=0 expected
 table=$(oem_jaguar_member radio-assets.tsv) || return 1
 awk -F '\t' 'NF!=3 || $1!~/^[A-Za-z0-9_.\/-]+$/ || $1~/(^|\/)\.\.?(\/|$)/ || seen[$1]++ || $2!~/^[0-9]+$/ || length($3)!=64 || $3~/[^0-9a-f]/ {bad=1} END{exit bad || NR<1 || NR>2}' "$table" || return 1
 while IFS="$(printf '\t')" read -r src size digest;do
  case "$OEM_MODEL:$src:$size" in
   XV2-2:lib/firmware/IPQ6018/WIFI_FW/bdwlan.b13.stock:65536|XV2-2T1:lib/firmware/IPQ6018/WIFI_FW/bdwlan.b13.stock:65536|XE3-4:lib/firmware/IPQ6018/WIFI_FW/bdwlan.b10-puma:65536|XE3-4:lib/firmware/qcn9000/WIFI_FW/bdwlan.bab-puma:131072) ;;
   *) return 1;;
  esac
  file=$(oem_bundle_member "payloads/$OEM_MODEL/assets/$src") || return 1
  [ "$(wc -c < "$file")" -eq "$size" ] && [ "$(oem_sha "$file")" = "$digest" ] || return 1
  count=$((count+1))
 done < "$table"
 expected=1;[ "$OEM_MODEL" != XE3-4 ] || expected=2
 [ "$count" = "$expected" ]
}
oem_jaguar_vault_prepare() (
 local table src size digest file board
 oem_jaguar_assets_check || exit 1
 table=$(oem_jaguar_member radio-assets.tsv) || exit 1
 board=$(oem_jaguar_member vault-board) || exit 1
 [ "$(wc -l < "$board")" -eq 1 ] || exit 1
 board=$(cat "$board")
 case "$OEM_MODEL:$board" in
  # This is the incoming kernel board_name, NOT controller compatible/model.
  # The packaged format-1 consumer compares it literally and has board_files
  # only for these labels; cambium,MODEL/generic jaguar are not aliases there.
  XV2-2:cambiumnetworks,xv2-2|XV2-2T1:cambiumnetworks,xv2-2t1|XE3-4:cambiumnetworks,xe3-4) ;;
  *) exit 1;;
 esac
 umask 077
 directory=$OEM_WORK/jaguar-vault
 [ ! -e "$directory" ] && mkdir -m 700 "$directory" && mkdir -m 700 "$directory/files" || exit 1
 {
  printf 'format 1\nboard %s\nsku %s\nart_sha256 %s\nnvram_sha256_at_capture unknown\nsource reviewed-oem-assets\ncreated %s\n' \
   "$board" "$OEM_SKU" "$(oem_sha "$OEM_SYS_ROOT/dev/mtd${OEM_JAGUAR_ART_MTD}ro")" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  while IFS="$(printf '\t')" read -r src size digest;do
   file=$(oem_bundle_member "payloads/$OEM_MODEL/assets/$src") || exit 1
   mkdir -p "$directory/files/${src%/*}" && cp "$file" "$directory/files/$src" && chmod 600 "$directory/files/$src" || exit 1
   [ "$(oem_sha "$directory/files/$src")" = "$digest" ] || exit 1
   printf 'file %s %s %s\n' "$src" "$size" "$digest"
  done < "$table"
 } > "$directory/MANIFEST" || exit 1
 (cd "$directory" && tar -cf "$OEM_WORK/jaguar-vault.tar" MANIFEST files) || exit 1
 chmod 600 "$OEM_WORK/jaguar-vault.tar" && [ "$(wc -c < "$OEM_WORK/jaguar-vault.tar")" -le 1015808 ]
)
oem_jaguar_target_locate() {
 local node found= count=0
 for node in "$OEM_SYS_ROOT"/sys/class/ubi/ubi*/mtd_num;do
  [ -r "$node" ] || continue
  [ "$(cat "$node")" = "$OEM_JAGUAR_TARGET_MTD" ] || continue
  found=${node%/mtd_num};found=${found##*/};count=$((count+1))
 done
 [ "$count" -le 1 ] || return 1
 OEM_JAGUAR_TARGET_UBI=$found
}
oem_jaguar_live_target() (
 local profile flags
 oem_jaguar_table && oem_context_check || exit 1
 profile=$(oem_jaguar_member mtd.tsv) || exit 1
 oem_physical_inventory "$profile" "$OEM_SYS_ROOT/sys/class/mtd" "$OEM_PROTECTED_RANGES" && oem_write_boundary "$OEM_PROTECTED_RANGES" "$OEM_WRITE_PLAN" || exit 1
 [ "$OEM_JAGUAR_SOURCE_MTD" != "$OEM_JAGUAR_TARGET_MTD" ] || exit 1
 flags=$(cat "$OEM_SYS_ROOT/sys/class/mtd/mtd$OEM_JAGUAR_TARGET_MTD/flags") || exit 1
 printf '%s\n' "$flags" | awk 'NR!=1 || $0!~/^([0-9]+|0x[0-9a-fA-F]+)$/ {bad=1}END{exit bad}' || exit 1
 [ "$((flags&0x400))" -ne 0 ] || exit 1
 [ "$(cat "$OEM_SYS_ROOT/sys/class/ubi/$OEM_JAGUAR_TARGET_UBI/ro_mode")" = 0 ] &&
  [ "$(cat "$OEM_SYS_ROOT/sys/class/ubi/$OEM_JAGUAR_TARGET_UBI/eraseblock_size")" = 126976 ] &&
  [ "$(cat "$OEM_SYS_ROOT/sys/class/ubi/$OEM_JAGUAR_TARGET_UBI/min_io_size")" = 2048 ] || exit 1
 oem_bank_idle_check "$OEM_SYS_ROOT/sys/class/ubi" "$OEM_SYS_ROOT/dev" "$OEM_SYS_ROOT/proc" "$OEM_JAGUAR_TARGET_MTD" "$OEM_JAGUAR_TARGET_UBI" no
)
oem_jaguar_write_check() (
 local operation=$1 id=$2 name=$3 absent=${4:-0} sys=$OEM_SYS_ROOT/sys/class/ubi device=$OEM_JAGUAR_TARGET_UBI node count=0
 oem_jaguar_live_target || exit 1
 awk -F '\t' -v op="$operation" -v parent="$OEM_JAGUAR_TARGET_MTD" -v id="$id" -v name="$name" \
  '$1==op && $2==parent && $3==id && $4==name {n++}END{exit n!=1}' "$OEM_WRITE_PLAN" || exit 1
 if [ "$absent" = 1 ];then
  [ ! -e "$sys/${device}_$id" ] || exit 1
  for node in "$sys/$device"_*/name;do [ -r "$node" ] || continue;[ "$(cat "$node")" != "$name" ] || exit 1;done
  [ "$(cat "$sys/$device/mtd_num")" = "$OEM_JAGUAR_TARGET_MTD" ] || exit 1
  for node in "$sys"/ubi*/mtd_num;do [ -r "$node" ] || continue;[ "$(cat "$node")" != "$OEM_JAGUAR_TARGET_MTD" ] || count=$((count+1));done
  [ "$count" = 1 ]
 else oem_ubi_child_check "$sys" "$OEM_JAGUAR_TARGET_MTD" "$device" "$id" "$name";fi
)
oem_jaguar_readback() {
 local file=$1 device=$2 bytes expected actual
 bytes=$(wc -c < "$file") && expected=$(oem_sha "$file") || return 1
 actual=$(head -c "$bytes" "$device" | sha256sum | awk '{print $1}') || return 1
 [ "$actual" = "$expected" ]
}
oem_jaguar_stage_bank() (
 local sys=$OEM_SYS_ROOT/sys/class/ubi dev=$OEM_SYS_ROOT/dev device=$OEM_JAGUAR_TARGET_UBI node name id count=0 free blocks
 oem_jaguar_payload_hash_check && oem_jaguar_payload_capacity && oem_jaguar_live_target || exit 1
 # Fresh OEM bank contains only the two known software volumes. Existing
 # native identity is never guessed, removed or replaced by this fresh path.
 for node in "$sys/$device"_*/name;do
  [ -r "$node" ] || continue
  id=${node%/name};id=${id##*_};name=$(cat "$node") || exit 1
  case "$id:$name" in 0:kernel|1:ubi_rootfs) ;; *) oem_fail 'inactive bank has retained identity or an unknown namespace; no erase authorized';exit 1;;esac
  oem_ubi_child_check "$sys" "$OEM_JAGUAR_TARGET_MTD" "$device" "$id" "$name" || exit 1
  count=$((count+1))
 done
 [ "$count" = 2 ] || exit 1
 free=$(cat "$sys/$device/avail_eraseblocks") || exit 1
 case "$free" in ''|*[!0-9]*) exit 1;;esac
 for id in 0 1;do blocks=$(cat "$sys/${device}_$id/reserved_ebs") || exit 1;case "$blocks" in ''|*[!0-9]*) exit 1;;esac;free=$((free+blocks));done
 [ "$free" -ge "$OEM_JAGUAR_LEBS" ] || exit 1
 for id in 0 1;do
  name=kernel;[ "$id" = 0 ] || name=ubi_rootfs
  oem_jaguar_write_check ubi-remove "$id" "$name" && ubirmvol "$dev/$device" -n "$id" || exit 1
 done
 for name in kernel rootfs rootfs_data cambium_device_data certificates;do
  case "$name" in kernel) id=0;blocks=$OEM_JAGUAR_KERNEL_LEBS;;rootfs) id=1;blocks=$OEM_JAGUAR_ROOT_LEBS;;rootfs_data) id=2;blocks=$OEM_JAGUAR_DATA_LEBS;;cambium_device_data) id=3;blocks=8;;certificates) id=4;blocks=20;;esac
  oem_jaguar_write_check ubi-create "$id" "$name" 1 && ubimkvol "$dev/$device" -n "$id" -N "$name" -s "$((blocks*126976))" || exit 1
 done
 for id in 0 1 3;do
  case "$id" in 0) name=kernel;file=$OEM_JAGUAR_KERNEL;;1) name=rootfs;file=$OEM_JAGUAR_ROOT;;3) name=cambium_device_data;file=$OEM_WORK/jaguar-vault.tar;;esac
  oem_jaguar_payload_hash_check && oem_jaguar_write_check ubi-update "$id" "$name" && ubiupdatevol "$dev/${device}_$id" "$file" && sync && oem_jaguar_readback "$file" "$dev/${device}_$id" && oem_jaguar_payload_hash_check || exit 1
 done
)
oem_jaguar_protected_snapshot() (
 local node id name bytes hash index role offset size domain
 while IFS="$(printf '\t')" read -r index offset size role domain;do
  case "$role" in identity|bootcode) hash=$(oem_sha "$OEM_SYS_ROOT/dev/mtd${index}ro") && oem_hex64 "$hash" || exit 1;printf 'mtd%s %s\n' "$index" "$hash";;esac
 done < "$OEM_PROTECTED_RANGES"
 # Source software is immutable SquashFS/FIT; no customer-config export.
 for id in 0 1;do
  node=$OEM_SYS_ROOT/sys/class/ubi/ubi0_$id
  name=$(cat "$node/name") && bytes=$(cat "$node/reserved_ebs") || exit 1
  oem_ubi_child_check "$OEM_SYS_ROOT/sys/class/ubi" "$OEM_JAGUAR_SOURCE_MTD" ubi0 "$id" "$name" || exit 1
  hash=$(oem_sha "$OEM_SYS_ROOT/dev/ubi0_$id") && oem_hex64 "$hash" || exit 1
  printf 'source%s %s %s %s\n' "$id" "$name" "$bytes" "$hash"
 done
)
oem_adapter_migrate() (
 set +x;set +a;unset credential
 local credential=$1 job member mountpoint= key kind label size reason index
 oem_adapter_inspect && oem_adapter_preflight && oem_adapter_boot_preflight || exit 1
 oem_backup_receipt_check "$OEM_RECOVERY_DIR" || exit 1
 OW_SETTINGS_SYS=$OEM_SYS_ROOT/sys/class/ubi OW_SETTINGS_DEV=$OEM_SYS_ROOT/dev OW_SETTINGS_MOUNTS=$OEM_SYS_ROOT/proc/mounts OW_SETTINGS_OWNER=0
 OW_EXPECT_SERIAL=$OEM_SERIAL OW_EXPECT_FAMILY=jaguar OW_EXPECT_MODEL=$OEM_MODEL
 OW_EXPECT_OPERATION=production-oem-migration OW_EXPECT_RELEASE=$OEM_SOURCE_RELEASE OW_EXPECT_CONTRACT=$OEM_JAGUAR_CONTRACT OW_EXPECT_SOURCE=$OEM_SOURCE_SLOT OW_EXPECT_TARGET=$OEM_TARGET_SLOT
 if command -v hexdump >/dev/null 2>&1;then job=$(head -c 32 "$OEM_SYS_ROOT/dev/urandom" | hexdump -v -e '1/1 "%02x"');else job=$(od -An -tx1 -N32 "$OEM_SYS_ROOT/dev/urandom" | tr -d ' \n');fi
 oem_hex64 "$job" || exit 1
 OW_EXPECT_JOB=$job
 printf 'format\t2\nserial\t%s\nfamily\tjaguar\nmodel\t%s\nsource_operation\tproduction-oem-migration\nsource_release\t%s\nsource_contract_sha256\t%s\nsource_slot\t%s\ntarget_slot\t%s\nimage_sha256\t%s\njob_id\t%s\n' "$OEM_SERIAL" "$OEM_MODEL" "$OEM_SOURCE_RELEASE" "$OEM_JAGUAR_CONTRACT" "$OEM_SOURCE_SLOT" "$OEM_TARGET_SLOT" "$OEM_JAGUAR_IMAGE_PIN" "$job" > "$OEM_WORK/binding.tsv" || exit 1
 printf '{"server":"%s:18443","tls_ca":"/etc/ssl/certs/ca-certificates.crt"}\n' "$OEM_CONTROLLER" > "$OEM_WORK/est.json"
 printf '{"server":"%s","port":15002,"cert":"/etc/ucentral/operational.pem","ca":"/etc/ssl/certs/ca-certificates.crt","hostname_validate":1}\n' "$OEM_CONTROLLER" > "$OEM_WORK/gateway.json"
 chmod 600 "$OEM_WORK/binding.tsv" "$OEM_WORK/est.json" "$OEM_WORK/gateway.json" || exit 1
 ow_settings_prepare "$OEM_WORK/binding.tsv" "$OEM_WORK/est.json" "$OEM_WORK/gateway.json" "$credential" "$OEM_WORK/seed" || exit 1
 credential=
 oem_jaguar_vault_prepare || exit 1
 OEM_JAGUAR_VAULT_PIN=$(oem_sha "$OEM_WORK/jaguar-vault.tar") && oem_hex64 "$OEM_JAGUAR_VAULT_PIN" || exit 1
 oem_jaguar_env_read > "$OEM_WORK/env-before" && oem_jaguar_protected_snapshot > "$OEM_WORK/protected-before" || exit 1
 printf '%s\n' bootcmd image jaguar_storage_pending jaguar_boot0 jaguar_boot1 jaguar_stable0 jaguar_stable1 jaguar_ab_version jaguar_ab_confirmed jaguar_ab_target jaguar_ab_state jaguar_installer_target jaguar_installer_job jaguar_installer_image > "$OEM_WORK/env-allowed" || exit 1
 while IFS="$(printf '\t')" read -r kind label size reason;do index=$(oem_physical_index "$OEM_SYS_ROOT/sys/class/mtd" "$label") || exit 1;[ "$(oem_sha "$OEM_RECOVERY_DIR/$kind.bin")" = "$(oem_sha "$OEM_SYS_ROOT/dev/mtd${index}ro")" ] || exit 1;done < "$OEM_RECOVERY_DIR/manifest.tsv"
 OEM_JAGUAR_JOURNAL="install:$OEM_SOURCE_SLOT:$OEM_TARGET_SLOT:$OEM_JAGUAR_IMAGE_PIN:$job"
 oem_jaguar_payload_hash_check || exit 1
 oem_jaguar_persist_source "$OEM_JAGUAR_JOURNAL" || exit 1
 oem_jaguar_target_locate || exit 1
 if [ -z "$OEM_JAGUAR_TARGET_UBI" ];then ubiattach -m "$OEM_JAGUAR_TARGET_MTD" && oem_jaguar_target_locate || exit 1;fi
 [ -n "$OEM_JAGUAR_TARGET_UBI" ] && oem_jaguar_stage_bank || exit 1
 OW_STAGE_ADMISSION=qualified OW_EXPECT_TARGET_MTD=$OEM_JAGUAR_TARGET_MTD OW_EXPECT_TARGET_VOLUME=${OEM_JAGUAR_TARGET_UBI}_2
 umask 077
 mountpoint=$(mktemp -d /tmp/cambium-jaguar-settings.XXXXXX) || exit 1
 trap '[ -z "$mountpoint" ] || { umount "$mountpoint" 2>/dev/null;rmdir "$mountpoint" 2>/dev/null; }' EXIT
 mount -t ubifs "$OEM_SYS_ROOT/dev/$OW_EXPECT_TARGET_VOLUME" "$mountpoint" && ow_settings_stage_overlay "$OEM_WORK/seed" "$OEM_JAGUAR_IMAGE" "$mountpoint" && sync || exit 1
 umount "$mountpoint" && rmdir "$mountpoint" || exit 1
 mountpoint=
 oem_jaguar_protected_snapshot > "$OEM_WORK/protected-after" && cmp -s "$OEM_WORK/protected-before" "$OEM_WORK/protected-after" || exit 1
 oem_jaguar_env_read > "$OEM_WORK/env-after" && oem_env_preserved "$OEM_WORK/env-before" "$OEM_WORK/env-after" "$OEM_WORK/env-allowed" || exit 1
 oem_jaguar_before_select() (
  oem_jaguar_payload_hash_check || exit 1
  oem_jaguar_protected_snapshot > "$OEM_WORK/protected-after" && cmp -s "$OEM_WORK/protected-before" "$OEM_WORK/protected-after" || exit 1
  oem_jaguar_env_read > "$OEM_WORK/env-after" && oem_env_preserved "$OEM_WORK/env-before" "$OEM_WORK/env-after" "$OEM_WORK/env-allowed"
 )
 oem_jaguar_arm || exit 1
 fw_setenv -c "$OEM_JAGUAR_ENV_CONFIG" jaguar_storage_pending && sync || exit 1
 oem_jaguar_env_read | awk -F= '$1=="jaguar_storage_pending" {found=1}END{exit found}' || exit 1
 printf 'handoff=one-shot-armed\nonboarded=not-yet-verified\nsysupgrade_ready=not-yet-verified\n'
)

# Native one-shot components reused by the full caller; no new bootloader gate
# and no claim that a Linux watchdog proves pre-kernel hang recovery.
oem_jaguar_target_command() {
 local bank offset part
 oem_jaguar_table && oem_context_check || return 1
 case "$OEM_TARGET_SLOT" in
  0) offset=0x0;part=rootfs;;
  1) offset=$(printf '0x%x' "$OEM_JAGUAR_BANK");part=rootfs_1;;
  *) return 1;;
 esac
 bank=$(printf '0x%x' "$OEM_JAGUAR_BANK")
 printf '%s\n' "nand device 0 && setenv mtdids nand0=nand0 && setenv mtdparts \"mtdparts=nand0:$bank@$offset(fs)\" && ubi part fs && ubi read 0x60000000 kernel && setenv bootargs \"console=ttyMSM0,115200n8 cnss2.bdf_pci0=0xab ubi.mtd=$part root=/dev/ubiblock0_1 rootfstype=squashfs rootwait swiotlb=1\" && bootm 0x60000000#$OEM_JAGUAR_FIT"
}
oem_jaguar_source_command() {
 oem_jaguar_table && oem_context_check || return 1
 printf '%s\n' "setenv image $OEM_SOURCE_SLOT; bootipq"
}
oem_adapter_boot_preflight() {
 local current expected tool
 oem_jaguar_table && oem_context_check || return 1
 [ "$(oem_jaguar_env_value image)" = "$OEM_SOURCE_SLOT" ] || return 1
 current=$(oem_jaguar_env_value bootcmd) || return 1
 case "$current" in
  bootipq) ;;
  "run jaguar_boot$OEM_SOURCE_SLOT")
   expected=$(oem_jaguar_source_command) || return 1
   [ "$(oem_jaguar_env_value "jaguar_boot$OEM_SOURCE_SLOT")" = "$expected" ] || return 1;;
  *) return 1;;
 esac
 for tool in fw_printenv fw_setenv sync mktemp rm rmdir; do command -v "$tool" >/dev/null 2>&1 || return 1; done
 oem_jaguar_target_command >/dev/null || return 1
 OEM_BOOT_PRIOR_SLOT=$OEM_SOURCE_SLOT OEM_BOOT_TARGET_SLOT=$OEM_TARGET_SLOT
 OEM_BOOT_MODE=persist-prior-before-load OEM_BOOT_WATCHDOG=manual-reset
}
oem_jaguar_persist_source() (
 local journal=$1 command key value
 oem_adapter_boot_preflight || exit 1
 printf '%s\n' "$journal" | awk -F: -v source="$OEM_SOURCE_SLOT" -v target="$OEM_TARGET_SLOT" \
  'NF!=5 || $1!="install" || $2!=source || $3!=target || length($4)!=64 || $4~/[^0-9a-f]/ || length($5)!=64 || $5~/[^0-9a-f]/ {bad=1} END{exit bad || NR!=1}' || exit 1
 command=$(oem_jaguar_source_command) || exit 1
 umask 077
 work=$(mktemp -d /tmp/cambium-jaguar-source.XXXXXX) || exit 1
 trap 'rm -f "$work/environment";rmdir "$work"' EXIT
 printf 'jaguar_boot%s %s\nbootcmd run jaguar_boot%s\nimage %s\njaguar_storage_pending %s\n' \
  "$OEM_SOURCE_SLOT" "$command" "$OEM_SOURCE_SLOT" "$OEM_SOURCE_SLOT" "$journal" > "$work/environment" || exit 1
 fw_setenv -c "$OEM_JAGUAR_ENV_CONFIG" -s "$work/environment" && sync || exit 1
 while read -r key value; do [ "$(oem_jaguar_env_value "$key")" = "$value" ] || exit 1;done < "$work/environment"
 oem_adapter_boot_preflight
)
oem_jaguar_arm() (
 local target trial key value
 oem_adapter_boot_preflight || exit 1
 [ "$(oem_jaguar_env_value jaguar_storage_pending)" = "$OEM_JAGUAR_JOURNAL" ] || exit 1
 oem_hex64 "$OW_EXPECT_JOB" && oem_hex64 "$OEM_JAGUAR_IMAGE_PIN" || exit 1
 [ "$OEM_JAGUAR_JOURNAL" = "install:$OEM_SOURCE_SLOT:$OEM_TARGET_SLOT:$OEM_JAGUAR_IMAGE_PIN:$OW_EXPECT_JOB" ] || exit 1
 # An interrupted/foreign/partial incoming enrollment must not be overwritten.
 oem_jaguar_env_read | awk -F= '$1~/^jaguar_installer_(target|job|image)$/ {if(NF!=2 || length($2) || seen[$1]++)bad=1} END{exit bad}' || exit 1
 target=$(oem_jaguar_target_command) || exit 1
 trial="setenv bootcmd run jaguar_boot$OEM_SOURCE_SLOT && setenv image $OEM_SOURCE_SLOT && setenv jaguar_ab_state trial-started && saveenv && run jaguar_boot$OEM_TARGET_SLOT; run jaguar_boot$OEM_SOURCE_SLOT"
 umask 077
 work=$(mktemp -d /tmp/cambium-jaguar-arm.XXXXXX) || exit 1
 trap 'rm -f "$work/environment";rmdir "$work"' EXIT
 {
  printf 'jaguar_boot%s %s\n' "$OEM_TARGET_SLOT" "$target"
  printf 'jaguar_stable%s run jaguar_boot%s\n' "$OEM_SOURCE_SLOT" "$OEM_SOURCE_SLOT"
  printf 'jaguar_stable%s run jaguar_boot%s; run jaguar_boot%s\n' "$OEM_TARGET_SLOT" "$OEM_TARGET_SLOT" "$OEM_SOURCE_SLOT"
  printf 'jaguar_ab_version 1\njaguar_ab_confirmed %s\njaguar_ab_target %s\njaguar_ab_state armed\n' "$OEM_SOURCE_SLOT" "$OEM_TARGET_SLOT"
  printf 'jaguar_installer_target %s\njaguar_installer_job %s\njaguar_installer_image %s\n' "$OEM_TARGET_SLOT" "$OW_EXPECT_JOB" "$OEM_JAGUAR_IMAGE_PIN"
 } > "$work/environment" || exit 1
 fw_setenv -c "$OEM_JAGUAR_ENV_CONFIG" -s "$work/environment" && sync || exit 1
 while read -r key value;do [ "$(oem_jaguar_env_value "$key")" = "$value" ] || exit 1;done < "$work/environment"
 oem_adapter_boot_preflight || exit 1
 command -v oem_jaguar_before_select >/dev/null && oem_jaguar_before_select || exit 1
 [ "$(oem_jaguar_env_value jaguar_installer_target)" = "$OEM_TARGET_SLOT" ] &&
  [ "$(oem_jaguar_env_value jaguar_installer_job)" = "$OW_EXPECT_JOB" ] &&
  [ "$(oem_jaguar_env_value jaguar_installer_image)" = "$OEM_JAGUAR_IMAGE_PIN" ] || exit 1
 fw_setenv -c "$OEM_JAGUAR_ENV_CONFIG" bootcmd "$trial" && sync || exit 1
 [ "$(oem_jaguar_env_value bootcmd)" = "$trial" ]
)
