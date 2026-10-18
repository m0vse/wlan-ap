#!/bin/sh
# Configure only an owned target on an already-UP wired interface. No NAND reads.
set -eu
[ "$#" = 5 ] || { echo 'usage: netconsole-setup DEV LOCAL_IP REMOTE_IP REMOTE_MAC REMOTE_PORT' >&2; exit 2; }
dev=$1;local_ip=$2;remote_ip=$3;remote_mac=$4;remote_port=$5
case "$dev" in up0v0) ;; *) echo 'only qualified management up0v0 supported' >&2;exit 1;; esac
[ -L /sys/class/net/up0v0/lower_up ] && [ -e /sys/class/net/up/brif/eth0 ] || exit 1
[ "$(cat /tmp/sysinfo/board_name)" = 'cambiumnetworks,x7-35x' ] || exit 1
for ip in "$local_ip" "$remote_ip"; do echo "$ip" | awk -F. 'NF!=4{exit 1}{for(i=1;i<=4;i++)if($i!~/^[0-9]+$/||$i>255)exit 1}' || exit 1;done
echo "$remote_mac" | grep -Eq '^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$' || exit 1
case "$remote_port" in ''|*[!0-9]*) exit 1;;esac
[ "$remote_port" -ge 1024 ] && [ "$remote_port" -le 65535 ] || exit 1
[ "$(cat /sys/class/net/$dev/operstate)" = up ] && [ "$(cat /sys/class/net/$dev/carrier)" = 1 ] || exit 1
[ -d /sys/module/netconsole ] || modprobe netconsole
if ! grep -q ' /sys/kernel/config configfs ' /proc/mounts; then mount -t configfs configfs /sys/kernel/config;fi
base=/sys/kernel/config/netconsole/miami_failure_capture
if [ -d "$base" ]; then
 if [ "$(cat "$base/enabled")" = 1 ]; then
  [ "$(cat "$base/dev_name")" = "$dev" ] && [ "$(cat "$base/local_ip")" = "$local_ip" ] && [ "$(cat "$base/remote_ip")" = "$remote_ip" ] && [ "$(cat "$base/remote_mac")" = "$remote_mac" ] && [ "$(cat "$base/remote_port")" = "$remote_port" ] && exit 0
  echo 'owned target already enabled with different settings; explicit reconfiguration required' >&2;exit 1
 fi
else mkdir "$base";fi
printf '%s\n' "$dev" > "$base/dev_name"
printf '%s\n' "$local_ip" > "$base/local_ip"
printf '%s\n' "$remote_ip" > "$base/remote_ip"
printf '%s\n' "$remote_mac" > "$base/remote_mac"
printf '%s\n' "$remote_port" > "$base/remote_port"
printf '6665\n' > "$base/local_port"
printf '1\n' > "$base/enabled"
[ "$(cat "$base/enabled")" = 1 ]
printf '<3>MIAMI_CAPTURE_HEARTBEAT boot=%s uptime=%s setup=1\n' "$(cat /proc/sys/kernel/random/boot_id)" "$(cut -d' ' -f1 /proc/uptime)" > /dev/kmsg
