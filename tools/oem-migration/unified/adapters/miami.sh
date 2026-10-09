#!/bin/sh
# Delegate storage/boot/FORMAT2 to the independently pinned, generated Miami
# installer. Source it inside a function/subshell, never exec it with the key.
oem_miami_core() { oem_bundle_member miami-installer.sh; }
oem_miami_run() (
 core=$(oem_miami_core) || exit 1
 CAMBIUM_INSTALL_SERVER=$OEM_DOWNLOAD_URL
 CAMBIUM_ENROLMENT_SERVER=$OEM_CONTROLLER
 CAMBIUM_INSTALL_CACHE_DIR=$OEM_WORK/cache
 CAMBIUM_INSTALL_LOCAL_ONLY=1
 export CAMBIUM_INSTALL_SERVER CAMBIUM_ENROLMENT_SERVER CAMBIUM_INSTALL_CACHE_DIR CAMBIUM_INSTALL_LOCAL_ONLY
 set -- "$@"
 . "$core"
)
oem_adapter_inspect() {
 [ "$OEM_SKU:$OEM_MODEL" = 0000002c:X7-35X ] || return 1
 [ ! -e /etc/openwrt_release ] || return 1
 command -v get_esn >/dev/null && command -v fw_printenv >/dev/null || return 1
 OEM_SERIAL=$(get_esn | tr 'A-F' 'a-f') || return 1
 OEM_SOURCE_RELEASE=$(oem_read_release /etc/version) || return 1
 value=$(fw_printenv image) || return 1
 case "$value" in image=0) OEM_SOURCE_SLOT=0;; image=1) OEM_SOURCE_SLOT=1;; *) return 1;; esac
 OEM_TARGET_SLOT=$((1-OEM_SOURCE_SLOT))
}
oem_adapter_preflight() {
 core=$(oem_miami_core) || return 1
 grep -q 'CAMBIUM_INSTALL_LOCAL_ONLY' "$core" || {
  oem_fail 'Miami generated provider requires the local-only staging hook'; return 1
 }
 # The existing check owns exact NAND/NOR/source selector/runtime validation.
 for name in profiles/X7-35X/mtd-slot$OEM_TARGET_SLOT.tsv profiles/X7-35X/critical.tsv profiles/X7-35X/source.tsv; do
  oem_bundle_member "$name" >/dev/null || { oem_fail "missing reviewed Miami $name"; return 1; }
 done
 oem_source_identifiers_check /etc/version "$OEM_BUNDLE/profiles/X7-35X/source.tsv" || return 1
 oem_physical_inventory "$OEM_BUNDLE/profiles/X7-35X/mtd-slot$OEM_TARGET_SLOT.tsv" /sys/class/mtd "$OEM_WORK/physical.tsv" || return 1
 OEM_PROTECTED_RANGES=$OEM_WORK/physical.tsv
 OEM_WRITE_PLAN=$OEM_WORK/write-plan.tsv
 target=$(oem_physical_index /sys/class/mtd "$([ "$OEM_TARGET_SLOT" = 0 ] && echo rootfs || echo rootfs_1)") || return 1
 env=$(oem_physical_index /sys/class/mtd 0:APPSBLENV) || return 1
 printf 'ubi-remove\t%s\t0\tkernel\nubi-remove\t%s\t1\trootfs\nubi-remove\t%s\t2\trootfs_data\nenvironment-fields\t%s\tfields\tpreserve-unlisted\n' "$target" "$target" "$target" "$env" > "$OEM_WRITE_PLAN"
 oem_write_boundary "$OEM_PROTECTED_RANGES" "$OEM_WRITE_PLAN" || return 1
 [ -d "$OEM_WORK/cache" ] || mkdir -m 700 "$OEM_WORK/cache" || return 1
 [ ! -e "$OEM_WORK/miami-preflight.done" ] || rm -f "$OEM_WORK/miami-preflight.done" || return 1
 # Full pre-erase checks reuse exported functions from that exact script.
 (
  CAMBIUM_INSTALL_SERVER=$OEM_DOWNLOAD_URL CAMBIUM_ENROLMENT_SERVER=$OEM_CONTROLLER
  CAMBIUM_INSTALL_CACHE_DIR=$OEM_WORK/cache CAMBIUM_INSTALL_LOCAL_ONLY=1
  export CAMBIUM_INSTALL_SERVER CAMBIUM_ENROLMENT_SERVER CAMBIUM_INSTALL_CACHE_DIR CAMBIUM_INSTALL_LOCAL_ONLY
  set -- check
  . "$core" || exit 1
  select_payload || exit 1
  oem_fetch_local "$KERNEL" "$KERNEL_SHA" "$KERNEL_SIZE" "$OEM_WORK/cache/$KERNEL" || exit 1
  oem_fetch_local "$ROOTFS" "$ROOTFS_SHA" "$ROOTFS_SIZE" "$OEM_WORK/cache/$ROOTFS" || exit 1
  [ "${ENROLMENT_READY:-0}" = 1 ] || exit 1
  case "$SLOT" in 0) pair=$PAIR0 pin=$PAIR0_SHA size=$PAIR0_SIZE;; 1) pair=$PAIR1 pin=$PAIR1_SHA size=$PAIR1_SIZE;; *) exit 1;; esac
  oem_fetch_local "$pair" "$pin" "$size" "$OEM_WORK/cache/$pair" || exit 1
  # Preserve the reviewed core checks, allowing only a proven idle rootfs
  # mapping during inspection. Its removal requires the outer INSTALL consent.
  busy() { oem_bank_idle_check "$R/sys/class/ubi" "$R/dev" "$R/proc" "$T" "$UBI" yes || fail 'target is busy or mapped ambiguously'; }
  attach && inventory || exit 1
  [ "$BANK_KIND" = oem ] || vault_check || exit 1
  [ -z "$(volume certificates || true)" ] || { oem_fail 'existing identity is incompatible with clean migration; preserve it and inspect the lifecycle'; exit 1; }
  # The original writer repeats capacity validation immediately before erase.
  free=$(cat "$R/sys/class/ubi/$UBI/avail_eraseblocks") || exit 1
  for name in kernel ubi_rootfs rootfs rootfs_data miami_openwifi_trial; do
   v=$(volume "$name" || true)
   [ -z "$v" ] || free=$((free+$(cat "$R/sys/class/ubi/$v/reserved_ebs")))
  done
  reserve=0;[ "$BANK_KIND" != oem ] || reserve=72
  [ "$((free-POOL-64-reserve))" -ge 67 ] || exit 1
  printf '%s\t%s\n' "$T" "$UBI" > "$OEM_WORK/miami-target.tsv"
  printf '%s\n' complete > "$OEM_WORK/miami-preflight.done"
 ) || return 1
 [ -f "$OEM_WORK/miami-preflight.done" ] && [ "$(cat "$OEM_WORK/miami-preflight.done")" = complete ]
}
oem_adapter_recovery() {
 IFS="$(printf '\t')" read -r target ubi < "$OEM_WORK/miami-target.tsv" || return 1
 oem_bank_remove_idle_root_map /sys/class/ubi /dev /proc "$target" "$ubi" || return 1
 OEM_RECOVERY_DIR=$OEM_WORK/critical
 oem_backup_capture "$OEM_BUNDLE/profiles/X7-35X/critical.tsv" /sys/class/mtd /dev "$OEM_WORK/critical" &&
 oem_backup_upload "$OEM_WORK/critical"
}
oem_adapter_migrate() (
 key=$1
 oem_miami_run install --yes --replace-inactive-bank --backed-up || return 1
 # Internal positional parameters are shell memory, not process argv.
 oem_miami_run arm --yes --enrolment-key "$key"
)

oem_adapter_boot_preflight() {
 core=$(oem_miami_core) || return 1
 # Independently pinned provider + actual OEM tool/config/source checks.
 # These exact commands were fixture-tested and used by the hardware pilot.
 grep -F "restore='setenv bootcmd bootipq && setenv changing_bootcmd && saveenv'" "$core" >/dev/null &&
 grep -F "put bootcmd 'run miami_persistent_restore && run miami_persistent_load || bootipq'" "$core" >/dev/null || return 1
 [ "$(fw_printenv bootcmd)" = bootcmd=bootipq ] && [ "$(fw_printenv image)" = "image=$OEM_SOURCE_SLOT" ] || return 1
 OEM_BOOT_PRIOR_SLOT=$OEM_SOURCE_SLOT OEM_BOOT_TARGET_SLOT=$OEM_TARGET_SLOT
 OEM_BOOT_MODE=persist-prior-before-load
 # Verified fallback on reset/powercycle; no unsupported automatic-WD claim.
 OEM_BOOT_WATCHDOG=manual-reset
}
