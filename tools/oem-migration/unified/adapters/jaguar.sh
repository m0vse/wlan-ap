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
 header=$(od -An -tx1 -N6 "$OEM_SYS_ROOT/dev/mtd${index}ro" | tr -d ' \n') || return 1
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
 local profile member
 oem_jaguar_table || return 1
 member=$(oem_jaguar_member bank.tsv) || { oem_fail "$OEM_MODEL: exact OEM/OpenWiFi bank descriptor is missing"; return 1; }
 # Do not substitute a stock sysupgrade writer for an unclosed OEM operation.
 # bank.tsv must be closed with per-model FIT, volume sizing, local payloads,
 # reused authenticated BDFs and the preserved source/own-ART vault binding.
 [ -s "$member" ] || return 1
 profile=$(oem_jaguar_member mtd.tsv) || return 1
 OEM_PROTECTED_RANGES=$OEM_WORK/jaguar-ranges.tsv
 oem_physical_inventory "$profile" "$OEM_SYS_ROOT/sys/class/mtd" "$OEM_PROTECTED_RANGES" || return 1
 awk -F '\t' -v active="$OEM_JAGUAR_SOURCE_MTD" -v target="$OEM_JAGUAR_TARGET_MTD" -v env="$OEM_JAGUAR_ENV_MTD" \
  '$1==active {if($4!="active-oem")bad=1;a++} $1==target {if($4!="target")bad=1;t++} $1==env {if($4!="environment")bad=1;e++} $4=="target" && $1!=target {bad=1} END{exit bad || a!=1 || t!=1 || e!=1}' "$OEM_PROTECTED_RANGES" || return 1
 oem_fail "$OEM_MODEL: OEM volume rewrite/BDF/certificate descriptor is not yet source-closed; no prompt or write permitted"
}
oem_adapter_recovery() { oem_fail 'Jaguar recovery is unavailable until its exact OEM bank writer is closed'; }
oem_adapter_migrate() { oem_fail 'Jaguar OEM writer is not enabled; retained OEM and unique factory data are untouched'; }
