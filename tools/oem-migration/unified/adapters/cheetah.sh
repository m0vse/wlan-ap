#!/bin/sh
# Cheetah adapter for the single shared OEM installer.
# Converted-stock FORMAT2 tests qualify a different outgoing operation.
# The retained OEM reference writes an additional OpenWrt UBI volume using
# fixed device indices; it is not a production exact-model OEM writer.
# Do not turn either reference into admission for persistent migration.

_cheetah_oem_unavailable() {
    case "${OEM_MODEL:-}" in
        XV2-21X)
            printf '%s\n' 'XV2-21X full OEM migration is unavailable: complete bundle staging, OEM volume namespace transition and boot arming are not integrated. Local write/readback components are tested separately.' >&2
            ;;
        XV2-22H|XV2-23T)
            printf '%s\n' 'This Cheetah model has no qualified exact OEM layout, asset and boot adapter.' >&2
            ;;
        *)
            printf '%s\n' 'Unknown or mismatched Cheetah model; refusing OEM migration.' >&2
            ;;
    esac
    return 1
}

oem_adapter_inspect() { oem_cheetah_inspect_oem; }

oem_adapter_preflight() { _cheetah_oem_unavailable; }
oem_adapter_recovery() { _cheetah_oem_unavailable; }
oem_adapter_migrate() { _cheetah_oem_unavailable; }

_cheetah_boot_unproven() {
    OEM_BOOT_PRIOR_SLOT=
    OEM_BOOT_TARGET_SLOT=
    OEM_BOOT_MODE=
    OEM_BOOT_WATCHDOG=
    printf '%s\n' 'Cheetah exact-prior restore/save boot handler is not yet available for this route; no candidate write or boot arm is allowed. Manual-reset recovery is allowed; no new watchdog proof is required.' >&2
    return 1
}
oem_adapter_boot_preflight() {
 OEM_BOOT_PRIOR_SLOT= OEM_BOOT_TARGET_SLOT= OEM_BOOT_MODE= OEM_BOOT_WATCHDOG=
 oem_cheetah_tuple && oem_context_check || return 1
 local before=$OEM_WORK/cheetah-boot-before
 [ ! -L "$before" ] || return 1
 (umask 077;fw_printenv -c "$OEM_CHEETAH_ENV_CONFIG" > "$before") || return 1
 awk 'index($0,"=")==0 {bad=1} {key=$0;sub(/=.*/,"",key);if(key!~/^[A-Za-z0-9_]+$/ || seen[key]++)bad=1}END{exit bad || NR<2}' "$before" || return 1
 [ "$(awk -F= '$1=="image"{print substr($0,index($0,"=")+1)}' "$before")" = "$OEM_SOURCE_SLOT" ] &&
 [ "$(awk -F= '$1=="bootcmd"{print substr($0,index($0,"=")+1)}' "$before")" = bootipq ] ||
  { oem_cheetah_fail 'actual prior OEM selector/default disagrees with the captured bootipq contract'; return 1; }
 OEM_CHEETAH_PRIOR_MARKER=$(awk -F= '$1=="changing_bootcmd"{print substr($0,index($0,"=")+1)}' "$before") || return 1
 case "$OEM_CHEETAH_PRIOR_MARKER" in ''|0|1) ;; *) return 1;; esac
 oem_cheetah_trial_command >/dev/null || return 1
 OEM_BOOT_PRIOR_SLOT=$OEM_SOURCE_SLOT OEM_BOOT_TARGET_SLOT=$OEM_TARGET_SLOT
 OEM_BOOT_MODE=persist-prior-before-load OEM_BOOT_WATCHDOG=manual-reset
}
oem_upgrade_boot_preflight() { _cheetah_boot_unproven; }

