#!/bin/sh
# Bounded test return from confirmed OpenWiFi to an inactive OEM candidate.
# Does not clear native certificates, revoke enrollment or erase unique data.
oem_restore_sage_member() { oem_bundle_member "profiles/$OEM_MODEL/restore/$1"; }
oem_restore_sage_load() {
 local name member
 for name in cambium-sage-pair-write.sh cambium-installer-settings.sh cambium-sage-oem-reset.sh cambium-sage-oem-recovery.sh cambium-sage-oem-defaults.sh runtime-implementation-contract.sh; do
  member=$(oem_bundle_member "lib/$name") || return 1
  . "$member" || return 1
 done
}
oem_restore_inspect() {
 local member release contract status field value
 OEM_SERIAL= OEM_SOURCE_RELEASE= OEM_SOURCE_SLOT= OEM_TARGET_SLOT=
 [ "$OEM_FAMILY:$OEM_MODEL:$OEM_SKU" = sage:E410:0000000a ] || {
  oem_fail "$OEM_MODEL: exact OEM-return boot/defaults mapping is unavailable; E410B is not inferred from E410"; return 1;
 }
 oem_restore_sage_load || return 1
 member=$(oem_restore_sage_member source-sets/runtime-implementation.set) || return 1
 ow_runtime_contract_check "$member" "$OEM_SYS_ROOT" || return 1
 member=$(oem_restore_sage_member source-contract) || return 1
 [ "$(wc -l < "$member")" -eq 2 ] || return 1
 release=$(sed -n '1p' "$member") contract=$(sed -n '2p' "$member")
 oem_hex64 "$contract" || return 1
 OEM_SOURCE_RELEASE=$(awk -F= '$1=="DISTRIB_TIP_VERSION" {v=$2;gsub(/^\047|\047$/,"",v);n++} END{if(n!=1 || v!~/^[A-Za-z0-9._~-]+$/)exit 1;print v}' "$OEM_SYS_ROOT/etc/openwrt_release") || return 1
 [ "$release" = "$OEM_SOURCE_RELEASE" ] && [ "$release" = "$OEM_SUPPORTED_RELEASE" ] || return 1
 status=$(cambium-ab-status) || return 1
 for field in family model mode running confirmed state; do
  value=$(printf '%s\n' "$status" | awk -v key="$field" 'index($0,key "=")==1 {v=substr($0,length(key)+2);n++} END{if(n!=1)exit 1;print v}') || return 1
  case "$field:$value" in
   family:sage|model:E410|mode:ab|state:confirmed) ;;
   running:0|running:1) OEM_SOURCE_SLOT=$value;;
   confirmed:0|confirmed:1) [ "$value" = "$OEM_SOURCE_SLOT" ] || return 1;;
   *) return 1;;
  esac
 done
 OEM_TARGET_SLOT=$((1-OEM_SOURCE_SLOT))
 # Use the exact existing authoritative label reader; do not derive radio MACs.
 . "$OEM_SYS_ROOT/lib/functions/system.sh" || return 1
 OEM_SERIAL=$(get_mac_label_dt | tr -d ':' | tr 'A-F' 'a-f') || return 1
 oem_context_check
}
oem_restore_preflight() {
 local member index flags pin name id operation
 [ "$OEM_MODEL" = E410 ] || return 1
 member=$(oem_restore_sage_member operator-artifact-pins) || return 1
 [ "$(wc -l < "$member")" -eq 3 ] || return 1
 CSR_KERNEL_PIN=$(sed -n '1p' "$member") CSR_ROOT_PIN=$(sed -n '2p' "$member") CSR_SHARED_PIN=$(sed -n '3p' "$member")
 CSR_KERNEL=$(oem_bundle_member "payloads/$OEM_MODEL/oem/kernel.itb") || return 1
 CSR_ROOT=$(oem_bundle_member "payloads/$OEM_MODEL/oem/rootfs.ubifs") || return 1
 CSR_SHARED_MANIFEST=$(oem_bundle_member "payloads/$OEM_MODEL/oem/shared.json") || return 1
 for pin in "$CSR_KERNEL_PIN" "$CSR_ROOT_PIN" "$CSR_SHARED_PIN"; do oem_hex64 "$pin" || return 1; done
 [ "$(oem_sha "$CSR_KERNEL")" = "$CSR_KERNEL_PIN" ] && [ "$(oem_sha "$CSR_ROOT")" = "$CSR_ROOT_PIN" ] && [ "$(oem_sha "$CSR_SHARED_MANIFEST")" = "$CSR_SHARED_PIN" ] || return 1
 CSR_MODEL=E410 CSR_ACTIVE=$OEM_SOURCE_SLOT
 CSR_MTD_SYS=$OEM_SYS_ROOT/sys/class/mtd CSR_UBI_SYS=$OEM_SYS_ROOT/sys/class/ubi
 CSR_DEV=$OEM_SYS_ROOT/dev CSR_PROC_MTD=$OEM_SYS_ROOT/proc/mtd CSR_CMDLINE=$OEM_SYS_ROOT/proc/cmdline CSR_MOUNTS=$OEM_SYS_ROOT/proc/mounts
 CSP_SYS=$CSR_UBI_SYS CSP_DEV=$CSR_DEV CSP_CMDLINE=$CSR_CMDLINE CSP_MOUNTS=$CSR_MOUNTS CSP_ACTIVE=$CSR_ACTIVE
 CSP_FS_MTD=$(oem_physical_index "$CSR_MTD_SYS" fs) || return 1
 CSR_ENV_CONFIG=$OEM_SYS_ROOT/tmp/cambium-ab-fw_env.config
 [ -r "$CSR_ENV_CONFIG" ] && [ ! -L "$CSR_ENV_CONFIG" ] || return 1
 member=$(oem_restore_sage_member "source-boot$CSR_ACTIVE.sha256") || return 1
 [ "$(wc -l < "$member")" -eq 1 ] || return 1
 CSR_SOURCE_BOOT_PIN=$(cat "$member"); oem_hex64 "$CSR_SOURCE_BOOT_PIN" || return 1
 # This separate test-return path does NOT erase config NOR or shared nvram.
 # Read-only config is permitted; the older full-reset CSR path stays guarded.
 index=$(oem_physical_index "$CSR_MTD_SYS" config) || return 1
 flags=$(cat "$CSR_MTD_SYS/mtd$index/flags") || return 1
 printf '%s\n' "$flags" | awk 'NR!=1 || $0!~/^([0-9]+|0x[0-9a-fA-F]+)$/ {bad=1} END{exit bad}' || return 1
 member=$(oem_restore_sage_member mtd.tsv) || return 1
 OEM_PROTECTED_RANGES=$OEM_WORK/sage-restore-ranges.tsv
 oem_physical_inventory "$member" "$CSR_MTD_SYS" "$OEM_PROTECTED_RANGES" || return 1
 OEM_WRITE_PLAN=$OEM_WORK/sage-restore-write-plan.tsv
 : > "$OEM_WRITE_PLAN" || return 1
 csp_payload_check "$CSR_KERNEL" "$CSR_ROOT" 372 ubifs || return 1
 for name in "linux$OEM_TARGET_SLOT" "rootfs$OEM_TARGET_SLOT"; do
  case "$name" in linux*) id=$((2*OEM_TARGET_SLOT));; *) id=$((2*OEM_TARGET_SLOT+1));; esac
  oem_ubi_child_check "$CSP_SYS" "$CSP_FS_MTD" ubi0 "$id" "$name" || return 1
  printf 'ubi-update\t%s\t%s\t%s\n' "$CSP_FS_MTD" "$id" "$name" >> "$OEM_WRITE_PLAN" || return 1
  [ "$name" != "rootfs$OEM_TARGET_SLOT" ] || printf 'ubi-resize\t%s\t%s\t%s\n' "$CSP_FS_MTD" "$id" "$name" >> "$OEM_WRITE_PLAN" || return 1
 done
 if [ "$CSP_OVERLAY_LEBS" -gt 0 ]; then
  oem_ubi_child_check "$CSP_SYS" "$CSP_FS_MTD" ubi0 "$CSP_OVERLAY_ID" "rootfs_data$OEM_TARGET_SLOT" || return 1
  printf 'ubi-remove\t%s\t%s\trootfs_data%s\n' "$CSP_FS_MTD" "$CSP_OVERLAY_ID" "$OEM_TARGET_SLOT" >> "$OEM_WRITE_PLAN" || return 1
 fi
 index=$(oem_physical_index "$CSR_MTD_SYS" 0:APPSBLENV) || return 1
 printf 'environment-fields\t%s\tfields\tpreserve-unlisted\n' "$index" >> "$OEM_WRITE_PLAN" || return 1
 oem_write_boundary "$OEM_PROTECTED_RANGES" "$OEM_WRITE_PLAN" || return 1
 CSR_RESET_QUALIFIED=qualified CSR_RECOVERY_BOOT_QUALIFIED=qualified CSR_OEM_DEFAULTS_QUALIFIED=qualified
 CSR_RECOVERY=$OEM_WORK/critical CSR_RECEIPT=$CSR_RECOVERY/OFFDEVICE_VERIFIED CSR_RECOVERY_FORMAT=unified
 # Recovery receipt is checked after backup as well, never self-created here.
 csp_payload_check "$CSR_KERNEL" "$CSR_ROOT" 372 ubifs
}
oem_restore_boot_preflight() {
 csr_boot_preflight || return 1
 OEM_BOOT_PRIOR_SLOT=$OEM_SOURCE_SLOT OEM_BOOT_TARGET_SLOT=$OEM_TARGET_SLOT
 OEM_BOOT_MODE=persist-prior-before-load OEM_BOOT_WATCHDOG=manual-reset
}
oem_restore_recovery() {
 local plan
 plan=$(oem_restore_sage_member critical-backup.tsv) || return 1
 OEM_RECOVERY_DIR=$OEM_WORK/critical
 oem_backup_capture "$plan" "$CSR_MTD_SYS" "$CSR_DEV" "$OEM_RECOVERY_DIR" && oem_backup_upload "$OEM_RECOVERY_DIR" || return 1
}
oem_restore_sage_write_check() {
 local operation=$1 id=$2 name file
 file=$(oem_restore_sage_member mtd.tsv) || return 1
 oem_physical_inventory "$file" "$CSR_MTD_SYS" "$OEM_PROTECTED_RANGES" && oem_write_boundary "$OEM_PROTECTED_RANGES" "$OEM_WRITE_PLAN" || return 1
 name=$(cat "$CSP_SYS/ubi0_$id/name") || return 1
 awk -F '\t' -v op="$operation" -v parent="$CSP_FS_MTD" -v id="$id" -v name="$name" \
  '$1==op && $2==parent && $3==id && $4==name {n++} END{exit n!=1}' "$OEM_WRITE_PLAN" || return 1
 oem_ubi_child_check "$CSP_SYS" "$CSP_FS_MTD" ubi0 "$id" "$name"
}
oem_restore_migrate() (
 local id
 oem_restore_preflight && oem_restore_boot_preflight || return 1
 csr_deferred_storage_boundary() {
  local file
  file=$(oem_restore_sage_member mtd.tsv) || return 1
  oem_physical_inventory "$file" "$CSR_MTD_SYS" "$OEM_PROTECTED_RANGES" && oem_write_boundary "$OEM_PROTECTED_RANGES" "$OEM_WRITE_PLAN"
 }
 ubiupdatevol() {
  local device
  if [ "$1" = -t ]; then [ "$#" = 2 ] || return 1; device=$2
  else [ "$#" = 2 ] || return 1; device=$1; fi
  id=${device##*_}
  [ "$device" = "$CSP_DEV/ubi0_$id" ] || return 1
  oem_restore_sage_write_check ubi-update "$id" && command ubiupdatevol "$@"
 }
 ubirmvol() {
  [ "$1:$2:$#" = "$CSP_DEV/ubi0:-n:3" ] || return 1
  oem_restore_sage_write_check ubi-remove "$3" && command ubirmvol "$@"
 }
 ubirsvol() {
  [ "$1:$2:$4:$#" = "$CSP_DEV/ubi0:-n:-s:5" ] && [ "$5" = "$((372*126976))" ] || return 1
  oem_restore_sage_write_check ubi-resize "$3" && command ubirsvol "$@"
 }
 csr_restore_oem_deferred || return 1
 printf 'handoff=one-shot-oem-armed\noem_boot=not-yet-verified\ndefaults_committed=no\n'
)

# OEM confirmation is distinct from factory reset. The native reset script
# reboots; never execute it under a confirmation-only prompt.
oem_restore_confirm_inspect() {
 local contract member version argument slot= attachment= format=
 [ "$OEM_FAMILY:$OEM_MODEL:$OEM_SKU" = sage:E410:0000000a ] || return 1
 oem_restore_sage_load || return 1
 member=$(oem_restore_sage_member confirm/source-sets/runtime-implementation.set) || return 1
 ow_runtime_contract_check "$member" "$OEM_SYS_ROOT" || return 1
 member=$(oem_restore_sage_member confirm/source-contract) || return 1
 [ "$(wc -l < "$member")" -eq 2 ] || return 1
 version=$(sed -n '1p' "$member"); contract=$(sed -n '2p' "$member")
 [ "$version" = 4.2.3.3-r10 ] && [ "$OEM_SUPPORTED_RELEASE" = "$version" ] && oem_hex64 "$contract" || return 1
 [ "$(oem_read_release "$OEM_SYS_ROOT/etc/version")" = "$version" ] || return 1
 [ "$(awk -F= '$1=="PRODUCT" {v=$2;n++} END{if(n!=1)exit 1;print v}' "$OEM_SYS_ROOT/etc/version")" = sage ] || return 1
 for argument in $(cat "$OEM_SYS_ROOT/proc/cmdline"); do
  case "$argument" in
   root=ubi0:rootfs0|root=ubi0:rootfs1) [ -z "$slot" ] || return 1; slot=${argument##*rootfs};;
   root=*) return 1;;
   ubi.mtd=*) [ -z "$attachment" ] || return 1; attachment=${argument#ubi.mtd=};;
   rootfstype=*) [ -z "$format" ] || return 1; format=${argument#rootfstype=};;
  esac
 done
 [ "$attachment:$format" = fs:ubifs ] || return 1
 case "$slot" in 0|1) ;; *) return 1;; esac
 OEM_SOURCE_SLOT=$((1-slot)) OEM_TARGET_SLOT=$slot OEM_SOURCE_RELEASE=$version
 # Same hardware label reader as the forward adapter, individually loaded.
 member=$(oem_bundle_member adapters/sage.sh) || return 1
 . "$member" || return 1
 oem_sage_factory || return 1
 [ "$OEM_SAGE_FACTORY_PRODUCT" = PL-E410XXXA-EU ] || return 1
 OEM_SERIAL=$OEM_SAGE_FACTORY_SERIAL
 oem_context_check
}
oem_restore_confirm_preflight() {
 local member pin index environment key value
 CSR_MODEL=E410 CSR_ACTIVE=$OEM_SOURCE_SLOT CSR_OEM_SLOT=$OEM_TARGET_SLOT
 CSR_MTD_SYS=$OEM_SYS_ROOT/sys/class/mtd CSR_UBI_SYS=$OEM_SYS_ROOT/sys/class/ubi
 CSR_DEV=$OEM_SYS_ROOT/dev CSR_PROC_MTD=$OEM_SYS_ROOT/proc/mtd CSR_CMDLINE=$OEM_SYS_ROOT/proc/cmdline CSR_MOUNTS=$OEM_SYS_ROOT/proc/mounts CSR_OEM_VERSION=$OEM_SYS_ROOT/etc/version
 CSR_ENV_CONFIG=$OEM_SYS_ROOT/etc/fw_env.config
 [ -r "$CSR_ENV_CONFIG" ] || CSR_ENV_CONFIG=$OEM_SYS_ROOT/tmp/fw_env.config
 [ -r "$CSR_ENV_CONFIG" ] && [ ! -L "$CSR_ENV_CONFIG" ] || return 1
 index=$(oem_physical_index "$CSR_MTD_SYS" 0:APPSBLENV) || return 1
 [ "$(cat "$CSR_MTD_SYS/mtd$index/size")" = 65536 ] || return 1
 case "$(awk '!/^#/ && NF {print}' "$CSR_ENV_CONFIG")" in
  "/dev/mtd$index 0x0 0x00010000 0x00010000 1"|"/dev/mtd$index 0x0 0x10000 0x10000 1") ;;
  *) return 1;;
 esac
 member=$(oem_restore_sage_member operator-artifact-pins) || return 1
 [ "$(wc -l < "$member")" -eq 3 ] || return 1
 CSR_KERNEL_PIN=$(sed -n '1p' "$member") CSR_ROOT_PIN=$(sed -n '2p' "$member") CSR_SHARED_PIN=$(sed -n '3p' "$member")
 CSR_KERNEL=$(oem_bundle_member "payloads/$OEM_MODEL/oem/kernel.itb") || return 1
 CSR_ROOT=$(oem_bundle_member "payloads/$OEM_MODEL/oem/rootfs.ubifs") || return 1
 CSR_SHARED_MANIFEST=$(oem_bundle_member "payloads/$OEM_MODEL/oem/shared.json") || return 1
 for pin in "$CSR_KERNEL_PIN" "$CSR_ROOT_PIN" "$CSR_SHARED_PIN"; do oem_hex64 "$pin" || return 1; done
 [ "$(oem_sha "$CSR_KERNEL")" = "$CSR_KERNEL_PIN" ] && [ "$(oem_sha "$CSR_ROOT")" = "$CSR_ROOT_PIN" ] && [ "$(oem_sha "$CSR_SHARED_MANIFEST")" = "$CSR_SHARED_PIN" ] || return 1
 member=$(oem_restore_sage_member "source-boot$CSR_ACTIVE.sha256") || return 1
 [ "$(wc -l < "$member")" -eq 1 ] || return 1
 CSR_SOURCE_BOOT_PIN=$(cat "$member")
 CSR_RECOVERY_BOOT_QUALIFIED=qualified CSR_OEM_DEFAULTS_QUALIFIED=qualified
 csr_boot_preflight || return 1
 environment=$(fw_printenv -c "$CSR_ENV_CONFIG" 2>&1) || return 1
 printf '%s\n' "$environment" | awk -F= -v source="$OEM_SOURCE_SLOT" -v target="$OEM_TARGET_SLOT" '
  {position=index($0,"=");key=substr($0,1,position-1);if(!position || key!~/^[A-Za-z0-9_#.-]+$/ || seen[key]++)bad=1}
  $1=="image" {if($2!=source || NF!=2)bad=1;i++}
  $1=="bootcmd" {if($2!="run sage_boot" source || NF!=2)bad=1;b++}
  $1=="sage_ab_state" {if($2!="trial-started" || NF!=2)bad=1;s++}
  $1=="sage_ab_confirmed" {if($2!=source || NF!=2)bad=1;c++}
  $1=="sage_ab_target" {if($2!=target || NF!=2)bad=1;t++}
  $1=="sage_oem_restore_target" {if($2!=target || NF!=2)bad=1;r++}
  $1=="sage_oem_restore_state" {if($2!="armed" || NF!=2)bad=1;j++}
  END{exit bad || i!=1 || b!=1 || s!=1 || c!=1 || t!=1 || r!=1 || j!=1}' || return 1
 member=$(oem_restore_sage_member mtd.tsv) || return 1
 OEM_PROTECTED_RANGES=$OEM_WORK/sage-confirm-ranges.tsv
 oem_physical_inventory "$member" "$CSR_MTD_SYS" "$OEM_PROTECTED_RANGES" || return 1
 index=$(oem_physical_index "$CSR_MTD_SYS" fs) || return 1
 oem_ubi_child_check "$CSR_UBI_SYS" "$index" ubi0 "$((2*OEM_TARGET_SLOT))" "linux$OEM_TARGET_SLOT" &&
  oem_ubi_child_check "$CSR_UBI_SYS" "$index" ubi0 "$((2*OEM_TARGET_SLOT+1))" "rootfs$OEM_TARGET_SLOT" || return 1
 # The authenticated runtime ledger and actual root command line establish
 # deployed OEM files. Its mounted UBIFS root can legitimately change after
 # boot; raw golden-root equality belongs to preboot staging, not confirmation.
 csp_readback "$CSR_KERNEL" "$CSR_DEV/ubi0_$((2*OEM_TARGET_SLOT))" &&
  oem_restore_sage_native_reset_instructions >/dev/null
}
oem_restore_confirm() {
 oem_restore_confirm_preflight || return 1
 OEM_BACKUP_ID=$(od -An -tx1 -N16 "$OEM_SYS_ROOT/dev/urandom" | tr -d ' \n') || return 1
 [ "${#OEM_BACKUP_ID}" = 32 ] || return 1
 oem_restore_recovery && oem_backup_receipt_check "$OEM_RECOVERY_DIR" || return 1
 CSR_RECOVERY=$OEM_RECOVERY_DIR CSR_RECEIPT=$OEM_RECOVERY_DIR/OFFDEVICE_VERIFIED CSR_RECOVERY_FORMAT=unified
 CSR_OEM_BOOT_VERIFIED=qualified
 csr_apply_oem_defaults || return 1
 oem_restore_sage_native_reset_instructions
}
oem_restore_sage_native_reset_instructions() {
 local file hash
 # Validate the exact existing native tools before suggesting a reset. The
 # generic confirmation command must NEVER run this rebooting vendor script.
 for file in delconfig.sh savecfg2nor.sh savecfgfromnnand.sh; do
  case "$file" in
   delconfig.sh) hash=4fb70585e9abfae317899a78ce7e988895731a58899b477e16156a28437fcd09;;
   savecfg2nor.sh) hash=f71c829e276e500c88d86cc812e6e90f2e39bd464fe9a2b45704018f951520d0;;
   savecfgfromnnand.sh) hash=a1f72635074c3fe4dd498ae3d75953512481d8843ecbc5c3c006f94fb1fe0644;;
  esac
  [ "$(oem_sha "$OEM_SYS_ROOT/usr/bin/scripts/$file")" = "$hash" ] || return 1
 done
 printf '%s\n' 'OEM confirmed; shared configuration and certificates are still preserved.' \
  'Separate explicit factory-reset action (reboots): /bin/sh /usr/bin/scripts/delconfig.sh force' \
  'After OEM has rebooted with defaults: /bin/sh /usr/bin/scripts/savecfg2nor.sh' \
  'The native save script masks flashcp errors. Verify the named NOR gzip/tar config.txt equals the regenerated /mnt/flash/config/config.txt; exit 0 alone is not proof.'
}
