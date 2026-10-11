#!/bin/sh
# Common installer boundaries. No enrollment request, private key or CSR creation.
oem_fail() { printf '%s\n' "OEM migration stopped: $*" >&2; return 1; }
oem_sha() { sha256sum < "$1" | awk '{print $1}'; }
oem_hex64() { [ "${#1}" = 64 ] && case "$1" in *[!0-9a-f]*) return 1;; *) return 0;; esac; }
oem_token() { case "$1" in ''|*[!A-Za-z0-9._-]*) return 1;; *) return 0;; esac; }
oem_read_hex() (
 file=$1 bytes=$2
 case "$bytes" in ''|*[!0-9]*) return 1;; esac
 [ "$bytes" -ge 1 ] && [ "$bytes" -le 64 ] || return 1
 if command -v od >/dev/null 2>&1; then
  raw=$(od -An -tx1 -N"$bytes" "$file") || return 1
 elif command -v hexdump >/dev/null 2>&1; then
  raw=$(hexdump -v -n "$bytes" -e '1/1 "%02x"' "$file") || return 1
 else
  return 1
 fi
 value=$(printf '%s' "$raw" | tr -d ' \n') || return 1
 [ "${#value}" -eq "$((2*bytes))" ] || return 1
 case "$value" in *[!0-9a-f]*) return 1;; esac
 printf '%s\n' "$value"
)
oem_detect() {
 OEM_SKU= OEM_FAMILY= OEM_MODEL=
 for path in "$OEM_SYS_ROOT/proc/device-tree/cambium-platform/board-sku" "$OEM_SYS_ROOT/sys/firmware/devicetree/base/cambium-platform/board-sku"; do
  [ -r "$path" ] || continue
  [ "$(wc -c < "$path")" -eq 4 ] || return 1
  value=$(oem_read_hex "$path" 4) || return 1
  [ "${#value}" = 8 ] || return 1
  [ -z "$OEM_SKU" ] || [ "$OEM_SKU" = "$value" ] || return 1
  OEM_SKU=$value
 done
 if [ -z "$OEM_SKU" ] && [ -r "$OEM_SYS_ROOT/proc/sku" ]; then
  value=$(cat "$OEM_SYS_ROOT/proc/sku") || return 1
  case "$value" in ''|*[!0-9]*) return 1;; esac
  [ "${#value}" -le 3 ] && [ "$value" -le 255 ] || return 1
  OEM_SKU=$(printf '%08x' "$value")
 fi
 OEM_REPORTED_SKU=$OEM_SKU
 # Legacy Sage firmware can omit SKU DT data or report A's SKU on a factory B
 # unit. Use only its authenticated, strict manufacturing decoder.
 if [ -z "$OEM_SKU" ] || [ "$OEM_SKU" = 0000000a ] || [ "$OEM_SKU" = 00000015 ]; then
  decoder=$(oem_bundle_member adapters/sage.sh 2>/dev/null || true)
  if [ -n "$decoder" ]; then
   tuple=$(
    . "$decoder" || exit 1
    command -v oem_sage_detect >/dev/null || exit 1
    oem_sage_detect
   ) || tuple=
   if [ -n "$tuple" ]; then
    printf '%s\n' "$tuple" | awk -F '\t' 'NF!=2 || $1!~/^000000(0a|15)$/ || $2!~/^E410B?$/ {bad=1} END{exit bad || NR!=1}' || return 1
    OEM_SKU=$(printf '%s\n' "$tuple" | cut -f1)
   fi
  fi
 fi
 case "$OEM_SKU" in ????????) ;; *) oem_fail 'factory SKU cannot be read safely'; return 1;; esac
 row=$(awk -F '\t' -v sku="$OEM_SKU" '!/^#/ && $1==sku {print;n++} END{if(n!=1)exit 1}' "$OEM_BUNDLE/recognition.tsv") || { oem_fail 'unknown model; no changes made'; return 1; }
 OEM_FAMILY=$(printf '%s\n' "$row" | cut -f2)
 OEM_MODEL=$(printf '%s\n' "$row" | cut -f3)
 oem_token "$OEM_FAMILY" && oem_token "$OEM_MODEL"
}
oem_release_check() {
 oem_hex64 "$OEM_RELEASE_PIN" || { oem_fail 'independent release hash is required'; return 1; }
 [ -d "$OEM_BUNDLE" ] && [ ! -L "$OEM_BUNDLE" ] && [ "$(readlink -f "$OEM_BUNDLE")" = "$OEM_BUNDLE" ] || return 1
 [ -f "$OEM_BUNDLE/SHA256SUMS" ] && [ ! -L "$OEM_BUNDLE/SHA256SUMS" ] || return 1
 [ "$(oem_sha "$OEM_BUNDLE/SHA256SUMS")" = "$OEM_RELEASE_PIN" ] || return 1
 awk 'NF!=2 || length($1)!=64 || $1~/[^0-9a-f]/ || $2!~/^[A-Za-z0-9_.\/-]+$/ || $2~/^\// || $2~/(^|\/)\.\.?(\/|$)/ || seen[$2]++ {bad=1} END{exit bad || NR<2}' "$OEM_BUNDLE/SHA256SUMS" || return 1
 while read -r digest name; do
  [ -f "$OEM_BUNDLE/$name" ] && [ ! -L "$OEM_BUNDLE/$name" ] || return 1
  [ "$(readlink -f "$OEM_BUNDLE/$name")" = "$OEM_BUNDLE/$name" ] || return 1
 done < "$OEM_BUNDLE/SHA256SUMS"
 (cd "$OEM_BUNDLE" && sha256sum -c SHA256SUMS >/dev/null 2>&1) || return 1
 # Every control file read or sourced below must itself be authenticated.
 for name in "${OEM_MODEL_MAP:-models.tsv}" deployment.tsv; do
  awk -v name="$name" '$2==name {n++} END{exit n!=1}' "$OEM_BUNDLE/SHA256SUMS" || return 1
 done
 row=$(awk -F '\t' -v sku="$OEM_SKU" -v family="$OEM_FAMILY" -v model="$OEM_MODEL" 'NF!=5 {bad=1} $1==sku && $2==family && $3==model {print;n++} END{exit bad || n!=1}' "$OEM_BUNDLE/${OEM_MODEL_MAP:-models.tsv}") || { oem_fail 'this exact model has no released adapter'; return 1; }
 OEM_SUPPORTED_RELEASE=$(printf '%s\n' "$row" | cut -f5)
 case "$OEM_SUPPORTED_RELEASE" in ''|*[!A-Za-z0-9._~-]*) return 1;; esac
 OEM_ADAPTER=$(printf '%s\n' "$row" | cut -f4)
 case "$OEM_ADAPTER" in miami|sage|jaguar|cheetah|thor) ;; *) oem_fail 'model is recognized but unsupported'; return 1;; esac
 name=adapters/${OEM_ADAPTER_PREFIX:-}$OEM_ADAPTER.sh
 awk -v name="$name" '$2==name {n++} END{exit n!=1}' "$OEM_BUNDLE/SHA256SUMS" || return 1
 # Deployment is non-executable and contains no enrollment secret.
 awk -F '\t' 'NF!=2 || $1!~/^(controller|download_url|backup_url)$/ || seen[$1]++ {bad=1} END{exit bad || NR!=3}' "$OEM_BUNDLE/deployment.tsv" || return 1
 OEM_CONTROLLER=$(awk -F '\t' '$1=="controller"{print $2}' "$OEM_BUNDLE/deployment.tsv")
 OEM_DOWNLOAD_URL=$(awk -F '\t' '$1=="download_url"{print $2}' "$OEM_BUNDLE/deployment.tsv")
 OEM_BACKUP_URL=$(awk -F '\t' '$1=="backup_url"{print $2}' "$OEM_BUNDLE/deployment.tsv")
 case "$OEM_CONTROLLER" in ''|*[!A-Za-z0-9.-]*|.*|*.) return 1;; esac
 for value in "$OEM_DOWNLOAD_URL" "$OEM_BACKUP_URL"; do
  case "$value" in http://*|https://*) ;; *) return 1;; esac
  case "$value" in *[[:space:]]*|*\?*|*\#*|*@*) return 1;; esac
 done
}
oem_context_check() {
 case "$OEM_SERIAL" in ''|*[!0-9a-f]*|000000000000|ffffffffffff) return 1;; esac
 [ "${#OEM_SERIAL}" = 12 ] || return 1
 case "$OEM_SOURCE_SLOT:$OEM_TARGET_SLOT" in 0:1|1:0) ;; *) return 1;; esac
 case "$OEM_SOURCE_RELEASE" in ''|*[!A-Za-z0-9._~-]*) return 1;; esac
 [ "${#OEM_SOURCE_RELEASE}" -le 64 ] || return 1
 [ "$OEM_SOURCE_RELEASE" = "$OEM_SUPPORTED_RELEASE" ] || {
  oem_fail "OEM release $OEM_SOURCE_RELEASE is unsupported; this model requires $OEM_SUPPORTED_RELEASE. Upgrade OEM through its supported procedure first."
  return 1
 }
}
oem_context_fingerprint() { printf '%s\n' "$OEM_SKU" "${OEM_REPORTED_SKU:-}" "$OEM_MODEL" "$OEM_SERIAL" "$OEM_SOURCE_RELEASE" "$OEM_SOURCE_SLOT" "$OEM_TARGET_SLOT" | sha256sum | awk '{print $1}'; }

