#!/bin/sh
# Confirm a healthy retained-OEM entry; only reviewed ENV fields change.
set -eu
set +x
umask 077
case "$*" in --yes) probe= ;; *)
 [ "$#" = 3 ] && [ "$1" = --yes ] && [ "$2" = --network-url ] || { echo 'Usage: confirm-oem-entry.sh --yes [--network-url EXISTING_INSTALLER_ENDPOINT]' >&2;exit 2; }
 probe=$3;;esac
kit=$(CDPATH= cd -- "$(dirname "$0")" && pwd -P)
# These are existing common release readers, packaged by the kit assembler.
. "$kit/shared/oem-common.sh"
. "$kit/shared/oem-protection.sh"
. "$kit/shared/oem-network.sh"
[ "$(id -u)" = 0 ] || exit 1
OEM_SYS_ROOT=
work=$(mktemp -d /tmp/miami-oem-confirm.XXXXXX)
trap 'rm -rf "$work"' EXIT
get() { value=$(fw_printenv -c "$config" "$1" 2>/dev/null) || return 1;case "$value" in "$1="*) printf '%s\n' "${value#*=}";;*) return 1;;esac; }
legacy_route() {
 case "$1" in 0) part=rootfs;offset=0xc0000;;1) part=rootfs_1;offset=0x60c0000;;*) return 1;;esac
 printf "nand device 0 && setenv mtdids nand0=nand0 && setenv mtdparts 'mtdparts=nand0:0x6000000@%s(fs)' && ubi part fs && ubi read 0x60000000 kernel && setenv bootargs console=ttyMSM0,115200n8 ubi.mtd=%s root=/dev/ubiblock0_1 rootfstype=squashfs rootwait && bootm 0x60000000#config@mi01.6-acadia-slot%s\n" "$offset" "$part" "$1"
}
squash_extent() (
 dev=$1
 count=$(head -c 96 "$dev" | wc -c) || exit 1
 [ "$count" -eq 96 ] || exit 1
 [ "$(od -An -tx1 -N4 "$dev" | tr -d ' \n')" = 68737173 ] || exit 1
 [ "$(od -An -tx1 -j28 -N4 "$dev" | tr -d ' \n')" = 04000000 ] || exit 1
 raw=$(od -An -tx1 -j40 -N8 "$dev" | tr -d ' \n') || exit 1
 [ "${#raw}" = 16 ] || exit 1
 case "$raw" in *[!0-9a-f]*) exit 1;;esac
 [ "${raw#????????}" = 00000000 ] || exit 1
 little=$(printf '%s' "$raw" | cut -c1-8)
 value=$(printf '%s' "$little" | sed 's/\(..\)\(..\)\(..\)\(..\)/0x\4\3\2\1/')
 extent=$((value))
 [ "$extent" -ge 96 ] && [ "$extent" -le 100663296 ] || exit 1
 printf '%s\n' "$extent"
)
root_digest() (
 dev=$1 extent=$2
 # Stream only verification counts/digests; never copy or back up a unit rootfs.
 count=$(head -c "$extent" "$dev" | wc -c) || exit 1
 [ "$count" -eq "$extent" ] || exit 1
 sum=$(head -c "$extent" "$dev" | sha256sum) || exit 1
 printf '%s\n' "${sum%% *}"
)
gluebi_content_check() (
 dev=$1 view=$2
 node=/sys/class/ubi/${ubi}_1
 lebs=$(cat "$node/reserved_ebs") leb=$(cat "$node/usable_eb_size")
 data_bytes=$(cat "$node/data_bytes") view_bytes=$(cat "$view/size")
 case "$lebs:$leb:$data_bytes:$view_bytes" in *[!0-9:]*) exit 1;;esac
 [ -n "$lebs" ] && [ -n "$leb" ] && [ -n "$data_bytes" ] && [ -n "$view_bytes" ] || exit 1
 [ "$lebs" -ge 1 ] && [ "$lebs" -le 768 ] && [ "$leb" -ge 1 ] && [ "$leb" -le 131072 ] || exit 1
 capacity=$((lebs*leb))
 [ "$data_bytes" -ge 96 ] && [ "$data_bytes" -le "$capacity" ] && [ "$view_bytes" -ge 96 ] && [ "$view_bytes" -le "$capacity" ] || exit 1
 [ "$view_bytes" = "$data_bytes" ] && [ "$(cat "$view/erasesize")" = "$leb" ] && [ "$(cat "$view/writesize")" = "$(cat "/sys/class/ubi/$ubi/min_io_size")" ] || exit 1
 extent=$(squash_extent "/dev/${ubi}_1") && mounted_extent=$(squash_extent "$dev") || exit 1
 [ "$extent" = "$mounted_extent" ] && [ "$extent" -le "$data_bytes" ] && [ "$extent" -le "$view_bytes" ] || exit 1
 actual=$(root_digest "/dev/${ubi}_1" "$extent") && mounted=$(root_digest "$dev" "$extent") || exit 1
 [ "$actual" = "$mounted" ]
)
prove() {
 [ ! -e /etc/openwrt_release ] || return 1
 [ "$(od -An -tx1 /proc/device-tree/cambium-platform/board-sku | tr -d ' \n')" = 0000002c ] || return 1
 oem_source_identifiers_check /etc/version "$kit/profiles/X7-35X/source.tsv" || return 1
 env_mtd=$(oem_physical_index /sys/class/mtd 0:APPSBLENV)
 # fwtools must select only the physically proved APPSBLENV partition.
 config=
 for c in /tmp/fw_env.config /etc/fw_env.config;do [ ! -f "$c" ] || { config=$c;break; };done
 [ -n "$config" ] || return 1
 awk -v dev="/dev/mtd$env_mtd" '!/^#/ && NF {n++;if($1!=dev && $1!=dev"ro")bad=1;if($2!~/^(0|0x0+)$/ || $3!~/^(65536|0x0*10000)$/)bad=1} END{exit bad || n!=1}' "$config" || return 1
 source=$(get miami_oem_once_source);target=$(get miami_oem_once_target)
 case "$source:$target" in 0:1|1:0);;*) return 1;;esac
 [ "$(get miami_oem_once_state)" = started ] && [ "$(get miami_oem_once_source_release)" = b6d1a26f ] || return 1
 [ "$(get bootcmd)" = "run miami_boot$source" ] && [ "$(get changing_bootcmd)" = 1 ] || return 1
 # OEM startup may save its actual selector. The sealed OW boot function
 # remains independent of image and is still the durable fallback.
 observed=$(get image)
 [ "$observed" = "$source" ] || [ "$observed" = "$target" ] || return 1
 prior=$(legacy_route "$source")
 [ "$(get miami_boot$source)" = "$prior" ] || return 1
 [ -z "$(get miami_ab_version || true)" ] && [ -z "$(get miami_storage_pending || true)" ] || return 1
 case "$target" in 0) running=rootfs;;1) running=rootfs_1;;esac
 [ "$(sed -n 's/.*ubi\.mtd=\([^ ]*\).*/\1/p' /proc/cmdline)" = "$running" ] || return 1
 # Existing profile suffix is the inactive/write target, now the old OW bank.
 oem_physical_inventory "$kit/profiles/X7-35X/mtd-slot$source.tsv" /sys/class/mtd "$work/ranges.tsv" || return 1
 mtd=$(oem_physical_index /sys/class/mtd "$running")
 env_mtd=$(oem_physical_index /sys/class/mtd 0:APPSBLENV)
 count=0;ubi=
 for d in /sys/class/ubi/ubi[0-9]*;do
  [ -f "$d/mtd_num" ] || continue
  [ "$(cat "$d/mtd_num")" != "$mtd" ] || { ubi=${d##*/};count=$((count+1)); }
 done
 [ "$count" = 1 ] || return 1
 rootdev=$(awk '$2=="/" {n++;dev=$1;if($3!="squashfs" || $4!~/(^|,)ro(,|$)/)bad=1} END{if(bad || n!=1)exit 1;print dev}' /proc/mounts) || return 1
 if [ "$rootdev" != "/dev/ubiblock${ubi#ubi}_1" ];then
  # OEM exposes the same UBI child through gluebi; its MTD number varies.
  case "$rootdev" in /dev/mtdblock*) index=${rootdev#/dev/mtdblock};;*) return 1;;esac
  case "$index" in ''|*[!0-9]*) return 1;;esac
  view=/sys/class/mtd/mtd$index
  [ "$(cat "$view/type")" = ubi ] && [ "$(cat "$view/name")" = ubi_rootfs ] || return 1
  parent=
  if [ -e "$view/device" ] || [ -L "$view/device" ];then parent=$(readlink -f "$view/device") || return 1;fi
  expected=$(readlink -f "/sys/class/ubi/${ubi}_1") || return 1
  if [ "$parent" != "$expected" ];then
   # A known wrong UBI parent is never rescued by matching image contents.
   for candidate in /sys/class/ubi/ubi[0-9]*_[0-9]*;do
    [ ! -d "$candidate" ] || [ "$parent" != "$(readlink -f "$candidate")" ] || return 1
   done
   # This OEM's gluebi exposes only its own virtual-MTD device path.
   [ -z "$parent" ] || [ "$parent" = "$(readlink -f "$view")/device" ] || return 1
   reader=$rootdev
   [ ! -e "/dev/mtd${index}ro" ] || reader=/dev/mtd${index}ro
   gluebi_content_check "$reader" "$view" || return 1
  fi
 fi
 for pair in 0:kernel 1:ubi_rootfs;do
  id=${pair%%:*};name=${pair#*:};node=/sys/class/ubi/${ubi}_$id
  [ "$(cat "$node/name")" = "$name" ] && [ "$(cat "$node/upd_marker")" = 0 ] && [ "$(cat "$node/corrupted")" = 0 ] || return 1
 done
 [ "$(od -An -tx1 -N4 "/dev/${ubi}_0" | tr -d ' \n')" = d00dfeed ] && [ "$(od -An -tx1 -N4 "/dev/${ubi}_1" | tr -d ' \n')" = 68737173 ] || return 1

}
prove || { echo 'Retained OEM entry proof failed; OpenWiFi fallback retained' >&2;exit 1; }
ip -4 -o addr show scope global | awk '{split($4,a,"/");if(a[1]!~/^127\./ && a[1]!~/^169\.254\./ && a[1]!="0.0.0.0" && a[1]~/^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/)n++} END{exit n<1}' || { echo 'OEM global IPv4 is unavailable' >&2;exit 1; }
gateway=$(ip -4 route show default | awk '$1=="default" && $2=="via" {if(!seen[$3]++) {gateway=$3;n++}} END{if(n!=1)exit 1;print gateway}') || { echo 'OEM default route is unavailable or ambiguous' >&2;exit 1; }
printf '%s\n' "$gateway" | awk -F. 'NF!=4 {exit 1} {for(i=1;i<=4;i++)if($i!~/^[0-9]+$/ || $i>255)exit 1;if($1<1 || $1>223 || $1==127)exit 1}' || exit 1
if [ -n "$probe" ];then
 case "$probe" in http://*) authority=${probe#http://};;https://*) authority=${probe#https://};;*) exit 1;;esac
 authority=${authority%%/*}
 case "$probe" in *[[:space:]]*|*\?*|*\#*|*@*) exit 1;;esac
 host=${authority%%:*};oem_token "$host" || exit 1
 if [ "$host" != "$authority" ];then
  port=${authority#*:};case "$port" in ''|*[!0-9]*) exit 1;;esac
  [ "${#port}" -le 5 ] && [ "$port" -ge 1 ] && [ "$port" -le 65535 ] || exit 1
 fi
 oem_bounded_run 20 wget -O /dev/null "$probe" || { echo 'Existing installer endpoint is unreachable; OpenWiFi fallback retained' >&2;exit 1; }
elif command -v ping >/dev/null 2>&1;then
 oem_bounded_run 10 ping -c 1 -W 5 "$gateway" >/dev/null || { echo 'Gateway reachability failed; OpenWiFi fallback retained' >&2;exit 1; }
else
 echo 'Gateway ping unavailable: use --network-url with the existing installer endpoint' >&2;exit 1
fi
# --yes is the operator's healthy-console confirmation, never a new service.
prove || exit 1
fw_printenv -c "$config" > "$work/before"
printf '%s\n' bootcmd image bootcount changing_bootcmd miami_oem_once_state > "$work/allowed"
cp "$work/before" "$work/before-check"
oem_env_preserved "$work/before" "$work/before-check" "$work/allowed" || exit 1
printf 'bootcount 0\nbootcmd bootipq\nimage %s\nchanging_bootcmd\nmiami_oem_once_state confirmed\n' "$target" > "$work/confirm"
printf 'bootcount 0\nbootcmd run miami_boot%s\nimage %s\nchanging_bootcmd 1\nmiami_oem_once_state started\n' "$source" "$source" > "$work/rollback"
# Roll back to the preserved OW fallback on any failed batch/readback.
confirmed=0
rollback() {
 if [ "$confirmed" != 1 ];then
  fw_setenv -c "$config" -s "$work/rollback" && sync &&
   [ "$(get bootcount)" = 0 ] && [ "$(get bootcmd)" = "run miami_boot$source" ] && [ "$(get image)" = "$source" ] &&
   [ "$(get changing_bootcmd)" = 1 ] && [ "$(get miami_oem_once_state)" = started ] && [ "$(get miami_boot$source)" = "$prior" ] &&
   fw_printenv -c "$config" > "$work/rollback-readback" && oem_env_preserved "$work/before" "$work/rollback-readback" "$work/allowed" || echo 'OEM confirmation rollback is uncertain; do not reboot' >&2
 fi
 rm -rf "$work"
}
trap rollback EXIT
fw_setenv -c "$config" -s "$work/confirm" && sync || exit 1
fw_printenv -c "$config" > "$work/after"
[ "$(get bootcount)" = 0 ] && [ "$(get bootcmd)" = bootipq ] && [ "$(get image)" = "$target" ] && [ -z "$(get changing_bootcmd || true)" ] && [ "$(get miami_oem_once_state)" = confirmed ] && [ "$(get miami_boot$source)" = "$prior" ] || exit 1
oem_env_preserved "$work/before" "$work/after" "$work/allowed" || exit 1
confirmed=1
printf 'Retained OEM slot %s confirmed; original OpenWiFi bank and identity untouched. No firmware write or reboot performed.\n' "$target"
