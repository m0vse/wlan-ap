#!/bin/sh
# Minimal unique per-device data only. Firmware and customer configuration
# never enter this allowlist. Reuse model/release assets in the image/provider.
oem_backup_plan_check() {
 awk -F '\t' '
  NF!=4 || seen[$1]++ || seenpart[$2]++ {bad=1}
  $1!~/^(ART|MFG|ENV|BOOTCONFIG0|BOOTCONFIG1|UNITDATA)$/ {bad=1}
  $2!~/^(0:ART|ART|art|mfginfo|0:mfginfo|0:APPSBLENV|u-boot-env|0:BOOTCONFIG|0:BOOTCONFIG1|BOOTCONFIG|BOOTCONFIG1|MRAM)$/ {bad=1}
  $3!~/^[0-9]+$/ || $3==0 || $3>2097152 || $4!~/^[A-Za-z0-9_.-]+$/ {bad=1}
  $1=="MFG" && $3>262144 {bad=1}
  $1=="ENV" && $3>131072 {bad=1}
  $1~/^BOOTCONFIG/ && $3>65536 {bad=1}
  $1=="ART" && $2!~/^(0:ART|ART|art)$/ {bad=1}
  $1=="MFG" && $2!~/^(mfginfo|0:mfginfo)$/ {bad=1}
  $1=="ENV" && $2!~/^(0:APPSBLENV|u-boot-env)$/ {bad=1}
  $1~/^BOOTCONFIG/ && $2!~/^(0:BOOTCONFIG1?|BOOTCONFIG1?)$/ {bad=1}
  $1=="UNITDATA" && $2!="MRAM" {bad=1}
  END{exit bad || NR<2 || NR>6}' "$1"
}
oem_backup_capture() (
 plan=$1 sys=$2 dev=$3 output=$4
 oem_backup_plan_check "$plan" || exit 1
 [ ! -e "$output" ] && [ ! -L "$output" ] || exit 1
 # Resolve and validate the entire plan before copying any bytes.
 resolved=$OEM_WORK/critical-resolved.tsv
 : > "$resolved"
 while IFS="$(printf '\t')" read -r kind name limit reason; do
  found= count=0
  for node in "$sys"/mtd[0-9]*; do
   index=${node##*/mtd};case "$index" in ''|*[!0-9]*) continue;; esac
   [ -f "$node/name" ] && [ "$(cat "$node/name")" = "$name" ] || continue
   type=$(cat "$node/type") || exit 1
   case "$type" in nor|nand) ;; *) continue;; esac
   found=$index;count=$((count+1))
  done
  [ "$count" = 1 ] || exit 1
  size=$(cat "$sys/mtd$found/size") || exit 1
  case "$size:$limit" in *[!0-9:]*) exit 1;; esac
  [ "$size" -gt 0 ] && [ "$size" -le "$limit" ] || exit 1
  [ -c "$dev/mtd${found}ro" ] || exit 1
  printf '%s\t%s\t%s\t%s\t%s\n' "$kind" "$name" "$found" "$size" "$reason" >> "$resolved"
 done < "$plan"
 mkdir -m 700 "$output" || exit 1
 while IFS="$(printf '\t')" read -r kind name index size reason; do
  dd if="$dev/mtd${index}ro" of="$output/$kind.bin" bs=65536 2>/dev/null || exit 1
  [ "$(wc -c < "$output/$kind.bin")" -eq "$size" ] || exit 1
  chmod 600 "$output/$kind.bin" || exit 1
  [ "$(oem_sha "$output/$kind.bin")" = "$(oem_sha "$dev/mtd${index}ro")" ] || exit 1
  printf '%s\t%s\t%s\t%s\n' "$kind" "$name" "$size" "$reason" >> "$output/manifest.tsv"
 done < "$resolved"
 chmod 600 "$output/manifest.tsv" || exit 1
 (cd "$output" && sha256sum ./*.bin manifest.tsv > SHA256SUMS) || exit 1
 chmod 600 "$output/SHA256SUMS" || exit 1
 sync || exit 1
)
# Existing cambium-serve/relay upload protocol: hex chunks with independently
# checked chunk and final whole-file SHA256 replies. No new service or API.
oem_backup_upload() {
 directory=$1
 if ! wget --help 2>&1 | grep -q -- '--post-file'; then
  command -v curl >/dev/null || return 1
  for file in "$directory"/*.bin "$directory/manifest.tsv" "$directory/SHA256SUMS"; do
   [ -f "$file" ] && [ ! -L "$file" ] || return 1
   reply=$(oem_bounded_run 15 curl -sS -f -T "$file" "${OEM_BACKUP_URL%/}/upload/cambium-$OEM_SERIAL-$OEM_BACKUP_ID-${file##*/}") || return 1
   [ "${reply%% *}" = "$(oem_sha "$file")" ] || return 1
  done
  printf '%s\n' "$(oem_sha "$directory/SHA256SUMS")" > "$directory/OFFDEVICE_VERIFIED"
  chmod 600 "$directory/OFFDEVICE_VERIFIED" && sync
  return $?
 fi
 for file in "$directory"/*.bin "$directory/manifest.tsv" "$directory/SHA256SUMS"; do
  [ -f "$file" ] && [ ! -L "$file" ] || return 1
  name=cambium-$OEM_SERIAL-$OEM_BACKUP_ID-${file##*/}
  url=${OEM_BACKUP_URL%/}/upload/$name
  size=$(wc -c < "$file");offset=0
  while [ "$offset" -lt "$size" ]; do
   dd if="$file" of="$OEM_WORK/chunk" bs=262144 skip=$((offset/262144)) count=1 2>/dev/null || return 1
   od -An -v -tx1 "$OEM_WORK/chunk" | tr -d ' \n' > "$OEM_WORK/chunk.hex" || return 1
   reply=$(oem_bounded_run 15 wget -q -O - --post-file "$OEM_WORK/chunk.hex" "$url?offset=$offset") || return 1
   [ "${reply%% *}" = "$(oem_sha "$OEM_WORK/chunk")" ] || return 1
   offset=$((offset+262144))
  done
  reply=$(oem_bounded_run 15 wget -q -O - --post-data done "$url?done") || return 1
  [ "${reply%% *}" = "$(oem_sha "$file")" ] || return 1
 done
 printf '%s\n' "$(oem_sha "$directory/SHA256SUMS")" > "$directory/OFFDEVICE_VERIFIED"
 chmod 600 "$directory/OFFDEVICE_VERIFIED" && sync
}