oem_prompt_key() {
 [ -r /dev/tty ] && [ -w /dev/tty ] || return 1
 OEM_TTY_STATE=$(stty -g < /dev/tty) || return 1
 stty -echo < /dev/tty || return 1
 printf 'Onboarding key: ' > /dev/tty
 IFS= read -r OEM_KEY < /dev/tty
 result=$?
 stty "$OEM_TTY_STATE" < /dev/tty || return 1
 OEM_TTY_STATE=
 printf '\n' > /dev/tty
 [ "$result" = 0 ] || return 1
 case "$OEM_KEY" in ''|*[!A-Za-z0-9_-]*) return 1;; esac
 [ "${#OEM_KEY}" = 64 ]
}
oem_confirm() {
 printf 'Install OpenWiFi in inactive slot %s, preserving OEM and device calibration? Type INSTALL: ' "$OEM_TARGET_SLOT" > /dev/tty
 IFS= read -r answer < /dev/tty && [ "$answer" = INSTALL ]
}
oem_reboot_choice() {
 printf 'Migration staged and boot armed. Reboot now? [y/N] ' > /dev/tty
 IFS= read -r answer < /dev/tty || return 1
 case "$answer" in y|Y) sync && reboot;; *) printf 'Reboot manually when ready.\n';; esac
}
oem_cleanup() {
 [ -z "${OEM_TTY_STATE:-}" ] || stty "$OEM_TTY_STATE" < /dev/tty
 unset OEM_KEY key ENROLMENT_KEY credential
 # Failed runs retain recovery receipts and adapter journals. Never undo writes.
 [ -z "${OEM_LOCK:-}" ] || rmdir "$OEM_LOCK" 2>/dev/null
}

