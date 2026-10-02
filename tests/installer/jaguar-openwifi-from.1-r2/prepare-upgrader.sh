#!/bin/sh
# Operator-run outgoing bridge updater; never flashes or reboots an AP.
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
mode=${1:---check}
image=${2:?usage: prepare-upgrader.sh --check|--install|--verify-installed IMAGE}
case "$mode" in --check|--install|--verify-installed|--recover) ;; *) exit 2 ;; esac
bundle=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
die() { echo "Jaguar outgoing updater: $*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || die 'root is required for verified device preflight'
(cd "$bundle" && sha256sum -c SHA256SUMS) || die 'bundle checksum mismatch'
# Authenticate the complete reviewed source tuple before sourcing AP scripts.
. "$bundle/source-set-check.sh"
. "$bundle/minimum-release-contract.sh"
. "$bundle/runtime-implementation-contract.sh"
metadata_fingerprint() {
 local file value
 for file in /etc/openwrt_release /etc/cambium-openwrt-release; do
  if [ -f "${BRIDGE_ROOT:-}$file" ] && [ ! -L "${BRIDGE_ROOT:-}$file" ]; then
   value=$(sha256sum < "${BRIDGE_ROOT:-}$file") || return 1
   printf '%s:%s\n' "$file" "${value%% *}"
  elif [ ! -e "${BRIDGE_ROOT:-}$file" ] && [ ! -L "${BRIDGE_ROOT:-}$file" ]; then printf '%s:-\n' "$file"
  else return 1; fi
 done
}
release_gate() {
 local fingerprint
 ow_release_contract_check "$bundle/release-contract-policy" "${BRIDGE_ROOT:-}" || return 1
 fingerprint=$(metadata_fingerprint) || return 1
 [ -z "${RELEASE_FINGERPRINT:-}" ] || [ "$fingerprint" = "$RELEASE_FINGERPRINT" ] ||
  { echo 'Release metadata changed during invocation; refusing new writes' >&2; return 1; }
 RELEASE_FINGERPRINT=$fingerprint
}
runtime_gate() { ow_runtime_contract_check "$bundle/source-sets/runtime-implementation.set" "${BRIDGE_ROOT:-}"; }
source_gate() {
 runtime_gate || return 1
 [ "${1:-}" = repair-code-only ] || release_gate || return 1
 # stage2 sources every upgrade shell file; functions are retained wholesale.
 # Reject additional wildcard-loaded scripts as well as changed known files.
 for path in /lib/*.sh /lib/functions/*.sh /lib/upgrade/*.sh; do
  [ -e "$path" ] || [ -L "$path" ] || continue
  grep -Fxq "$path" "$bundle/source-sets/required-paths" || return 1
 done
 for source_set in "$bundle"/source-sets/outgoing-*.set "$bundle/source-sets/installed-bridge.set"; do
  if ow_source_set_matches "$source_set" "$bundle/source-sets/required-paths"; then
   MATCHED_SOURCE_SET=$source_set
   return 0
  fi
 done
 return 1
}
BRIDGE_ROOT=''
BRIDGE_JOURNAL=$BRIDGE_ROOT/root/jaguar-upgrader-transaction
. "$bundle/bridge-transaction.sh"
runtime_gate || die 'unknown updater executable/library identity; qualify the newer implementation offline'
if [ "$mode" = --recover ] || [ -e "$BRIDGE_JOURNAL" ]; then
 ow_release_contract_check "$bundle/release-contract-policy" "$BRIDGE_ROOT" || echo 'Metadata not upgrade-qualified; attempting only authenticated code recovery' >&2
else
 release_gate || die 'release is below minimum, malformed or incompatible with this route'
fi
case "$mode" in
 --install|--recover)
  bridge_recover_pending || die 'pending bridge transaction needs recovery; no AP script sourced' ;;
 *)
  [ ! -e "$BRIDGE_JOURNAL" ] && [ ! -L "$BRIDGE_JOURNAL" ] || die 'pending bridge transaction: use explicit --recover; check mode performs no recovery writes' ;;
esac
if [ "$mode" = --recover ]; then
 source_gate repair-code-only || die 'recovered updater implementation is not approved'
 ow_release_contract_check "$bundle/release-contract-policy" "$BRIDGE_ROOT" || die 'authenticated updater repair complete, but release is not qualified for upgrade'
 echo 'PASS: approved outgoing source restored/verified; no AP script sourced, flash or reboot'
 exit 0
fi
if [ "$mode" = --verify-installed ]; then
 source_gate || die 'installed updater contains unknown source files'
 ow_source_set_matches "$bundle/source-sets/installed-bridge.set" "$bundle/source-sets/required-paths" || die 'installed updater source tuple is not approved'
else
 source_gate || die 'outgoing updater source tuple is unknown or modified'
fi
# Complete authenticated stock closure includes optional unset variables.
set +u
. /lib/functions/system.sh
case "$(board_name)" in
 cambiumnetworks,xv2-2|cambiumnetworks,xv2-2t1) ;;
 *) die 'only qualified XV2-2/XV2-2T1 preserving source models are allowed' ;;
esac
for binary in tr sysupgrade sync cp mv chmod dirname date fw_printenv fw_setenv ubiformat ubiattach ubidetach ubimkvol ubiupdatevol sha256sum hexdump tar ls cmp mktemp find awk sed wc mount umount readlink openssl uci; do
 dependency=$(command -v "$binary") && [ -x "$dependency" ] || die "missing/nonexecutable stage2 dependency: $binary"
done
. "$bundle/preservation-check.sh"
jaguar_configuration_preservation_check || die 'configuration minor version is not approved for preservation'
grep -Fq '/lib/functions/*.sh' /lib/upgrade/stage2 || die 'stage2 does not retain family modules'
grep -Fq '/lib/upgrade/*.sh' /lib/upgrade/stage2 || die 'stage2 does not retain updater libraries'
export CAMBIUM_AB_MODULES="$bundle/modules"
export CAMBIUM_AB_LIB="$bundle/cambium-ab.sh"
export CAMBIUM_AB_CERTIFICATE_LIB="$bundle/cambium-ab-certificates.sh"
. "$bundle/cambium-ab.sh"
. "$bundle/cambium-ab-upgrade.sh"
ab_upgrade_preflight || die 'identity, protected layout, converted banks or trial-state preflight failed'
[ "$AB_QUALIFIED" = 1 ] || die 'unqualified model'
[ "${AB_CERTIFICATE_CONTENT_VERSION:-0}" = 1 ] || die 'canonical certificate content helper missing'
[ "${AB_CERTIFICATE_POLICY_VERSION:-0}" = 1 ] || die 'canonical certificate allocation policy missing'
probe=$(mktemp /tmp/jaguar-upgrader-permissions.XXXXXX) || die 'mktemp failed'
chmod 600 "$probe"
ab_certificate_private_file "$probe" || { rm -f "$probe"; die 'outgoing ls/awk permission format is incompatible'; }
rm -f "$probe"
grep -q 'ab_certificate_export' "$bundle/platform.sh" || die 'certificate snapshot hook missing'
[ "$(ab_certificate_lebs)" = 20 ] || die 'durable certificate reservation policy missing'
jaguar_certificate_source_check || die 'active certificate source bank, mount or geometry is not approved'
jaguar_runtime_identity_check || die 'valid matching private runtime credentials are required before preservation'
# This extracts and validates only in tmpfs; it never writes either bank.
cambium_ab_check_image "$image" || die 'image FIT, vault or capacity preflight failed'
# Snapshot canonical store content and authoritative runtime credentials into
# private tmpfs only. The actual writer exports again after service shutdown.
checkwork=$(mktemp -d /tmp/jaguar-upgrader-certificates.XXXXXX)
AB_CERTIFICATE_ARCHIVE=$checkwork/archive
AB_CERTIFICATE_DESCRIPTOR=$checkwork/descriptor
ab_certificate_export && ab_certificate_validate_snapshot || {
 rm -rf "$checkwork"
 die 'preserving certificate snapshot preflight failed'
}
rm -rf "$checkwork"
# The exact reviewed outgoing sysupgrade remains authoritative for metadata,
# signatures. Separate minor guard above is necessary because stock -T starts
# SAVE_CONFIG=0 before -f is parsed. No force, -n or UCI fence override.
sysupgrade -T "$image" || die 'current sysupgrade compatibility/signature preflight failed'
case "$mode" in
 --check)
  echo 'PASS: outgoing bridge payload and image preflight; not installed; no flash writes'
  exit 0 ;;
 --install)
  bridge_install || die 'bridge transaction failed; originals restored or recovery journal retained'
  echo 'PASS: complete outgoing bridge installed and verified transactionally; no flash writes or reboot'
  exit 0
  ;;
esac
for item in 'cambium-ab.sh:/lib/functions/cambium-ab.sh' 'cambium-ab-upgrade.sh:/lib/upgrade/cambium-ab.sh' 'cambium-ab-certificates.sh:/lib/upgrade/cambium-ab-certificates.sh' 'modules/cambium-ab-jaguar.sh:/lib/functions/cambium-ab-jaguar.sh' 'platform.sh:/lib/upgrade/platform.sh'; do
 src=${item%%:*}; dst=${item#*:}
 cmp -s "$bundle/$src" "$dst" || die "installed file differs: $dst"
done
ow_source_set_matches "$bundle/source-sets/installed-bridge.set" "$bundle/source-sets/required-paths" || die 'installed complete source tuple differs'
echo 'PASS: exact outgoing updater files verified; no flash writes or reboot'
