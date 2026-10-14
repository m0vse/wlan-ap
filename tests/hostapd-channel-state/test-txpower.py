#!/usr/bin/env python3
"""Exercise the actual QCA7 power setter, mocking iw/netifd; no AP I/O."""
import argparse
import pathlib
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--source', type=pathlib.Path, required=True)
parser.add_argument('--negative-control', action='store_true')
args = parser.parse_args()
source = args.source.read_text()
start = source.index('mac80211_set_vif_txpower() {')
end = source.index('\n}', start) + 2
function = source[start:end]
harness = r'''
json_select() { :; }
json_get_var() {
 case "$1" in
 ifname) ifname=fixture0;; ppe_vp) ppe_vp=0;;
 link_mac_addr) link_mac_addr=02:00:00:00:00:01;;
 esac
}
json_get_vars() { vif_txpower="$fixture_power"; mld="${fixture_mld:-}"; }
set_default() { :; }
get_link_id() { printf '%s' "$fixture_link"; }
wireless_setup_vif_failed() { failure="$1"; }
iw() {
 case "$*" in
 *'set txpower'*) actual="$*"; return "$fixture_error";;
 *'set_intf_offload'*) offload=$((offload+1)); return 0;;
 *) return 99;;
 esac
}
'''
count = 0
links = ('', '0', '1') if 'get_link_id' in function else ('',)
for link in links:
    for power in ('', '23'):
        for error in (0, 1, 22):
            setup = (f"fixture_link='{link}'; fixture_power='{power}'; "
                     f"fixture_error={error}; htmode={'EHT160' if link else 'HE80'}; "
                     'offload=0; txpower_failed=0; failure=; actual=\n')
            command = ('dev fixture0 set txpower ' + (f'-l {link} ' if link else '')
                       + ('fixed 2300' if power else 'auto'))
            checks = f"mac80211_set_vif_txpower fixture; result=$?\n[ \"$actual\" = '{command}' ] || exit 10\n"
            if error:
                checks += '[ "$result" != 0 ] && [ "$failure" = TXPOWER_SET_FAILED ] && [ "$txpower_failed" = 1 ] && [ "$offload" = 0 ] || exit 11\n'
            else:
                checks += f'[ "$result" = 0 ] && [ -z "$failure" ] && [ "$txpower_failed" = 0 ] && [ "$offload" = {1 if "set_intf_offload" in function else 0} ] || exit 12\n'
            result = subprocess.run(['sh'], input=function+harness+setup+checks,
                                    text=True, capture_output=True)
            if args.negative_control and error:
                assert result.returncode != 0, 'Old setter concealed no failure'
                print('PASS negative control: successful offload masked a power-set failure')
                raise SystemExit(0)
            assert result.returncode == 0, (link, power, error, result.stderr)
            count += 1
if not args.negative_control:
    assert 'wireless_setup_failed TXPOWER_SET_FAILED' in source
    assert 'txpower_failed=0\n\tfor_each_interface' in source
    if 'get_link_id' in function:
        for link in ('', '-1', '16', 'wrong'):
            setup = f"fixture_mld=ml0; fixture_link='{link}'; fixture_power=23; fixture_error=0; htmode=EHT160; offload=0; txpower_failed=0; failure=; actual=\n"
            checks = 'mac80211_set_vif_txpower fixture; result=$?\n[ "$result" != 0 ] && [ "$txpower_failed" = 1 ] && [ "$failure" = TXPOWER_LINK_UNAVAILABLE ] && [ -z "$actual" ] || exit 13\n'
            result = subprocess.run(['sh'], input=function+harness+setup+checks, text=True, capture_output=True)
            assert result.returncode == 0, (link, result.stderr)
            count += 1
    print(f'PASS {count} actual power-setter controls; iw/netifd mocked')