# Verified captured factory format: physical SPI mfginfo, 64KiB, header
# 05ca/serial TLV length12. Do not use a UBI-exported alias or donor identity.
oem_cheetah_tuple() {
 [ "${OEM_FAMILY:-}:${OEM_MODEL:-}:${OEM_SKU:-}" = cheetah:XV2-21X:00000023 ]
}
oem_cheetah_fail() { printf '%s\n' "Cheetah: $*" >&2; return 1; }
oem_cheetah_env() {
 [ -n "${OEM_CHEETAH_ENV_CONFIG:-}" ] && [ -f "$OEM_CHEETAH_ENV_CONFIG" ] || return 1
 fw_printenv -c "$OEM_CHEETAH_ENV_CONFIG" -n "$1"
}
oem_cheetah_inspect_oem() {
 local sys dev mfg envnode serial release slot idx arg value count=0 erase bank
 OEM_SERIAL= OEM_SOURCE_RELEASE= OEM_SOURCE_SLOT= OEM_TARGET_SLOT=
 oem_cheetah_tuple || return 1
 command -v oem_physical_index >/dev/null && command -v oem_read_release >/dev/null || return 1
 release=$(oem_read_release "${OEM_SYS_ROOT:-}/etc/version") || return 1
 [ -n "${OEM_SUPPORTED_RELEASE:-}" ] && [ "$release" = "$OEM_SUPPORTED_RELEASE" ] ||
  { oem_cheetah_fail 'source version is not the exact released version; no fetch or writes'; return 1; }
 sys=${OEM_SYS_ROOT:-}/sys/class/mtd;dev=${OEM_SYS_ROOT:-}/dev
 for bank in rootfs rootfs_1; do
  idx=$(oem_physical_index "$sys" "$bank") || return 1
  [ "$(cat "$sys/mtd$idx/type")" = nand ] && [ "$(cat "$sys/mtd$idx/size")" = 100663296 ] &&
  [ "$(cat "$sys/mtd$idx/erasesize")" = 131072 ] && [ "$(cat "$sys/mtd$idx/writesize")" = 2048 ] || return 1
 done
 mfg=$(oem_physical_index "$sys" mfginfo) || return 1
 [ "$(cat "$sys/mtd$mfg/type")" = nor ] && [ "$(cat "$sys/mtd$mfg/size")" = 65536 ] || return 1
 [ ! -L "$dev/mtd${mfg}ro" ] && { [ -n "${OEM_SYS_ROOT:-}" ] || [ -c "$dev/mtd${mfg}ro" ]; } || return 1
 [ "$(od -An -tx1 -N6 "$dev/mtd${mfg}ro" | tr -d ' \n')" = 05ca01000c00 ] || return 1
 serial=$(dd if="$dev/mtd${mfg}ro" bs=1 skip=6 count=12 2>/dev/null | tr 'A-F' 'a-f') || return 1
 case "$serial" in ''|*[!0-9a-f]*|000000000000|ffffffffffff) return 1;; esac
 [ "${#serial}" = 12 ] || return 1
 for arg in $(cat "${OEM_SYS_ROOT:-}/proc/cmdline"); do
  case "$arg" in ubi.mtd=*) value=${arg#ubi.mtd=};value=${value%%,*};count=$((count+1));; *) continue;; esac
  case "$value" in rootfs) slot=0;; rootfs_1) slot=1;;
   *[!0-9]*|'') return 1;;
   *) idx=$(oem_physical_index "$sys" rootfs) || return 1
      if [ "$value" = "$idx" ]; then slot=0;else
       idx=$(oem_physical_index "$sys" rootfs_1) || return 1
       [ "$value" = "$idx" ] || return 1;slot=1
      fi;;
  esac
 done
 [ "$count" = 1 ] || return 1
 envnode=$(oem_physical_index "$sys" 0:APPSBLENV) || return 1
 [ "$(cat "$sys/mtd$envnode/type")" = nor ] && [ "$(cat "$sys/mtd$envnode/size")" = 65536 ] || return 1
 erase=$(cat "$sys/mtd$envnode/erasesize") || return 1
 case "$erase" in ''|*[!0-9]*) return 1;; esac
 [ "$erase" -gt 0 ] && [ "$erase" -le 65536 ] && [ "$((65536 % erase))" = 0 ] || return 1
 [ -n "${OEM_WORK:-}" ] && [ -d "$OEM_WORK" ] && [ ! -L "$OEM_WORK" ] || return 1
 OEM_CHEETAH_ENV_CONFIG=$OEM_WORK/cheetah-fw-env.config
 [ ! -L "$OEM_CHEETAH_ENV_CONFIG" ] || return 1
 (umask 077;printf '%s 0x0 0x10000 0x%x %s\n' "$dev/mtd$envnode" "$erase" "$((65536/erase))" > "$OEM_CHEETAH_ENV_CONFIG") || return 1
 [ "$(oem_cheetah_env image)" = "$slot" ] || return 1
 OEM_SERIAL=$serial OEM_SOURCE_RELEASE=$release OEM_SOURCE_SLOT=$slot OEM_TARGET_SLOT=$((1-slot))
}
# Bounded reuse of the retained update/readback operation. This is not an
# admission shortcut: the full caller must already have staged every object,
# proved boot/protected ranges and received its critical-only upload receipt.
# No erase/remove/rename/new-volume operation is hidden in this primitive.
oem_cheetah_update_local_child() {
 local child=$1 name=$2 payload=$3 size=$4 digest=$5 sys device parent path sum plan target_name major minor actual capacity leb blocks
 oem_cheetah_tuple && oem_context_check && oem_boot_check || return 1
 case "$child:$name" in 0:kernel|1:rootfs) ;; *) return 1;; esac
 case "$size" in ''|*[!0-9]*) return 1;; esac
 [ "$size" -gt 0 ] && [ "$size" -le 100663296 ] && oem_hex64 "$digest" || return 1
 [ -n "${OEM_WORK:-}" ] && [ "$(readlink -f "$OEM_WORK/cache")" = "$OEM_WORK/cache" ] || return 1
 case "$payload" in "$OEM_WORK/cache/"*) ;; *) return 1;; esac
 [ -f "$payload" ] && [ ! -L "$payload" ] && [ "$(readlink -f "$payload")" = "$payload" ] || return 1
 actual=$(wc -c < "$payload") || return 1
 case "$actual" in *[!0-9[:space:]]*|'') return 1;; esac
 [ "$actual" -eq "$size" ] && [ "$(oem_sha "$payload")" = "$digest" ] || return 1
 oem_write_boundary "$OEM_PROTECTED_RANGES" "$OEM_WRITE_PLAN" || return 1
 parent=${OEM_CHEETAH_TARGET_MTD:-};device=${OEM_CHEETAH_TARGET_UBI:-};sys=${OEM_SYS_ROOT:-}/sys/class/ubi
 case "$parent:$device" in [0-9]*:ubi[0-9]*) ;; *) return 1;; esac
 case "$parent" in *[!0-9]*) return 1;; esac
 case "${device#ubi}" in ''|*[!0-9]*) return 1;; esac
 case "$OEM_TARGET_SLOT" in 0) target_name=rootfs;; 1) target_name=rootfs_1;; *) return 1;; esac
 [ "$(oem_physical_index "${OEM_SYS_ROOT:-}/sys/class/mtd" "$target_name")" = "$parent" ] || return 1
 plan=$(awk -F '\t' -v p="$parent" -v c="$child" -v n="$name" '$1=="ubi-update" && $2==p && $3==c && $4==n{nrows++}END{print nrows+0}' "$OEM_WRITE_PLAN") || return 1
 [ "$plan" = 1 ] || return 1
 oem_ubi_child_check "$sys" "$parent" "$device" "$child" "$name" || return 1
 blocks=$(cat "$sys/${device}_$child/reserved_ebs") && leb=$(cat "$sys/${device}_$child/usable_eb_size") || return 1
 case "$blocks:$leb" in *[!0-9:]*|:*|*:) return 1;; esac
 [ "$blocks" -ge 1 ] && [ "$blocks" -le 768 ] && [ "$leb" = 126976 ] && [ "$size" -le "$((blocks*leb))" ] || return 1
 path=${OEM_SYS_ROOT:-}/dev/${device}_$child
 [ ! -L "$path" ] && { [ -n "${OEM_SYS_ROOT:-}" ] || [ -c "$path" ]; } || return 1
 if [ -z "${OEM_SYS_ROOT:-}" ]; then
  actual=$(LC_ALL=C ls -ln "$path" | awk '$1~/^c/ && $3==0 {gsub(/,/,"",$5); print $5 ":" $6}') || return 1
  [ "$actual" = "$(cat "$sys/${device}_$child/dev")" ] || return 1
 fi
 (umask 077;printf 'local-update-start\t%s\t%s\n' "$child" "$name" >> "$OEM_WORK/cheetah-update.journal") || return 1
 ubiupdatevol "$path" "$payload" || return 1
 sum=$(head -c "$size" "$path" | sha256sum | awk '{print $1}') || return 1
 [ "$sum" = "$digest" ] || return 1
 oem_ubi_child_check "$sys" "$parent" "$device" "$child" "$name" || return 1
 sync || return 1
 printf 'local-update-readback-verified\t%s\t%s\n' "$child" "$name" >> "$OEM_WORK/cheetah-update.journal"
}

