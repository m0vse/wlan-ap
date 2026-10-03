#!/bin/sh
# Compile the actual patched installed-layout modules; never runs configuration.
set -eu
fixture=$1
helper=$2
root=$3
qemu=$4
checkdir=$(mktemp -d /tmp/regulatory-installed-syntax.XXXXXX)
cp -R "$fixture/renderer/"* "$checkdir/"
cp -R "$fixture/system/"* "$checkdir/"
cp "$helper" "$checkdir/wifi/regulatory.uc"
cp "$(dirname "$0")/syntax-import.uc" "$checkdir/syntax-import.uc"
for module in renderer.uc syntax-import.uc; do
    "$qemu" -L "$root" "$root/usr/bin/ucode" -L "$root/usr/lib/ucode" \
        -L "$root/usr/share/ucentral" -L "$checkdir" \
        -c -o "$checkdir/check.uc.out" "$checkdir/$module"
done
printf 'Patched installed renderer and state/wifi target syntax PASS: %s\n' "$checkdir"
