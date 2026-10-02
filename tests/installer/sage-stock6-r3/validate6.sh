#!/bin/sh
set -eu
release=/home/phil/openwifi-sage-build/release-sage-2026.10.02.6
root=$(python3 -c 'import json;print(json.load(open("/home/phil/openwifi-sage-build/release-sage-2026.10.02.6/capture.json"))["root"])')
bundle=/tmp/sage6-stock-capacity-bundle
image=$release/cambium-sage-sage-2026.10.02.6-sysupgrade.bin
python3 /tmp/prepare-bundle.py "$bundle" "$image"
cp "$image" "$bundle/"
cmp "$root/lib/functions/cambium-ab-sage.sh" "$bundle/modules/cambium-ab-sage.sh"
python3 /tmp/check-static-ram-closure.py "$root" > "$release/static-ram-closure.json"
OW_RAM_TEST_BOARD=cambiumnetworks,e410b python3 /tmp/test-incoming-ram-copy.py "$root" "$image" sage > "$release/e410b-fit-ram-tests.json"
OW_RAM_TEST_BOARD=cambiumnetworks,e410 python3 /tmp/test-incoming-ram-copy.py "$root" "$image" sage > "$release/e410-fit-ram-tests.json"
OW_SAGE_TEST_BASE=/tmp/openwifi-sage-stock3-tests OW_SAGE_TEST_PAYLOAD="$bundle" OW_SAGE_IMAGE_SHA256=$(sha256sum "$image" | cut -d ' ' -f 1) OW_TEST_ASH=/home/phil/openwifi-cheetah-build/operator-r2/busybox-ash/busybox python3 "$bundle/test-stock-sysupgrade.py" > "$release/stock-validator-tests.json"
python3 "$bundle/test-wrapper-flow.py" "$bundle" sage stock-clean > "$release/wrapper-tests.json"
/usr/bin/qemu-arm -L "$root" "$root/bin/busybox" ash -n "$root/lib/functions/cambium-ab-sage.sh"
printf '%s\n' 'PASS: exact shipped module, stock/E410B validator, E410/E410B FIT+RAM, future floor285 and unchanged kernel/modules'