# Source of the one-shot command: save the observed OEM default/image/marker
# before the named candidate function is called. All candidate commands are
# themselves &&-gated. Reset fallback is manual unless an existing watchdog
# is independently known; this source does not invent a watchdog prerequisite.
oem_cheetah_candidate_command() {
 local part offset
 oem_cheetah_tuple || return 1
 case "$OEM_TARGET_SLOT" in 0) part=rootfs;offset=0x80000;; 1) part=rootfs_1;offset=0x6080000;; *) return 1;; esac
 printf 'nand device 0 && setenv mtdids nand0=nand0 && setenv mtdparts "mtdparts=nand0:0x06000000@%s(fs)" && ubi part fs && ubi read 0x60000000 kernel && setenv bootargs "console=ttyMSM0,115200n8 ubi.mtd=%s root=/dev/ubiblock0_1 rootfstype=squashfs rootwait" && bootm 0x60000000#config@mp03.3-ocelot\n' "$offset" "$part"
}
oem_cheetah_trial_command() {
 oem_cheetah_tuple || return 1
 case "$OEM_SOURCE_SLOT:$OEM_TARGET_SLOT" in 0:1|1:0) ;; *) return 1;; esac
 case "${OEM_CHEETAH_PRIOR_MARKER:-}" in ''|0|1) ;; *) return 1;; esac
 printf 'setenv bootcmd bootipq && setenv image %s && setenv changing_bootcmd %s && saveenv && run cheetah_boot%s; bootipq\n' "$OEM_SOURCE_SLOT" "${OEM_CHEETAH_PRIOR_MARKER:-}" "$OEM_TARGET_SLOT"
}

