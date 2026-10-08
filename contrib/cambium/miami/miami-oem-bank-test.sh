#!/bin/sh
# Exact X7-35X OEM -> private OpenWiFi one-shot bank-backed RAM test.
# Never erases/formats a bank or removes an existing UBI volume.
set -eu
umask 077
mode=${1:-}; shift || true
case "$mode" in check|backup|upload|stage|arm|cleanup) ;; *) echo 'usage: miami-oem-bank-test.sh check | backup | upload http://SERVER:8000 | stage IMAGE auto|low --yes --backed-up | arm auto|low --yes | cleanup --yes' >&2; exit 2 ;; esac
fail() { echo "miami-bank-test: $*" >&2; exit 1; }
get() { value=$(fw_printenv "$1" 2>/dev/null) || return 1; case "$value" in "$1="*) printf '%s\n' "${value#*=}" ;; *) return 1;; esac; }
put() { fw_setenv "$1" "$2"; [ "$(get "$1")" = "$2" ] || fail "environment readback failed: $1"; }
remove() { fw_setenv "$1"; ! get "$1" >/dev/null || fail "environment deletion failed: $1"; }
quote() { case "$1" in *"'"*|*'
'*) fail 'unsupported single quote/newline in environment';; esac; }
# Internal fixture root; production always uses the actual filesystem.
R=${MIAMI_BANK_TEST_ROOT:-}
mtd() { for d in "$R"/sys/class/mtd/mtd*; do [ -f "$d/name" ] || continue; [ "$(cat "$d/name")" = "$1" ] && { echo "${d##*/mtd}"; return; }; done; return 1; }
[ ! -f "$R/etc/openwrt_release" ] || fail 'run from OEM, not OpenWrt; return using cambium-ab-stock first'
for tool in fw_printenv sha256sum dd; do command -v "$tool" >/dev/null || fail "missing $tool"; done
sku=
if [ -r "$R/proc/device-tree/cambium-platform/board-sku" ]; then
 hex=$(od -An -tx1 "$R/proc/device-tree/cambium-platform/board-sku" | tr -d ' \n'); sku=$(printf '%d' "0x$hex")
elif [ -r "$R/proc/sku" ]; then sku=$(tr -dc '0-9' < "$R/proc/sku"); fi
[ "$sku" = 44 ] || fail 'requires X7-35X / SKU44'
run=$(sed -n 's/.*ubi\.mtd=\([^ ]*\).*/\1/p' "$R/proc/cmdline")
img=$(get image) || fail 'missing OEM image selector'
case "$run:$img" in
 rootfs:0) OEM=rootfs TARGET=rootfs_1 SLOT=1 OFFSET=0x60c0000 ;;
 rootfs_1:1) OEM=rootfs_1 TARGET=rootfs SLOT=0 OFFSET=0xc0000 ;;
 *) fail "OEM cmdline bank '$run' and image '$img' disagree" ;;
