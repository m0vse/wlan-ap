from pathlib import Path
import re

p=Path('/home/phil/openwifi-gambit-build/wlan-ap/openwrt/cambium/tests/cambium-ab.sh')
s=p.read_text()
header=s.split('# --- board table and identity')[0]
helpers='\n'.join(re.findall(r'^(?:guard|healthy_sage)\(\) \{.*\}$',s,re.M))+'\n'
body=s[s.index('# Gambit keeps its kernels outside UBI.'):]
extra='''
# Exercise the opposite direction, certificate reservation and backup handoff.
new_gambit_ap 0
printf '%s\\n' 'gambit_ab_version=1' 'gambit_ab_confirmed=0' 'gambit_ab_state=confirmed' >> "$S/env"
rm -f "$S/preinit-certificates"
export AB_CERTIFICATE_PREINIT="$S/preinit-certificates"
printf preserved-config > "$S/upgrade.tgz"
export UPGRADE_BACKUP="$S/upgrade.tgz"
check 'E400 bank 0 to 1 without preinit marker retains certificates and backup' 0 dispatch79 platform_do_upgrade "$S/e400.bin"
assert 'E400 certificate volume ID4 retained' [ "$(cat "$S/flash/mtd3/4.name")" = certificates ]
assert 'E400 certificate volume reserves20LEBs' [ "$(cat "$S/flash/mtd3/4.size")" -eq $((20 * LEB)) ]
assert 'E400 opposite-bank config restoration uses rootfs1' grep -q 'restore-config rootfs1 ' "$S/calls"
assert 'E400 bank0 partitions untouched' never_wrote 'erase mtd0|format mtd1|nandwrite mtd0'
unset UPGRADE_BACKUP AB_CERTIFICATE_PREINIT

new_gambit_ap
printf '%s\\n' 'gambit_ab_version=1' 'gambit_ab_confirmed=1' 'gambit_ab_state=confirmed' >> "$S/env"
ubiattach -m 1 >/dev/null
touch "$S/detach_false_error"
check 'E400 attached inactive root is refused without forced detach' 1 dispatch79 platform_do_upgrade "$S/e400.bin"
assert 'E400 attached-target refusal makes no flash writes' never_wrote 'erase|format|nandwrite'
rm -f "$S/detach_false_error"
'''
extra += r"""
# Fresh process, only copied core/module paths: no preinit runtime marker.
for bank in 0 1; do
    new_gambit_ap "$bank"
    printf '%s\n' 'gambit_ab_version=1' "gambit_ab_confirmed=$bank" 'gambit_ab_state=confirmed' >> "$S/env"
    mkdir -p "$S/ramfs/lib/functions" "$S/ramfs/lib/upgrade"
    cp "$ab_pkg/cambium-ab.sh" "$S/ramfs/lib/functions/cambium-ab.sh"
    cp "$ab_pkg/cambium-ab-upgrade.sh" "$S/ramfs/lib/upgrade/cambium-ab.sh"
    cp "$top/package/cambium/cambium-gambit-support/files/cambium-ab-gambit.sh" "$S/ramfs/lib/functions/"
    check "E400 copied RAMFS paths bank $bank retains reservation" 0 env \
        CAMBIUM_AB_LIB="$S/ramfs/lib/functions/cambium-ab.sh" \
        CAMBIUM_AB_MODULES="$S/ramfs/lib/functions" \
        CAMBIUM_AB_UPGRADE_LIB="$S/ramfs/lib/upgrade/cambium-ab.sh" \
        sh -c '. "$CAMBIUM_FUNCTIONS"; . "$CAMBIUM_SYSTEM_FUNCTIONS"; . "$CAMBIUM_AB_UPGRADE_LIB"; ab_identity && [ "$(ab_certificate_lebs)" = 20 ]'
    sed -i 's/AB_CERTIFICATE_LEBS=20/AB_CERTIFICATE_LEBS=19/' "$S/ramfs/lib/functions/cambium-ab-gambit.sh"
    check "E400 invalid copied reservation bank $bank refused" 1 env \
        CAMBIUM_AB_LIB="$S/ramfs/lib/functions/cambium-ab.sh" \
        CAMBIUM_AB_MODULES="$S/ramfs/lib/functions" \
        CAMBIUM_AB_UPGRADE_LIB="$S/ramfs/lib/upgrade/cambium-ab.sh" \
        sh -c '. "$CAMBIUM_FUNCTIONS"; . "$CAMBIUM_SYSTEM_FUNCTIONS"; . "$CAMBIUM_AB_UPGRADE_LIB"; ab_identity && ab_certificate_lebs'
    assert "E400 policy checks bank $bank perform no writes" never_wrote 'erase|format|nandwrite'
done
"""
body=body.replace('nand_restore_config() { echo "restore-config $CI_UBIPART $1" >> "$S/calls"; }', 'nand_restore_config() { echo "restore-config $CI_UBIPART $1" >> "$S/calls"; }\n ab_certificate_validate_snapshot() { [ ! -f "$S/certificate_snapshot_fail" ]; }\n ab_certificate_restore() { echo restore-certificates >> "$S/calls"; [ ! -f "$S/certificate_restore_fail" ]; }')
extra += r"""
new_gambit_ap
printf '%s\n' 'gambit_ab_version=1' 'gambit_ab_confirmed=1' 'gambit_ab_state=confirmed' >> "$S/env"
touch "$S/certificate_restore_fail"
check 'E400 certificate restore failure prevents trial arm' 1 dispatch79 platform_do_upgrade "$S/e400.bin"
assert 'E400 restore failure records write-failed' [ "$(env_get gambit_ab_state)" = write-failed ]
assert 'E400 restore failure never selects trial boot' sh -c '! grep -q "^bootcmd=run gambit_trial" "$1"' sh "$S/env"
rm -f "$S/certificate_restore_fail"
"""
extra += r"""
new_gambit_ap
printf '%s\n' 'gambit_ab_version=1' 'gambit_ab_confirmed=1' 'gambit_ab_state=confirmed' >> "$S/env"
touch "$S/certificate_snapshot_fail"
check 'E400 missing RAM snapshot refused before inactive writes' 1 dispatch79 platform_do_upgrade "$S/e400.bin"
assert 'E400 invalid snapshot causes no erase or allocation' never_wrote 'erase|format|nandwrite|mkvol|update'
rm -f "$S/certificate_snapshot_fail"
"""
body=body.replace('echo "$pass passed, $fail failed"',extra+'\necho "$pass passed, $fail failed"')
p.with_name('gambit-ab-scoped.sh').write_text(header+helpers+body)
print('Scoped E400 harness generated from shared real-code tests')
