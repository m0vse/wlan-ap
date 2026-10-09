#!/bin/sh
# Operator-only OEM restoration for clean migration testing. No issuer reset.
set -eu
set +x
set +a
umask 077
LC_ALL=C;export LC_ALL
OEM_HERE=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
OEM_SYS_ROOT=
OEM_BUNDLE=$OEM_HERE
OEM_RELEASE_PIN=RELEASE_PIN_NOT_CONFIGURED
[ "${1:-}" != --help ] || { printf '%s\n' 'Usage: cambium-oem-restore-test [--check|--restore|--confirm] [--release-dir DIR --release-pin SHA256]';exit 0; }
unset OEM_KEY key ENROLMENT_KEY credential
OEM_KEY= OEM_LOCK= OEM_TTY_STATE= OEM_WORK=
OEM_NETWORK_BUDGET_LEFT=600
mode=${1:---check};shift || true
case "$mode" in --check|--restore|--confirm) ;; *) exit 2;; esac
while [ "$#" -gt 0 ]; do
 [ "$#" -ge 2 ] || exit 2
 case "$1" in --release-dir) OEM_BUNDLE=$2;; --release-pin) OEM_RELEASE_PIN=$2;; *) exit 2;; esac
 shift 2
done
# Authenticate all helpers before loading the shared framework.
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
[ "$(id -u)" = 0 ] || exit 1
if [ "$mode" = --confirm ]; then
 [ ! -e "$OEM_SYS_ROOT/etc/openwrt_release" ] || { oem_fail 'OEM confirmation must run on the restored OEM firmware';exit 1; }
else
 [ -r "$OEM_SYS_ROOT/etc/openwrt_release" ] || exit 1
fi
oem_detect || exit 1
# Same pinned release mechanism, but a separate restoration model map/adapter.
OEM_MODEL_MAP=restore-models.tsv
[ "$mode" != --confirm ] || OEM_MODEL_MAP=restore-confirm-models.tsv
OEM_ADAPTER_PREFIX=restore-
oem_release_check || { oem_fail 'no reviewed restoration for this model/source'; exit 1; }
for name in lib/protection.sh lib/critical-backup.sh lib/network.sh; do
 member=$(oem_bundle_member "$name") || exit 1
 . "$member"
done
member=$(oem_bundle_member "adapters/restore-$OEM_ADAPTER.sh") || exit 1
. "$member"
if [ "$mode" = --confirm ]; then
 for phase in oem_restore_confirm_inspect oem_restore_confirm_preflight oem_restore_confirm;do command -v "$phase" >/dev/null || { oem_fail 'model has no reviewed OEM confirmation handler';exit 1; };done
 OEM_WORK=$(mktemp -d /tmp/cambium-oem-confirm.XXXXXX) || exit 1
 oem_restore_confirm_inspect && oem_context_check && oem_restore_confirm_preflight || exit 1
 printf 'Confirm this verified OEM boot as the working default? Type CONFIRM OEM: ' > /dev/tty
 IFS= read -r answer < /dev/tty && [ "$answer" = 'CONFIRM OEM' ] || exit 1
 oem_restore_confirm_inspect && oem_context_check && oem_restore_confirm_preflight && oem_restore_confirm || exit 1
 printf 'OEM boot confirmed. Follow only the reviewed model factory-reset procedure before a clean migration test.\n'
 exit 0
fi
for phase in oem_restore_inspect oem_restore_preflight oem_restore_boot_preflight oem_restore_recovery oem_restore_migrate; do command -v "$phase" >/dev/null || exit 1; done
OEM_WORK=$(mktemp -d /tmp/cambium-oem-restore.XXXXXX) || exit 1
oem_restore_inspect && oem_context_check && oem_restore_preflight && oem_boot_inspect oem_restore_boot_preflight &&
 oem_write_boundary "$OEM_PROTECTED_RANGES" "$OEM_WRITE_PLAN" || exit 1
printf 'OEM restoration test: %s %s; source OpenWiFi slot %s retained; target %s.\n' "$OEM_FAMILY" "$OEM_MODEL" "$OEM_SOURCE_SLOT" "$OEM_TARGET_SLOT"
printf 'Plan: verified inactive OEM payloads; critical data protected; reviewed nonunique factory reset only; no CA reset.\n'
[ "$mode" != --check ] || exit 0
OEM_LOCK=/tmp/cambium-unified-oem.lock
mkdir "$OEM_LOCK" || { OEM_LOCK=;exit 1; }
oem_restore_inspect && oem_context_check && oem_restore_preflight && oem_boot_inspect oem_restore_boot_preflight &&
 oem_write_boundary "$OEM_PROTECTED_RANGES" "$OEM_WRITE_PLAN" || exit 1
OEM_CONTEXT_PIN=$(oem_context_fingerprint)
printf 'Restore OEM for migration testing? Type RESTORE OEM: ' > /dev/tty
IFS= read -r answer < /dev/tty && [ "$answer" = 'RESTORE OEM' ] || exit 1
OEM_BACKUP_ID=$(od -An -tx1 -N16 /dev/urandom | tr -d ' \n') || exit 1
[ "${#OEM_BACKUP_ID}" = 32 ] || exit 1
oem_restore_recovery && oem_backup_receipt_check "${OEM_RECOVERY_DIR:-}" || exit 1
oem_restore_inspect && oem_context_check && oem_restore_preflight && oem_boot_inspect oem_restore_boot_preflight &&
 [ "$(oem_context_fingerprint)" = "$OEM_CONTEXT_PIN" ] &&
 oem_write_boundary "$OEM_PROTECTED_RANGES" "$OEM_WRITE_PLAN" || exit 1
oem_restore_migrate || { oem_fail 'restore failed; keep source and journal; do not reboot'; exit 1; }
printf 'OEM test boot staged. Original OpenWiFi identity is retained according to the adapter plan.\n'
oem_reboot_choice