esac
T=$(mtd "$TARGET") || fail 'target bank missing'
O=$(mtd "$OEM") || fail 'OEM bank missing'
E=$(mtd 0:APPSBLENV) || fail 'environment missing'
for n in "$T" "$O"; do [ "$(cat "$R/sys/class/mtd/mtd$n/size")" = 100663296 ] || fail 'bank is not 96 MiB'; done
[ "$(cat "$R/sys/class/mtd/mtd$E/size")" = 65536 ] || fail 'unexpected environment size'
for spec in "$T:$OFFSET:$TARGET" "$O:$([ "$OEM" = rootfs ] && echo 0xc0000 || echo 0x60c0000):$OEM"; do
 n=${spec%%:*}; rest=${spec#*:}; off=${rest%%:*}; name=${rest#*:}
 if [ -r "$R/sys/class/mtd/mtd$n/offset" ]; then
  [ "$(cat "$R/sys/class/mtd/mtd$n/offset")" = "$((off))" ] || fail 'bank offset differs'
 else
  bounds=$(printf '0x%012x-0x%012x : "%s"' "$((off))" "$((off+100663296))" "$name")
  dmesg | grep -F "$bounds" >/dev/null || fail "cannot confirm offset for $name from sysfs/dmesg"
 fi
done
[ "$(get bootcmd)" = bootipq ] || fail 'bootcmd is not idle bootipq'
! get changing_bootcmd >/dev/null || [ -z "$(get changing_bootcmd)" ] || fail 'boot change already pending'
config=
for c in "$R/tmp/fw_env.config" "$R/etc/fw_env.config"; do [ ! -f "$c" ] || { config=$c; break; }; done
[ -n "$config" ] || fail 'no fw_env.config'
awk -v m="/dev/mtd$E" '!/^#/ && NF {if($1!=m && $1!=m "ro")bad=1;n++} END{exit(bad || n!=1)}' "$config" || fail 'fw_env.config does not select only APPSBLENV'
# Captured OEM fwtools may use /tmp config instead of /etc. Verify actual access.
command -v strace >/dev/null || fail 'strace missing; cannot verify OEM environment device access'
trace=$(mktemp "$R/tmp/miami-bank-env.XXXXXX")
strace -f -e trace=open,openat -o "$trace" fw_printenv bootcmd >/dev/null 2>&1 || fail 'environment access trace failed'
grep -F "\"${config#$R}\"" "$trace" >/dev/null || fail 'fwtool is not using the inspected config'
{ grep -F "\"/dev/mtd$E\"" "$trace" >/dev/null || grep -F "\"/dev/mtd${E}ro\"" "$trace" >/dev/null; } || fail 'fwtool did not open APPSBLENV'
grep -oE '"/dev/mtd[0-9]+(ro)?"' "$trace" | while read -r device; do
 case "$device" in "\"/dev/mtd$E\""|"\"/dev/mtd${E}ro\"") ;; *) fail 'fwtool opened an unexpected MTD device';; esac
