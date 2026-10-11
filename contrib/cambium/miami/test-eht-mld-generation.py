#!/usr/bin/env python3
"""Execute the actual SDK BSS renderer with isolated JSON/base/mount inputs."""
from pathlib import Path
import os,shlex,subprocess,tempfile
repo=Path(__file__).resolve().parents[3]
source=(repo/'feeds/qca-wifi-7/wifi-scripts/files/lib/netifd/wireless/mac80211.sh').read_text()
body=source[source.index('mac80211_hostapd_setup_bss() {'):source.index('\nmac80211_get_addr() {')]
with tempfile.TemporaryDirectory(prefix='eht-mld-render-') as td:
 root=Path(td).resolve();body=body.replace('/var/run/hostapd-',str(root)+'/hostapd-')
 prelude='''N='
'
append() { local name=$1 value=$2; eval "$name=\\\"\\${$name}\\${N}$value\\\""; }
set_default() { eval "[ -n \\\"\\${$1}\\\" ] || $1=$2"; }
json_get_vars() { local name; for name in "$@"; do case "$name" in mld) mld=${TEST_MLD:-};; wds_bridge) wds_bridge=;; *) eval "$name=0";; esac; done; }
hostapd_set_bss_options() { append hostapd_cfg 'wpa_key_mgmt=SAE'; append hostapd_cfg 'ieee80211w=2'; }
auth_type=sae vif=fixture vif_phy_suffix= epcs_params=
'''
 cases=[('HE80','absent',False),('HE80','group0',False),('EHT20','absent',False),('EHT80','',False),('EHT160','group0',True)]
 for index,(mode,mld,want) in enumerate(cases):
  env={**os.environ,'htmode':mode}
  if mld!='absent':env['TEST_MLD']=mld
  script=root/'render.sh';script.write_text(prelude+body+'\nmac80211_hostapd_setup_bss phy'+str(index)+' ap0 02:00:00:00:00:01 interface\n')
  p=subprocess.run(shlex.split(os.environ.get('TEST_ASH','/bin/sh'))+[str(script)],env=env,capture_output=True,text=True)
  assert p.returncode==0,(mode,mld,p.stderr)
  text=(root/f'hostapd-phy{index}.conf').read_text()
  assert ('mld_ap=1' in text)==want,(mode,mld,text)
  assert 'wpa_key_mgmt=SAE' in text and 'ieee80211w=2' in text
 print('PASS: actual SDK BSS rendering HE/EHT absent/empty MLD and explicit group; SAE/PMF unchanged')
