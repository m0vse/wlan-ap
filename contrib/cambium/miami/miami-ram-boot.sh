#!/bin/sh
# Prepare a one-shot TFTP boot from OEM or stock OpenWrt. Default is read-only.
# --arm writes ONLY the boot environment; neither NAND bank is written.
set -eu
umask 077
mode=${1:-}; shift || true
case "$mode" in prepare|arm|cleanup) ;; *) echo 'usage: miami-ram-boot.sh prepare SERVER_IP AP_IP FILENAME SHA256 | arm --yes --backed-up | cleanup --yes' >&2; exit 2 ;; esac
DIR=${MIAMI_RAM_BOOT_WORK:-/tmp/miami-ram-boot}
fail() { echo "miami-ram-boot: $*" >&2; exit 1; }
get() { fw_printenv -n "$1" 2>/dev/null; }
put() { fw_setenv "$1" "$2"; [ "$(get "$1")" = "$2" ] || fail "environment readback failed: $1"; }
remove() { fw_setenv "$1"; ! get "$1" >/dev/null || fail "environment deletion failed: $1"; }
quote_value() { case "$1" in *"'"*|*'
'*) fail 'single quotes/newlines in saved environment are unsupported; no changes made' ;; esac; }
board_check() {
 node=${MIAMI_RAM_SKU_NODE:-/proc/device-tree/cambium-platform/board-sku}
 sku=
 if [ -r "$node" ]; then
  hex=$(od -An -tx1 "$node" 2>/dev/null | tr -d ' \n')
  [ -n "$hex" ] || hex=$(hexdump -v -e '1/1 "%02x"' "$node" 2>/dev/null)
  [ -z "$hex" ] || sku=$(printf '%d' "0x$hex")
 elif [ -r /proc/sku ]; then sku=$(tr -dc '0-9' </proc/sku); fi
 [ "$sku" = 44 ] || fail 'requires exact X7-35X / SKU44'
}
board_check
command -v fw_printenv >/dev/null || fail 'fw_printenv missing'
case "$mode" in
prepare)
 [ "$#" = 4 ] || fail 'prepare needs SERVER_IP AP_IP FILENAME SHA256'
 server=$1 address=$2 file=$3 hash=$4
 for ip in "$server" "$address"; do
  printf '%s\n' "$ip" | awk -F. 'NF!=4{exit 1}{for(i=1;i<=4;i++)if($i!~/^[0-9]+$/ || $i>255)exit 1}' || fail 'invalid IPv4 address'
 done
 case "$file" in ''|*[!A-Za-z0-9._-]*) fail 'filename must be a simple TFTP basename' ;; esac
 [ "${#hash}" = 64 ] || fail 'expected SHA256 length'
 case "$hash" in *[!0-9a-f]*) fail 'invalid SHA256' ;; esac
 for key in miami_ram_restore miami_ram_load; do ! get "$key" >/dev/null || fail 'old test variables exist; clean up before preparing'; done
 [ ! -e "$DIR" ] || fail "working directory exists: $DIR (retain its backup)"
 mkdir -m 700 "$DIR"
 old=$(get bootcmd) || fail 'cannot read bootcmd'
 [ -n "$old" ] || fail 'empty bootcmd'
 quote_value "$old"
 printf '%s\n' "$old" > "$DIR/bootcmd.before"
 restore="setenv bootcmd '$old'"
 if changing=$(get changing_bootcmd); then
  quote_value "$changing"
  printf '%s\n' "$changing" > "$DIR/changing.before"
  restore="$restore; setenv changing_bootcmd '$changing'"
 else restore="$restore; setenv changing_bootcmd"; fi
 restore="$restore; saveenv"
 printf '%s\n' "$restore" > "$DIR/restore"
 # All network/bootargs changes happen AFTER saveenv and remain volatile.
 load="setenv ipaddr $address; setenv serverip $server; setenv netretry no; setenv bootargs console=ttyMSM0,115200n8; tftpboot 0x60000000 $file && bootm 0x60000000#config@mi01.6-acadia; reset"
 printf '%s\n' "$load" > "$DIR/load"
 printf '%s\n' "$hash" > "$DIR/expected-image.sha256"
 # Raw environment backup is read-only; nothing contains calibration payloads.
 loader=$(sed -n 's/^mtd\([0-9]*\):.*"0:APPSBL"$/\1/p' /proc/mtd)
 [ -n "$loader" ] || fail 'cannot identify the U-Boot partition'
 dd if="/dev/mtd${loader}ro" bs=65536 count=10 2>/dev/null | strings | grep -qx tftpboot ||
  fail 'tftpboot was not found in this U-Boot image; do not arm this route'
 number=$(sed -n 's/^mtd\([0-9]*\):.*"0:APPSBLENV"$/\1/p' /proc/mtd)
 [ -n "$number" ] || fail 'cannot identify 0:APPSBLENV for backup'
 dd if="/dev/mtd${number}ro" of="$DIR/APPSBLENV.bin" bs=65536 count=1 2>/dev/null || fail 'environment backup failed'
 [ "$(wc -c < "$DIR/APPSBLENV.bin")" -eq 65536 ] || fail 'unexpected environment partition size'
 (cd "$DIR" && sha256sum APPSBLENV.bin > SHA256SUMS)
 echo "Prepared $DIR. No flash was changed. Copy the entire directory off-device before arm."
 echo 'Check the TFTP file against expected-image.sha256. This test loader is not hardware-qualified.'
 ;;
