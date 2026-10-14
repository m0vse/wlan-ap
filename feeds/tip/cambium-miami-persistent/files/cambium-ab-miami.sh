#!/bin/sh
# X7-35X legacy OEM preservation and explicit healthy-seed A/B admission.
case " ${AB_FAMILIES:-} " in *" miami "*) ;; *) AB_FAMILIES="${AB_FAMILIES:+$AB_FAMILIES }miami" ;; esac

ab_miami_board() {
	[ "$1" = 'cambiumnetworks,x7-35x' ] || return 1
	AB_NAME=Miami AB_MODEL=X7-35X AB_SKU=0000002c AB_ENV=miami
	AB_IMAGE_DIR=sysupgrade-cambiumnetworks_miami
	AB_BANK_SIZE=06000000 AB_SLOT0_OFFSET=0xc0000 AB_SLOT1_OFFSET=0x60c0000 AB_BANK_LEBS=724
	AB_VAULT=1 AB_VAULT_LEBS=72 AB_CERTIFICATE_LEBS=64
	AB_BOARD_DATA=/usr/sbin/miami-board-data AB_OWN_BOARD_DATA=1
	AB_LAN='up0v0 up' AB_RADIOS=0 AB_QUALIFIED=0
	AB_FIT=config@mi01.6-acadia-slot0
	if ab_miami_ab_profile; then
	 local slot
	 slot=$(hexdump -v -e '1/1 "%02x"' "${AB_DT:-/proc/device-tree}/cambium-platform/storage-slot") || return 1
	 case "$slot" in 00000000) slot=1 ;; 00000001) slot=0 ;; *) return 1 ;; esac
	 AB_IMAGE_DIR=sysupgrade-cambiumnetworks_miami-ab-slot$slot
	 AB_FIT=config@mi01.6-acadia-ab-slot$slot
	fi
	AB_PROTECTED='0:TRAINING 0:LICENSE 0:NVRAM crashLog 0:SBL1 0:SBL1_1 0:MIBIB 0:BOOTCONFIG 0:BOOTCONFIG1 0:APPSBL 0:DEVCFG 0:DEVCFG_1 0:TME 0:TME_1 config 0:CDT 0:APPSBL_1 0:ART mfginfo 0:QSEE 0:QSEE_1 0:CDT_1 0:EXTRADATA'
}

ab_miami_ab_profile() {
 local dt=${AB_DT:-/proc/device-tree} policy version
 [ -r "$dt/cambium-platform/storage-policy" ] && [ -r "$dt/cambium-platform/upgrade-policy" ] || return 1
 policy=$(tr -d '\000' < "$dt/cambium-platform/storage-policy") || return 1
 version=$(hexdump -v -e '1/1 "%02x"' "$dt/cambium-platform/upgrade-policy") || return 1
 [ "$policy:$version" = ab:00000001 ]
}


ab_miami_slot_command() {
 local part offset variant
 case "$1" in 0) part=rootfs; offset=$AB_SLOT0_OFFSET ;; 1) part=rootfs_1; offset=$AB_SLOT1_OFFSET ;; *) return 1 ;; esac
 case "$2" in legacy) variant= ;; ab) variant=ab- ;; *) return 1 ;; esac
 printf "nand device 0 && setenv mtdids nand0=nand0 && setenv mtdparts 'mtdparts=nand0:0x6000000@%s(fs)' && ubi part fs && ubi read 0x60000000 kernel && setenv bootargs console=ttyMSM0,115200n8 ubi.mtd=%s root=/dev/ubiblock0_1 rootfstype=squashfs rootwait && bootm 0x60000000#config@mi01.6-acadia-%sslot%s\n" "$offset" "$part" "$variant" "$1"
}

