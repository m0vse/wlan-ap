#!/bin/sh
# Operator-run outgoing bridge updater; never flashes or reboots an AP.
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
mode=${1:---check}
image=${2:?usage: prepare-upgrader.sh --check|--install|--verify-installed IMAGE}
route_request=${3:-auto}
case "$route_request" in auto|stock|openwifi) ;; *) exit 2 ;; esac
case "$mode" in --check|--install|--verify-installed) ;; *) exit 2 ;; esac
bundle=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
die() { echo "Thor outgoing updater: $*" >&2; exit 1; }
[ -f "$image" ] && [ ! -L "$image" ] || die 'image must be a regular local file'
[ "$(id -u)" = 0 ] || die 'root is required for verified device preflight'
(cd "$bundle" && sha256sum -c SHA256SUMS) || die 'bundle checksum mismatch'
image_name=$(cat "$bundle/IMAGE")
case "$image_name" in ''|*/*|*..*) die 'invalid bundled image name' ;; esac
expected=$(sha256sum < "$bundle/$image_name") || die 'cannot hash bundled image'
actual=$(sha256sum < "$image") || die 'cannot hash requested image'
[ "${actual%% *}" = "${expected%% *}" ] || die 'requested image is not the frozen Thor .10 image'
# Authenticate the complete reviewed source tuple before sourcing AP scripts.
. "$bundle/source-set-check.sh"
. "$bundle/minimum-release-contract.sh"
. "$bundle/runtime-implementation-contract.sh"
. "$bundle/source-route.sh"
source_gate() {
 current_metadata=$(ow_thor_metadata_fingerprint) || return 1
 detected=$(ow_thor_route "$bundle") || return 1
 [ "$route_request" = auto ] || [ "$detected" = "$route_request" ] || return 1
 [ "$(ow_thor_metadata_fingerprint)" = "$current_metadata" ] || return 1
 [ -z "${approved_metadata:-}" ] || [ "$current_metadata" = "$approved_metadata" ] || return 1
 approved_metadata=$current_metadata
 SOURCE_ROUTE=$detected
}
if [ "$mode" = --verify-installed ]; then
 source_gate || die 'installed updater contains unknown source files'
 ow_thor_installed_matches "$bundle" "$SOURCE_ROUTE" || die 'installed updater source tuple is not approved'
else
 source_gate || die 'outgoing updater source tuple is unknown or modified'
fi
# Complete source closure is authenticated above; stock libraries use optional
# unset variables (including IPKG_INSTROOT). Use their normal contract now.
set +u
route=$SOURCE_ROUTE
route_request=$route
if [ "$route" = stock ]; then
 export SAVE_CONFIG=0
fi
echo "Source-gated operator route: $route"
. /lib/functions/system.sh
[ "$(board_name)" = cambiumnetworks,xv3-8 ] || die 'only qualified XV3-8 is allowed'
for binary in fwtool dd cut sort basename dirname chmod chown cp mv rm mkdir gzip head seq tr mknod cat grep date fw_printenv fw_setenv ubiformat ubiattach ubidetach ubimkvol ubiupdatevol sha256sum hexdump tar ls cmp mktemp find awk sed wc mount umount readlink; do
 dependency=$(command -v "$binary") && [ -x "$dependency" ] || die "missing/nonexecutable stage2 dependency: $binary"
done
[ -x /usr/libexec/validate_firmware_image ] && [ -x /sbin/sysupgrade ] && [ -x /lib/upgrade/stage2 ] && [ -x /lib/upgrade/do_stage2 ] || die 'nonexecutable sysupgrade stage scripts'
[ "$route" != stock ] || grep -Fq -- '--no-provisioning)' /sbin/sysupgrade || die 'stock sysupgrade lacks required no-provisioning option'
grep -Fq '/lib/functions/*.sh' /lib/upgrade/stage2 || die 'stage2 does not retain family modules'
grep -Fq '/lib/upgrade/*.sh' /lib/upgrade/stage2 || die 'stage2 does not retain updater libraries'
export CAMBIUM_AB_MODULES="$bundle/modules"
export CAMBIUM_AB_LIB="$bundle/cambium-ab.sh"
export CAMBIUM_AB_CERTIFICATE_LIB="$bundle/routes/$route/cambium-ab-certificates.sh"
. "$bundle/cambium-ab.sh"
. "$bundle/cambium-ab-upgrade.sh"
ab_upgrade_preflight || die 'identity, protected layout, converted banks or trial-state preflight failed'
[ "$AB_QUALIFIED" = 1 ] || die 'unqualified model'
! ab_ubi_for_mtd "$AB_TARGET_MTD" >/dev/null || die 'inactive target is attached; refusing preparation'
[ "$AB_MODEL" = XV3-8 ] && [ "$AB_SKU" = 00000013 ] || die 'only XV3-8 SKU19 is allowed'
[ "${AB_CERTIFICATE_CONTENT_VERSION:-0}" = 1 ] || die 'canonical certificate content helper missing'
[ "${AB_CERTIFICATE_POLICY_VERSION:-0}" = 1 ] || die 'canonical certificate allocation policy missing'
probe=$(mktemp /tmp/thor-upgrader-permissions.XXXXXX) || die 'mktemp failed'
chmod 600 "$probe"
ab_certificate_private_file "$probe" || { rm -f "$probe"; die 'outgoing ls/awk permission format is incompatible'; }
rm -f "$probe"
grep -q 'ab_certificate_export' "$bundle/platform.sh" || die 'certificate snapshot hook missing'
[ "$(ab_certificate_lebs)" = 20 ] || die 'durable certificate reservation policy missing'
# This extracts and validates only in tmpfs; it never writes either bank.
cambium_ab_check_image "$image" || die 'image FIT, vault or capacity preflight failed'
# Read-only source inspection catches unsafe credentials and missing crypto
# tools before installing the bridge or stopping any AP service. The actual
# upgrade exports a fresh snapshot after service shutdown.
checkwork=$(mktemp -d /tmp/thor-upgrader-certificates.XXXXXX)
AB_CERTIFICATE_ARCHIVE=$checkwork/archive
AB_CERTIFICATE_DESCRIPTOR=$checkwork/descriptor
ab_certificate_export && ab_certificate_validate_snapshot || {
 rm -rf "$checkwork"
 die 'active certificate source, crypto tools or snapshot preflight failed'
}
tar tf "$AB_CERTIFICATE_ARCHIVE" > "$checkwork/members" || { rm -rf "$checkwork"; die 'outgoing tar cannot list snapshot'; }
if grep -Eq '\.(pem|ca)$' "$checkwork/members"; then
 crypto=$(command -v openssl) && [ -x "$crypto" ] || { rm -rf "$checkwork"; die 'credential-bearing outgoing store requires compatible OpenSSL'; }
 openssl version >/dev/null || { rm -rf "$checkwork"; die 'outgoing OpenSSL cannot execute'; }
fi
rm -rf "$checkwork"
source_gate || die 'outgoing scripts changed during preflight'
targets="cambium-ab.sh:/lib/functions/cambium-ab.sh cambium-ab-upgrade.sh:/lib/upgrade/cambium-ab.sh routes/$route/cambium-ab-certificates.sh:/lib/upgrade/cambium-ab-certificates.sh modules/cambium-ab-thor.sh:/lib/functions/cambium-ab-thor.sh platform.sh:/lib/upgrade/platform.sh"
transaction_active=0
cleanup_staged() {
 [ ! -f "$backup/staged" ] || while read -r staged dst; do rm -f "$staged"; done < "$backup/staged"
}
bridge_metadata() {
 LC_ALL=C ls -ldn "$1" | awk '{ print $1 ":" $3 ":" $4 }'
}
recovery_code_known() (
 ow_source_wildcards_known "$bundle/source-sets/required-paths" || exit 1
 while read -r digest path; do
  # Only fixed transaction targets may hold either original or reviewed staged bytes.
  candidate=$path
  replacement=
  for item in $targets; do [ "${item#*:}" != "$candidate" ] || replacement=${item%%:*}; done
  if [ -f "$candidate" ] && [ ! -L "$candidate" ]; then
   actual=$(sha256sum < "$candidate") || exit 1
   actual=${actual%% *}
  elif [ ! -e "$candidate" ] && [ ! -L "$candidate" ]; then actual=-
  else exit 1; fi
  if [ -z "$replacement" ]; then
   [ "$actual" = "$digest" ] || exit 1
   continue
  fi
  current_metadata=absent
  [ "$actual" = - ] || current_metadata=$(bridge_metadata "$candidate") || exit 1
  if [ "$actual" = "$digest" ]; then
   original_metadata=$(awk -v path="$candidate" '$2==path {print $1}' "$backup/original-metadata") || exit 1
   [ "$current_metadata" != "$original_metadata" ] || continue
  fi
  [ -n "$replacement" ] || exit 1
  staged_digest=$(sha256sum < "$bundle/$replacement") || exit 1
  [ "$actual" = "${staged_digest%% *}" ] || exit 1
  staged_metadata=$(awk -v path="$candidate" '$2==path {print $1}' "$backup/staged-metadata") || exit 1
  [ "$current_metadata" = "$staged_metadata" ] || exit 1
 done < "$backup/original-source.set"
)
recovery_originals_known() (
 cmp -s "$backup/original-source.set" "$bundle/source-sets/outgoing-$route.set" ||
  cmp -s "$backup/original-source.set" "$bundle/source-sets/installed-$route.set" || exit 1
 LC_ALL=C awk -v targets="$targets" '
  BEGIN {n=split(targets,items," "); for(i=1;i<=n;i++){split(items[i],pair,":"); allowed[pair[2]]=1}}
  NF!=2 || ($1!="present" && $1!="absent") || !($2 in allowed) || seen[$2]++ {bad=1}
  END {exit (bad || NR!=n)}
 ' "$backup/original-presence" || exit 1
 for item in $targets; do
  dst=${item#*:}
  logical=$dst
  digest=$(awk -v path="$logical" '$2==path {print $1}' "$backup/original-source.set") || exit 1
  [ -n "$digest" ] || exit 1
  if [ "$digest" = - ]; then
   grep -Fxq "absent $dst" "$backup/original-presence" && [ ! -e "$backup$dst" ] && [ ! -L "$backup$dst" ] || exit 1
  else
   grep -Fxq "present $dst" "$backup/original-presence" && [ -f "$backup$dst" ] && [ ! -L "$backup$dst" ] || exit 1
   actual=$(sha256sum < "$backup$dst") || exit 1
   [ "${actual%% *}" = "$digest" ] || exit 1
   expected_metadata=$(awk -v path="$dst" '$2==path {print $1}' "$backup/original-metadata") || exit 1
   [ "$(bridge_metadata "$backup$dst")" = "$expected_metadata" ] || exit 1
  fi
 done
)
recover_bridge() {
 recovery_failed=0
 ow_runtime_contract_check "$bundle/runtime-sets/$route.set" || { echo "RECOVERY FAILED: unreviewed recovery tools; retain originals" >&2; return 1; }
 recovery_originals_known || { echo "RECOVERY FAILED: unauthenticated originals; retain receipt" >&2; return 1; }
 recovery_code_known || { echo "RECOVERY FAILED: unknown current code; retain originals" >&2; return 1; }
 while read -r presence dst; do
  if [ "$presence" = present ]; then
   restore=$(mktemp "$dst.thor-restore.XXXXXX") || { recovery_failed=1; continue; }
   if cp -p "$backup$dst" "$restore" && mv "$restore" "$dst"; then
    [ "$(bridge_metadata "$dst")" = "$(bridge_metadata "$backup$dst")" ] && cmp -s "$dst" "$backup$dst" || recovery_failed=1
   else
    rm -f "$restore"; recovery_failed=1
   fi
  else
   rm -f "$dst" || recovery_failed=1
  fi
 done < "$backup/original-presence"
 cleanup_staged
 ow_source_set_matches "$backup/original-source.set" "$bundle/source-sets/required-paths" || recovery_failed=1
 if [ "$recovery_failed" = 0 ]; then
  echo 'RECOVERY: exact original complete source tuple restored; mode/uid/gid verified' >> "$backup/receipt"
  echo "Bridge installation failed; original files restored. Receipt: $backup/receipt" >&2
 else
  echo 'RECOVERY FAILED: retain originals and stop; no flash attempted' >> "$backup/receipt"
  echo "Bridge recovery incomplete; stop and retain $backup/receipt and originals" >&2
 fi
}
installation_exit() {
 result=$?
 trap - 0 HUP INT TERM
 set +e
 if [ "$result" != 0 ] && [ "$transaction_active" = 1 ]; then
  recover_bridge
 else
  cleanup_staged
  if [ "$result" != 0 ]; then
   echo 'FAILED during staging: no target replacement began; preserve originals' >> "$backup/receipt"
   echo "Bridge staging failed; no targets replaced. Receipt: $backup/receipt" >&2
  fi
 fi
 exit "$result"
}
case "$mode" in
 --check)
  echo 'PASS: outgoing bridge payload and image preflight; not installed; no flash writes'
  exit 0 ;;
 --install)
  backup=/root/thor-upgrader-backup-$(date -u +%Y%m%dT%H%M%SZ)-$$
  mkdir -m 700 "$backup"
  : > "$backup/staged"
  : > "$backup/original-presence"
  : > "$backup/original-metadata"
  : > "$backup/staged-metadata"
  echo 'Thor bridge transaction: only the five listed targets; no flash or boot environment writes' > "$backup/receipt"
  chmod 600 "$backup/receipt" "$backup/staged" "$backup/original-presence"
  trap installation_exit 0
  trap 'exit 129' HUP
  trap 'exit 130' INT
  trap 'exit 143' TERM
  for source_set in "$bundle/source-sets/outgoing-$route.set" "$bundle/source-sets/installed-$route.set"; do
   if ow_source_set_matches "$source_set" "$bundle/source-sets/required-paths"; then
    cp "$source_set" "$backup/original-source.set"
    break
   fi
  done
  [ -f "$backup/original-source.set" ] || die 'original tuple changed before staging'
  # Preserve every original and stage/compare every new file before replacing any.
  for item in $targets; do
   src=${item%%:*}; dst=${item#*:}
   mkdir -p "$backup$(dirname "$dst")"
   if [ -f "$dst" ] && [ ! -L "$dst" ]; then
    cp -p "$dst" "$backup$dst"
    cmp -s "$dst" "$backup$dst" || die "original backup differs: $dst"
    [ "$(bridge_metadata "$dst")" = "$(bridge_metadata "$backup$dst")" ] || die "original backup metadata differs: $dst"
    printf 'present %s\n' "$dst" >> "$backup/original-presence"
    printf '%s %s\n' "$(bridge_metadata "$dst")" "$dst" >> "$backup/original-metadata"
    ls -ldn "$dst" >> "$backup/receipt"
    sha256sum "$backup$dst" >> "$backup/receipt"
   else
    [ ! -e "$dst" ] && [ ! -L "$dst" ] || die "unsafe original target: $dst"
    printf 'absent %s\n' "$dst" >> "$backup/original-presence"
    printf 'absent %s\n' "$dst" >> "$backup/original-metadata"
    printf 'originally absent: %s\n' "$dst" >> "$backup/receipt"
   fi
   staged=$(mktemp "$dst.thor-new.XXXXXX") || die "cannot stage bridge file: $dst"
   printf '%s %s\n' "$staged" "$dst" >> "$backup/staged"
   cp "$bundle/$src" "$staged"
   chmod 644 "$staged"
   chown 0:0 "$staged"
   printf '%s %s\n' "$(bridge_metadata "$staged")" "$dst" >> "$backup/staged-metadata"
   cmp -s "$bundle/$src" "$staged" || die "staged bridge differs: $dst"
  done
  source_gate || die 'outgoing scripts changed during staging'
  ow_source_set_matches "$backup/original-source.set" "$bundle/source-sets/required-paths" || die 'original tuple changed during staging'
  transaction_active=1
  while read -r staged dst; do mv "$staged" "$dst"; done < "$backup/staged"
  ;;
esac
source_gate || die 'release metadata or implementation changed during installation'
for item in $targets; do
 src=${item%%:*}; dst=${item#*:}
 cmp -s "$bundle/$src" "$dst" || die "installed file differs: $dst"
done
ow_thor_installed_matches "$bundle" "$SOURCE_ROUTE" || die 'installed complete source tuple differs'
if [ "$mode" = --install ]; then
 echo 'COMMITTED: exact complete installed bridge tuple verified' >> "$backup/receipt"
 transaction_active=0
 cleanup_staged
 trap - 0 HUP INT TERM
 echo "Outgoing bridge files installed; originals and receipt preserved in $backup"
fi
echo 'PASS: exact outgoing updater files verified; no flash writes or reboot'
