#!/bin/sh
# Separate preserving OpenWiFi route. Default check never flashes/reboots.
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
mode=${1:---check}
case "$mode" in --check|--install) ;; *) exit 2 ;; esac
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
image_name=$(cat "$here/IMAGE")
case "$image_name" in ''|*/*|*..*) exit 1 ;; esac
image=$here/$image_name
(cd "$here" && sha256sum -c SHA256SUMS)
if [ "$mode" = --install ]; then
 sh "$here/prepare-upgrader.sh" --recover "$image"
fi
sh "$here/prepare-upgrader.sh" --check "$image"
if [ -L /etc/ucentral/ucentral.active ] || [ -e /etc/ucentral/ucentral.active ]; then
 active=$(readlink -f /etc/ucentral/ucentral.active)
 case "$active" in /etc/ucentral/*|/rom/etc/ucentral/ucentral.cfg.0000000001) ;; *) echo 'Unsupported active document path' >&2; exit 1 ;; esac
 [ -f "$active" ] && [ -s "$active" ] || exit 1
fi
[ "$mode" = --install ] || exit 0
work=$(mktemp -d /tmp/jaguar-openwifi-install.XXXXXX)
chmod 700 "$work"
mkdir "$work/archive"
sysupgrade -b "$work/existing.tgz"
tar -xzf "$work/existing.tgz" -C "$work/archive"
mkdir -p "$work/archive/etc"
for path in /etc/config /etc/config-shadow /etc/ucentral; do
 [ ! -d "$path" ] || cp -a "$path" "$work/archive/etc/"
done
(cd "$work/archive" && tar -czf "$work/preserved.tgz" .)
chmod 600 "$work/preserved.tgz"
sh "$here/prepare-upgrader.sh" --install "$image"
sh "$here/prepare-upgrader.sh" --verify-installed "$image"
sysupgrade -T "$image"
echo 'Starting operator-authorized preserving A/B trial; current bank remains rollback bank.'
sysupgrade -v -f "$work/preserved.tgz" "$image"