# Mixed first-conversion pairs retain the exact prior legacy FIT route. Only
# an admitted image in this upgrade process may select the new target route.
ab_miami_boot_command() {
 local active stored expected legacy mode
 case "$1" in 0|1) ;; *) return 1 ;; esac
 if ! ab_miami_ab_profile; then
  [ ! -e "${AB_DT:-/proc/device-tree}/cambium-platform/storage-policy" ] || return 1
  ab_miami_slot_command "$1" legacy; return
 fi
 active=$(ab_running_slot) || return 1
 expected=$(ab_miami_slot_command "$1" ab) || return 1
 if [ "${AB_MIAMI_IMAGE_TARGET:-}" = "$1" ]; then printf '%s\n' "$expected";return;fi
 if [ "$1" = "$active" ]; then
  # A bridge is not the persistent source image. Its source route must be
  # independently sealed by the bootstrap before the one-shot boot.
  mode=$(tr -d '\000' < "${AB_DT:-/proc/device-tree}/cambium-platform/boot-mode" 2>/dev/null) || mode=
  case "$mode" in
   '') printf '%s\n' "$expected"; return ;;
   bridge) [ "${AB_MIAMI_BRIDGE_VALIDATED:-}" = 1 ] || return 1
    ab_miami_slot_command "$1" legacy;return ;;
   *) return 1 ;;
  esac
 fi
 stored=$(ab_getenv "miami_boot$1") || return 1
 legacy=$(ab_miami_slot_command "$1" legacy) || return 1
 [ "$stored" = "$expected" ] || [ "$stored" = "$legacy" ] || return 1
 printf '%s\n' "$stored"
}

ab_miami_guarded_command() {
	local command restore
	command=$(ab_miami_boot_command "$1") || return 1
	restore='setenv bootcount 0 && setenv bootcmd bootipq && setenv changing_bootcmd && saveenv'
	if ab_miami_ab_profile; then
	 restore="setenv bootcount 0 && setenv bootcmd bootipq && setenv image $((1 - $1)) && setenv changing_bootcmd && saveenv"
	fi
	[ "$(ab_getenv miami_persistent_restore)" = "$restore" ] || return 1
	[ "$(ab_getenv miami_persistent_load)" = "$command" ] || return 1
	[ "$(ab_getenv miami_persistent_slot)" = "$1" ] || return 1
	echo 'if run miami_persistent_restore; then run miami_persistent_load; bootipq; fi'
}

ab_miami_label_identity() {
 local mac
 mac=$(get_mac_label_dt | tr -d ':' | tr 'A-F' 'a-f') || return 1
 case "$mac" in ''|*[!0-9a-f]*|000000000000|ffffffffffff|001122334455) return 1 ;; esac
 [ "${#mac}" = 12 ] && [ $((0x${mac%??????????} & 1)) = 0 ] || return 1
 [ "$mac" = "$(get_mac_label | tr -d ':' | tr 'A-F' 'a-f')" ]
}

ab_miami_storage_context() {
 local slot env
 ab_miami_label_identity || return 1
 slot=$(hexdump -v -e '1/1 "%02x"' "${AB_DT:-/proc/device-tree}/cambium-platform/storage-slot") || return 1
 [ "$slot" = "$(printf '%08x' "$AB_ACTIVE")" ] || return 1
 ab_mtd_writable "$AB_ACTIVE_MTD" || return 1
 if [ -e "${AB_DT:-/proc/device-tree}/cambium-platform/storage-policy" ]; then
  ab_miami_ab_profile && ab_mtd_writable "$AB_TARGET_MTD" || return 1
 else
  ! ab_mtd_writable "$AB_TARGET_MTD" || return 1
 fi
 env=$(ab_mtd_index 0:APPSBLENV) || return 1
 ab_mtd_writable "$env" || return 1
}

ab_miami_certificate_mount() {
 local cert
 cert=$(ab_ubi_volume "$AB_ACTIVE_UBI" certificates) || return 1
 [ "$(cat "${AB_UBI_SYS:-/sys/class/ubi}/$cert/reserved_ebs")" = 64 ] || return 1
 awk -v dev="${AB_DEV:-/dev}/$cert" -v named="$AB_ACTIVE_UBI:certificates" '
 $2=="/certificates" {n++;if(($1==dev||$1==named)&&$3=="ubifs"&&("," $4 ",")~/,rw,/)good++}
 index($2,"/certificates/")==1 {child++}
 END {exit !(n==1&&good==1&&!child)}' "${AB_PROC_MOUNTS:-/proc/mounts}"
}

