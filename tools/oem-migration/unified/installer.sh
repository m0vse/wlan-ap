#!/bin/sh
# One operator interface; the incoming firmware owns native EST enrollment.
set -eu
set +x
set +a
umask 077
LC_ALL=C
export LC_ALL
OEM_HERE=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
OEM_SYS_ROOT=
OEM_BUNDLE=$OEM_HERE
OEM_RELEASE_PIN=RELEASE_PIN_NOT_CONFIGURED
unset OEM_KEY key ENROLMENT_KEY credential
OEM_KEY= OEM_LOCK= OEM_TTY_STATE= OEM_WORK=
OEM_NETWORK_BUDGET_LEFT=600
mode=install
case "${1:-}" in check|install) mode=$1;shift;; --help) printf 'Usage: cambium-oem-install [check|install] [--release-dir DIR --release-pin SHA256]\n';exit 0;; esac
while [ "$#" -gt 0 ]; do
 [ "$#" -ge 2 ] || exit 2
 case "$1" in --release-dir) OEM_BUNDLE=$2;; --release-pin) OEM_RELEASE_PIN=$2;; *) exit 2;; esac
 shift 2
done
# Check all downloaded code before sourcing any helper. The launcher itself
# must be obtained through the independently verified release channel.
[ "${#OEM_RELEASE_PIN}" = 64 ] || exit 1
case "$OEM_RELEASE_PIN" in *[!0-9a-f]*) exit 1;; esac
[ -d "$OEM_BUNDLE" ] && [ ! -L "$OEM_BUNDLE" ] && [ "$(readlink -f "$OEM_BUNDLE")" = "$OEM_BUNDLE" ] || exit 1
[ -f "$OEM_BUNDLE/SHA256SUMS" ] && [ ! -L "$OEM_BUNDLE/SHA256SUMS" ] || exit 1
[ "$(sha256sum < "$OEM_BUNDLE/SHA256SUMS" | awk '{print $1}')" = "$OEM_RELEASE_PIN" ] || exit 1
awk 'NF!=2 || length($1)!=64 || $1~/[^0-9a-f]/ || $2!~/^[A-Za-z0-9_.\/-]+$/ || $2~/^\// || $2~/(^|\/)\.\.?(\/|$)/ || seen[$2]++ {bad=1} END{exit bad || NR<4}' "$OEM_BUNDLE/SHA256SUMS" || exit 1
while read -r digest name; do
 [ -f "$OEM_BUNDLE/$name" ] && [ ! -L "$OEM_BUNDLE/$name" ] && [ "$(readlink -f "$OEM_BUNDLE/$name")" = "$OEM_BUNDLE/$name" ] || exit 1
done < "$OEM_BUNDLE/SHA256SUMS"
(cd "$OEM_BUNDLE" && sha256sum -c SHA256SUMS >/dev/null 2>&1) || exit 1
for name in lib/common.sh recognition.tsv; do
 awk -v name="$name" '$2==name {n++} END{exit n!=1}' "$OEM_BUNDLE/SHA256SUMS" || exit 1
done
. "$OEM_BUNDLE/lib/common.sh"
member=$(oem_bundle_member lib/protection.sh) || exit 1
. "$member"
trap oem_cleanup EXIT
trap 'exit 1' HUP INT TERM
[ "$(id -u)" = 0 ] || { oem_fail 'run on the AP as root'; exit 1; }
[ ! -e "$OEM_SYS_ROOT/etc/openwrt_release" ] || { oem_fail 'this entry point requires OEM firmware'; exit 1; }
for tool in awk od tr cut cat sha256sum readlink stty mkdir rmdir mktemp sync; do command -v "$tool" >/dev/null || exit 1; done
oem_detect || exit 1
printf 'Detected %s %s.\n' "$OEM_FAMILY" "$OEM_MODEL"
oem_release_check || { oem_fail 'release/model validation failed before changes'; exit 1; }
readonly OEM_SKU OEM_FAMILY OEM_MODEL OEM_BUNDLE OEM_CONTROLLER OEM_DOWNLOAD_URL OEM_BACKUP_URL OEM_SUPPORTED_RELEASE
for name in lib/protection.sh lib/critical-backup.sh lib/network.sh; do
 member=$(oem_bundle_member "$name") || exit 1
 . "$member"