oem_bundle_member() (
 name=$1
 case "$name" in ''|/*|*'/../'*|../*|*'/./'*|*[!A-Za-z0-9_./-]*) return 1;; esac
 digest=$(awk -v name="$name" '$2==name{print $1;n++}END{if(n!=1)exit 1}' "$OEM_BUNDLE/SHA256SUMS") || {
  [ -n "${OEM_OBJECT_ROOT:-}" ] && [ -n "${OEM_SELECTED_PAYLOADS:-}" ] || return 1
  row=$(awk -F '\t' -v name="$name" '$3==name{print $5, $6;n++}END{if(n!=1)exit 1}' "$OEM_SELECTED_PAYLOADS") || return 1
  read -r size digest <<EOF_OBJECT
$row
EOF_OBJECT
  file=$OEM_OBJECT_ROOT/$name
  oem_private_file "$file" && [ "$(readlink -f "$file")" = "$file" ] &&
   [ "$(wc -c < "$file")" -eq "$size" ] && [ "$(oem_sha "$file")" = "$digest" ] || return 1
  printf '%s\n' "$file";return 0
 }
 [ -f "$OEM_BUNDLE/$name" ] && [ ! -L "$OEM_BUNDLE/$name" ] && [ "$(readlink -f "$OEM_BUNDLE/$name")" = "$OEM_BUNDLE/$name" ] || return 1
 [ "$(oem_sha "$OEM_BUNDLE/$name")" = "$digest" ] || return 1
 printf '%s\n' "$OEM_BUNDLE/$name"
)
oem_read_release() {
 file=$1
 [ -f "$file" ] && [ ! -L "$file" ] || return 1
 awk -F= '$1=="VERSION"{value=$2;n++}END{if(n!=1 || value!~/^[A-Za-z0-9._~-]+$/ || length(value)>64)exit 1;print value}' "$file"
}

oem_boot_check() {
 case "${OEM_BOOT_WATCHDOG:-}" in verified|manual-reset) ;; *) oem_fail 'boot failure reset policy is unknown';return 1;; esac
 [ "${OEM_BOOT_PRIOR_SLOT:-}" = "$OEM_SOURCE_SLOT" ] &&
 [ "${OEM_BOOT_TARGET_SLOT:-}" = "$OEM_TARGET_SLOT" ] &&
 [ "${OEM_BOOT_MODE:-}" = persist-prior-before-load ] || {
  oem_fail 'one-shot prior-slot/saveenv contract is not proven for this source'; return 1
 }
}

oem_source_identifiers_check() {
 actual=$1 expected=$2
 [ -f "$actual" ] && [ ! -L "$actual" ] || return 1
 awk -F '\t' 'NF!=2 || $1!~/^(PRODUCT|VERSION|BUILD_DATE|BUILD_VERSION)$/ || seen[$1]++ {bad=1} END{exit bad || NR<2}' "$expected" || return 1
 while IFS="$(printf '\t')" read -r field expected_value; do
  value=$(awk -v key="$field" 'index($0,key "=")==1{print substr($0,length(key)+2);n++}END{if(n!=1)exit 1}' "$actual") || return 1
  [ "$value" = "$expected_value" ] || { oem_fail 'OEM build identifiers disagree with the supported source profile';return 1; }
 done < "$expected"
}

oem_private_directory() {
 [ -d "$1" ] && [ ! -L "$1" ] && [ "$(readlink -f "$1")" = "$1" ] || return 1
 LC_ALL=C ls -ldn "$1" | awk 'NR==1 && $1=="drwx------" && $3==0{good=1}END{exit NR!=1 || !good}'
}
oem_private_file() {
 [ -f "$1" ] && [ ! -L "$1" ] || return 1
 LC_ALL=C ls -ldn "$1" | awk 'NR==1 && $1=="-rw-------" && $2==1 && $3==0{good=1}END{exit NR!=1 || !good}'
}

oem_boot_inspect() {
 OEM_BOOT_PRIOR_SLOT= OEM_BOOT_TARGET_SLOT= OEM_BOOT_MODE= OEM_BOOT_WATCHDOG=
 "$1" && oem_boot_check
}
