#!/bin/sh
# Validated physical partition inventory and child-only write plans.
# Columns: physical MTD index, offset, size, role, flash-domain. Roles are model-derived,
# never supplied by an operator flag. Essential boot code stays protected.
oem_ranges_check() (
 awk -F '\t' '
  NF!=5 || $1!~/^[0-9]+$/ || $2!~/^[0-9]+$/ || $3!~/^[0-9]+$/ || $3==0 || seen[$1]++ {bad=1}
  $4!~/^(identity|bootcode|active-oem|target|environment|shared-parent|container|nonunique-config)$/ {bad=1}
  $5!~/^(nand|nor)[0-9]+$/ {bad=1}
  {idx[NR]=$1;off[NR]=$2;size[NR]=$3;role[NR]=$4;domain[NR]=$5}
  END {
   for(i=1;i<=NR;i++)for(j=i+1;j<=NR;j++)
    if(domain[i]==domain[j] && off[i]<off[j]+size[j] && off[j]<off[i]+size[i]) {
     if(role[i]=="container" && role[j]!="container" && off[j]>=off[i] && off[j]+size[j]<=off[i]+size[i])continue
     if(role[j]=="container" && role[i]!="container" && off[i]>=off[j] && off[i]+size[i]<=off[j]+size[j])continue
     bad=1
    }
   exit bad || NR<3
  }' "$1"
)
# For Sage, target and active banks share one UBI MTD: parent must be marked
# shared-parent, never eraseable. Child identity + UBI parent proof is required.
oem_write_boundary() (
 inventory=$1 plan=$2
 oem_ranges_check "$inventory" || return 1
 awk -F '\t' -v target="${OEM_TARGET_SLOT:-}" '
  FNR==NR {role[$1]=$4;next}
  NF!=4 || $1!~/^(ubi-update|ubi-remove|ubi-resize|ubi-create|environment-fields)$/ || $2!~/^[0-9]+$/ {bad=1}
  $1=="environment-fields" {if(role[$2]!="environment" || $3!="fields" || $4!="preserve-unlisted")bad=1;next}
  {if(role[$2]!="target" && role[$2]!="shared-parent")bad=1}
  role[$2]=="shared-parent" {
   if(target!~/^[01]$/ || ($4!="linux" target && $4!="rootfs" target && $4!="rootfs_data" target))bad=1
   if($4=="linux" target && $3!=2*target)bad=1
   if($4=="rootfs" target && $3!=2*target+1)bad=1
  }
  role[$2]=="target" {
   if($4=="kernel" && $3!=0 || $4=="rootfs" && $3!=1 || $4=="rootfs_data" && $3!=2)bad=1
   if($4=="ubi_rootfs" && $3!=1)bad=1
   if($4=="cambium_device_data" && ($3!=3 || $1!~/^(ubi-create|ubi-update)$/))bad=1
   if($4=="certificates" && ($3!=4 || $1!="ubi-create"))bad=1
  }
  $3!~/^[0-9]+$/ || $4!~/^(kernel|rootfs|ubi_rootfs|rootfs_data|cambium_device_data|certificates|linux[01]|rootfs[01]|rootfs_data[01])$/ {bad=1}
  END{exit bad || FNR<1}' "$inventory" "$plan"
)
# Proof ties one named child ID to one physical parent. Refuse alternate
# attachments, duplicate volume names and unhealthy UBI before each operation.
oem_ubi_child_check() (
 sys=$1 parent=$2 device=$3 child=$4 expected=$5
 case "$device:$child" in ubi[0-9]*:[0-9]*) ;; *) return 1;; esac
 [ "$(cat "$sys/$device/mtd_num")" = "$parent" ] || return 1
 count=0
 for node in "$sys"/ubi*/mtd_num; do
  [ -r "$node" ] || continue
  [ "$(cat "$node")" != "$parent" ] || count=$((count+1))
 done
 [ "$count" = 1 ] || return 1
 [ "$(cat "$sys/${device}_$child/name")" = "$expected" ] &&
 [ "$(cat "$sys/${device}_$child/upd_marker")" = 0 ] &&
 [ "$(cat "$sys/${device}_$child/corrupted")" = 0 ] || return 1
 count=0
 for node in "$sys"/"$device"_*/name; do
  [ -r "$node" ] || continue
  [ "$(cat "$node")" != "$expected" ] || count=$((count+1))
 done
 [ "$count" = 1 ]
)

