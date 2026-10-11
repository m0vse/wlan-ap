#!/bin/bash
set -euo pipefail
task_root=${1:?extracted Gambit rootfs}
task_qemu=${2:-/usr/bin/qemu-mips}
test -x "$task_qemu"
test -x "$task_root/bin/busybox"
task_fixture=$(mktemp -d /tmp/gambit-target-utilities.XXXXXX)
mkdir "$task_fixture/source" "$task_fixture/restored"
printf 'isolated certificate-store fixture\n' > "$task_fixture/source/public-fixture"
chmod 0600 "$task_fixture/source/public-fixture"
task_bb() { "$task_qemu" -cpu 24Kc -L "$task_root" "$task_root/bin/busybox" "$@"; }
ls() { task_bb ls "$@"; }
awk() { task_bb awk "$@"; }
export LC_ALL=C
AB_CERTIFICATE_OWNER=$(id -u)
. "$task_root/lib/upgrade/cambium-ab-certificates.sh"
ab_certificate_private_file "$task_fixture/source/public-fixture"
task_original_owner=$AB_CERTIFICATE_OWNER
AB_CERTIFICATE_OWNER=$((task_original_owner + 1))
if ab_certificate_private_file "$task_fixture/source/public-fixture"; then
    echo 'ERROR: target ls/awk accepted wrong snapshot owner' >&2
    exit 1
fi
AB_CERTIFICATE_OWNER=$task_original_owner
chmod 0644 "$task_fixture/source/public-fixture"
if ab_certificate_private_file "$task_fixture/source/public-fixture"; then
    echo 'ERROR: target ls/awk accepted nonprivate snapshot mode' >&2
    exit 1
fi
chmod 0600 "$task_fixture/source/public-fixture"
task_bb cmp -s "$task_fixture/source/public-fixture" "$task_fixture/source/public-fixture"
task_temp=$(task_bb mktemp -d "$task_fixture/mktemp.XXXXXX")
test -d "$task_temp"
(
    cd "$task_fixture/source"
    task_bb sha256sum public-fixture > .cambium-ab-manifest
    task_bb sha256sum -c .cambium-ab-manifest
    task_bb tar cf "$task_fixture/archive.tar" .
)
task_bb tar tf "$task_fixture/archive.tar" > "$task_fixture/archive.entries"
task_bb tar tvf "$task_fixture/archive.tar" > "$task_fixture/archive.details"
task_bb tar xf "$task_fixture/archive.tar" -C "$task_fixture/restored"
(
    cd "$task_fixture/restored"
    task_bb sha256sum -c .cambium-ab-manifest
)
task_bb find "$task_fixture/restored" -type f -exec "$task_qemu" -cpu 24Kc -L "$task_root" "$task_root/bin/busybox" ls -ldn '{}' ';' > "$task_fixture/file-modes"
test "$(wc -l < "$task_fixture/file-modes")" = 2
task_bb hexdump -v -e '4/1 "%02x"' "$task_fixture/source/public-fixture" > "$task_fixture/hexdump"
test -s "$task_fixture/hexdump"
echo "TARGET_UTILITY_FIXTURE=$task_fixture"
echo 'PASS: actual MIPS BusyBox ls/awk permission acceptance/refusal, cmp, mktemp, tar, sha256sum check, find and hexdump'

# Ephemeral fixture only: no live identity or CA material.
umask 077
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=gambit-utility-fixture \
    -keyout "$task_fixture/key.pem" -out "$task_fixture/cert.pem" >/dev/null 2>&1
"$task_qemu" -cpu 24Kc -L "$task_root" "$task_root/usr/bin/openssl" \
    x509 -in "$task_fixture/cert.pem" -pubkey -noout > "$task_fixture/certificate-public"
"$task_qemu" -cpu 24Kc -L "$task_root" "$task_root/usr/bin/openssl" \
    pkey -in "$task_fixture/key.pem" -pubout > "$task_fixture/key-public"
task_bb cmp -s "$task_fixture/certificate-public" "$task_fixture/key-public"
echo 'PASS: actual MIPS OpenSSL reads matching ephemeral certificate and key without logging private material'

"$task_qemu" -cpu 24Kc -L "$task_root" "$task_root/usr/bin/openssl" \
    dgst -sha256 -sign "$task_fixture/key.pem" -out "$task_fixture/signature" "$task_fixture/source/public-fixture"
"$task_qemu" -cpu 24Kc -L "$task_root" "$task_root/usr/bin/openssl" \
    dgst -sha256 -verify "$task_fixture/key-public" -signature "$task_fixture/signature" "$task_fixture/source/public-fixture"
echo 'PASS: actual MIPS OpenSSL signs and verifies isolated fixture data'