done
rm -f "$trace"
DIR="$R/tmp/miami-bank-test-backup"
VOL=miami_openwifi_trial
owned=0 UBI=
release() { if [ "$owned" = 1 ]; then ubidetach -m "$T" >/dev/null 2>&1 || echo 'target UBI detach failed' >&2; fi; }
trap release EXIT
find_ubi() { UBI=; count=0; for d in "$R"/sys/class/ubi/ubi[0-9]*; do [ -f "$d/mtd_num" ] || continue; [ "$(cat "$d/mtd_num")" != "$T" ] || { UBI=${d##*/}; count=$((count+1)); }; done; [ "$count" -le 1 ] || fail 'multiple UBI devices for target'; }
volume() { found=; count=0; for d in "$R/sys/class/ubi/$UBI"_[0-9]*; do [ -f "$d/name" ] || continue; [ "$(cat "$d/name")" != "$1" ] || { found=${d##*/}; count=$((count+1)); }; done; [ "$count" -le 1 ] || fail 'duplicate volume name'; [ -n "$found" ] || return 1; echo "$found"; }
busy() {
 # Refuse active mappings, including aliases/UBIFS name forms, without unmounting.
 for table in "$R/proc/mounts" "$R/proc/self/mountinfo"; do
  [ -r "$table" ] || continue
  grep -E "(^|[[:space:]/])${UBI}([_:]|[[:space:]])|(^|[[:space:]/])ubiblock${UBI#ubi}_|(^|[[:space:]:])(rootfs_data|cambium_device_data|miami_openwifi_trial)([[:space:]]|$)" "$table" >/dev/null && fail 'target or ambiguous target volume is mounted'
 done
 for d in "$R"/sys/class/block/ubiblock*; do [ ! -e "$d" ] || case "${d##*/}" in ubiblock${UBI#ubi}_*) fail 'target has a block-device mapping';; esac; done
 for fd in "$R"/proc/[0-9]*/fd/*; do
  [ -L "$fd" ] || continue
  path=$(readlink "$fd" 2>/dev/null || true)
  case "$path" in /dev/$UBI|/dev/${UBI}_*|/dev/mtd$T|/dev/mtd${T}ro) fail 'target has an open userspace device';; esac
 done
}
attach() {
 for tool in ubiattach ubidetach; do command -v "$tool" >/dev/null || fail "missing $tool"; done
 find_ubi
 if [ -z "$UBI" ]; then ubiattach "$R/dev/ubi_ctrl" -m "$T" >/dev/null; owned=1; find_ubi; fi
 [ -n "$UBI" ] || fail 'target did not attach'
 busy
 for name in kernel rootfs rootfs_data cambium_device_data; do volume "$name" >/dev/null || fail "target is not the existing OpenWrt/vault bank: missing $name"; done
 volume ubi_rootfs >/dev/null && fail 'target contains OEM ubi_rootfs; refusing'
 [ "$(cat "$R/sys/class/ubi/$UBI/ro_mode")" = 0 ] || fail 'target UBI is read-only'
}
profile() {
 case "$1" in
 auto) HASH=389d3dc6a9ec11f363bee2619569874488752b557a27475369f6759da569a837 SIZE=26302672 ;;
 low) HASH=61b906024bc1bfd99bd20db738d363f12872096a411ab705aca40e3816e89c60 SIZE=26340776 ;;
 *) fail 'profile must be auto or low';;
 esac
}
readback() { v=$(volume "$VOL") || fail 'test volume missing'; [ "$(head -c "$SIZE" "$R/dev/$v" | sha256sum | cut -d ' ' -f1)" = "$HASH" ] || fail 'staged FIT readback differs'; }
echo "OEM preserved: $OEM (mtd$O, image=$img); test target: $TARGET (mtd$T, slot=$SLOT)"
upload_backups() {
 base=$1
 case "$base" in http://*|https://*) ;; *) fail 'upload needs an HTTP(S) cambium-serve.py URL';; esac
 [ -f "$DIR/SHA256SUMS" ] || fail 'run backup first'
 (cd "$DIR" && sha256sum -c SHA256SUMS >/dev/null) || fail 'backup checksums differ'
 # Match cambium-install.sh: BusyBox wget cannot POST raw data containing NULs.
 if command -v wget >/dev/null && wget --help 2>&1 | grep -q -- '--post-file'; then method=wget
 elif command -v curl >/dev/null; then method=curl
 else fail 'backup upload requires wget --post-file or curl'; fi
 if [ ! -f "$DIR/upload-prefix" ]; then printf 'miami-openwifi-bank%s-%s\n' "$SLOT" "$(date -u +%Y%m%dT%H%M%SZ)" > "$DIR/upload-prefix"; fi
 prefix=$(cat "$DIR/upload-prefix")
 case "$prefix" in ''|*[!A-Za-z0-9._-]*) fail 'invalid backup upload prefix';; esac
 awk -v p="$prefix-" '{print $1 "  " p $2}' "$DIR/SHA256SUMS" > "$DIR/server-SHA256SUMS"
 for name in target-bank.bin APPSBLENV.bin environment.txt target SHA256SUMS; do
  file="$DIR/$name"; [ "$name" != SHA256SUMS ] || file="$DIR/server-SHA256SUMS"
  url=${base%/}/upload/$prefix-$name
  echo "Uploading $name to cambium-serve.py"
  if [ "$method" = curl ]; then
   got=$(curl -sS -f -T "$file" "$url") || fail "upload failed: $name"
  else
   size=$(wc -c < "$file"); off=0; chunk=262144
   while [ "$off" -lt "$size" ]; do
    dd if="$file" of="$DIR/chunk" bs="$chunk" skip=$((off/chunk)) count=1 2>/dev/null
    if command -v hexdump >/dev/null; then hexdump -v -e '1/1 "%02x"' "$DIR/chunk" > "$DIR/chunk.hex"
    else od -An -v -tx1 "$DIR/chunk" > "$DIR/chunk.hex"; fi
    got=$(wget -q -O - --post-file "$DIR/chunk.hex" "$url?offset=$off") || fail "chunk upload failed: $name at $off"
    want=$(sha256sum "$DIR/chunk" | cut -d ' ' -f1)
    [ "${got%% *}" = "$want" ] || fail "uploaded chunk checksum differs: $name at $off"
    off=$((off+chunk))
   done
   got=$(wget -q -O - --post-data done "$url?done") || fail "upload completion failed: $name"
  fi
  want=$(sha256sum "$file" | cut -d ' ' -f1)
  [ "${got%% *}" = "$want" ] || fail "uploaded whole-file checksum differs: $name"
 done
 rm -f "$DIR/chunk" "$DIR/chunk.hex"
 cp "$DIR/SHA256SUMS" "$DIR/uploaded"
 echo "Backups received in uploads/$prefix-*; every chunk/file checksum verified. No flash changed."
 echo "On the Mac: cd ~/Downloads/uploads && shasum -a 256 -c $prefix-SHA256SUMS"
}
case "$mode" in
upload)
 [ "$#" = 1 ] || fail 'upload requires cambium-serve.py base URL'
 upload_backups "$1" ;;
cleanup)
 [ "$#" = 1 ] && [ "$1" = --yes ] || fail 'cleanup requires --yes'
 command -v fw_setenv >/dev/null || fail 'missing fw_setenv'
 for key in miami_bank_restore miami_bank_load; do if get "$key" >/dev/null; then remove "$key"; fi; done
 sync; echo 'Test helper keys removed. Staged volume and all existing volumes preserved.' ;;
check)
 [ "$#" = 0 ] || fail 'check takes no arguments'
 echo 'Read-only checks passed; no attach, flash write or reboot.' ;;
backup)
 [ "$#" = 0 ] || fail 'backup takes no arguments'
 [ ! -e "$DIR" ] || fail 'backup directory already exists; retain/copy it before retry'
 mkdir -m 700 "$DIR"
 printf '%s\n' "$TARGET" > "$DIR/target"
 dd if="$R/dev/mtd${T}ro" of="$DIR/target-bank.bin" bs=131072 2>/dev/null
 dd if="$R/dev/mtd${E}ro" of="$DIR/APPSBLENV.bin" bs=65536 count=1 2>/dev/null
 [ "$(wc -c < "$DIR/target-bank.bin")" -eq 100663296 ] || fail 'short bank backup'
 [ "$(wc -c < "$DIR/APPSBLENV.bin")" -eq 65536 ] || fail 'short environment backup'
 fw_printenv > "$DIR/environment.txt"
 (cd "$DIR" && sha256sum target-bank.bin APPSBLENV.bin environment.txt target > SHA256SUMS)
 echo "Backed up to $DIR; copy all files off-device and verify SHA256SUMS before stage." ;;
stage)
 [ "$#" = 4 ] && [ "$3 $4" = '--yes --backed-up' ] || fail 'stage needs IMAGE auto|low --yes --backed-up'
 file=$1; profile "$2"
 [ -f "$file" ] && [ "$(wc -c < "$file")" -eq "$SIZE" ] || fail 'image size differs'
 [ "$(sha256sum "$file" | cut -d ' ' -f1)" = "$HASH" ] || fail 'image checksum differs'
 if [ -f "$DIR/SHA256SUMS" ]; then
  [ "$(cat "$DIR/target")" = "$TARGET" ] || fail 'local backup is for another target'
  (cd "$DIR" && sha256sum -c SHA256SUMS >/dev/null) || fail 'backup checksums differ'
 else
  echo 'Using --backed-up confirmation of your existing off-device backup; /tmp backup is absent after reboot.'
 fi
 command -v ubiupdatevol >/dev/null || fail 'missing ubiupdatevol'
 command -v ubimkvol >/dev/null || fail 'missing ubimkvol'
 attach
 if v=$(volume "$VOL"); then
  # The name alone does not establish ownership: accept only one of our pinned FITs.
  known=0
  for spec in 26302672:389d3dc6a9ec11f363bee2619569874488752b557a27475369f6759da569a837 26296344:2228cdc7bf9eb57a516daa4bac7d9a045b9e820f7e83bdbccdb2a917e6622d92 26337136:b7b83f812cf85813e5e3ae9ac530733df9352c5a84663cabab0e57d3507ee879 26340776:61b906024bc1bfd99bd20db738d363f12872096a411ab705aca40e3816e89c60 26343696:9616e310f9e9c50e82ded4593eb9f6c6b3b5af6384d7d35a2433ae1af5ab6147 26346008:31592ddab77c84c331c76fe3cbaf7520eb11ac8c470b22513be86696569185ff; do
   length=${spec%%:*}; want=${spec#*:}
   [ "$(head -c "$length" "$R/dev/$v" | sha256sum | cut -d ' ' -f1)" != "$want" ] || known=1
  done
  [ "$known" = 1 ] || fail 'existing test volume contains unknown data; not overwriting'
  [ "$(cat "$R/sys/class/ubi/$v/data_bytes")" -ge "$SIZE" ] || fail 'existing test volume too small; no volumes will be removed'
 else
  leb=$(cat "$R/sys/class/ubi/$UBI/eraseblock_size"); free=$(cat "$R/sys/class/ubi/$UBI/avail_eraseblocks")
  [ "$free" -ge "$(( (26346008+leb-1)/leb ))" ] || fail 'not enough free space; no existing volumes will be removed'
  busy
  ubimkvol "$R/dev/$UBI" -N "$VOL" -s 26346008 >/dev/null
  v=$(volume "$VOL") || fail 'test volume creation failed'
 fi
 busy
 ubiupdatevol "$R/dev/$v" "$file"; sync; readback
 echo 'FIT staged and read back. Existing kernel/rootfs/settings/vault preserved. Not armed; no reboot.' ;;
arm)
 [ "$#" = 2 ] && [ "$2" = --yes ] || fail 'arm needs auto|low --yes'
 profile "$1"; command -v fw_setenv >/dev/null || fail 'missing fw_setenv'
 attach; readback; release; owned=0
 for key in miami_bank_restore miami_bank_load; do ! get "$key" >/dev/null || fail 'old bank-test helpers exist; inspect/clean before rearming'; done
 restore='setenv bootcmd bootipq; setenv changing_bootcmd; saveenv'
 load="nand device 0 && setenv mtdids nand0=nand0 && setenv mtdparts 'mtdparts=nand0:0x6000000@$OFFSET(fs)' && ubi part fs && ubi read 0x60000000 $VOL $(printf '0x%x' "$SIZE") && setenv bootargs console=ttyMSM0,115200n8 && bootm 0x60000000#config@mi01.6-acadia; reset"
 # No save occurs after changing mtdparts/bootargs. OEM defaults stay saved.
 armed=0
 rollback() { release; [ "$armed" = 1 ] && return; fw_setenv bootcmd bootipq || echo 'bootcmd rollback failed; do not reboot' >&2; fw_setenv changing_bootcmd || echo 'marker rollback failed; do not reboot' >&2; }
 trap rollback EXIT
 put miami_bank_restore "$restore"; put miami_bank_load "$load"
 put changing_bootcmd 1
 put bootcmd 'run miami_bank_restore && run miami_bank_load; reset'
 armed=1; trap - EXIT; sync
 echo 'One-shot armed; bootcmd returns to bootipq before NAND load. Reboot manually with serial logging. Later reboot returns to OEM.' ;;
esac
