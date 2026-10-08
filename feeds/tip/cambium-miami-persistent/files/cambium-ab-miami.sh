#!/bin/sh
# OEM-preserving X7-35X storage pilot. No dual-bank conversion admission.
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
	AB_PROTECTED='0:NVRAM crashLog 0:ART mfginfo 0:SBL1 0:SBL1_1 0:APPSBL 0:APPSBL_1'
}

ab_miami_boot_command() {
	local part offset
	case "$1" in 0) part=rootfs; offset=$AB_SLOT0_OFFSET ;; 1) part=rootfs_1; offset=$AB_SLOT1_OFFSET ;; *) return 1 ;; esac
	printf "nand device 0 && setenv mtdids nand0=nand0 && setenv mtdparts 'mtdparts=nand0:0x6000000@%s(fs)' && ubi part fs && ubi read 0x60000000 kernel && setenv bootargs console=ttyMSM0,115200n8 ubi.mtd=%s root=/dev/ubiblock0_1 rootfstype=squashfs rootwait && bootm 0x60000000#config@mi01.6-acadia-slot%s\n" "$offset" "$part" "$1"
}

ab_miami_guarded_command() {
	local command restore
	command=$(ab_miami_boot_command "$1") || return 1
	restore='setenv bootcmd bootipq && setenv changing_bootcmd && saveenv'
	[ "$(ab_getenv miami_persistent_restore)" = "$restore" ] || return 1
	[ "$(ab_getenv miami_persistent_load)" = "$command; reset" ] || return 1
	[ "$(ab_getenv miami_persistent_slot)" = "$1" ] || return 1
	echo 'run miami_persistent_restore && run miami_persistent_load || bootipq'
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
 ! ab_mtd_writable "$AB_TARGET_MTD" || return 1
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
	[ -n "$gateway" ] && ping -I "$lan" -c 1 -W 2 "$gateway" >/dev/null 2>&1
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
 local root=${AB_MIAMI_READINESS_ROOT:-} store work serial field file size fingerprint
 store=$root/certificates
 [ -d "$store" ] && [ ! -L "$store" ] && [ "$(readlink -f "$store")" = "$store" ] || return 1
 [ -d "$store/.installer-import" ] && [ ! -L "$store/.installer-import" ] || return 1
 for file in "$store" "$store/.installer-import"; do
  LC_ALL=C ls -ldn "$file" | awk '$1=="drwx------" && $3==0 {good=1} END {exit !good}' || return 1
 done
 for field in key.pem cert.pem operational.pem operational.ca .installer-import/transaction.json .installer-import/completion.json; do
  file=$store/$field
  [ -f "$file" ] && [ ! -L "$file" ] || return 1
  LC_ALL=C ls -ldn "$file" | awk '$1=="-rw-------" && $2==1 && $3==0 {good=1} END {exit !good}' || return 1
  size=$(wc -c < "$file") || return 1
  [ "$size" -gt 0 ] && [ "$size" -le 131072 ] || return 1
 done
 serial=$(get_mac_label_dt | tr -d ':' | tr 'A-F' 'a-f') || return 1
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
