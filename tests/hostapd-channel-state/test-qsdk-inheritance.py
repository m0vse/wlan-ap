"""Execute actual candidate shell functions; config, sysfs and iw are mocked.
No AP access. Source-order checks disclose that full netifd integration is not
executed here. This is a review candidate, not hardware qualification.
"""
import json,subprocess,re,os
from pathlib import Path
p=Path(__file__).parent
root=p.parent.parent
src=(root/'feeds/qca-wifi-7/wifi-scripts/files/lib/netifd/wireless/mac80211.sh').read_text(); before=subprocess.check_output(['git','show',os.environ.get('TEST_BASELINE_REF','193f4705c51d6ea50b02488d520c1c87089cfdd3')+':feeds/qca-wifi-7/wifi-scripts/files/lib/netifd/wireless/mac80211.sh'],cwd=root,text=True)
functions=src[src.index('mac80211_power_normalize()'):src.index('mac80211_set_fq_limit()')]
def run(name,peers,power='',radio=-1,override='',mode='ap',mld='1',fail=False,identity_missing=False,expected=True):
 cfg='\n'.join(f'cfg_{k}_{s}={v!r}' for s,d in peers.items() for k,v in d.items())
 script='''set -u
[() { if [builtin_placeholder] ; then :; fi; }
'''
 # Mock only external sysfs existence/identity; use bash builtin for all
 # actual numeric/string validation in the candidate.
 stub=r'''
function [ { if [[ "$1" == -d && "$2" == /sys/class/ieee80211/* ]]; then return 0; elif [[ "$1" == -d && "$2" == /sys/class/net/* ]]; then return 1; else builtin [ "$@"; fi; }
config_get() { local var=$1 section=$2 key=$3 fallback=${4-}; local lookup="cfg_${key}_${section}"; printf -v "$var" '%s' "${!lookup-$fallback}"; }
config_load() { :; }
config_foreach() { local cb=$1; for sec in PEERS; do "$cb" "$sec"; done; }
readlink() { case "${@: -1}" in */phy0) echo /sys/devices/wiphy0;; */phy1) echo /sys/devices/wiphy1;; *) return 1;; esac; }
miami_phy_by_path() { return 1; }
iwinfo() { return 1; }
wireless_setup_failed() { echo "FAIL $*"; }
wireless_setup_vif_failed() { echo "FAIL $*"; }
json_select() { :; }
json_get_var() { case "$2" in _ifname) printf -v "$1" late;; _ppe_vp) printf -v "$1" 0;; *) printf -v "$1" '';; esac; }
json_get_vars() { for field in "$@"; do case "$field" in mode) printf -v mode '%s' "$CASE_MODE";; vif_txpower) printf -v vif_txpower '%s' "$CASE_OVERRIDE";; esac; done; }
get_link_id() { echo ''; }
set_default() { local var=$1; [[ -n "${!var-}" ]] || printf -v "$var" '%s' "$2"; }
timeout() { shift 3; "$@"; }
iw() { echo "IW $*"; [[ "$FAIL_IW" != 1 ]]; }
'''.replace('PEERS',' '.join(peers))
 script=cfg+'\n'+stub+'\n'+functions+f'\ndevice=radio0; phy=phy0; txpower={power!r}; radio={radio}; vif_txpower={override!r}; mld={mld!r}; mode={mode!r}; CASE_MODE={mode!r}; CASE_OVERRIDE={override!r}; FAIL_IW={int(fail)}; inherited_txpower_ready=0; txpower_failed=0\n'
 script+='mac80211_prepare_inherited_txpower; rc=$?\nif [ "$rc" = 0 ]; then mac80211_set_vif_txpower late; rc=$?; fi\necho RESULT=$rc\n'
 out=subprocess.run(['bash'],input=script,text=True,capture_output=True)
 ok='RESULT=0' in out.stdout
 assert ok==expected,(name,out.stdout,out.stderr)
 if expected and mode=='ap' and (not override or override in ['17','17.0']): assert 'IW dev late set txpower' not in out.stdout,(name,out.stdout)
 if expected and radio >= 0:
  assert f'IW phy phy0 set txpower radio {radio} ' in out.stdout,(name,out.stdout)
 assert 'TXPOWER_SHARED_PHY' not in out.stdout,(name,out.stdout)
 print(name+': PASS')
 return out.stdout
base={'radio0':{'type':'mac80211','phy':'phy0'}}
run('auto ACS late secondary BSS',base)
run('same PHY uniform fixed multi-radio MLO',{'radio0':{'type':'mac80211','phy':'phy0','txpower':'17'},'radio1':{'type':'mac80211','phy':'phy0:1','txpower':'17'}},power='17',radio=1,override='17')
run('same PHY independent fixed caps accepted',{'radio0':{'type':'mac80211','phy':'phy0','txpower':'17'},'radio1':{'type':'mac80211','phy':'phy0:1','txpower':'20'}},power='17',radio=1)
run('disjoint physical PHY different caps',{'radio0':{'type':'mac80211','phy':'phy0','txpower':'17'},'radio1':{'type':'mac80211','phy':'phy1','txpower':'20'}},power='17')
run('explicit differing BSS override needs actual link',base,override='12',expected=False)
run('genuine PHY programming failure',base,fail=True,expected=False)
run('peer identity irrelevant to radio-scoped request',{'radio0':{'type':'mac80211','phy':'phy0'},'radio1':{'type':'mac80211'}})
run('disabled peer excluded',{'radio0':{'type':'mac80211','phy':'phy0'},'radio1':{'type':'mac80211','disabled':'1'}})
run('requested runtime cap independent of UCI peers',{'radio0':{'type':'mac80211','phy':'phy0','txpower':'18'}},power='17')
run('fractional cap retains existing truncation',{'radio0':{'type':'mac80211','phy':'phy0','txpower':'17.5'}},power='17.5',override='17.0')
run('zero cap remains fixed zero',{'radio0':{'type':'mac80211','phy':'phy0','txpower':'0'}},power='0')
for legacy_mode in ['sta','mesh','adhoc','monitor']:
 run('legacy '+legacy_mode+' setter fallthrough',base,mode=legacy_mode,mld='')
run('unknown MLO link remains hard failure without AP inheritance',base,mode='sta',expected=False)
# Exact candidate startup must prepare the accepted PHY state before either
# MLO prepare-only early-return or ordinary hostapd start. Not a full daemon test.
setup=src[src.index('drv_mac80211_setup()'):]
assert setup.index('mac80211_prepare_inherited_txpower || return 1') < setup.index('if [ "$mlo_add_flag" = 1 ]') < setup.index('hostapd_set_config')
assert 'mac80211_prepare_inherited_txpower' not in before
print('actual startup ordering + old-source negative control: PASS')