# Confirm the existing OEM-retained guarded route after shared native
# acceptance. Do not manufacture dual-OpenWiFi conversion/confirmed state.
ab_miami_installer_confirmed_context() {
 local expected
 [ "$AB_ENV:$AB_FAMILY:$AB_MODEL" = miami:miami:X7-35X ] || return 1
 case "$AB_ACTIVE" in 0|1) ;; *) return 1 ;; esac
 command -v ab_converted >/dev/null 2>&1 || return 1
 [ -z "$(ab_getenv miami_ab_version)" ] || return 1
 ! ab_converted || return 1
 ab_miami_storage_context && ab_miami_certificate_mount || return 1
 [ "$(ab_getenv image)" = "$((1 - AB_ACTIVE))" ] &&
 [ "$(ab_getenv changing_bootcmd)" = 1 ] || return 1
 expected=$(ab_miami_guarded_command "$AB_ACTIVE") || return 1
 [ "$(ab_getenv bootcmd)" = "$expected" ]
}

ab_miami_healthy_extra() {
	local lan table gateway
	ab_miami_storage_context || return 1
	[ "$(cat "${CAMBIUM_BDF_STATUS:-/tmp/cambium-board-data.status}" 2>/dev/null)" = vault ] || return 1
	ab_miami_certificate_mount || return 1
	lan=$(lan_interface); table=$(lan_route_table "$lan") || return 1
	if [ "$table" = main ]; then
		gateway=$(ip -4 route show default dev "$lan" | awk '$1=="default"{print $3;exit}')
	else
		gateway=$(ip -4 route show table "$table" default dev "$lan" | awk '$1=="default"{print $3;exit}')
	fi
	[ -n "$gateway" ] && ping -I "$lan" -c 1 -W 2 "$gateway" >/dev/null 2>&1 || return 1
	if ab_miami_ab_profile; then
	 ab_miami_readiness_identity && ab_miami_native_connected || return 1
	fi
}

ab_miami_oem_return_ready() {
 local current guarded
 ab_miami_storage_context || return 1
 [ "$(ab_getenv image)" = "$((1 - AB_ACTIVE))" ] || return 1
 guarded=$(ab_miami_guarded_command "$AB_ACTIVE") || return 1
 current=$(ab_getenv bootcmd) || return 1
 [ "$current" = "$AB_STOCK_BOOTCMD" ] || [ "$current" = "$guarded" ]
}

