#!/usr/bin/env python3
"""Execute selected hostapd reload code for a power-only configuration update.

Power is applied by mac80211.sh before config_set; it is absent from the
generated hostapd radio/BSS configuration. Hardware and daemon objects are
fixtures. This does not replace an on-device update test.
"""
from pathlib import Path
import argparse
import subprocess
import tempfile

p = argparse.ArgumentParser()
p.add_argument('--ucode', required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[2]
source = (repo / 'feeds/qca-wifi-7/hostapd/files/hostapd.uc').read_text()

def function(name):
    start = source.index('function ' + name + '(')
    return source[start:source.index('\nfunction ', start + 1)]

script = r'''
let restarts=0, removals=0, updates=0;
function is_equal(a,b) { return sprintf('%J',a)==sprintf('%J',b); }
function phy_open(name, radio) { return {name,radio}; }
function iface_restart() { restarts++;return 0; }
function iface_remove() { removals++;return 0; }
function iface_update_supplicant_macaddr() { updates++; }
let hostapd={data:{config:{},pending_config:{}},interfaces:{},bss:{},
 printf:()=>null,remove_iface:()=>{removals++;}};
function configuration(radio) {
 return {phy:'phy1',radio_idx:radio,radio:['channel=1','hw_mode=a'],
         bss:[{ifname:radio?'ml0_0-link7':'ml0_0-link0',data:['ssid=fixture'],hash:{}}]};
}
''' + function('iface_reload_config') + function('iface_set_config') + r'''
hostapd.data.config['phy1:0']=configuration(0);
hostapd.data.config['phy1:1']=configuration(1);
let peer=sprintf('%J',hostapd.data.config['phy1:0']);
for(let i=0;i<100;i++) {
 assert(iface_set_config('phy1:1',1,configuration(1))===0,'power-only reload accepted');
 assert(restarts==0&&removals==0,'neither radio removed or restarted');
 assert(sprintf('%J',hostapd.data.config['phy1:0'])==peer,'peer config preserved');
}
assert(updates==100,'all reloads exercised');
// Negative control: a real channel/config change must reach restart.
let changed=configuration(1);changed.radio=['channel=5','hw_mode=a'];
assert(iface_set_config('phy1:1',1,changed)===0&&restarts==1,'restart instrumentation active');
print('PASS 100 actual hostapd power-only reloads preserve both interfaces; real channel change negative control restarts\n');
'''
with tempfile.TemporaryDirectory(prefix='qsdk-power-reload-') as td:
    path = Path(td) / 'test.uc'
    path.write_text(script)
    subprocess.run([a.ucode, str(path)], check=True)
