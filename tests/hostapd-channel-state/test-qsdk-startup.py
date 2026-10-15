"""Run the entire actual drv_mac80211_setup with real jshn and lib/functions.
External hw/netifd/hostapd operations and UCI export are fixture-backed.
Absolute hardware paths are redirected into a temp tree; no AP activity.
This tests startup ordering and JSON namespace, not real driver acceptance.
"""
import json,subprocess,tempfile,pathlib,os,re,shlex,sys
p=pathlib.Path(__file__).parent
source_repo=p.parent.parent
repo=pathlib.Path(os.environ.get('TEST_SDK',str(source_repo/'openwrt')))
fn=(repo/'package/base-files/files/lib/functions.sh').read_text()
jshn=next(repo.glob('build_dir/hostpkg/libubox-*/sh/jshn.sh'))
source=source_repo/'feeds/qca-wifi-7/wifi-scripts/files/lib/netifd/wireless/mac80211.sh'
baseline_file=os.environ.get('TEST_BASELINE_FILE')
src=((pathlib.Path(baseline_file).read_text() if baseline_file else subprocess.check_output(['git','show',os.environ.get('TEST_BASELINE_REF','193f4705c51d6ea50b02488d520c1c87089cfdd3')+':feeds/qca-wifi-7/wifi-scripts/files/lib/netifd/wireless/mac80211.sh'],cwd=source_repo,text=True)) if os.environ.get('TEST_SOURCE')=='qualified' else source.read_text())
netifd=(source.parent.parent/'netifd-wireless.sh').read_text()
def extract(s,name):
 a=s.index(name+'() {'); b=s.index('\n}',a)+2; return s[a:b]
