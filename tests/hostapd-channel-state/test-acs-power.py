#!/usr/bin/env python3
"""Actual regular startup tail and setter, with nl80211/netifd lifecycle actors.

This is a source regression, NOT an AP runtime acceptance check. Secondary BSS
creation is delayed for ACS/CAC, as observed during multi-BSS automatic-channel startup. Inheritance is
independently established from the shipped mac80211 cfg.c and iface.c.
"""
import argparse
import pathlib
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--source', type=pathlib.Path, required=True)
parser.add_argument('--negative-control', action='store_true')
args = parser.parse_args()
source = args.source.read_text()
start = source.index('mac80211_set_vif_txpower() {')
setter = source[start:source.index('\n}', start) + 2]
start = source.index('\tlocal phy_txpower_accepted=0') if '\tlocal phy_txpower_accepted=0' in source else source.index('\t[ -z "$phy_suffix" ] && {', source.index('drv_mac80211_setup()'))
tail = source[start:source.index('\n}', start)]
harness = r'''
json_select() { :; }
json_get_var() { ifname="$fixture_ifname"; }
json_get_vars() { vif_txpower="$fixture_override"; mode="$fixture_mode"; }
set_default() { eval '[ -n "${'"$1"'}" ] || '"$1"'="$2"'; }
wireless_setup_vif_failed() { failure="$1"; }
wireless_setup_failed() { failure="$1"; }
wireless_set_up() { up=1; }
iw() {
 case "$*" in
 phy*)
   phy_writes=$((phy_writes + 1))
   [ "$phy_error" = 0 ] || return "$phy_error"
   accepted_power="$txpower"
   return 0;;
 dev*)
   vif_writes=$((vif_writes + 1))
   [ "$2" != wlan0 ] || return "$primary_error"
   [ "$secondary_present" = 1 ] || return 19
   return "$secondary_error";;
 *) return 99;;
 esac
}
for_each_interface() {
 local i=0
 while [ "$i" -lt "$bss_count" ]; do
   fixture_ifname=wlan0
   [ "$i" = 0 ] || fixture_ifname="wlan0-$i"
   fixture_override=
   [ "$i" = 0 ] || fixture_override="$override"
   "$2" "$i"
   i=$((i + 1))
 done
}
'''
count = 0
def run(label, *, bss=4, power='17', override='', present=0,
        phy_error=0, primary_error=0, secondary_error=0, suffix='',
        mode='ap', expected='success', writes=1):
    global count
    setup = f'''
bss_count={bss}; txpower='{power}'; override='{override}'
secondary_present={present}; phy_error={phy_error}; primary_error={primary_error}
secondary_error={secondary_error}; phy_suffix='{suffix}'; phy=phy0
fixture_mode='{mode}'; ap_ifname=wlan0
up=0; failure=; phy_writes=0; vif_writes=0; accepted_power=
'''
    checks = '[ "$up" = 1 ] && [ -z "$failure" ]' if expected == 'success' else '[ "$up" = 0 ] && [ "$failure" = TXPOWER_SET_FAILED ]'
    checks += f' && [ "$vif_writes" = {writes} ] || exit 90\n'
    if expected == 'success' and not suffix:
        checks += '[ "$phy_writes" = 1 ] && [ "$accepted_power" = "$txpower" ] || exit 91\n'
    result = subprocess.run(['sh'], input=setter+'\n'+harness+'\nsetup_power() {\n'+tail+'\n}\n'+setup+'\nsetup_power\n'+checks, text=True, capture_output=True)
    if args.negative_control:
        assert result.returncode != 0, 'Broken startup unexpectedly accepted late secondary BSS'
        print('PASS negative control: original .14.1 fails actual startup tail with late ACS BSS')
        raise SystemExit(0)
    assert result.returncode == 0, (label, result.returncode, result.stderr)
    print('PASS', label)
    count += 1

for bss in (3, 4):
    for state, present in (('ACS-late', 0), ('fixed-created', 1), ('DFS-CAC-late', 0)):
        for power in ('17', '0', '', '17.9'):
            run(f'{bss}BSS/{state}/inherited/{power or "auto"}', bss=bss, present=present, power=power)
        run(f'{bss}BSS/{state}/equivalent-truncated-mBm', bss=bss, present=present, power='17.9', override='17.1')
        run(f'{bss}BSS/{state}/different-override', bss=bss, present=present, override='12', expected='success' if present else 'failure', writes=bss)
run('PHY-rejection', phy_error=22, expected='failure', writes=0)
run('primary-EINVAL', primary_error=22, expected='failure')
run('primary-missing', primary_error=19, expected='failure')
run('existing-explicit-override-EINVAL', present=1, override='12', secondary_error=22, expected='failure', writes=4)
run('zero-explicit-override', present=1, override='0', writes=4)
run('no-accepted-PHY-proof', suffix=':0', expected='failure', writes=4)
run('non-AP-is-not-inheritance-exemption', mode='sta', expected='failure', writes=4)
print(f'PASS {count} actual regular startup lifecycle controls; hardware/netifd mocked')