# Grow the existing inactive kernel only. OEM captures reserve 32/36 LEBs,
# smaller than the native kernel. Never remove/recreate a child implicitly.
# The caller stages all bundle objects before entering any write component.
oem_cheetah_grow_local_kernel() (
 oem_cheetah_tuple && oem_context_check && oem_boot_check || exit 1
 payload=$1 size=$2 digest=$3
 case "$size" in ''|*[!0-9]*) exit 1;; esac
 [ "$size" -gt 0 ] && [ "$size" -le 100663296 ] && oem_hex64 "$digest" || exit 1
 [ -n "${OEM_WORK:-}" ] && [ "$(readlink -f "$OEM_WORK/cache")" = "$OEM_WORK/cache" ] || exit 1
 case "$payload" in "$OEM_WORK/cache/"*) ;; *) exit 1;; esac
 [ -f "$payload" ] && [ ! -L "$payload" ] && [ "$(readlink -f "$payload")" = "$payload" ] || exit 1
 actual=$(wc -c < "$payload") || exit 1
 case "$actual" in ''|*[!0-9[:space:]]*) exit 1;; esac
 [ "$actual" -eq "$size" ] && [ "$(oem_sha "$payload")" = "$digest" ] || exit 1
 oem_write_boundary "$OEM_PROTECTED_RANGES" "$OEM_WRITE_PLAN" || exit 1
 parent=${OEM_CHEETAH_TARGET_MTD:-};device=${OEM_CHEETAH_TARGET_UBI:-}
 case "$parent" in ''|*[!0-9]*) exit 1;; esac
 case "$device" in ubi*) suffix=${device#ubi};; *) exit 1;; esac
 case "$suffix" in ''|*[!0-9]*) exit 1;; esac
 case "$OEM_TARGET_SLOT" in 0) target_name=rootfs;; 1) target_name=rootfs_1;; *) exit 1;; esac
 [ "$(oem_physical_index "${OEM_SYS_ROOT:-}/sys/class/mtd" "$target_name")" = "$parent" ] || exit 1
 [ "$(awk -F '\t' -v p="$parent" '$1=="ubi-resize" && $2==p && $3==0 && $4=="kernel"{n++}END{print n+0}' "$OEM_WRITE_PLAN")" = 1 ] || exit 1
 sys=${OEM_SYS_ROOT:-}/sys/class/ubi
 oem_ubi_child_check "$sys" "$parent" "$device" 0 kernel || exit 1
 # Shared helpers use shell globals: assign operation fields after them.
 node=$sys/${device}_0;path=${OEM_SYS_ROOT:-}/dev/$device
 [ ! -L "$path" ] && { [ -n "${OEM_SYS_ROOT:-}" ] || [ -c "$path" ]; } || exit 1
 if [ -z "${OEM_SYS_ROOT:-}" ]; then
  actual=$(LC_ALL=C ls -ln "$path" | awk '$1~/^c/ && $3==0 {gsub(/,/,"",$5);print $5 ":" $6}') || exit 1
  [ "$actual" = "$(cat "$sys/$device/dev")" ] || exit 1
 fi
 [ "$(cat "$node/type")" = dynamic ] || exit 1
 blocks=$(cat "$node/reserved_ebs") && leb=$(cat "$node/usable_eb_size") && free=$(cat "$sys/$device/avail_eraseblocks") || exit 1
 case "$blocks:$leb:$free" in *[!0-9:]*|:*|*::*|*:) exit 1;; esac
 [ "$blocks" -ge 1 ] && [ "$blocks" -le 768 ] && [ "$leb" -eq 126976 ] && [ "$free" -le 768 ] || exit 1
 needed=$(((size+leb-1)/leb))
 [ "$needed" -le 768 ] || exit 1
 # An already large enough volume is retained; this component never shrinks.
 [ "$needed" -gt "$blocks" ] || exit 0
 [ "$((needed-blocks))" -le "$free" ] || exit 1
 (umask 077;printf 'kernel-grow-start\t%s\t%s\n' "$blocks" "$needed" >> "$OEM_WORK/cheetah-update.journal") || exit 1
 ubirsvol "$path" -n 0 -s "$((needed*leb))" || exit 1
 oem_ubi_child_check "$sys" "$parent" "$device" 0 kernel || exit 1
 node=$sys/${device}_0
 [ "$(cat "$node/reserved_ebs")" -eq "$needed" ] && [ "$(cat "$node/type")" = dynamic ] &&
 [ "$(cat "$node/usable_eb_size")" -eq "$leb" ] || exit 1
 sync || exit 1
 printf 'kernel-grow-verified\t%s\n' "$needed" >> "$OEM_WORK/cheetah-update.journal"
)