arm)
 [ "$*" = '--yes --backed-up' ] || fail 'arm requires --yes --backed-up after copying the backup off-device'
 command -v fw_setenv >/dev/null || fail 'fw_setenv missing'
 for f in restore load bootcmd.before APPSBLENV.bin; do [ -s "$DIR/$f" ] || fail "missing prepared file: $f"; done
 [ "$(get bootcmd)" = "$(cat "$DIR/bootcmd.before")" ] || fail 'bootcmd changed since prepare'
 if [ -e "$DIR/changing.before" ]; then
  [ "$(get changing_bootcmd)" = "$(cat "$DIR/changing.before")" ] || fail 'changing_bootcmd changed since prepare'
 else ! get changing_bootcmd >/dev/null || fail 'changing_bootcmd appeared since prepare'; fi
 armed=0
 rollback() {
  [ "$armed" = 1 ] && return 0
  fw_setenv bootcmd "$(cat "$DIR/bootcmd.before")" || echo 'bootcmd rollback failed; retain backup and do not reboot' >&2
  if [ -e "$DIR/changing.before" ]; then fw_setenv changing_bootcmd "$(cat "$DIR/changing.before")"; else fw_setenv changing_bootcmd; fi
 }
 trap rollback EXIT
 # Arm last. A failure while writing helper variables leaves bootcmd intact.
 put miami_ram_restore "$(cat "$DIR/restore")"
 put miami_ram_load "$(cat "$DIR/load")"
 put changing_bootcmd 1
 put bootcmd 'run miami_ram_restore && run miami_ram_load; reset'
 armed=1
 trap - EXIT
 sync
 echo 'One-shot armed. Boot environment was changed; neither firmware bank was touched.'
 echo 'The previous boot command is restored and saved BEFORE TFTP. Reboot manually with serial logging active.'
 ;;
cleanup)
 [ "$*" = '--yes' ] || fail 'cleanup requires --yes'
 [ -s "$DIR/bootcmd.before" ] || fail 'restore the saved working directory to /tmp first'
 [ "$(get bootcmd)" = "$(cat "$DIR/bootcmd.before")" ] || fail 'previous bootcmd has not been restored; retain backup'
 for key in miami_ram_restore miami_ram_load; do if get "$key" >/dev/null; then remove "$key"; fi; done
 sync
 echo 'Test helper variables removed. Neither firmware bank was touched.'
 ;;
esac