code='\n'.join(extract(src,n) for n in ['mac80211_power_normalize','mac80211_power_phy_identity','mac80211_power_peer','mac80211_prepare_inherited_txpower','mac80211_check_inherited_ap_txpower','mac80211_set_vif_txpower','mac80211_set_suffix','drv_mac80211_setup'] if n+'() {' in src)
foreach=extract(netifd,'for_each_interface')
with tempfile.TemporaryDirectory() as temp:
 root=pathlib.Path(temp); (root/'sys/kernel/debug/ecm/ecm_classifier_default').mkdir(parents=True); (root/'usr/sbin').mkdir(parents=True); (root/'tmp').mkdir(); (root/'var/run').mkdir(parents=True)
 for tool in ['hostapd','wpa_supplicant']:
  f=root/'usr/sbin'/tool; f.write_text('#!/bin/sh\nexit 0\n'); f.chmod(0o755)
 for phy in ['phy0','phy1','phy2']: (root/'sys/class/ieee80211'/phy).mkdir(parents=True)
 hardware=re.sub(r'/sys/|/tmp/|/var/run/|/usr/sbin/',lambda m:str(root)+m.group(),code)
 bootstrap=f'. {jshn}\n'+fn+'\n'+foreach+'\n'+hardware+'\n'
 stubs=r'''
set_default() { local name=$1 value; eval "value=\${$name}"; [ -n "$value" ] || eval "$name=\"\$2\""; }
_wireless_set_brsnoop_isolation() { :; }
mac80211_derive_ml_info() { :; }
find_phy() { return 0; }
mac80211_get_band_name() { echo 2g; }
get_freq() { echo 2412; }
get_link_id() { echo ''; }
miami_phy_by_path() { return 1; }
iwinfo() { return 1; }
mac80211_check_ap() { has_ap=1; }
mac80211_set_noscan() { :; }
mac80211_hostapd_setup_base() { echo BASE; }
mac80211_prepare_vif() { echo PREPARE:$1; }
mac80211_setup_vif() { echo CREATE:$1; }
mac80211_prepare_iw_htmode() { :; }
mac80211_reset_config() { echo RESET; }
mac80211_freq_to_channel() { echo 0; }
wireless_setup_failed() { echo FAIL:$1; }
wireless_setup_vif_failed() { echo FAIL:$1; }
wireless_set_data() { :; }
wireless_set_up() { echo UP; }
wireless_set_retry() { :; }
wpa_supplicant_init_config() { :; }
wpa_supplicant_set_config() { :; }
wpa_supplicant_start() { :; }
hostapd_set_config() { echo HOSTAPD; }
hostapd_dpp_action() { :; }
mac80211_set_fq_limit() { :; }
wdev_tool() { echo WDEV; }
uci() { :; }
timeout() { shift 3; "$@"; }
iw() { case "$*" in *'set txpower'*) echo POWER:$*; return "$SET_RESULT";; *) return 0;; esac; }
'''
 for mlo in [0,1]:
  for cap,result in [('14',0),('',0),('0',0),('14',1),('14',124),('23',0)]:
   peers={f'radio{i}':{'phy':('phy0' if i==0 else 'phy1'),'txpower':('14' if i==1 else '23')} for i in range(3)}
   # Three logical radios matching the sanitized controller caps; mapping is
   # an explicit fixture, not an assertion about this AP's live PHY grouping.
   for i in range(3):
    fixture={'config':{'phy':('phy0' if i==0 else 'phy1'),'radio':(-1 if i==0 else i-1),'txpower':cap,'band':'2g' if i==0 else '5g' if i==1 else '6g','htmode':'EHT20','channel':1,'path':'fixture','num_global_macaddr':1},'data':{'rxantenna':'0xffffffff','txantenna':'0xffffffff'},'interfaces':{'primary':{'config':{'mode':'ap','_ifname':'fixture0','mld':'ml0'}},'late':{'config':{'mode':'ap','_ifname':'fixture1','mld':'ml0'}}}}
    uci='uci_load() { CONFIG_SECTIONS=; '+''.join(f'config wifi-device radio{k}; option type mac80211; option phy {peers["radio"+str(k)]["phy"]}; option txpower "{peers["radio"+str(k)]["txpower"]}"; ' for k in range(3))+'}\n'
    init=f'IPKG_INSTROOT=; SET_RESULT={result}; mlo_add_flag={mlo}; is_wiphy_multi_radio=0; auto_channel=1; txpower_failed=0; ppe_vp=0; json_load '+repr(json.dumps(fixture))+'\n'
    before='json_dump > '+str(root/'json-before')+'\n'
    end=f'drv_mac80211_setup radio{i}; rc=$?; echo RESULT=$rc; json_dump > {root}/json-after\n'
    env=dict(os.environ,PATH=str(repo/'staging_dir/host/bin')+':'+os.environ['PATH'])
    r=subprocess.run(shlex.split(os.environ.get('TEST_SHELL','bash')),input=bootstrap+stubs+uci+init+before+end,text=True,capture_output=True,env=env)
    lines=r.stdout.splitlines(); powers=[n for n,x in enumerate(lines) if x.startswith('POWER:')]
    if '--negative-control' in sys.argv:
     assert not powers and 'FAIL:TXPOWER_LINK_UNAVAILABLE' in lines and 'RESULT=1' in lines,(r.stdout,r.stderr)
     print('PASS old-source negative: full normal setup attempts unavailable MLO links and fails without pre-creation PHY inheritance')
     sys.exit(0)
    assert powers,(mlo,cap,result,r.stdout,r.stderr)
    if i:
     assert f'POWER:phy phy1 set txpower radio {i-1} ' in lines[powers[0]],r.stdout
    else:
     assert ' txpower radio ' not in lines[powers[0]],r.stdout
    if result:
     assert 'RESULT=1' in lines and 'HOSTAPD' not in lines and not any(x.startswith('PREPARE:') for x in lines),(r.stdout,r.stderr)
    else:
     assert 'RESULT=0' in lines,(mlo,cap,r.stdout,r.stderr)
     assert powers[0]<next(n for n,x in enumerate(lines) if x.startswith('PREPARE:')),(r.stdout,r.stderr)
     if not mlo:assert powers[0]<lines.index('HOSTAPD'),r.stdout
     # jshn config/data namespace returned to root despite config_load and
     # for_each_interface; wdev namespace legitimately has its own object.
     assert json.loads((root/'json-before').read_text())==json.loads((root/'json-after').read_text()),(r.stdout,r.stderr)
 print('PASS 36 entire actual setup executions: 3 generated radio JSON fixtures with 5/6 GHz sharing a wiphy and unequal UCI caps, normal/MLO-prepare-only branches, auto/fixed/zero and error/timeout; real jshn/config helpers; hardware/lifecycle calls mocked')