# Check the existing native identity without importing/rebinding the completed
# journal or invoking enrollment/renewal. Only temporary public-key data is made.
ab_miami_readiness_identity() (
 local root=${AB_MIAMI_READINESS_ROOT:-} store work serial field file size fingerprint public_readonly
 store=$root/certificates
 [ -d "$store" ] && [ ! -L "$store" ] && [ "$(readlink -f "$store")" = "$store" ] || return 1
 [ -d "$store/.installer-import" ] && [ ! -L "$store/.installer-import" ] || return 1
 for file in "$store" "$store/.installer-import"; do
  LC_ALL=C ls -ldn "$file" | awk '$1=="drwx------" && $3==0 {good=1} END {exit !good}' || return 1
 done
 for field in key.pem cert.pem operational.pem operational.ca .installer-import/transaction.json .installer-import/completion.json; do
  file=$store/$field
  [ -f "$file" ] && [ ! -L "$file" ] || return 1
  public_readonly=0
  case "$field" in operational.pem|operational.ca) public_readonly=1 ;; esac
  LC_ALL=C ls -ldn "$file" | awk -v public_readonly="$public_readonly" '
   ($1=="-rw-------" || (public_readonly==1 && $1=="-r--r-----")) && $2==1 && $3==0 {good=1}
   END {exit !good}' || return 1
  size=$(wc -c < "$file") || return 1
  [ "$size" -gt 0 ] && [ "$size" -le 131072 ] || return 1
 done
 serial=$(get_mac_label_dt | tr -d ':' | tr 'A-F' 'a-f') || return 1
 [ "$(jsonfilter -i "$store/.installer-import/transaction.json" -e '@.accepted')" = true ] &&
 [ "$(jsonfilter -i "$store/.installer-import/transaction.json" -e '@.committed')" = true ] || return 1
 [ "$(jsonfilter -i "$store/.installer-import/completion.json" -e '@.binding.serial')" = "$serial" ] &&
  [ "$(jsonfilter -i "$store/.installer-import/completion.json" -e '@.binding.family')" = miami ] &&
  [ "$(jsonfilter -i "$store/.installer-import/completion.json" -e '@.binding.model')" = X7-35X ] || return 1
 command -v openssl >/dev/null 2>&1 || return 1
 umask 077
 work=$(mktemp -d "${AB_MIAMI_READINESS_TMP:-/tmp}/cambium-ab-readiness.XXXXXX") || return 1
 trap 'rm -rf "$work"' EXIT
 openssl pkey -in "$store/key.pem" -pubout -outform DER -out "$work/key-public" 2>/dev/null &&
  openssl x509 -in "$store/operational.pem" -pubkey -noout > "$work/leaf-public.pem" 2>/dev/null &&
  openssl pkey -pubin -in "$work/leaf-public.pem" -outform DER -out "$work/leaf-public" 2>/dev/null &&
  cmp -s "$work/key-public" "$work/leaf-public" || return 1
 fingerprint=$(sha256sum "$work/key-public" | cut -d ' ' -f1) || return 1
 [ "$fingerprint" = "$(jsonfilter -i "$store/.installer-import/completion.json" -e '@.binding.spki_sha256')" ] &&
  [ "$fingerprint" = "$(jsonfilter -i "$store/.installer-import/transaction.json" -e '@.spki')" ] || return 1
 [ "$(openssl x509 -in "$store/operational.pem" -subject -noout -nameopt RFC2253 2>/dev/null)" = "subject=CN=$serial" ] &&
  openssl x509 -in "$store/operational.pem" -checkend 0 -noout >/dev/null 2>&1 &&
  openssl verify -purpose sslclient -CAfile "$store/operational.ca" "$store/operational.pem" >/dev/null 2>&1
)

