#!/bin/sh
# Read-only outgoing preservation prerequisites. No mount/allocation/UCI edits.
jaguar_configuration_preservation_check() {
 local compatibility
 command -v uci >/dev/null || return 1
 uci -q show system >/dev/null 2>&1 || return 1
 compatibility=$(uci -q get 'system.@system[0].compat_version' 2>/dev/null) || compatibility=
 case "${compatibility:-1.0}" in
  1.0) return 0 ;;
  *) echo 'Only configuration 1.0 is approved for preservation' >&2; return 1 ;;
 esac
}
jaguar_mounted_store_check() {
 local sys=${AB_UBI_SYS:-/sys/class/ubi} mounts=${AB_PROC_MOUNTS:-/proc/mounts}
 local store=${AB_CERTIFICATE_STORE:-/certificates} volume
 [ "$AB_LAYOUT" = banks ] && [ "$(ab_certificate_lebs)" = 20 ] || return 1
 [ "$(cat "$sys/$AB_ACTIVE_UBI/mtd_num")" = "$AB_ACTIVE_MTD" ] || return 1
 volume=$(ab_ubi_volume "$AB_ACTIVE_UBI" certificates) || return 1
 [ "$(cat "$sys/$volume/reserved_ebs")" = 20 ] &&
  [ "$(cat "$sys/$volume/usable_eb_size")" = "$AB_LEB" ] || return 1
 [ -d "$store" ] && [ ! -L "$store" ] || return 1
 awk -v path="$store" -v dev="${AB_DEV:-/dev}/$volume" -v named="$AB_ACTIVE_UBI:certificates" \
  '$2==path {count++; if(($1==dev || $1==named) && $3=="ubifs") good++} END {exit !(count==1 && good==1)}' "$mounts" || return 1
 ab_certificate_tree_safe "$store"
}
