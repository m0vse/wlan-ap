#!/bin/sh
# Bounded emergency factory-reset adapter, not a standalone restore command.
# Qualified caller supplies exact model/active slot, verified shared OEM files
# and independent hashes, this AP's minimal recovery and off-device receipt.
# Requires an already written/read-back inactive OEM candidate; never arms boot.
csr_is_device() { [ -c "$1" ]; }
csr_hash() { sha256sum < "$1" | awk '{print $1}'; }
csr_digest() { [ "${#1}" = 64 ] && case "$1" in *[!0-9a-f]*) return 1 ;; *) return 0 ;; esac; }
csr_mtd_index() {
    awk -v label="\"$1\"" '$4==label {sub(/mtd/,"",$1);sub(/:/,"",$1);v=$1;n++} END {if(n!=1 || v!~/^[0-9]+$/)exit 1;print v}' "${CSR_PROC_MTD:-/proc/mtd}"
}
csr_mtd_geometry() {
    awk -v label="\"$1\"" '$4==label {v=$2 " " $3;n++} END {if(n!=1)exit 1;print v}' "${CSR_PROC_MTD:-/proc/mtd}"
}
csr_recovery_check() {
    local dir=${CSR_RECOVERY:-} file label index ack
    [ -d "$dir" ] && [ ! -L "$dir" ] && [ "$(readlink -f "$dir")" = "$dir" ] || return 1
    [ "$(ow_settings_metadata "$dir" | awk -F: '{print $1 ":" $2}')" = 0:700 ] || return 1
    for file in appsblenv.bin art.bin manufacturing.bin SHA256SUMS; do
        ow_settings_private "$dir/$file" || return 1
    done
    (cd "$dir" && sha256sum -c SHA256SUMS >/dev/null 2>&1) || return 1
    for label in '0:APPSBLENV appsblenv' '0:ART art' 'mfginfo manufacturing'; do
        set -- $label
        index=$(csr_mtd_index "$1") || return 1
        [ "$(csr_mtd_geometry "$1")" = '00010000 00010000' ] || return 1
        csr_is_device "${CSR_DEV:-/dev}/mtd${index}ro" || return 1
        [ "$(wc -c < "$dir/$2.bin")" -eq 65536 ] || return 1
        [ "$2" != appsblenv ] || [ "${CSR_ALLOW_CHANGED_ENV:-0}" != 1 ] || continue
        [ "$(csr_hash "$dir/$2.bin")" = "$(csr_hash "${CSR_DEV:-/dev}/mtd${index}ro")" ] || return 1
    done
    ow_settings_private "${CSR_RECEIPT:-}" || return 1
    [ "$(wc -c < "$CSR_RECEIPT")" -eq 65 ] && [ "$(wc -l < "$CSR_RECEIPT")" -eq 1 ] || return 1
    ack=$(cat "$CSR_RECEIPT")
    csr_digest "$ack" && [ "$ack" = "$(csr_hash "$dir/SHA256SUMS")" ]
}
csr_preflight() {
    local phase=${1:-staged}
    case "$phase" in staged|payload-only) ;; *) return 1 ;; esac
    local sys=${CSR_MTD_SYS:-/sys/class/mtd} ubi=${CSR_UBI_SYS:-/sys/class/ubi} idx node count=0 lebs flags config snapshot payload expected i=1
    [ "${CSR_RESET_QUALIFIED:-}" = qualified ] || return 1
    case "${CSR_MODEL:-}:${CSR_ACTIVE:-}" in E410:0|E410:1|E410B:0|E410B:1) ;; *) return 1 ;; esac
    for payload in "${CSR_KERNEL_PIN:-}" "${CSR_ROOT_PIN:-}" "${CSR_SHARED_PIN:-}"; do csr_digest "$payload" || return 1; done
    for payload in "${CSR_KERNEL:-}" "${CSR_ROOT:-}" "${CSR_SHARED_MANIFEST:-}"; do
        [ -f "$payload" ] && [ ! -L "$payload" ] && [ "$(ow_settings_metadata "$payload")" = 0:600:1 ] || return 1
        case "$i" in 1) expected=$CSR_KERNEL_PIN ;; 2) expected=$CSR_ROOT_PIN ;; 3) expected=$CSR_SHARED_PIN ;; esac
        [ "$(csr_hash "$payload")" = "$expected" ] || return 1
        i=$((i + 1))
    done
    awk '$1~/^mtd[0-9]+:/ {if(seen[$1]++)bad=1} END {exit bad}' "${CSR_PROC_MTD:-/proc/mtd}" || return 1
    CSR_CONFIG_MTD=$(csr_mtd_index config) && CSR_FS_MTD=$(csr_mtd_index fs) || return 1
    [ "$(csr_mtd_geometry config)" = '00010000 00010000' ] &&
    [ "$(csr_mtd_geometry fs)" = '08000000 00020000' ] || return 1
    [ "$CSR_CONFIG_MTD" != "$CSR_FS_MTD" ] || return 1
    for payload in '0:APPSBLENV' '0:ART' mfginfo; do
        idx=$(csr_mtd_index "$payload") || return 1
        [ "$idx" != "$CSR_CONFIG_MTD" ] || return 1
    done
    [ "$(cat "$sys/mtd$CSR_CONFIG_MTD/name")" = config ] &&
    [ "$(cat "$sys/mtd$CSR_CONFIG_MTD/type")" = nor ] &&
    [ "$(cat "$sys/mtd$CSR_CONFIG_MTD/size")" = 65536 ] &&
    [ "$(cat "$sys/mtd$CSR_CONFIG_MTD/erasesize")" = 65536 ] || return 1
    flags=$(cat "$sys/mtd$CSR_CONFIG_MTD/flags") || return 1
    case "$flags" in 0x[0-9a-fA-F]*|[0-9]*) ;; *) return 1 ;; esac
    case "$flags" in *[!0-9a-fA-Fx]*) return 1 ;; esac
    [ "$((flags & 1024))" -ne 0 ] || return 1
    csr_is_device "${CSR_DEV:-/dev}/mtd$CSR_CONFIG_MTD" && csr_is_device "${CSR_DEV:-/dev}/mtd${CSR_CONFIG_MTD}ro" || return 1
    [ "$(cat "$ubi/ubi0/mtd_num")" = "$CSR_FS_MTD" ] &&
    [ "$(cat "$ubi/ubi0/eraseblock_size")" = 126976 ] &&
    [ "$(cat "$ubi/ubi0/min_io_size")" = 2048 ] || return 1
    for node in "$ubi/ubi0_"*/name; do
        [ -r "$node" ] || continue
        [ "$(cat "$node")" != nvram ] || count=$((count + 1))
    done
    [ "$count" = 1 ] && [ "$(cat "$ubi/ubi0_4/name")" = nvram ] &&
    [ "$(cat "$ubi/ubi0_4/usable_eb_size")" = 126976 ] &&
    [ "$(cat "$ubi/ubi0_4/type")" = dynamic ] || return 1
    lebs=$(cat "$ubi/ubi0_4/reserved_ebs") || return 1
    case "$lebs" in
        167) CSR_EMPTY_NVRAM_SHA=dd28e9ec502b8150c34b27b3a817a839f991ea3455fcd0eed2b34e2a97bed43b ;;
        187) CSR_EMPTY_NVRAM_SHA=a06f6ada3bbe79799330ff22f570f9f1976fb90c005941cc61f16f47cd2dd8ca ;;
        *) return 1 ;;
    esac
    CSR_NVRAM_BYTES=$((lebs * 126976))
    csr_is_device "${CSR_DEV:-/dev}/ubi0_4" || return 1
    # A mounted shared store may feed the running source's /etc. Never reset it.
    ! awk -v dev="${CSR_DEV:-/dev}/ubi0_4" -v block="${CSR_DEV:-/dev}/mtdblock$CSR_CONFIG_MTD" -v mtd="${CSR_DEV:-/dev}/mtd$CSR_CONFIG_MTD" '
        $1==dev || $1=="ubi0:nvram" || $1==block || $1==mtd {found=1} END {exit !found}' "${CSR_MOUNTS:-/proc/mounts}" || return 1
    # Exact existing ENV mapping, never a guessed/donor environment.
    idx=$(csr_mtd_index '0:APPSBLENV') || return 1
    [ -r "${CSR_ENV_CONFIG:-}" ] && [ ! -L "$CSR_ENV_CONFIG" ] || return 1
    config=$(awk '!/^#/ && NF {sub(/[[:space:]]*#.*/, "");if(NF) print}' "$CSR_ENV_CONFIG") || return 1
    set -- $config
    [ "$#" = 4 ] || [ "$#" = 5 ] || return 1
    [ "$1" = "/dev/mtd$idx" ] || return 1
    case "$2:$3:$4:${5:-1}" in 0x0:0x10000:0x10000:1|0x0:0x00010000:0x00010000:1) ;; *) return 1 ;; esac
    snapshot=$(fw_printenv -c "$CSR_ENV_CONFIG" 2>/dev/null) || return 1
    printf '%s\n' "$snapshot" | awk -F= -v active="$CSR_ACTIVE" '
        $1=="sage_installer_target" || $1=="sage_installer_job" || $1=="sage_installer_image" {if(seen[$1]++ || NF!=2 || length($2))bad=1}
        $1=="image" {images++;if(NF!=2 || $2!=active)bad=1}
        $1=="bootcmd" {commands++;if(NF!=2 || $2!="run sage_stable" active)bad=1}
        $1=="sage_ab_state" {states++;if(NF!=2 || $2!="confirmed")bad=1}
        END {exit bad || images!=1 || commands!=1 || states!=1}' || return 1
    for payload in flash_erase ubiupdatevol sync sha256sum head awk; do command -v "$payload" >/dev/null 2>&1 || return 1; done
    csr_recovery_check || return 1
    # Actual source-bank validation and exact inactive candidate readback.
    CSP_ACTIVE=$CSR_ACTIVE CSP_FS_MTD=$CSR_FS_MTD CSP_SYS=$ubi CSP_DEV=${CSR_DEV:-/dev}
    CSP_CMDLINE=${CSR_CMDLINE:-/proc/cmdline} CSP_MOUNTS=${CSR_MOUNTS:-/proc/mounts}
    case " $(cat "$CSP_CMDLINE") " in *' rootfstype=squashfs '*) ;; *) return 1 ;; esac
    csp_payload_check "$CSR_KERNEL" "$CSR_ROOT" 372 ubifs || return 1
    [ "$phase" != payload-only ] || return 0
    csp_readback "$CSR_KERNEL" "$CSP_DEV/ubi0_$((2 * CSP_TARGET))" &&
    csp_readback "$CSR_ROOT" "$CSP_DEV/ubi0_$((2 * CSP_TARGET + 1))"
}
csr_reset_shared() (
    CSR_ALLOW_CHANGED_ENV=0
    # Caller holds exclusive execution. Preflight repeats immediately before
    # writes; source firmware, calibration, mfg, ENV and certificates are not reset.
    csr_preflight || exit 1
    flash_erase "${CSR_DEV:-/dev}/mtd$CSR_CONFIG_MTD" 0 1 || exit 1
    sync || exit 1
    [ "$(csr_hash "${CSR_DEV:-/dev}/mtd${CSR_CONFIG_MTD}ro")" = 71189f7fb6aed638640078fba3a35fda6c39c8962e74dcc75935aac948da9063 ] || exit 1
    # Removing stale NOR first prevents OEM nvram recovery importing old config.
    ubiupdatevol -t "${CSR_DEV:-/dev}/ubi0_4" || exit 1
    sync || exit 1
    [ "$(cat "${CSR_UBI_SYS:-/sys/class/ubi}/ubi0_4/upd_marker")" = 0 ] &&
    [ "$(head -c "$CSR_NVRAM_BYTES" "${CSR_DEV:-/dev}/ubi0_4" | sha256sum | awk '{print $1}')" = "$CSR_EMPTY_NVRAM_SHA" ] || exit 1
    csr_recovery_check || exit 1
    printf 'factory_configuration_reset=verified\nboot_state_changed=no\n'
)
