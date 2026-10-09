#!/bin/sh
# Bounded local staging only. No firmware/device writes, no enrollment secret.
# Conservative aggregate budget: reserve an entire attempt before starting it.
oem_payload_map_check() {
 awk -F '\t' '
  function data(p,model,leaf,radio) {
   if(p~/\.(sh|py|uc|so|pem|key)$/)return 0
   if(p~/^(payloads|assets)\// && p!~("^(payloads|assets)/" model "/"))return 0
   if(p~/\.(bin|itb|squashfs|ubifs|ubi|json|contents)$/)return 1
   radio=(index(p,"payloads/" model "/assets/lib/firmware/")==1 || index(p,"assets/" model "/lib/firmware/")==1)
   leaf=p;sub(/^.*\//,"",leaf)
   return radio && leaf~/^(bdwlan\.[A-Za-z0-9_.-]+|regdb\.bin[A-Za-z0-9_.-]*|q6_fw[01]\.(mdt|b[0-9a-fA-F]+)|iu_fw\.(mdt|b[0-9a-fA-F]+))$/
  }
  NF!=6 || $1!~/^[A-Za-z0-9_-]+$/ || $2!~/^(install|restore|confirm)$/ || seen[$1 FS $2 FS $3]++ {bad=1}
  $3!~/^[A-Za-z0-9_.\/-]+$/ || !data($3,$1) || $4!~/^[A-Za-z0-9_.\/-]+$/ {bad=1}
  $3~/^\// || $4~/^\// || $3~/(^|\/)\.\.?(\/|$)/ || $4~/(^|\/)\.\.?(\/|$)/ || $3~/\/\// || $4~/\/\// {bad=1}
  $3~/^(lib|adapters|readers|profiles)\// {bad=1}
  $5!~/^[1-9][0-9]*$/ || $5>268435456 || length($6)!=64 || $6~/[^0-9a-f]/ {bad=1}
  END{exit bad || NR<1}' "$1"
}
oem_payload_stage() {
 [ -f "$OEM_BUNDLE/payload-map.tsv" ] || return 0
 local map selected model operation name remote size digest missing total=0 remaining directory offline=1
 map=$(oem_bundle_member payload-map.tsv) || return 1
 oem_payload_map_check "$map" || return 1
 OEM_SELECTED_PAYLOADS=$OEM_WORK/selected-payloads.tsv
 awk -F '\t' -v model="$OEM_MODEL" -v operation="$1" '$1==model && $2==operation' "$map" > "$OEM_SELECTED_PAYLOADS" || return 1
 [ -s "$OEM_SELECTED_PAYLOADS" ] || return 1
 chmod 600 "$OEM_SELECTED_PAYLOADS" || return 1
 while IFS="$(printf '\t')" read -r model operation name remote size digest; do
  awk -v name="$name" '$2==name{n++}END{exit n!=1}' "$OEM_BUNDLE/SHA256SUMS" || offline=0
 done < "$OEM_SELECTED_PAYLOADS"
 if [ "$offline" = 1 ]; then
  OEM_OBJECT_ROOT=$OEM_BUNDLE
  oem_payload_closure_check
  return $?
 fi
 OEM_OBJECT_ROOT=$OEM_WORK/cache
 [ -d "$OEM_OBJECT_ROOT" ] || mkdir -m 700 "$OEM_OBJECT_ROOT" || return 1
 while IFS="$(printf '\t')" read -r model operation name remote size digest; do
  directory=$(dirname "$OEM_OBJECT_ROOT/$name")
  mkdir -p "$directory" && chmod 700 "$directory" || return 1
  missing=$(oem_stage_missing_bytes "$OEM_OBJECT_ROOT/$name" "$digest" "$size") || return 1
  total=$((total+missing))
 done < "$OEM_SELECTED_PAYLOADS"
 oem_stage_space_check "$OEM_OBJECT_ROOT" "$total" || return 1
 remaining=$total
 while IFS="$(printf '\t')" read -r model operation name remote size digest; do
  missing=$(oem_stage_missing_bytes "$OEM_OBJECT_ROOT/$name" "$digest" "$size") || return 1
  remaining=$((remaining-missing));OEM_STAGE_EXTRA_BYTES=$remaining
  oem_fetch_local "$remote" "$digest" "$size" "$OEM_OBJECT_ROOT/$name" || return 1
 done < "$OEM_SELECTED_PAYLOADS"
 OEM_STAGE_EXTRA_BYTES=0
 oem_payload_closure_check
}
oem_payload_closure_check() (
 [ -n "${OEM_SELECTED_PAYLOADS:-}" ] || exit 0
 original=$(oem_bundle_member payload-map.tsv) || exit 1
 filtered=$OEM_WORK/payload-recheck.tsv
 awk -F '\t' -v model="$OEM_MODEL" -v operation="$OEM_OPERATION" '$1==model && $2==operation' "$original" > "$filtered" || exit 1
 cmp -s "$filtered" "$OEM_SELECTED_PAYLOADS" || exit 1
 while IFS="$(printf '\t')" read -r model operation name remote size digest; do
  file=$(oem_bundle_member "$name") || exit 1
  [ "$(wc -c < "$file")" -eq "$size" ] && [ "$(oem_sha "$file")" = "$digest" ] || exit 1
 done < "$OEM_SELECTED_PAYLOADS"
)
oem_stage_space_check() (
 directory=$1 bytes=$2
 case "$bytes" in ''|*[!0-9]*) return 1;; esac
 oem_private_directory "$directory" || return 1
 available=$(df -Pk "$directory" | awk 'NR==2 && $4~/^[0-9]+$/{print $4;good=1}END{if(!good)exit 1}') || return 1
 [ "$available" -ge "$(((bytes+1023)/1024))" ] || {
  oem_fail 'insufficient space for the actual local staging plan';return 1
 }
)

# A validated existing cache consumes space already counted by df. Anything
# else needs its full bounded object size, and an unsafe existing path refuses.
oem_stage_missing_bytes() (
 output=$1 expected=$2 size=$3
 oem_hex64 "$expected" || return 1
 case "$size" in ''|*[!0-9]*) return 1;; esac
 [ "$size" -gt 0 ] && [ "$size" -le 268435456 ] || return 1
 if [ -e "$output" ] || [ -L "$output" ]; then
  oem_private_file "$output" && [ "$(wc -c < "$output")" -eq "$size" ] &&
   [ "$(oem_sha "$output")" = "$expected" ] || return 1
  printf '0\n'
 else
  printf '%s\n' "$size"
 fi
)