done
. "$OEM_BUNDLE/adapters/$OEM_ADAPTER.sh"
for phase in oem_adapter_inspect oem_adapter_preflight oem_adapter_boot_preflight oem_adapter_recovery oem_adapter_migrate; do command -v "$phase" >/dev/null || exit 1; done
OEM_WORK=$(mktemp -d /tmp/cambium-unified-oem.XXXXXX) || exit 1
oem_adapter_inspect && oem_context_check && oem_adapter_preflight && oem_boot_inspect oem_adapter_boot_preflight || { oem_fail 'preflight failed; no firmware changed'; exit 1; }
[ -n "${OEM_PROTECTED_RANGES:-}" ] && [ -n "${OEM_WRITE_PLAN:-}" ] &&
 oem_write_boundary "$OEM_PROTECTED_RANGES" "$OEM_WRITE_PLAN" || { oem_fail 'protected write boundaries could not be proven'; exit 1; }
OEM_LOCK=/tmp/cambium-unified-oem.lock
mkdir "$OEM_LOCK" || { OEM_LOCK=; oem_fail 'another installer is active; inspect its journal'; exit 1; }
# Recheck mutable device state after serialization.
oem_adapter_inspect && oem_context_check && oem_adapter_preflight && oem_boot_inspect oem_adapter_boot_preflight && oem_write_boundary "$OEM_PROTECTED_RANGES" "$OEM_WRITE_PLAN" || exit 1
OEM_CONTEXT_PIN=$(oem_context_fingerprint)
if [ "$mode" = check ]; then
 printf 'schema\t1\noperation\toem-migration-check\nfamily\t%s\nmodel\t%s\nserial\t%s\nsource_slot\t%s\ntarget_slot\t%s\nstatus\tpreflight-passed\n' "$OEM_FAMILY" "$OEM_MODEL" "$OEM_SERIAL" "$OEM_SOURCE_SLOT" "$OEM_TARGET_SLOT"
 exit 0
fi
printf 'Serial %s; OEM slot %s retained; target slot %s. Preflight passed.\n' "$OEM_SERIAL" "$OEM_SOURCE_SLOT" "$OEM_TARGET_SLOT"
oem_prompt_key || { oem_fail 'private key input failed'; exit 1; }
oem_confirm || { oem_fail 'installation cancelled before backup or writes'; exit 1; }
OEM_BACKUP_ID=$(od -An -tx1 -N16 /dev/urandom | tr -d ' \n') || exit 1
[ "${#OEM_BACKUP_ID}" = 32 ] || exit 1
oem_adapter_recovery && oem_backup_receipt_check "${OEM_RECOVERY_DIR:-}" || { oem_fail 'critical backup was not verified off-device; no firmware changed'; exit 1; }
oem_adapter_inspect && oem_context_check && oem_adapter_preflight && oem_boot_inspect oem_adapter_boot_preflight && oem_write_boundary "$OEM_PROTECTED_RANGES" "$OEM_WRITE_PLAN" || exit 1
[ "$(oem_context_fingerprint)" = "$OEM_CONTEXT_PIN" ] || { oem_fail 'device/source context changed'; exit 1; }
(cd "$OEM_BUNDLE" && sha256sum -c SHA256SUMS >/dev/null 2>&1) || exit 1
# Function call: the key is never placed in a child process argv or environment.
oem_adapter_migrate "$OEM_KEY" || { OEM_KEY=; oem_fail 'migration failed; preserve the adapter journal and OEM bank'; exit 1; }
OEM_KEY=
printf 'Verified images and protected settings staged; boot armed. Native onboarding and sysupgrade readiness must be checked after boot.\n'
oem_reboot_choice
