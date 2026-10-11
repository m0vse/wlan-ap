#!/bin/sh
# Operator-led OEM migration. Independent published installer/payload pins must
# be checked by the operator before launching this program. Bundle checksums
# detect changes after that trusted launch; they are not their own authority.
# No trial exemption, Root credential, source enrollment or automatic reboot.
set +x
LC_ALL=C
export LC_ALL
cos_here=$(CDPATH= cd -- "$(dirname "$0")" && pwd) || exit 1
# Authenticate all helper bytes before sourcing any bundle code. The expected
# ledger digest is an explicit independent operator input, not a downloaded
# value from this same bundle. The launcher itself is verified before launch.
if [ "${COS_OPERATOR_SOURCE_ONLY:-0}" != 1 ]; then
    case "${1:-}" in --check|--install) ;; *) exit 2 ;; esac
    cos_bundle_pin=${2:-}
    [ "${#cos_bundle_pin}" = 64 ] || exit 1
    case "$cos_bundle_pin" in *[!0-9a-f]*) exit 1 ;; esac
    [ -f "$cos_here/SHA256SUMS" ] && [ ! -L "$cos_here/SHA256SUMS" ] || exit 1
    [ "$(sha256sum < "$cos_here/SHA256SUMS" | awk '{print $1}')" = "$cos_bundle_pin" ] || exit 1
    (cd "$cos_here" && sha256sum -c SHA256SUMS >/dev/null 2>&1) || exit 1
fi
. "$cos_here/lib/cambium-sage-pair-write.sh" || exit 1
. "$cos_here/lib/cambium-installer-settings.sh" || exit 1
. "$cos_here/lib/cambium-oem-sage-transaction.sh" || exit 1
. "$cos_here/lib/cambium-oem-sage-source.sh" || exit 1
. "$cos_here/lib/cambium-oem-sage-boot.sh" || exit 1
COS_READERS_DIR=$cos_here
OW_SETTINGS_OWNER=0

