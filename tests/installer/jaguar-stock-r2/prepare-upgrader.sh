#!/bin/sh
# Operator-run outgoing bridge updater; never flashes or reboots an AP.
set -eu
mode=${1:---check}
image=${2:?usage: prepare-upgrader.sh --check|--install|--verify-installed IMAGE}
case "$mode" in --check|--install|--verify-installed|--recover) ;; *) exit 2 ;; esac
bundle=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
die() { echo "Jaguar outgoing updater: $*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || die 'root is required for verified device preflight'
(cd "$bundle" && sha256sum -c SHA256SUMS) || die 'bundle checksum mismatch'
# Authenticate the complete reviewed source tuple before sourcing AP scripts.
. "$bundle/source-set-check.sh"
source_gate() {
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
case "$mode" in
 --install|--recover)
  bridge_recover_pending || die 'pending bridge transaction needs recovery; no AP script sourced' ;;
 *)
  [ ! -e "$BRIDGE_JOURNAL" ] && [ ! -L "$BRIDGE_JOURNAL" ] || die 'pending bridge transaction: use explicit --recover; check mode performs no recovery writes' ;;
esac
if [ "$mode" = --recover ]; then
 source_gate || die 'recovered outgoing source tuple is not approved'
 echo 'PASS: approved outgoing source restored/verified; no AP script sourced, flash or reboot'
 exit 0
fi
if [ "$mode" = --verify-installed ]; then
 source_gate || die 'installed updater contains unknown source files'
 ow_source_set_matches "$bundle/source-sets/installed-bridge.set" "$bundle/source-sets/required-paths" || die 'installed updater source tuple is not approved'
else
 source_gate || die 'outgoing updater source tuple is unknown or modified'
fi
. /lib/functions/system.sh
case "$(board_name)" in
 cambiumnetworks,xv2-2|cambiumnetworks,xv2-2t1) ;;
 *) die 'only XV2-2/XV2-2T1 qualified in this exact outgoing release are allowed' ;;
esac
for binary in sysupgrade sync cp mv chmod dirname date fw_printenv fw_setenv ubiformat ubiattach ubidetach ubimkvol ubiupdatevol sha256sum hexdump tar ls cmp mktemp find awk sed wc mount umount readlink; do
 command -v "$binary" >/dev/null || die "missing stage2 dependency: $binary"
done
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
# This extracts and validates only in tmpfs; it never writes either bank.
cambium_ab_check_image "$image" || die 'image FIT, vault or capacity preflight failed'
# Stock migration prepares an empty bound store in tmpfs. It neither reads
# stock credentials nor requires crypto tools to validate discarded identities.
checkwork=$(mktemp -d /tmp/jaguar-upgrader-certificates.XXXXXX)
AB_CERTIFICATE_ARCHIVE=$checkwork/archive
AB_CERTIFICATE_DESCRIPTOR=$checkwork/descriptor
ab_certificate_export && ab_certificate_validate_snapshot || {
 rm -rf "$checkwork"
 die 'empty stock-migration certificate snapshot preflight failed'
}
rm -rf "$checkwork"
# The exact reviewed outgoing sysupgrade remains authoritative for metadata,
# signatures and clean migration compatibility. No force or UCI fence override.
sysupgrade -n -T "$image" || die 'current sysupgrade compatibility/signature preflight failed'
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