oem_pid_stamp() {
 [ -r "/proc/$1/stat" ] || return 1
 awk '{print $22}' "/proc/$1/stat"
}
oem_kill_owned_tree() (
 pid=$1 stamp=$2
 [ "$(oem_pid_stamp "$pid" 2>/dev/null || true)" = "$stamp" ] || return 0
 if [ -r "/proc/$pid/task/$pid/children" ]; then
  children=$(cat "/proc/$pid/task/$pid/children")
  for child in $children; do
   childstamp=$(oem_pid_stamp "$child" 2>/dev/null || true)
   [ -z "$childstamp" ] || oem_kill_owned_tree "$child" "$childstamp"
  done
 fi
 [ "$(oem_pid_stamp "$pid" 2>/dev/null || true)" != "$stamp" ] || kill -KILL "$pid" 2>/dev/null || true
)
oem_bounded_run() {
 budget=$1;shift
 case "$budget" in ''|*[!0-9]*) return 1;; esac
 [ "$budget" -ge 1 ] && [ "$budget" -le 60 ] || return 1
 [ -r /proc/self/stat ] || return 1
 "$@" &
 worker=$!
 stamp=$(oem_pid_stamp "$worker" 2>/dev/null || true)
 (
  sleep "$budget"
  [ -z "$stamp" ] || oem_kill_owned_tree "$worker" "$stamp"
 ) &
 timer=$!
 status=0;wait "$worker" || status=$?
 kill "$timer" 2>/dev/null || true
 wait "$timer" 2>/dev/null || true
 return "$status"
}
oem_fetch_local() {
 name=$1 expected=$2 size=$3 output=$4
 oem_hex64 "$expected" || return 1
 case "$name" in ''|/*|*'/../'*|../*|*'/./'*|*'//'*|*[!A-Za-z0-9_./-]*) return 1;; esac
 case "$size" in ''|*[!0-9]*) return 1;; esac
 [ "$size" -gt 0 ] && [ "$size" -le 268435456 ] || return 1
 directory=$(dirname "$output")
 oem_private_directory "$directory" || return 1
 [ ! -L "$output" ] && [ ! -L "$output.part" ] || return 1
 if oem_private_file "$output" && [ "$(wc -c < "$output")" -eq "$size" ] && [ "$(oem_sha "$output")" = "$expected" ]; then return 0;fi
 # Keep at most a bounded partial regular file; never overwrite known data.
 [ ! -e "$output" ] && [ ! -e "$output.part" ] || return 1
 extra=${OEM_STAGE_EXTRA_BYTES:-0}
 case "$extra" in ''|*[!0-9]*) return 1;; esac
 oem_stage_space_check "$directory" "$((size+extra))" || return 1
 # Self-contained releases can supply the exact authenticated object locally.
 # Keep the legacy cache ABI without contacting HTTP for that copy.
 oem_source_file=$(oem_bundle_member "$name" 2>/dev/null || true)
 if [ -n "$oem_source_file" ]; then
  oem_private_file "$oem_source_file" && [ "$(wc -c < "$oem_source_file")" -eq "$size" ] &&
   [ "$(oem_sha "$oem_source_file")" = "$expected" ] || return 1
  cp "$oem_source_file" "$output" && chmod 600 "$output" &&
   oem_private_file "$output" && [ "$(oem_sha "$output")" = "$expected" ] && sync
  return $?
 fi
 attempt=0
 while [ "$attempt" -lt 2 ]; do
  [ "${OEM_NETWORK_BUDGET_LEFT:-0}" -ge 15 ] || return 1
  OEM_NETWORK_BUDGET_LEFT=$((OEM_NETWORK_BUDGET_LEFT-15));attempt=$((attempt+1))
  # File-size ulimit bounds even a server which sends an endless response.
  # BusyBox implementations use 512/1024-byte units; provision twice size.
  oem_bounded_run 15 sh -c 'umask 077; ulimit -f "$1" || exit 1; exec wget -q -O "$2" "$3"' sh "$(((size+511)/512))" "$output.part" "${OEM_DOWNLOAD_URL%/}/$name" || true
  if [ -f "$output.part" ] && [ ! -L "$output.part" ] && [ "$(wc -c < "$output.part")" -eq "$size" ] && [ "$(oem_sha "$output.part")" = "$expected" ]; then
   chmod 600 "$output.part" && mv "$output.part" "$output" || return 1
   oem_private_file "$output" && sync || return 1
   return 0
  fi
  [ ! -L "$output.part" ] || return 1
  [ ! -e "$output.part" ] || rm -f "$output.part" || return 1
 done
 return 1
}
