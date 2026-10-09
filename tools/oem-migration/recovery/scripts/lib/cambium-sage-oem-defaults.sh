#!/bin/sh
# Exact E410-A/EU OEM U-Boot defaults from the independently matched executable
# SHA below; compiled environment offsets 400090..400725 (nine entries).
# Compiled bootdelay is 2, not the historical runtime value 4. Test commands
# spitest/nandtest are neither modified nor executed. Factory fields are kept.
# Confirm only after a qualified inactive OEM boot/reset/root-access trial.
csr_render_oem_defaults() {
    [ "${CSR_MODEL:-}" = E410 ] && [ "${CSR_OEM_DEFAULTS_QUALIFIED:-}" = qualified ] || return 1
    case "${CSR_OEM_SLOT:-}" in 0|1) ;; *) return 1 ;; esac
    printf 'bootcmd bootipq\nbootdelay 2\nbaudrate 115200\nipaddr 192.168.1.11\nserverip 192.168.1.120\nimage %s\nbootcount 0\n' "$CSR_OEM_SLOT"
    # These are reviewed migration overrides, absent from compiled defaults.
    # Never remove arbitrary unknown keys or rewrite a donor whole environment.
    printf '%s\n' bootargs mtdids mtdparts sage_boot0 sage_boot1 sage_stable0 sage_stable1 \
        sage_ab_version sage_ab_confirmed sage_ab_target sage_ab_state sage_ab_last_failure \
        sage_oem_fallback sage_installer_target sage_installer_job sage_installer_image \
        sage_oem_restore_target sage_oem_restore_state \
        owrt_trial_slot owrt_fallback_slot owrt_migration_state
}
csr_apply_oem_defaults() (
    local idx product version work key value
    [ "${CSR_OEM_BOOT_VERIFIED:-}" = qualified ] || exit 1
    [ "$(id -u)" = 0 ] || exit 1
    case "${CSR_OEM_SLOT:-}" in 0|1) ;; *) exit 1 ;; esac
    [ "${CSR_MODEL:-}" = E410 ] && [ "${CSR_OEM_DEFAULTS_QUALIFIED:-}" = qualified ] || exit 1
    version=$(awk -F= '$1=="PRODUCT" {p=$2;np++} $1=="VERSION" {v=$2;nv++} END {if(np!=1 || nv!=1)exit 1;print p ":" v}' "${CSR_OEM_VERSION:-/etc/version}") || exit 1
    [ "$version" = sage:4.2.3.3-r10 ] || exit 1
    awk -v slot="$CSR_OEM_SLOT" '
        {for(i=1;i<=NF;i++) {
            if($i~/^ubi.mtd=/){u++;if($i!="ubi.mtd=fs")bad=1}
            if($i~/^root=/){r++;if($i!="root=ubi0:rootfs" slot)bad=1}
            if($i~/^rootfstype=/){t++;if($i!="rootfstype=ubifs")bad=1}
        }}
        END {exit bad || u!=1 || r!=1 || t!=1}
    ' "${CSR_CMDLINE:-/proc/cmdline}" || exit 1
    idx=$(csr_mtd_index mfginfo) || exit 1
    product=$(tr '\000' '\n' < "${CSR_DEV:-/dev}/mtd${idx}ro" | sed -n 's/.*\(PL-E410XXX[A-B]-[A-Z][A-Z]\).*/\1/p') || exit 1
    [ "$product" = PL-E410XXXA-EU ] || exit 1
    idx=$(csr_mtd_index '0:APPSBL') || exit 1
    [ "$(csr_mtd_geometry '0:APPSBL')" = '00080000 00010000' ] &&
    csr_is_device "${CSR_DEV:-/dev}/mtd${idx}ro" &&
    [ "$(csr_hash "${CSR_DEV:-/dev}/mtd${idx}ro")" = 066bfcc317291b23e44bd42f1d10c4d08ca82ded6ca05abd15f5da280ae4dba1 ] || exit 1
    # The source ENV changed during the one-shot. Verify its saved capture and
    # off-device receipt, while still comparing this AP's ART/mfg live bytes.
    CSR_ALLOW_CHANGED_ENV=1
    csr_recovery_check || exit 1
    csr_digest "${CSR_KERNEL_PIN:-}" && csr_digest "${CSR_SHARED_PIN:-}" &&
    [ "$(csr_hash "$CSR_KERNEL")" = "$CSR_KERNEL_PIN" ] &&
    [ "$(csr_hash "$CSR_SHARED_MANIFEST")" = "$CSR_SHARED_PIN" ] || exit 1
    csp_readback "$CSR_KERNEL" "${CSR_DEV:-/dev}/ubi0_$((2 * CSR_OEM_SLOT))" || exit 1
    # Mapping is the qualified same-device 64KiB config retained by caller.
    [ -r "${CSR_ENV_CONFIG:-}" ] && [ ! -L "$CSR_ENV_CONFIG" ] || exit 1
    idx=$(csr_mtd_index '0:APPSBLENV') || exit 1
    case "$(awk '!/^#/ && NF {print}' "$CSR_ENV_CONFIG")" in
        "/dev/mtd$idx 0x0 0x00010000 0x00010000 1"|"/dev/mtd$idx 0x0 0x10000 0x10000 1") ;;
        *) exit 1 ;;
    esac
    umask 077
    work=$(mktemp -d /tmp/cambium-oem-defaults.XXXXXX) || exit 1
    trap 'rm -f "$work/defaults" "$work/defaults-before" "$work/defaults-readback" "$work/env-errors"; rmdir "$work"' EXIT
    fw_printenv -c "$CSR_ENV_CONFIG" > "$work/defaults-before" 2> "$work/env-errors" || exit 1
    [ ! -s "$work/env-errors" ] || exit 1
    csr_render_oem_defaults > "$work/defaults" || exit 1
    fw_setenv -c "$CSR_ENV_CONFIG" -s "$work/defaults" && sync || exit 1
    # Require a successful complete read even for removed keys. Per-key
    # absence cannot hide unreadable ENV after a failed physical update.
    fw_printenv -c "$CSR_ENV_CONFIG" > "$work/defaults-readback" 2> "$work/env-errors" || exit 1
    [ ! -s "$work/env-errors" ] || exit 1
    while read -r key value; do
        awk -F= -v key="$key" -v value="$value" '
            $1==key {n++;if(NF!=2 || $2!=value)bad=1}
            END {exit bad || (value!="" && n!=1) || (value=="" && n!=0)}
        ' "$work/defaults-readback" || exit 1
    done < "$work/defaults"
    # Every unlisted key, including per-device identity, must remain exact.
    awk '
        FILENAME==ARGV[1] {changed[$1]=1;next}
        {i=index($0,"=");if(!i){bad=1;next};key=substr($0,1,i-1)}
        key in changed {next}
        FILENAME==ARGV[2] {if(before[key]++)bad=1;original[key]=$0;next}
        {if(after[key]++ || !(key in original) || original[key]!=$0)bad=1}
        END {for(key in original)if(after[key]!=1)bad=1;exit bad}
    ' "$work/defaults" "$work/defaults-before" "$work/defaults-readback" || exit 1
    csr_recovery_check || exit 1
    printf 'oem_defaults=verified\nreboot_performed=no\n'
)
