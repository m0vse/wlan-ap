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
jaguar_certificate_source_check() {
 local sys=${AB_UBI_SYS:-/sys/class/ubi} mounts=${AB_PROC_MOUNTS:-/proc/mounts}
 local store=${AB_CERTIFICATE_STORE:-/certificates} volume reserved capacity count
 [ "$AB_LAYOUT" = banks ] && [ "$(ab_certificate_lebs)" = 20 ] || return 1
 [ "$(cat "$sys/$AB_ACTIVE_UBI/mtd_num")" = "$AB_ACTIVE_MTD" ] || return 1
 volume=$(ab_ubi_volume "$AB_ACTIVE_UBI" certificates) || volume=
 if [ -n "$volume" ]; then
  reserved=$(cat "$sys/$volume/reserved_ebs") || return 1
  capacity=$(cat "$sys/$volume/usable_eb_size") || return 1
  case "$reserved:$capacity" in *[!0-9:]*|:*|*:) return 1 ;; esac
  [ "${#reserved}" -le 6 ] && [ "$reserved" -gt 0 ] &&
   [ "$reserved" -le "$AB_BANK_LEBS" ] && [ "$capacity" = "$AB_LEB" ] || return 1
 fi
 [ ! -L "$store" ] && { [ ! -e "$store" ] || [ -d "$store" ]; } || return 1
 count=$(awk -v path="$store" '$2==path {count++} END {print count+0}' "$mounts") || return 1
 if [ "$count" = 0 ]; then
  # An old .1 bank may have an unmounted UBIFS/erased certificate volume,
  # or no volume at all. Canonical export below validates/mounts UBIFS
  # read-only, overlays validated runtime identity and bounds the snapshot.
  # Never allocate, format, resize or mount the old store read-write here.
  return 0
 fi
 [ "$count" = 1 ] && [ -n "$volume" ] && [ -d "$store" ] || return 1
 awk -v path="$store" -v dev="${AB_DEV:-/dev}/$volume" -v named="$AB_ACTIVE_UBI:certificates" \
  '$2==path {count++; if(($1==dev || $1==named) && $3=="ubifs") good++} END {exit !(count==1 && good==1)}' "$mounts" || return 1
 ab_certificate_tree_safe "$store"
}

jaguar_runtime_identity_check() {
 local runtime=${AB_CERTIFICATE_RUNTIME:-/etc/ucentral} work result=0
 ab_certificate_private_file "$runtime/key.pem" &&
  [ -f "$runtime/cert.pem" ] && [ ! -L "$runtime/cert.pem" ] || return 1
 command -v openssl >/dev/null || return 1
 umask 077
 work=$(mktemp -d /tmp/jaguar-runtime-certificate-check.XXXXXX) || return 1
 openssl x509 -in "$runtime/cert.pem" -pubkey -noout > "$work/cert-public" 2>/dev/null &&
  openssl pkey -in "$runtime/key.pem" -pubout > "$work/key-public" 2>/dev/null &&
  cmp -s "$work/cert-public" "$work/key-public" || result=1
 rm -f "$work/cert-public" "$work/key-public"
 rmdir "$work" || result=1
 return "$result"
}
