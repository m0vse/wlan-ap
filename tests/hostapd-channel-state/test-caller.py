#!/usr/bin/env python3
"""Run the actual ucode iface-add caller with successful/failed native-start results."""
import argparse,pathlib,subprocess,tempfile
p=argparse.ArgumentParser();p.add_argument('--source',type=pathlib.Path,required=True);p.add_argument('--ucode',required=True);p.add_argument('--negative-control',action='store_true');a=p.parse_args()
s=a.source.read_text();start=s.index('function iface_add(');end=s.index('\nfunction iface_config_macaddr_list',start);body=s[start:end]
harness=r'''
let verdict=true;
let iface={start:()=>verdict};
let hostapd={add_iface:()=>0,interfaces:{fixture:iface},printf:()=>null};
function iface_freq_info(i,c,p){return p;}
function iface_gen_config(c,enabled){return 'fixture';}
'''
checks=r'''
let config={radio_idx:1,bss:[{ifname:'fixture'}]};
if(iface_add('fixture',config,{frequency:5955})!=true)die('successful start rejected');
verdict=false;
if(iface_add('fixture',config,{frequency:5955})!=false)die('failed start treated as success');
verdict=null;
if(iface_add('fixture',config,{frequency:5955})!=false)die('missing start result treated as success');
print('PASS 3 actual ucode caller controls: true accepted, false/null rejected\n');
'''
with tempfile.TemporaryDirectory(prefix='hostapd-channel-caller-') as t:
 f=pathlib.Path(t)/'caller.uc';f.write_text(harness+body+checks)
 r=subprocess.run([a.ucode,str(f)],capture_output=True,text=True)
 if a.negative_control:assert r.returncode!=0;print('PASS negative control: old ucode caller reports false/null as success')
 else:print(r.stdout,end='');print(r.stderr,end='');assert r.returncode==0