# Read-only callback for the common cambium-ab-ready command. The successful
# OEM-preserving pilot is onboarded; it is not a qualified A/B installation.
ab_miami_sysupgrade_readiness() {
 local root=${AB_MIAMI_READINESS_ROOT:-} state field status value received applied ru au boot
 AB_UPGRADE_READY=unsupported AB_UPGRADE_REASON=miami-identity-invalid
 ab_identity && ab_miami_label_identity && ab_miami_certificate_mount || return 0
 for field in target job image; do
  [ -z "$(ab_getenv "miami_installer_$field")" ] || {
   AB_UPGRADE_REASON=native-onboarding-pending; return 0
  }
 done
 [ ! -e "$root/root/.cambium-installer-settings" ] &&
  [ ! -L "$root/root/.cambium-installer-settings" ] || {
  AB_UPGRADE_REASON=native-seed-not-consumed; return 0
 }
 state=$root/certificates/.installer-import/transaction.json
 [ -f "$state" ] && [ ! -L "$state" ] &&
  [ "$(jsonfilter -i "$state" -e '@.accepted')" = true ] &&
  [ "$(jsonfilter -i "$state" -e '@.committed')" = true ] || {
  AB_UPGRADE_REASON=native-acceptance-unavailable; return 0
 }
 for field in key.pem cert.pem operational.pem operational.ca; do
  [ -f "$root/certificates/$field" ] && [ ! -L "$root/certificates/$field" ] || {
   AB_UPGRADE_REASON=native-identity-incomplete; return 0
  }
 done
 ab_miami_readiness_identity || { AB_UPGRADE_REASON=native-identity-invalid; return 0; }
 # Native status establishes authenticated transport and applied config.
 # No enrollment/renewal request, key creation or ENV write is made here.
 status=$(ubus -t 5 call ucentral status) || { AB_UPGRADE_REASON=native-disconnected; return 0; }
 for field in connected connection_generation config_received_sequence config_applied_sequence boot_report_transport; do
  value=$(printf '%s' "$status" | jsonfilter -e "@.$field") || value=
  case "$value" in ''|*[!0-9]*) AB_UPGRADE_REASON=native-status-invalid; return 0 ;; esac
  [ "$value" -gt 0 ] || { AB_UPGRADE_REASON=native-not-applied; return 0; }
 done
 received=$(printf '%s' "$status" | jsonfilter -e '@.config_received_sequence')
 applied=$(printf '%s' "$status" | jsonfilter -e '@.config_applied_sequence')
 ru=$(printf '%s' "$status" | jsonfilter -e '@.config_received_uuid')
 au=$(printf '%s' "$status" | jsonfilter -e '@.config_applied_uuid')
 [ "$received" = "$applied" ] && [ -n "$ru" ] && [ "$ru" = "$au" ] || {
  AB_UPGRADE_REASON=native-config-not-applied; return 0
 }
 AB_UPGRADE_READY=onboarded AB_UPGRADE_REASON=ab-profile-not-installed
 # Readiness cannot be manufactured from the pilot's one-shot boot alone.
 ab_hook upgrade_preflight || return 0
 [ "$AB_QUALIFIED" = 1 ] || { AB_UPGRADE_REASON=ab-qualification-pending; return 0; }
 ab_converted && [ "$(ab_getenv miami_ab_confirmed)" = "$AB_ACTIVE" ] || {
  AB_UPGRADE_REASON=ab-confirmation-pending; return 0
 }
 state=$(ab_getenv miami_ab_state); boot=$(ab_getenv bootcmd)
 case "$state:$boot" in
  "confirmed:run miami_stable$AB_ACTIVE"|"rolled-back:run miami_boot$AB_ACTIVE") ;;
  *) AB_UPGRADE_REASON=ab-confirmation-pending; return 0 ;;
 esac
 "ab_${AB_FAMILY}_upgrade_preflight" || { AB_UPGRADE_REASON=ab-preflight-failed; return 0; }
 AB_UPGRADE_READY=ready AB_UPGRADE_REASON=confirmed-native-ab
}

ab_miami_upgrade_geometry() {
 local sys=${AB_MTD_SYS:-/sys/class/mtd} n d name kind off size parent bank_parent env_parent env_idx
 local first second
 first=$sys/mtd$AB_MTD0; second=$sys/mtd$AB_MTD1
 [ "$AB_MTD0" != "$AB_MTD1" ] || return 1
 bank_parent=$(readlink -f "$first/device") || return 1
 [ -n "$bank_parent" ] && [ "$bank_parent" = "$(readlink -f "$second/device")" ] || return 1
 for n in "$AB_MTD0" "$AB_MTD1"; do
  d=$sys/mtd$n
  [ "$(cat "$d/type")" = nand ] && [ "$(cat "$d/size")" = 100663296 ] &&
   [ "$(cat "$d/erasesize")" = 131072 ] && [ "$(cat "$d/writesize")" = 2048 ] || return 1
 done
 [ "$(cat "$first/offset")" = 786432 ] && [ "$(cat "$second/offset")" = 101449728 ] || return 1
 env_idx=$(ab_mtd_index 0:APPSBLENV) || return 1
 case "$env_idx" in ''|*[!0-9]*) return 1 ;; esac
 d=$sys/mtd$env_idx
 env_parent=$(readlink -f "$d/device") || return 1
 [ -n "$env_parent" ] && [ "$env_parent" != "$bank_parent" ] &&
  [ "$(cat "$d/type")" = nor ] && [ "$(cat "$d/size")" = 65536 ] &&
  [ "$(cat "$d/offset")" = 2424832 ] && [ "$(cat "$d/erasesize")" = 65536 ] &&
  [ "$(cat "$d/writesize")" = 1 ] && ab_mtd_writable "$env_idx" || return 1
 for d in "$sys"/mtd[0-9]*; do
  n=${d##*/mtd}; case "$n" in ''|*[!0-9]*) continue ;; esac
  kind=$(cat "$d/type") || return 1
  [ "$kind" != ubi ] || continue
  case "$kind" in nand|nor) ;; *) return 1 ;; esac
  name=$(cat "$d/name") || return 1
  case "$name" in rootfs|rootfs_1|0:APPSBLENV) continue ;; esac
  case " $AB_PROTECTED " in *" $name "*) ;; *) return 1 ;; esac
  ! ab_mtd_writable "$n" || return 1
  off=$(cat "$d/offset") && size=$(cat "$d/size") || return 1
  case "$off:$size" in ''|*[!0-9:]*) return 1 ;; esac
  [ "$size" -gt 0 ] || return 1
  parent=$(readlink -f "$d/device") || return 1
  case "$parent" in
   "$bank_parent") [ "$kind" = nand ] && { [ "$((off+size))" -le 786432 ] || [ "$off" -ge 202113024 ]; } || return 1 ;;
   "$env_parent") [ "$kind" = nor ] && { [ "$((off+size))" -le 2424832 ] || [ "$off" -ge 2490368 ]; } || return 1 ;;
   *) return 1 ;;
  esac
  case "$name" in
   0:ART) [ "$kind:$off:$size" = nor:3145728:1048576 ] || return 1 ;;
   mfginfo) [ "$kind:$off:$size" = nor:4194304:65536 ] || return 1 ;;
  esac
 done
}