cos_pin() { [ "${#1}" = 64 ] && case "$1" in *[!0-9a-f]*) return 1 ;; *) return 0 ;; esac; }
cos_operator_context() {
    local evidence model status
    evidence=$(sh "$COS_READERS_DIR/cambium-oem-sage-prepare.sh" check) || return 1
    model=$(printf '%s\n' "$evidence" | awk -F= '$1=="model" {v=$2;n++} END {if(n!=1)exit 1;print v}') || return 1
    case "$model" in E410|E410B) ;; *) return 1 ;; esac
    status=$(awk -F '\t' -v model="$model" '$3==model {v=$9;n++} END {if(n!=1)exit 1;print v}' "$COS_READERS_DIR/cambium-oem-models.tsv") || return 1
    # Unsupported/unqualified status is never overridden by an operator flag.
    [ "$status" = qualified ] || { echo 'OEM model is not production qualified; no changes permitted.' >&2; return 1; }
    [ "$(wc -l < "$cos_here/operator-model")" -eq 2 ] || return 1
    [ "$(sed -n '1p' "$cos_here/operator-model")" = "$model" ] || return 1
    [ "$(printf '%s\n' "$evidence" | awk -F= '$1=="product" {v=$2;n++} END {if(n!=1)exit 1;print v}')" = "$(sed -n '2p' "$cos_here/operator-model")" ] || return 1
    OW_EXPECT_MODEL=$model
}
cos_admit() {
    local context release contract extra
    cos_operator_context || return 1
    [ "$(wc -l < "$cos_here/operator-artifact-pins")" -eq 3 ] || return 1
    [ "$(sed -n '1p' "$cos_here/operator-artifact-pins")" = "$COS_IMAGE_PIN" ] &&
    [ "$(sed -n '2p' "$cos_here/operator-artifact-pins")" = "$COS_KERNEL_PIN" ] &&
    [ "$(sed -n '3p' "$cos_here/operator-artifact-pins")" = "$COS_ROOT_PIN" ] || return 1
    [ -f "$cos_here/SHA256SUMS" ] && [ ! -L "$cos_here/SHA256SUMS" ] || return 1
    (cd "$cos_here" && sha256sum -c SHA256SUMS >/dev/null 2>&1) || return 1
    . "$cos_here/runtime-implementation-contract.sh" || return 1
    ow_runtime_contract_check "$cos_here/source-sets/runtime-implementation.set" || return 1
    [ "$(wc -l < "$cos_here/source-contract")" -eq 2 ] || return 1
    release=$(sed -n '1p' "$cos_here/source-contract")
    contract=$(sed -n '2p' "$cos_here/source-contract")
    [ "$release" = 4.2.3.3-r10 ] && cos_pin "$contract" || return 1
    context=$(sh "$COS_READERS_DIR/cambium-oem-sage-context.sh" check) || return 1
    OW_EXPECT_SERIAL=$(printf '%s\n' "$context" | cut -f1)
    OW_EXPECT_SOURCE=$(printf '%s\n' "$context" | cut -f4)
    case "$OW_EXPECT_SOURCE" in 0|1) ;; *) return 1 ;; esac
    OW_EXPECT_TARGET=$((1 - OW_EXPECT_SOURCE))
    OW_EXPECT_FAMILY=sage OW_EXPECT_OPERATION=production-oem-migration
    OW_EXPECT_RELEASE=$release OW_EXPECT_CONTRACT=$contract
    # Private job identity is not a signing key or independent admission grant.
    ow_settings_tree "$COS_SETTINGS" || return 1
    OW_EXPECT_JOB=$OW_JOB
    CSP_FS_MTD=$(awk '$4=="\"fs\"" {sub(/mtd/,"",$1);sub(/:/,"",$1);v=$1;n++} END {if(n!=1)exit 1;print v}' /proc/mtd) || return 1
    CSP_SYS=/sys/class/ubi CSP_DEV=/dev CSP_CMDLINE=/proc/cmdline CSP_MOUNTS=/proc/mounts
    OW_SETTINGS_SYS=/sys/class/ubi OW_SETTINGS_DEV=/dev OW_SETTINGS_MOUNTS=/proc/mounts
    OW_SETTINGS_OWNER=0
    COS_OEM_BOOT_COMMAND="setenv image $OW_EXPECT_SOURCE; bootipq"
    case "$OW_EXPECT_MODEL" in E410) COS_TARGET_FIT=config@5 ;; E410B) COS_TARGET_FIT=config@17 ;; esac
    # Reached only through a sealed qualified model/source operator tuple.
    COS_BOOT_QUALIFIED=qualified
}
cos_authenticate() {
    local file expected index=1
    for file in "$@"; do
        case "$index" in 1) expected=$COS_IMAGE_PIN ;; 2) expected=$COS_KERNEL_PIN ;; 3) expected=$COS_ROOT_PIN ;; *) return 1 ;; esac
        cos_pin "$expected" && [ -f "$file" ] && [ ! -L "$file" ] &&
        [ "$(ow_settings_metadata "$file")" = 0:600:1 ] || return 1
        [ "$(ow_settings_hash "$file")" = "$expected" ] || return 1
        index=$((index + 1))
    done
    [ "$index" = 4 ]
}
cos_recovery() {
    local parent name index file ack
    case "$COS_BACKUP" in /*) ;; *) return 1 ;; esac
    parent=$(dirname "$COS_BACKUP")
    [ -d "$parent" ] && [ ! -L "$parent" ] && [ "$(readlink -f "$parent")" = "$parent" ] || return 1
    [ "$(ow_settings_metadata "$parent" | awk -F: '{print $1 ":" $2}')" = 0:700 ] || return 1
    if [ ! -e "$COS_BACKUP" ] && [ ! -L "$COS_BACKUP" ]; then
        sh "$COS_READERS_DIR/cambium-oem-sage-prepare.sh" backup "$COS_BACKUP" || return 1
    fi
    [ -d "$COS_BACKUP" ] && [ ! -L "$COS_BACKUP" ] && [ "$(readlink -f "$COS_BACKUP")" = "$COS_BACKUP" ] || return 1
    [ "$(ow_settings_metadata "$COS_BACKUP" | awk -F: '{print $1 ":" $2}')" = 0:700 ] || return 1
    for file in appsblenv.bin art.bin manufacturing.bin SHA256SUMS CAPTURE_COMPLETE; do
        ow_settings_private "$COS_BACKUP/$file" || return 1
    done
    (cd "$COS_BACKUP" && sha256sum -c SHA256SUMS >/dev/null 2>&1) || return 1
    for name in '0:APPSBLENV appsblenv' '0:ART art' 'mfginfo manufacturing'; do
        set -- $name
        index=$(awk -v label="\"$1\"" '$4==label {sub(/mtd/,"",$1);sub(/:/,"",$1);v=$1;n++} END {if(n!=1)exit 1;print v}' /proc/mtd) || return 1
        [ "$(wc -c < "$COS_BACKUP/$2.bin")" -eq 65536 ] || return 1
        [ "$(ow_settings_hash "$COS_BACKUP/$2.bin")" = "$(ow_settings_hash "/dev/mtd${index}ro")" ] || return 1
    done
    # This receipt is delivered privately by the operator only after off-device
    # copy and verification. Its single digest binds this exact capture, not a
    # donor firmware dump. Missing receipt prevents all inactive firmware writes.
    ow_settings_private "$COS_ACK" || { echo 'Copy and verify critical recovery off-device, then supply its private checksum receipt.' >&2; return 1; }
    [ "$(wc -c < "$COS_ACK")" -eq 65 ] && [ "$(wc -l < "$COS_ACK")" -eq 1 ] || return 1
    ack=$(cat "$COS_ACK")
    cos_pin "$ack" && [ "$ack" = "$(ow_settings_hash "$COS_BACKUP/SHA256SUMS")" ]
}
cos_operator_install() {
    [ "$#" = 7 ] || return 2
    COS_PAYLOAD=$1 COS_SETTINGS=$2 COS_BACKUP=$3 COS_ACK=$4
    COS_IMAGE_PIN=$5 COS_KERNEL_PIN=$6 COS_ROOT_PIN=$7
    cos_pin "$COS_IMAGE_PIN" && cos_pin "$COS_KERNEL_PIN" && cos_pin "$COS_ROOT_PIN" || return 1
    [ "$(id -u)" = 0 ] || return 1
    cos_install "$COS_PAYLOAD/image.bin" "$COS_PAYLOAD/kernel.itb" "$COS_PAYLOAD/rootfs.squashfs" "$COS_SETTINGS"
}
# Source-only test loading exposes functions but never changes dispatch policy.
[ "${COS_OPERATOR_SOURCE_ONLY:-0}" != 1 ] || return 0
case "${1:-}" in
    --check) [ "$#" = 2 ] && cos_operator_context ;;
    --install) shift 2; cos_operator_install "$@" ;;
    *) echo 'Usage: --check BUNDLE_SHA256 | --install BUNDLE_SHA256 PAYLOAD_DIR SETTINGS_DIR RECOVERY_DIR RECEIPT IMAGE_SHA256 KERNEL_SHA256 ROOT_SHA256' >&2; exit 2 ;;
esac
