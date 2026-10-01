#!/bin/sh
set -eu
checker=${1:?Usage: test-init-backups.sh checker}
fixture=$(mktemp -d)
trap 'rm -rf "$fixture"' EXIT HUP INT TERM
mkdir -p "$fixture/package/netifd/files/etc/init.d" "$fixture/root/etc/rc.d"
touch "$fixture/package/netifd/files/etc/init.d/network"
"$checker" "$fixture"
for suffix in .orig .rej .bak '~'; do
	backup="$fixture/package/netifd/files/etc/init.d/network$suffix"
	touch "$backup"
	if "$checker" "$fixture" >/dev/null 2>&1; then
		echo "Missed init backup: $suffix" >&2
		exit 1
	fi
	rm "$backup"
done
ln -s ../init.d/network.orig "$fixture/root/etc/rc.d/S20network.orig"
if "$checker" "$fixture" >/dev/null 2>&1; then
	echo 'Missed dangling backup boot entry' >&2
	exit 1
fi
rm "$fixture/root/etc/rc.d/S20network.orig"
ln -s ../init.d/network.orig "$fixture/root/etc/rc.d/S20other"
if "$checker" "$fixture" >/dev/null 2>&1; then
	echo 'Missed renamed boot link to backup script' >&2
	exit 1
fi
rm "$fixture/root/etc/rc.d/S20other"
mkdir -p "$fixture/package/netifd/patches"
touch "$fixture/package/netifd/patches/intentional.orig"
"$checker" "$fixture"
echo 'PASS: clean init tree, four backup suffixes, dangling and renamed boot links'