oem_physical_index() (
 sys=$1 name=$2 found= count=0
 for node in "$sys"/mtd[0-9]*; do
  index=${node##*/mtd};case "$index" in ''|*[!0-9]*) continue;; esac
  [ -r "$node/name" ] && [ "$(cat "$node/name")" = "$name" ] || continue
  case "$(cat "$node/type")" in nand|nor) ;; *) continue;; esac
  found=$index;count=$((count+1))
 done
 [ "$count" = 1 ] || return 1
 printf '%s\n' "$found"
)
# Profile: name, flash-domain, offset, size, type, erase, write, role.
# Profiles come from reviewed model/source geometry, not operator guesses.
oem_physical_inventory() (
 profile=$1 sys=$2 output=$3
 awk -F '\t' 'NF!=8 || seen[$1]++ || $2!~/^(nand|nor)[0-9]+$/ || $3!~/^[0-9]+$/ || $4!~/^[0-9]+$/ || $5!~/^(nand|nor)$/ || $2!~("^" $5 "[0-9]+$") || $6!~/^[0-9]+$/ || $7!~/^[0-9]+$/ || $8!~/^(identity|bootcode|active-oem|target|environment|shared-parent|container|nonunique-config)$/ {bad=1} END{exit bad || NR<3}' "$profile" || exit 1
 : > "$output"
 domains=$output.domains
 : > "$domains"
 while IFS="$(printf '\t')" read -r name domain offset size type erase write role; do
  index=$(oem_physical_index "$sys" "$name") || exit 1
  node=$sys/mtd$index
  physical=$(oem_mtd_domain "$node") || exit 1
  awk -F '\t' -v domain="$domain" -v physical="$physical" '($1==domain && $2!=physical) || ($2==physical && $1!=domain){bad=1} END{exit bad}' "$domains" || exit 1
  printf '%s\t%s\n' "$domain" "$physical" >> "$domains"
  [ "$(cat "$node/type")" = "$type" ] && [ "$(cat "$node/size")" = "$size" ] &&
  [ "$(cat "$node/erasesize")" = "$erase" ] && [ "$(cat "$node/writesize")" = "$write" ] || exit 1
  # Missing offsets are not inferred from partition order. A reviewed adapter
  # may produce a sysfs-equivalent inventory from unambiguous OEM boot ranges.
  actualoffset=$(oem_mtd_offset "$node" "$name" "$role" "$physical") || exit 1
  [ "$actualoffset" = "$offset" ] || exit 1
  case "$name:$role" in *ART*:identity|*art*:identity|*mfg*:identity|*MFG*:identity|*APPSBLENV*:environment|u-boot-env:environment) ;;
   *ART*:*|*art*:*|*mfg*:*|*MFG*:*|*APPSBLENV*:*|u-boot-env:*) exit 1;;
  esac
  printf '%s\t%s\t%s\t%s\t%s\n' "$index" "$offset" "$size" "$role" "$domain" >> "$output"
 done < "$profile"
 # Complete physical inventory: a hidden/unknown partition may hold unique data.
 expected=$(wc -l < "$output");actual=0
 for node in "$sys"/mtd[0-9]*; do
  index=${node##*/mtd};case "$index" in ''|*[!0-9]*) continue;; esac
  [ -r "$node/type" ] || continue
  case "$(cat "$node/type")" in nand|nor) actual=$((actual+1));; esac
 done
 [ "$expected" -eq "$actual" ] && oem_ranges_check "$output"
)

oem_mtd_domain() (
 node=$1
 if [ -e "$node/device" ]; then
  actual=$(readlink -f "$node/device") || return 1
 else
  actual=$(readlink -f "$node") || return 1
 fi
 case "$actual" in */mtd/mtd[0-9]*) printf '%s\n' "${actual%/mtd/mtd*}";; *) [ -e "$node/device" ] && printf '%s\n' "$actual";; esac
)
oem_mtd_offset() (
 node=$1 name=$2 role=$3 physical=$4
 if [ -r "$node/offset" ]; then cat "$node/offset";return;fi
 # Whole-chip masters have offset zero by definition; their name must be the
 # verified physical device, and no whole-chip operation is ever admitted.
 if [ "$role" = container ]; then
  if [ "$name" = "${physical##*/}" ]; then printf '0\n';return;fi
  count=$(dmesg | awk -v marker=" MTD partitions on \"$name\":" 'index($0,marker){n++}END{print n+0}') || return 1
  [ "$count" = 1 ] || return 1
  printf '0\n';return
 fi
 # Older OEM kernels omit sysfs offsets. Use only unique live kernel ranges.
 rows=$(dmesg | awk -v name="$name" '
  match($0,/0x[0-9a-f]+-0x[0-9a-f]+ : "[^"]+"/) {
   row=substr($0,RSTART,RLENGTH);split(row,parts," : ");label=parts[2];gsub(/"/,"",label)
   if(label==name){split(parts[1],range,"-");print range[1] " " range[2];n++}
  }END{if(n!=1)exit 1}') || return 1
 read -r start end <<EOF_RANGE
$rows
EOF_RANGE
 case "$start:$end" in 0x*:0x*) ;; *) return 1;; esac
 [ "$((end-start))" = "$(cat "$node/size")" ] || return 1
 printf '%s\n' "$((start))"
)
# Complete fw_printenv snapshots, plus an explicit reviewed field list.
# Any unrelated addition, deletion or value change is a failure.
oem_env_preserved() (
 before=$1 after=$2 allowed=$3
 awk 'NF!=1 || $1!~/^[A-Za-z0-9_]+$/ || $1~/^(eth.*addr|serial.*|.*[Mm][Aa][Cc].*|.*[Cc][Aa][Ll].*)$/ || seen[$1]++ {bad=1} END{exit bad || NR<1}' "$allowed" || return 1
 awk '
  FILENAME==ARGV[1]{allow[$0]=1;next}
  {key=$0;sub(/=.*/,"",key);if(index($0,"=")==0 || key!~/^[A-Za-z0-9_]+$/)bad=1}
  FILENAME==ARGV[2]{if(seenbefore[key]++)bad=1;old[key]=$0;next}
  {if(seenafter[key]++)bad=1;new[key]=$0}
  END{for(key in old)if(!allow[key] && old[key]!=new[key])bad=1;for(key in new)if(!allow[key] && old[key]!=new[key])bad=1;exit bad}' "$allowed" "$before" "$after"
)