oem_backup_uploader_check() {
 wget --help 2>&1 | grep -q -- '--post-file' || command -v curl >/dev/null
}

oem_backup_receipt_check() {
 directory=$1
 oem_private_directory "$directory" || return 1
 for name in SHA256SUMS OFFDEVICE_VERIFIED manifest.tsv; do oem_private_file "$directory/$name" || return 1;done
 [ "$(wc -c < "$directory/OFFDEVICE_VERIFIED")" -eq 65 ] &&
 [ "$(cat "$directory/OFFDEVICE_VERIFIED")" = "$(oem_sha "$directory/SHA256SUMS")" ] || return 1
 awk 'NF!=2 || length($1)!=64 || $1~/[^0-9a-f]/ {bad=1}
  {name=$2;sub(/^\.\//,"",name);if(name!~/^(ART.bin|MFG.bin|ENV.bin|BOOTCONFIG0.bin|BOOTCONFIG1.bin|UNITDATA.bin|manifest.tsv)$/ || seen[name]++)bad=1}
  END{exit bad || NR<3}' "$directory/SHA256SUMS" || return 1
 (cd "$directory" && sha256sum -c SHA256SUMS >/dev/null 2>&1) || return 1
 while read -r digest name; do oem_private_file "$directory/$name" || return 1;done < "$directory/SHA256SUMS"
}
