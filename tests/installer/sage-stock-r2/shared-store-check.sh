#!/bin/sh
# Read-only shared-store prerequisites; never mount, allocate, copy or erase.
sage_shared_store_check() {
 local sys=${AB_UBI_SYS:-/sys/class/ubi} mounts=${AB_PROC_MOUNTS:-/proc/mounts}
 local store=${AB_CERTIFICATE_STORE:-/certificates} runtime=${AB_CERTIFICATE_RUNTIME:-/etc/ucentral}
 local volume reserved capacity available work result=0
 [ "$AB_LAYOUT" = pair ] && [ "$(ab_certificate_lebs)" = 0 ] || return 1
 [ "$(cat "$sys/$AB_ACTIVE_UBI/mtd_num")" = "$AB_ACTIVE_MTD" ] || return 1
 volume=$(ab_ubi_volume "$AB_ACTIVE_UBI" certificates) || volume=
 if [ -z "$volume" ]; then
  available=$(cat "$sys/$AB_ACTIVE_UBI/avail_eraseblocks") || return 1
  case "$available" in ''|*[!0-9]*) return 1 ;; esac
  [ "$available" -ge 20 ] || { echo 'Shared certificates absent and capacity below 20 LEBs' >&2; return 1; }
  echo 'Shared certificates absent: explicit provision/persist prerequisite; no allocation attempted' >&2
  return 1
 fi
 reserved=$(cat "$sys/$volume/reserved_ebs") || return 1
 capacity=$(cat "$sys/$volume/usable_eb_size") || return 1
 case "$reserved:$capacity" in *[!0-9:]*|:*|*:) return 1 ;; esac
 [ "$reserved" -ge 20 ] && [ "$capacity" = "$AB_LEB" ] || return 1
 awk -v path="$store" -v dev="${AB_DEV:-/dev}/$volume" -v named="$AB_ACTIVE_UBI:certificates" \
  '$2==path { count++; if(($1==dev || $1==named) && $3=="ubifs") good++ } END { exit !(count==1 && good==1) }' "$mounts" || return 1
 ab_certificate_tree_safe "$store" || return 1
 for file in key.pem cert.pem; do
  [ -f "$store/$file" ] && [ ! -L "$store/$file" ] &&
   [ -f "$runtime/$file" ] && [ ! -L "$runtime/$file" ] &&
   cmp -s "$store/$file" "$runtime/$file" || return 1
 done
 for file in "$store/key.pem" "$runtime/key.pem"; do
  LC_ALL=C ls -ldn "$file" | awk -v owner="${AB_CERTIFICATE_OWNER:-0}" \
   'substr($1,8,3)=="---" && $3==owner { good=1 } END { exit !good }' || return 1
 done
 command -v openssl >/dev/null || return 1
 umask 077
 work=$(mktemp -d /tmp/sage-shared-certificate-check.XXXXXX) || return 1
 openssl x509 -in "$store/cert.pem" -pubkey -noout > "$work/cert-public" 2>/dev/null &&
  openssl pkey -in "$store/key.pem" -pubout > "$work/key-public" 2>/dev/null &&
  cmp -s "$work/cert-public" "$work/key-public" || result=1
 rm -f "$work/cert-public" "$work/key-public"
 rmdir "$work" || result=1
 return "$result"
}