# Bank-local preflight: one precisely identified idle rootfs block view may be
# reported for removal after INSTALL confirmation. Everything else stays busy.
oem_bank_idle_check() (
 sys=$1 dev=$2 proc=$3 parent=$4 ubi=$5 allow_root_map=$6
 [ "$(cat "$sys/$ubi/mtd_num")" = "$parent" ] || return 1
 count=0
 for node in "$sys"/ubi*/mtd_num; do
  [ -r "$node" ] || continue
  [ "$(cat "$node")" != "$parent" ] || count=$((count+1))
 done
 [ "$count" = 1 ] || return 1
 for table in "$proc/mounts" "$proc/self/mountinfo"; do
  [ -r "$table" ] || return 1
  grep -E "(^|[[:space:]/])${ubi}([_:]|[[:space:]])|(^|[[:space:]/])ubiblock${ubi#ubi}_" "$table" >/dev/null && return 1
 done
 for node in "${sys%/ubi}/block"/ubiblock*; do
  [ -e "$node" ] || continue
  case "${node##*/}" in ubiblock${ubi#ubi}_*) ;;
   *) continue;;
  esac
  [ "$allow_root_map" = yes ] && [ "${node##*/}" = "ubiblock${ubi#ubi}_1" ] || return 1
  case "$(cat "$sys/${ubi}_1/name")" in rootfs|ubi_rootfs) ;; *) return 1;; esac
  number=$(cat "$node/dev") || return 1
  case "$number" in *[!0-9:]*|''|:*|*:) return 1;; esac
  awk -v number="$number" '$3==number {bad=1}END{exit bad}' "$proc/self/mountinfo" || return 1
 done
 for fd in "$proc"/[0-9]*/fd/*; do
  [ -L "$fd" ] || continue
  path=$(readlink "$fd" 2>/dev/null) || return 1
  case "$path" in "$dev/$ubi"|"$dev/${ubi}_"*|"$dev/mtd$parent"|"$dev/mtd${parent}ro"|"$dev/ubiblock${ubi#ubi}_"*) return 1;; esac
 done
)
oem_bank_remove_idle_root_map() (
 sys=$1 dev=$2 proc=$3 parent=$4 ubi=$5
 oem_bank_idle_check "$sys" "$dev" "$proc" "$parent" "$ubi" yes || return 1
 node=${sys%/ubi}/block/ubiblock${ubi#ubi}_1
 if [ -e "$node" ]; then
  command -v ubiblock >/dev/null || return 1
  ubiblock --remove "$dev/${ubi}_1" || return 1
  [ ! -e "$node" ] || return 1
 fi
 oem_bank_idle_check "$sys" "$dev" "$proc" "$parent" "$ubi" no
)

# OEM-side factory config reset is permitted only after explicit healthy OEM
# confirmation. This helper never changes data itself or authorizes identity,
# boot-code, source-bank or whole-chip erasure.
oem_confirmed_config_boundary() (
 inventory=$1 plan=$2
 [ "${OEM_RESTORE_CONFIRMED:-}" = 1 ] && [ "${OEM_RUNNING_OS:-}" = oem ] || return 1
 oem_ranges_check "$inventory" || return 1
 awk -F '\t' '
  FNR==NR{role[$1]=$4;size[$1]=$3;next}
  NF!=4{bad=1}
  $1=="nor-config-reset"{if(role[$2]!="nonunique-config" || size[$2]!=65536 || $3!="single-partition" || $4!="config")bad=1;next}
  $1=="ubi-config-reset"{if(role[$2]!="shared-parent" || $3!~/^[0-9]+$/ || $4!="nvram")bad=1;next}
  {bad=1}
  END{exit bad || FNR<1}' "$inventory" "$plan"
)
