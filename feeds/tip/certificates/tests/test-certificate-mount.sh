#!/bin/sh
# Run the actual mount helper against redirected paths and stubbed mount/UBI.
set -eu
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")/../files" && pwd)
fixture=$(mktemp -d /tmp/openwifi-certificate-mount-test.XXXXXX)
mkdir -p "$fixture/lib/functions" "$fixture/etc/ucentral" "$fixture/certificates" "$fixture/identity"
printf 'test\n' > "$fixture/identity/key.pem"
printf 'test\n' > "$fixture/identity/cert.pem"
: > "$fixture/mounts"
printf '%s\n' 'board_name() { echo cambiumnetworks,xv2-2t1; }' \
    "mount() { printf '%s\\n' \"\$*\" >> '$fixture/mount-calls'; cp '$fixture/identity/'* '$fixture/certificates/'; }" > "$fixture/lib/functions.sh"
printf '%s\n' 'ab_family() { AB_CERTIFICATE_LEBS=${CERTIFICATE_TEST_LEBS:-20}; AB_LAYOUT=${TEST_LAYOUT:-banks}; return 0; }' \
    'ab_identity() { AB_ACTIVE_UBI=${ACTIVE_TEST_UBI:-ubi1}; return 0; }' \
    'ab_ubi_volume() { echo "${1}_4"; }' > "$fixture/lib/functions/cambium-ab.sh"
sed -e "s|/lib/|$fixture/lib/|g" -e "s|/etc/|$fixture/etc/|g" \
    -e "s|/certificates|$fixture/certificates|g" -e "s|/proc/mounts|$fixture/mounts|g" \
    "$source_dir/usr/bin/mount_certs" > "$fixture/mount_certs"
sh "$fixture/mount_certs"
grep -q '/dev/ubi1_4' "$fixture/mount-calls"
# Existing credentials do not short-circuit validation of a wrong-bank mount.
printf 'ubi0:certificates %s ubifs rw 0 0\n' "$fixture/certificates" > "$fixture/mounts"
if sh "$fixture/mount_certs"; then exit 1; fi
test "$(wc -l < "$fixture/mount-calls")" = 1
printf 'ubi1:certificates %s ubifs rw 0 0\n' "$fixture/certificates" > "$fixture/mounts"
sh "$fixture/mount_certs"
test "$(wc -l < "$fixture/mount-calls")" = 1
: > "$fixture/mounts"
TEST_LAYOUT=pair CERTIFICATE_TEST_LEBS=0 ACTIVE_TEST_UBI=ubi0 sh "$fixture/mount_certs"
tail -1 "$fixture/mount-calls" | grep -q '/dev/ubi0_4'
printf '%s\n' "Active-bank mount selection and wrong-bank refusal passed; fixtures: $fixture"
