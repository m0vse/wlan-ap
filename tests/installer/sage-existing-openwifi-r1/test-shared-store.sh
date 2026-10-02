#!/bin/sh
# Actual check function, isolated sysfs/mount records and newly generated key.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
fixture=$(mktemp -d /tmp/sage-shared-store-test.XXXXXX)
trap 'rm -rf "$fixture"' EXIT HUP INT TERM
AB_LAYOUT=pair AB_ACTIVE_UBI=ubi9 AB_ACTIVE_MTD=7 AB_LEB=126976
AB_UBI_SYS=$fixture/sys AB_PROC_MOUNTS=$fixture/mounts
AB_CERTIFICATE_STORE=$fixture/store AB_CERTIFICATE_RUNTIME=$fixture/runtime
AB_CERTIFICATE_OWNER=$(id -u)
mkdir -p "$fixture/sys/ubi9" "$fixture/sys/ubi9_7" "$fixture/store" "$fixture/runtime"
printf '7\n' > "$fixture/sys/ubi9/mtd_num"
printf '1\n' > "$fixture/sys/ubi9/avail_eraseblocks"
printf '20\n' > "$fixture/sys/ubi9_7/reserved_ebs"
printf '126976\n' > "$fixture/sys/ubi9_7/usable_eb_size"
printf 'ubi9:certificates %s ubifs rw 0 0\n' "$fixture/store" > "$fixture/mounts"
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=fixture \
 -keyout "$fixture/store/key.pem" -out "$fixture/store/cert.pem" >/dev/null 2>&1
cp "$fixture/store/"*.pem "$fixture/runtime/"
chmod 600 "$fixture/store/key.pem" "$fixture/runtime/key.pem"
volume=ubi9_7
ab_ubi_volume() { [ -n "$volume" ] && echo "$volume"; }
ab_certificate_lebs() { echo 0; }
ab_certificate_tree_safe() { [ -z "$(find "$1" ! -type f ! -type d -print)" ]; }
. "$here/shared-store-check.sh"
before=$(sha256sum "$fixture/store/"*.pem)
sage_shared_store_check
chmod 644 "$fixture/store/key.pem"
if sage_shared_store_check; then exit 1; fi
chmod 600 "$fixture/store/key.pem"
printf '19\n' > "$fixture/sys/ubi9_7/reserved_ebs"
if sage_shared_store_check; then exit 1; fi
printf '20\n' > "$fixture/sys/ubi9_7/reserved_ebs"
printf '8\n' > "$fixture/sys/ubi9/mtd_num"
if sage_shared_store_check; then exit 1; fi
printf '7\n' > "$fixture/sys/ubi9/mtd_num"
printf 'ubi0:certificates %s ubifs rw 0 0\n' "$fixture/store" > "$fixture/mounts"
if sage_shared_store_check; then exit 1; fi
printf 'ubi9:certificates %s ubifs rw 0 0\n' "$fixture/store" > "$fixture/mounts"
ln -s key.pem "$fixture/store/unsafe"
if sage_shared_store_check; then exit 1; fi
rm "$fixture/store/unsafe"
printf '\nchanged\n' >> "$fixture/runtime/key.pem"
if sage_shared_store_check; then exit 1; fi
cp "$fixture/store/key.pem" "$fixture/runtime/key.pem"
volume=
printf '19\n' > "$fixture/sys/ubi9/avail_eraseblocks"
if sage_shared_store_check; then exit 1; fi
printf '20\n' > "$fixture/sys/ubi9/avail_eraseblocks"
if sage_shared_store_check; then exit 1; fi
volume=ubi9_7
sage_shared_store_check
[ "$before" = "$(sha256sum "$fixture/store/"*.pem)" ]
echo 'PASS: shared geometry/capacity/mount/credential refusals; no store writes'