ab_miami_upgrade_preflight() {
 ab_miami_ab_profile && ab_miami_storage_context && ab_miami_upgrade_geometry || return 1
 # Never admit the old OEM-retained profile, a RAM bridge without a sealed
 # source ticket, or an unconfirmed source as an ordinary sysupgrade.
 if [ -e "${AB_DT:-/proc/device-tree}/cambium-platform/boot-mode" ]; then
  command -v ab_miami_bridge_validate >/dev/null || return 1
  ab_miami_bridge_validate
  return $?
 fi
 if ab_miami_certificate_mount; then
  ab_miami_readiness_identity || return 1
 else
  ab_miami_snapshot_identity || return 1
 fi
 if ! ab_converted; then
  ab_miami_seed_context || return 1
  AB_MIAMI_FIRST_UPGRADE_VALIDATED=seed
  return 0
 fi
 [ "$(ab_getenv miami_ab_confirmed)" = "$AB_ACTIVE" ] || return 1
 case "$(ab_getenv miami_ab_state)" in confirmed|rolled-back|write-failed) ;; *) return 1 ;; esac
}

ab_miami_check_kernel() {
 local magic
 ab_miami_ab_profile || return 1
 [ "$AB_IMAGE_DIR" = "sysupgrade-cambiumnetworks_miami-ab-slot$AB_TARGET" ] &&
 [ "$AB_FIT" = "config@mi01.6-acadia-ab-slot$AB_TARGET" ] || return 1
 magic=$(hexdump -n 4 -v -e '4/1 "%02x"' "$1") || return 1
 [ "$magic" = d00dfeed ] || return 1
 tr '\000' '\n' < "$1" | grep -q "^$(printf '\001')$AB_FIT\$" || return 1
 AB_MIAMI_IMAGE_TARGET=$AB_TARGET
}

ab_miami_native_connected() {
 local status connected received applied received_uuid applied_uuid generation transport
 status=$(ubus -t 5 call ucentral status) || return 1
 connected=$(printf '%s' "$status" | jsonfilter -e '@.connected') || return 1
 received=$(printf '%s' "$status" | jsonfilter -e '@.config_received_sequence') || return 1
 applied=$(printf '%s' "$status" | jsonfilter -e '@.config_applied_sequence') || return 1
 received_uuid=$(printf '%s' "$status" | jsonfilter -e '@.config_received_uuid') || return 1
 applied_uuid=$(printf '%s' "$status" | jsonfilter -e '@.config_applied_uuid') || return 1
 generation=$(printf '%s' "$status" | jsonfilter -e '@.connection_generation') || return 1
 transport=$(printf '%s' "$status" | jsonfilter -e '@.boot_report_transport') || return 1
 for value in "$connected" "$received" "$applied" "$generation" "$transport"; do
  case "$value" in ''|*[!0-9]*) return 1 ;; esac
  [ "$value" -gt 0 ] || return 1
 done
 [ "$received" = "$applied" ] && [ -n "$received_uuid" ] && [ "$received_uuid" = "$applied_uuid" ]
}

