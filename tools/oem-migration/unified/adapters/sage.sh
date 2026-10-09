#!/bin/sh
# Sage source adapter. Pure existing pair/settings writers, not the old launcher.
# Release files are individually authenticated before they are read or sourced.
oem_sage_factory() {
 local node index found= count=0 header product serial device reported
 for node in "$OEM_SYS_ROOT"/sys/class/mtd/mtd[0-9]*; do
  index=${node##*/mtd}; case "$index" in ''|*[!0-9]*) continue;; esac
  [ -r "$node/name" ] && [ "$(cat "$node/name")" = mfginfo ] || continue
  case "$(cat "$node/type")" in nor|nand) ;; *) continue;; esac
  [ "$(cat "$node/size")" = 65536 ] || return 1
  found=$index; count=$((count+1))
 done
 [ "$count" = 1 ] || return 1
 device=$OEM_SYS_ROOT/dev/mtd${found}ro
 [ -n "$OEM_SYS_ROOT" ] || [ -c "$device" ] || return 1
 header=$(od -An -tx1 -N6 "$device" | tr -d ' \n') || return 1
 [ "$header" = 05ca01000c00 ] || return 1
 serial=$(dd if="$device" bs=1 skip=6 count=12 2>/dev/null | tr 'A-F' 'a-f') || return 1
 case "$serial" in ''|*[!0-9a-f]*|000000000000|ffffffffffff) return 1;; esac
 [ "${#serial}" = 12 ] || return 1
 case "$(printf '%s' "$serial" | cut -c2)" in 1|3|5|7|9|b|d|f) return 1;; esac
 product=$(tr '\000' '\n' < "$device" | grep -o 'PL-E410XXX[AB]-[A-Z][A-Z]') || return 1
 [ "$(printf '%s\n' "$product" | wc -l)" -eq 1 ] || return 1
 OEM_SAGE_FACTORY_SERIAL=$serial OEM_SAGE_FACTORY_PRODUCT=$product
}
oem_sage_detect() {
 local model effective reported=${OEM_REPORTED_SKU:-${OEM_SKU:-}}
 oem_sage_factory || return 1
 case "$OEM_SAGE_FACTORY_PRODUCT:$reported" in
  PL-E410XXXA-??:|PL-E410XXXA-??:0000000a) model=E410; effective=0000000a;;
  PL-E410XXXB-??:|PL-E410XXXB-??:00000015|PL-E410XXXB-??:0000000a) model=E410B; effective=00000015;;
  *) return 1;;
 esac
 printf '%s\t%s\n' "$effective" "$model"
}
oem_sage_member() { oem_bundle_member "profiles/$OEM_MODEL/$1"; }
oem_sage_load() {
 local name member
 for name in cambium-oem-sage-prepare.sh cambium-oem-sage-storage-check.sh cambium-oem-sage-context.sh cambium-oem-models.tsv; do
  oem_bundle_member "readers/sage/$name" >/dev/null || return 1
 done
 OEM_SAGE_READERS=$OEM_BUNDLE/readers/sage
 for name in cambium-sage-pair-write.sh cambium-installer-settings.sh cambium-oem-sage-transaction.sh cambium-oem-sage-boot.sh runtime-implementation-contract.sh; do
  member=$(oem_bundle_member "lib/$name") || return 1
  . "$member" || return 1
 done
}
oem_adapter_inspect() {
 local context model slot pending
 OEM_SERIAL= OEM_SOURCE_RELEASE= OEM_SOURCE_SLOT= OEM_TARGET_SLOT=
 case "$OEM_FAMILY:$OEM_MODEL:$OEM_SKU" in sage:E410:0000000a|sage:E410B:00000015) ;; *) oem_fail 'this Sage hardware tuple is unsupported'; return 1;; esac
 oem_sage_load || return 1
 if [ -z "$OEM_SYS_ROOT" ]; then
  context=$(sh "$OEM_SAGE_READERS/cambium-oem-sage-context.sh" check) || return 1
 else
  context=$(sh "$OEM_SAGE_READERS/cambium-oem-sage-context.sh" inspect-capture "$OEM_SYS_ROOT") || return 1
 fi
 [ "$(printf '%s\n' "$context" | wc -l)" -eq 1 ] || return 1
 model=$(printf '%s\n' "$context" | cut -f3)
 [ "$model" = "$OEM_MODEL" ] || { oem_fail 'Sage factory A/B identity disagrees with SKU'; return 1; }
 pending=$(printf '%s\n' "$context" | cut -f5-7 | tr -d '\t')
 [ -z "$pending" ] || { oem_fail 'an enrollment transaction is already pending'; return 1; }
 slot=$(printf '%s\n' "$context" | cut -f4)
 case "$slot" in 0|1) ;; *) return 1;; esac
 OEM_SERIAL=$(printf '%s\n' "$context" | cut -f1)
 OEM_SOURCE_RELEASE=$(oem_read_release "$OEM_SYS_ROOT/etc/version") || return 1
 OEM_SOURCE_SLOT=$slot OEM_TARGET_SLOT=$((1-slot))
 oem_context_check
}
oem_sage_profile() {
 local file model product release digest evidence actual
 file=$(oem_sage_member operator-model) || return 1
 [ "$(wc -l < "$file")" -eq 2 ] || return 1
 model=$(sed -n '1p' "$file") product=$(sed -n '2p' "$file")
 [ "$model" = "$OEM_MODEL" ] || return 1
 case "$model:$product" in E410:PL-E410XXXA-??|E410B:PL-E410XXXB-??) ;; *) return 1;; esac
 if [ -z "$OEM_SYS_ROOT" ]; then evidence=$(sh "$OEM_SAGE_READERS/cambium-oem-sage-prepare.sh" check) || return 1
 else evidence=$(sh "$OEM_SAGE_READERS/cambium-oem-sage-prepare.sh" inspect-capture "$OEM_SYS_ROOT") || return 1; fi
 actual=$(printf '%s\n' "$evidence" | awk -F= '$1=="product" {v=$2;n++} END{if(n!=1)exit 1;print v}') || return 1
 [ "$actual" = "$product" ] || return 1
 file=$(oem_sage_member source-contract) || return 1
 [ "$(wc -l < "$file")" -eq 2 ] || return 1
 release=$(sed -n '1p' "$file") digest=$(sed -n '2p' "$file")
 [ "$release" = "$OEM_SOURCE_RELEASE" ] && oem_hex64 "$digest" || return 1
 OEM_SAGE_CONTRACT=$digest
 file=$(oem_sage_member operator-artifact-pins) || return 1
 [ "$(wc -l < "$file")" -eq 3 ] || return 1
 COS_IMAGE_PIN=$(sed -n '1p' "$file") COS_KERNEL_PIN=$(sed -n '2p' "$file") COS_ROOT_PIN=$(sed -n '3p' "$file")
 oem_hex64 "$COS_IMAGE_PIN" && oem_hex64 "$COS_KERNEL_PIN" && oem_hex64 "$COS_ROOT_PIN" || return 1
 COS_IMAGE=$(oem_bundle_member "payloads/$OEM_MODEL/image.bin") || return 1
 COS_KERNEL=$(oem_bundle_member "payloads/$OEM_MODEL/kernel.itb") || return 1
 COS_ROOT=$(oem_bundle_member "payloads/$OEM_MODEL/rootfs.squashfs") || return 1
 [ "$(oem_sha "$COS_IMAGE")" = "$COS_IMAGE_PIN" ] && [ "$(oem_sha "$COS_KERNEL")" = "$COS_KERNEL_PIN" ] && [ "$(oem_sha "$COS_ROOT")" = "$COS_ROOT_PIN" ] || return 1
 # The release publisher verifies the extracted FIT, not an AP-supplied claim.
 # Tie the exact tested configuration to the independently pinned kernel.
 file=$(oem_sage_member fit.tsv) || return 1
 case "$OEM_MODEL" in E410) COS_TARGET_FIT=config@5;; E410B) COS_TARGET_FIT=config@17;; esac
 awk -F '\t' -v hash="$COS_KERNEL_PIN" -v model="$OEM_MODEL" -v sku="$OEM_SKU" -v fit="$COS_TARGET_FIT" \
  'NF!=4 || $1!=hash || $2!=model || $3!=sku || $4!=fit {bad=1} END{exit bad || NR!=1}' "$file" || return 1
 file=$(oem_sage_member source-sets/runtime-implementation.set) || return 1
 ow_runtime_contract_check "$file" "$OEM_SYS_ROOT" || return 1
}
oem_sage_environment() (
 set +x; set +a; unset oem_private_environment_blob
 oem_private_environment_blob=$(fw_printenv -c "$COS_ENV_CONFIG" 2>&1) || exit 1
 # fwtools can succeed using compiled defaults after a bad-CRC warning. Never
 # permit that fallback to overwrite an unreadable factory environment.
 printf '%s\n' "$oem_private_environment_blob" | awk '
  {i=index($0,"=");key=substr($0,1,i-1);if(!i || key!~/^[A-Za-z0-9_#.-]+$/ || seen[key]++)bad=1}
  END{exit bad || NR<1}' || exit 1
 printf '%s\n' "$oem_private_environment_blob"
)
oem_sage_pending() {
 local snapshot
 snapshot=$(oem_sage_environment) || return 1
 printf '%s\n' "$snapshot" | awk -F= '
  $1~/^sage_installer_(target|job|image)$/ || $1=="sage_storage_pending" {if(NF!=2 || length($2) || seen[$1]++)bad=1}
  END{exit bad}'
}
oem_sage_context() {
 CSP_SYS=$OEM_SYS_ROOT/sys/class/ubi CSP_DEV=$OEM_SYS_ROOT/dev
 CSP_CMDLINE=$OEM_SYS_ROOT/proc/cmdline CSP_MOUNTS=$OEM_SYS_ROOT/proc/mounts
 CSP_FS_MTD=$(oem_physical_index "$OEM_SYS_ROOT/sys/class/mtd" fs) || return 1
 OEM_SAGE_ENV_MTD=$(oem_physical_index "$OEM_SYS_ROOT/sys/class/mtd" 0:APPSBLENV) || return 1
 COS_ENV_CONFIG=$OEM_SYS_ROOT/etc/fw_env.config
 [ -r "$COS_ENV_CONFIG" ] || COS_ENV_CONFIG=$OEM_SYS_ROOT/tmp/fw_env.config
 [ -r "$COS_ENV_CONFIG" ] && [ ! -L "$COS_ENV_CONFIG" ] || return 1
 OW_SETTINGS_SYS=$CSP_SYS OW_SETTINGS_DEV=$CSP_DEV OW_SETTINGS_MOUNTS=$CSP_MOUNTS OW_SETTINGS_OWNER=0
 OW_EXPECT_SERIAL=$OEM_SERIAL OW_EXPECT_FAMILY=sage OW_EXPECT_MODEL=$OEM_MODEL
 OW_EXPECT_OPERATION=production-oem-migration OW_EXPECT_RELEASE=$OEM_SOURCE_RELEASE
 OW_EXPECT_CONTRACT=$OEM_SAGE_CONTRACT OW_EXPECT_SOURCE=$OEM_SOURCE_SLOT OW_EXPECT_TARGET=$OEM_TARGET_SLOT
 CSP_ACTIVE=$OEM_SOURCE_SLOT
 COS_OEM_BOOT_COMMAND="setenv image $OEM_SOURCE_SLOT; bootipq"
 COS_BOOT_QUALIFIED=qualified
}
oem_adapter_preflight() {
 local file name id operation flags
 oem_sage_profile && oem_sage_context && oem_sage_pending && cos_boot_preflight || return 1
 [ -n "${OEM_WORK:-}" ] && [ -d "$OEM_WORK" ] && [ ! -L "$OEM_WORK" ] || return 1
 file=$(oem_sage_member mtd.tsv) || return 1
 OEM_PROTECTED_RANGES=$OEM_WORK/sage-ranges.tsv OEM_WRITE_PLAN=$OEM_WORK/sage-write-plan.tsv
 oem_physical_inventory "$file" "$OEM_SYS_ROOT/sys/class/mtd" "$OEM_PROTECTED_RANGES" || return 1
 awk -F '\t' -v fs="$CSP_FS_MTD" -v env="$OEM_SAGE_ENV_MTD" \
  '$1==fs {if($3!=134217728 || $4!="shared-parent")bad=1;n++} $1==env {if($4!="environment")bad=1;e++} END{exit bad || n!=1 || e!=1}' "$OEM_PROTECTED_RANGES" || return 1
 for id in "$CSP_FS_MTD" "$OEM_SAGE_ENV_MTD"; do
  flags=$(cat "$OEM_SYS_ROOT/sys/class/mtd/mtd$id/flags") || return 1
  printf '%s\n' "$flags" | awk 'NR!=1 || $0!~/^([0-9]+|0x[0-9a-fA-F]+)$/ {bad=1} END{exit bad}' || return 1
  [ "$((flags & 0x400))" -ne 0 ] || return 1
 done
 [ "$(cat "$CSP_SYS/ubi0/ro_mode")" = 0 ] || return 1
 csp_payload_check "$COS_KERNEL" "$COS_ROOT" 285 squashfs && cos_certificate_capacity before || return 1
 : > "$OEM_WRITE_PLAN" || return 1
 for name in "linux$OEM_TARGET_SLOT" "rootfs$OEM_TARGET_SLOT"; do
  case "$name" in linux*) id=$((2*OEM_TARGET_SLOT));; *) id=$((2*OEM_TARGET_SLOT+1));; esac
  oem_ubi_child_check "$CSP_SYS" "$CSP_FS_MTD" ubi0 "$id" "$name" || return 1
  for operation in ubi-update ubi-remove ubi-create; do
   [ "$name" != "linux$OEM_TARGET_SLOT" ] || [ "$operation" = ubi-update ] || continue
   printf '%s\t%s\t%s\t%s\n' "$operation" "$CSP_FS_MTD" "$id" "$name" >> "$OEM_WRITE_PLAN" || return 1
  done
 done
 printf 'ubi-create\t%s\t%s\trootfs_data%s\nenvironment-fields\t%s\tfields\tpreserve-unlisted\n' \
  "$CSP_FS_MTD" "$CSP_OVERLAY_ID" "$OEM_TARGET_SLOT" "$OEM_SAGE_ENV_MTD" >> "$OEM_WRITE_PLAN" || return 1
 if [ "$CSP_OVERLAY_LEBS" -gt 0 ]; then
  printf 'ubi-remove\t%s\t%s\trootfs_data%s\n' "$CSP_FS_MTD" "$CSP_OVERLAY_ID" "$OEM_TARGET_SLOT" >> "$OEM_WRITE_PLAN" || return 1
 fi
 oem_write_boundary "$OEM_PROTECTED_RANGES" "$OEM_WRITE_PLAN" || return 1
 for name in mount umount ubiupdatevol ubirmvol ubimkvol fw_setenv fw_printenv sync cmp; do command -v "$name" >/dev/null || return 1; done
}
oem_adapter_recovery() {
 local plan
 plan=$(oem_sage_member critical-backup.tsv) || return 1
 OEM_RECOVERY_DIR=$OEM_WORK/critical
 oem_backup_capture "$plan" "$OEM_SYS_ROOT/sys/class/mtd" "$OEM_SYS_ROOT/dev" "$OEM_RECOVERY_DIR" && oem_backup_upload "$OEM_RECOVERY_DIR" || return 1
}
oem_adapter_boot_preflight() {
 local pin file index
 cos_boot_preflight || return 1
 # Existing per-model bootloader bytes, not an operator approval flag. No
 # assertion that a Linux watchdog proves automatic pre-kernel hang recovery.
 file=$(oem_sage_member bootloader.sha256) || { oem_fail "$OEM_MODEL: reviewed bootloader mapping is missing"; return 1; }
 [ "$(wc -l < "$file")" -eq 1 ] || return 1
 pin=$(cat "$file"); oem_hex64 "$pin" || return 1
 index=$(oem_physical_index "$OEM_SYS_ROOT/sys/class/mtd" 0:APPSBL) || return 1
 [ "$(cat "$OEM_SYS_ROOT/sys/class/mtd/mtd$index/type")" = nor ] && [ "$(cat "$OEM_SYS_ROOT/sys/class/mtd/mtd$index/size")" = 524288 ] || return 1
 [ "$(oem_sha "$OEM_SYS_ROOT/dev/mtd${index}ro")" = "$pin" ] || return 1
 OEM_BOOT_PRIOR_SLOT=$OEM_SOURCE_SLOT OEM_BOOT_TARGET_SLOT=$OEM_TARGET_SLOT
 OEM_BOOT_MODE=persist-prior-before-load OEM_BOOT_WATCHDOG=manual-reset
}
# Each destructive UBI command remains the original writer operation, with an
# additional live parent/name/health and exact plan proof immediately before it.
oem_sage_write_check() {
 local operation=$1 child=$2 name=$3 create=${4:-0} file
 file=$(oem_sage_member mtd.tsv) || return 1
 oem_physical_inventory "$file" "$OEM_SYS_ROOT/sys/class/mtd" "$OEM_PROTECTED_RANGES" && oem_write_boundary "$OEM_PROTECTED_RANGES" "$OEM_WRITE_PLAN" || return 1
 awk -F '\t' -v op="$operation" -v parent="$CSP_FS_MTD" -v id="$child" -v name="$name" \
  '$1==op && $2==parent && $3==id && $4==name {n++} END{exit n!=1}' "$OEM_WRITE_PLAN" || return 1
 if [ "$create" = 1 ]; then
  [ ! -e "$CSP_SYS/ubi0_$child" ] || return 1
  [ "$(cat "$CSP_SYS/ubi0/mtd_num")" = "$CSP_FS_MTD" ] || return 1
  [ "$(grep -l -x "$CSP_FS_MTD" "$CSP_SYS"/ubi*/mtd_num | wc -l)" -eq 1 ]
 else
  oem_ubi_child_check "$CSP_SYS" "$CSP_FS_MTD" ubi0 "$child" "$name"
 fi
}
oem_sage_critical_check() {
 local kind label index bytes reason
 [ "$(cat "$OEM_WORK/critical/OFFDEVICE_VERIFIED")" = "$(oem_sha "$OEM_WORK/critical/SHA256SUMS")" ] || return 1
 (cd "$OEM_WORK/critical" && sha256sum -c SHA256SUMS >/dev/null 2>&1) || return 1
 while IFS="$(printf '\t')" read -r kind label bytes reason; do
  [ "$kind" != ENV ] || continue
  index=$(oem_physical_index "$OEM_SYS_ROOT/sys/class/mtd" "$label") || return 1
  [ "$(oem_sha "$OEM_WORK/critical/$kind.bin")" = "$(oem_sha "$OEM_SYS_ROOT/dev/mtd${index}ro")" ] || return 1
 done < "$OEM_WORK/critical/manifest.tsv"
 oem_sage_environment > "$OEM_WORK/env-after" || return 1
 oem_env_preserved "$OEM_WORK/env-before" "$OEM_WORK/env-after" "$OEM_WORK/env-allowed" || return 1
 oem_sage_protected_snapshot > "$OEM_WORK/protected-after" || return 1
 cmp -s "$OEM_WORK/protected-before" "$OEM_WORK/protected-after"
}
oem_sage_protected_snapshot() {
 local node id name bytes hash
 for node in "$CSP_SYS"/ubi0_*/name; do
  [ -r "$node" ] || continue
  id=${node%/name}; id=${id##*_}; name=$(cat "$node") || return 1
  case "$name" in "linux$OEM_TARGET_SLOT"|"rootfs$OEM_TARGET_SLOT"|"rootfs_data$OEM_TARGET_SLOT") continue;; esac
  case "$id" in ''|*[!0-9]*) return 1;; esac
  oem_ubi_child_check "$CSP_SYS" "$CSP_FS_MTD" ubi0 "$id" "$name" || return 1
  bytes=$(cat "$CSP_SYS/ubi0_$id/reserved_ebs") || return 1
  # The OEM root is mounted writable UBIFS on this exact source baseline.
  # Normal daemon writes are not installer writes. Preserve these children
  # through the live parent/name/size proof and target-only command wrappers.
  case "$name" in
   nvram|certificates|"rootfs_data$OEM_SOURCE_SLOT"|"rootfs$OEM_SOURCE_SLOT") hash=mutable-no-installer-writes;;
   *) hash=$(oem_sha "$CSP_DEV/ubi0_$id") && oem_hex64 "$hash" || return 1;;
  esac
  printf '%s\t%s\t%s\t%s\n' "$id" "$name" "$bytes" "$hash" || return 1
 done
}
oem_adapter_migrate() (
 set +x
 set +a
 unset credential
 local credential=$1 job file id name kind label bytes reason index
 oem_adapter_inspect && oem_adapter_preflight && oem_adapter_boot_preflight || exit 1
 oem_sage_environment > "$OEM_WORK/env-before" || exit 1
 oem_sage_protected_snapshot > "$OEM_WORK/protected-before" || exit 1
 printf '%s\n' bootcmd image sage_storage_pending sage_boot0 sage_boot1 sage_stable0 sage_stable1 sage_ab_version sage_ab_confirmed sage_ab_target sage_ab_state sage_installer_target sage_installer_job sage_installer_image > "$OEM_WORK/env-allowed" || exit 1
 job=$(od -An -tx1 -N32 "$OEM_SYS_ROOT/dev/urandom" | tr -d ' \n') || exit 1
 oem_hex64 "$job" || exit 1
 OW_EXPECT_JOB=$job
 printf 'format\t2\nserial\t%s\nfamily\tsage\nmodel\t%s\nsource_operation\tproduction-oem-migration\nsource_release\t%s\nsource_contract_sha256\t%s\nsource_slot\t%s\ntarget_slot\t%s\nimage_sha256\t%s\njob_id\t%s\n' \
  "$OEM_SERIAL" "$OEM_MODEL" "$OEM_SOURCE_RELEASE" "$OEM_SAGE_CONTRACT" "$OEM_SOURCE_SLOT" "$OEM_TARGET_SLOT" "$COS_IMAGE_PIN" "$job" > "$OEM_WORK/binding.tsv" || exit 1
 printf '{"server":"%s:18443","tls_ca":"/etc/ssl/certs/ca-certificates.crt"}\n' "$OEM_CONTROLLER" > "$OEM_WORK/est.json" || exit 1
 printf '{"server":"%s","port":15002,"cert":"/etc/ucentral/operational.pem","ca":"/etc/ssl/certs/ca-certificates.crt","hostname_validate":1}\n' "$OEM_CONTROLLER" > "$OEM_WORK/gateway.json" || exit 1
 chmod 600 "$OEM_WORK/binding.tsv" "$OEM_WORK/est.json" "$OEM_WORK/gateway.json" || exit 1
 ow_settings_prepare "$OEM_WORK/binding.tsv" "$OEM_WORK/est.json" "$OEM_WORK/gateway.json" "$credential" "$OEM_WORK/seed" || exit 1
 credential=
 # Receipt and live unique assets, including raw ENV, must still match before
 # even the deliberate storage-journal environment write.
 [ "$(cat "$OEM_WORK/critical/OFFDEVICE_VERIFIED")" = "$(oem_sha "$OEM_WORK/critical/SHA256SUMS")" ] || exit 1
 (cd "$OEM_WORK/critical" && sha256sum -c SHA256SUMS >/dev/null 2>&1) || exit 1
 while IFS="$(printf '\t')" read -r kind label bytes reason; do
  index=$(oem_physical_index "$OEM_SYS_ROOT/sys/class/mtd" "$label") || exit 1
  [ "$(oem_sha "$OEM_WORK/critical/$kind.bin")" = "$(oem_sha "$OEM_SYS_ROOT/dev/mtd${index}ro")" ] || exit 1
 done < "$OEM_WORK/critical/manifest.tsv"
 OEM_SAGE_JOURNAL="install:$OEM_SOURCE_SLOT:$OEM_TARGET_SLOT:$COS_IMAGE_PIN:$job"
 cos_persist_source "$OEM_SAGE_JOURNAL" || exit 1
 cos_admit() { OW_STAGE_ADMISSION=qualified; }
 cos_authenticate() { [ "$(oem_sha "$1")" = "$COS_IMAGE_PIN" ] && [ "$(oem_sha "$2")" = "$COS_KERNEL_PIN" ] && [ "$(oem_sha "$3")" = "$COS_ROOT_PIN" ]; }
 cos_source_check() {
  cos_boot_preflight
 }
 cos_refuse_pending() {
  [ "$(fw_printenv -c "$COS_ENV_CONFIG" -n sage_storage_pending)" = "$OEM_SAGE_JOURNAL" ] || return 1
  oem_sage_environment | awk -F= '$1~/^sage_installer_(target|job|image)$/ && length($2) {bad=1} END{exit bad}'
 }
 cos_recovery() { oem_sage_critical_check; }
 ubiupdatevol() {
  case "$1" in "$CSP_DEV/ubi0_"*) id=${1##*_};; *) return 1;; esac
  name=$(cat "$CSP_SYS/ubi0_$id/name") || return 1
  oem_sage_write_check ubi-update "$id" "$name" && command ubiupdatevol "$@"
 }
 ubirmvol() {
  [ "$1:$2:$#" = "$CSP_DEV/ubi0:-n:3" ] || return 1
  name=$(cat "$CSP_SYS/ubi0_$3/name") || return 1
  oem_sage_write_check ubi-remove "$3" "$name" && command ubirmvol "$@"
 }
 ubimkvol() {
  [ "$1:$2:$4:$6:$#" = "$CSP_DEV/ubi0:-n:-N:-s:7" ] || return 1
  oem_sage_write_check ubi-create "$3" "$5" 1 && command ubimkvol "$@"
 }
 # Override only the unsafe semicolon armer; metadata/readback stays original.
 cos_arm() {
  oem_sage_critical_check && cos_boot_preflight && ow_settings_context "$1" || return 1
  local target trial work key value
  target=$(cos_native_target_command) || return 1
  trial="setenv bootcmd run sage_boot$OEM_SOURCE_SLOT && setenv image $OEM_SOURCE_SLOT && setenv sage_ab_state trial-started && saveenv && run sage_boot$OEM_TARGET_SLOT; run sage_boot$OEM_SOURCE_SLOT"
  work=$OEM_WORK/arm-metadata
  {
   printf 'sage_boot%s %s\nsage_boot%s %s\n' "$OEM_SOURCE_SLOT" "$COS_OEM_BOOT_COMMAND" "$OEM_TARGET_SLOT" "$target"
   printf 'sage_stable%s run sage_boot%s\n' "$OEM_SOURCE_SLOT" "$OEM_SOURCE_SLOT"
   printf 'sage_stable%s run sage_boot%s; run sage_boot%s\n' "$OEM_TARGET_SLOT" "$OEM_TARGET_SLOT" "$OEM_SOURCE_SLOT"
   printf 'sage_ab_version 1\nsage_ab_confirmed %s\nsage_ab_target %s\nsage_ab_state armed\n' "$OEM_SOURCE_SLOT" "$OEM_TARGET_SLOT"
   printf 'sage_installer_target %s\nsage_installer_job %s\nsage_installer_image %s\n' "$OEM_TARGET_SLOT" "$OW_EXPECT_JOB" "$COS_IMAGE_PIN"
  } > "$work" || return 1
  fw_setenv -c "$COS_ENV_CONFIG" -s "$work" && sync || return 1
  while read -r key value; do [ "$(fw_printenv -c "$COS_ENV_CONFIG" -n "$key")" = "$value" ] || return 1; done < "$work"
  oem_sage_critical_check || return 1
  fw_setenv -c "$COS_ENV_CONFIG" bootcmd "$trial" && sync || return 1
  [ "$(fw_printenv -c "$COS_ENV_CONFIG" -n bootcmd)" = "$trial" ]
 }
 cos_install "$COS_IMAGE" "$COS_KERNEL" "$COS_ROOT" "$OEM_WORK/seed" || exit 1
 oem_sage_critical_check || exit 1
 fw_setenv -c "$COS_ENV_CONFIG" sage_storage_pending && sync || exit 1
 ! fw_printenv -c "$COS_ENV_CONFIG" -n sage_storage_pending >/dev/null 2>&1 || exit 1
 printf 'handoff=one-shot-armed\nonboarded=not-yet-verified\nsysupgrade_ready=not-yet-verified\n'
)
