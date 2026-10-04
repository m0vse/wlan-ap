#!/bin/sh
# TEST-only actual runtime entrypoint checks. Invoke through a private mount namespace.
set -eu
source=$1
root=$2
emulator=$3
[ "$(id -u)" = 0 ] || { echo 'TEST requires root-owned private fixtures' >&2; exit 1; }
[ "$(readlink /proc/self/ns/mnt)" != "$(readlink /proc/1/ns/mnt)" ] || { echo 'TEST requires unshare --mount --propagation private' >&2; exit 1; }
fixture=$(mktemp -d /tmp/boot-entrypoint-fixture.XXXXXX)
mkdir -p "$fixture/etc/ucentral" "$fixture/run" "$fixture/sys/fs/pstore" "$fixture/share/ucentral" "$fixture/bin"
cp "$source/feeds/ucentral/ucentral-boot-report/files/usr/share/ucentral/boot_reporting.uc" "$fixture/share/ucentral/"
printf 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa\n' > "$fixture/boot-id"
printf '100.0 0\n' > "$fixture/uptime"
printf 'TEST-synthetic-firmware\n' > "$fixture/etc/openwrt_release"
mount --bind "$fixture/etc" /etc
mount --bind "$fixture/run" /run
mount --bind "$fixture/sys" /sys
mount --bind "$fixture/share" /usr/share
mount --bind "$fixture/boot-id" /proc/sys/kernel/random/boot_id
mount --bind "$fixture/uptime" /proc/uptime
cli() { "$emulator" -L "$root" "$root/usr/bin/ucode" -L "$root/usr/lib/ucode" "$source/feeds/ucentral/ucentral-boot-report/files/usr/libexec/ucentral-boot-report" "$@"; }
uc() { "$emulator" -L "$root" "$root/usr/bin/ucode" -L "$root/usr/lib/ucode" "$@"; }
cli collect
cli collect
cli clock-sync step 16
[ ! -e /run/ucentral-boot-report/clock-synced ]
cli clock-sync stratum 16
[ ! -e /run/ucentral-boot-report/clock-synced ]
cli clock-sync stratum 2
[ "$(cat /run/ucentral-boot-report/clock-synced)" = aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa ]
[ "$(stat -c %a /run/ucentral-boot-report/clock-synced)" = 600 ]
cli clock-sync step 16
[ -f /run/ucentral-boot-report/clock-synced ]
cli clock-sync unsync 16
[ ! -e /run/ucentral-boot-report/clock-synced ]
cli clock-sync periodic 3
[ -f /run/ucentral-boot-report/clock-synced ]
cli plan controller-requested
cli plan user-requested
cli plan orderly-shutdown
uc -e 'let fs=require("fs"), s=json(fs.readfile("/etc/ucentral/boot-reporting/history.json")); if (length(s.events)!=1 || s.intent.reason!="controller-requested" || s.reason!="unexpected-shutdown") die("TEST entrypoint precedence failed");'
cli cancel controller-requested
cli plan upgrade
uc -e 'let s=json(require("fs").readfile("/etc/ucentral/boot-reporting/history.json")); if(s.intent.reason!="firmware-upgrade") die("TEST upgrade normalization failed");'
cli send
uc -e 'let s=json(require("fs").readfile("/etc/ucentral/boot-reporting/history.json")); if(s.events[0].delivery!="pending") die("TEST offline queue lost");'
[ "$(stat -c %a /etc/ucentral/boot-reporting)" = 700 ]
[ "$(stat -c %a /etc/ucentral/boot-reporting/history.json)" = 600 ]
rmdir /sys/fs/pstore
cli collect
uc "$source/tests/boot-reporting/helper-tests.uc" "$source/feeds/ucentral/ucentral-schema/files/usr/share/ucentral/reboot_cause.uc"
# Map only the two command paths to harmless executables; NEVER invoke reboot.
printf '#!/bin/sh\nprintf "%%s\\n" "$*" >> "%s/report-calls"\nexit 0\n' "$fixture" > "$fixture/bin/report"
printf '#!/bin/sh\nprintf "%%s\\n" "$*" >> "%s/reboot-calls"\nexit "${REBOOT_TEST_RC:-0}"\n' "$fixture" > "$fixture/bin/reboot"
chmod 700 "$fixture/bin/report" "$fixture/bin/reboot"
sed "s@/usr/libexec/ucentral-boot-report@$fixture/bin/report@g;s@/sbin/reboot@$fixture/bin/reboot@g" "$source/feeds/ucentral/ucentral-boot-report/files/etc/profile.d/ucentral-reboot-history.sh" > "$fixture/profile"
ash() { "$emulator" -L "$root" "$root/bin/busybox" ash "$@"; }
ash -i -c ". '$fixture/profile'; reboot" 2>/dev/null
grep -Fxq 'plan user-requested' "$fixture/report-calls"
if REBOOT_TEST_RC=23 ash -i -c ". '$fixture/profile'; reboot" 2>/dev/null; then exit 1; else [ "$?" = 23 ]; fi
grep -Fxq 'cancel user-requested' "$fixture/report-calls"
before=$(wc -l < "$fixture/report-calls")
ash -i -c ". '$fixture/profile'; reboot --help" 2>/dev/null
[ "$(wc -l < "$fixture/report-calls")" = "$before" ]
ash -c ". '$fixture/profile'; command -V reboot" | grep -vq 'function'
sed "s@/usr/libexec/ucentral-boot-report@$fixture/bin/report@g" "$source/feeds/ucentral/ucentral-boot-report/files/etc/init.d/ucentral-boot-report" > "$fixture/service"
ash -c ". '$fixture/service'; stop() { :; }; shutdown"
grep -Fxq 'plan orderly-shutdown' "$fixture/report-calls"
echo 'TEST actual CLI, absent backend/pmsg, permissions, offline queue, interactive scope, failure cancellation and shutdown hook: PASS'