# These callbacks grant no admission to persistent pilot kernels. The shared
# writer invokes upgrade_written only after image/vault/cert readbacks pass.
ab_miami_first_upgrade() {
 if [ "${AB_MIAMI_FIRST_UPGRADE_VALIDATED:-}" = seed ]; then
  ab_miami_seed_context
  return $?
 fi
 [ "${AB_MIAMI_BRIDGE_VALIDATED:-}" = 1 ] &&
 command -v ab_miami_bridge_validate >/dev/null && ab_miami_bridge_validate
}
ab_miami_upgrade_written() {
 ab_converted && return 0
 [ "$(ab_getenv miami_ab_state)" = writing ] || return 1
 if [ "${AB_MIAMI_FIRST_UPGRADE_VALIDATED:-}" = seed ]; then
  ab_miami_seed_context && ab_setenv miami_ab_version 1
 else
  [ "${AB_MIAMI_BRIDGE_VALIDATED:-}" = 1 ] &&
   ab_setenv miami_ab_version 1 && ab_setenv miami_bridge_state written
 fi
}

# After the normal RAM pivot /certificates remains under the old root. The
# pre-pivot export is authoritative: validate its unchanged same-boot binding
# and accepted identity, without importing or rebinding the birth journal.
ab_miami_snapshot_identity() (
 local work
 [ "$(awk '$2=="/" {print $3;exit}' "${AB_PROC_MOUNTS:-/proc/mounts}")" = tmpfs ] || return 1
 ab_certificate_validate_snapshot || return 1
 umask 077
 work=$(mktemp -d /tmp/miami-ab-identity.XXXXXX) || return 1
 trap 'rm -rf "$work"' EXIT
 mkdir "$work/certificates" || return 1
 tar xf "$AB_CERTIFICATE_ARCHIVE" -C "$work/certificates" || return 1
 AB_MIAMI_READINESS_ROOT=$work
 ab_miami_readiness_identity
)

# Revalidate the sealed source after persistence/journaling, immediately before
# the shared writer can detach/format the inactive bank.
ab_miami_before_target_write() {
 if [ -e "${AB_DT:-/proc/device-tree}/cambium-platform/boot-mode" ]; then
  command -v ab_miami_bridge_validate >/dev/null && ab_miami_bridge_validate
 else
  ab_miami_upgrade_geometry && ab_miami_snapshot_identity &&
   { ab_converted || ab_miami_seed_context; }
 fi
}

# The OEM-installed seed is a normal persistent A/B kernel. Only its explicit
# healthy confirmation can admit replacing the remaining OEM peer. No old
# boot-ID hook, replacement key or premature converted marker is involved.
ab_miami_seed_context() {
 local boot
 [ "$AB_FAMILY:$AB_MODEL:$AB_SKU" = miami:X7-35X:0000002c ] || return 1
 ab_miami_ab_profile && [ ! -e "${AB_DT:-/proc/device-tree}/cambium-platform/boot-mode" ] || return 1
 [ -z "$(ab_getenv miami_ab_version)" ] &&
 [ "$(ab_getenv miami_ab_confirmed)" = "$AB_ACTIVE" ] || return 1
 case "$(ab_getenv miami_ab_state)" in confirmed|writing) ;; *) return 1;;esac
 boot=$(cat "${AB_BOOT_ID:-/proc/sys/kernel/random/boot_id}") || return 1
 [ "${#boot}" = 36 ] && [ "$(ab_getenv miami_ab_seed_boot_id)" = "$boot" ] || return 1
 [ "$(ab_getenv miami_boot$AB_ACTIVE)" = "$(ab_miami_slot_command "$AB_ACTIVE" ab)" ] &&
 [ "$(ab_getenv bootcmd)" = "run miami_boot$AB_ACTIVE" ] &&
 [ "$(ab_getenv image)" = "$AB_ACTIVE" ]
}
