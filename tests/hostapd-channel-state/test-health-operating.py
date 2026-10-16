#!/usr/bin/env python3
"""Execute the full actual health sender; inject read-only IO and netlink state."""
import argparse,json,pathlib,re,subprocess,tempfile
p=argparse.ArgumentParser();p.add_argument('--health',type=pathlib.Path,required=True);p.add_argument('--modules',type=pathlib.Path,required=True);p.add_argument('--ucode',required=True);a=p.parse_args()
source=a.health.read_text();source=re.sub(r'^#![^\n]*\n','',source)
source='\n'.join(line for line in source.splitlines() if not line.startswith('import '))
source=re.sub(r'REQUIRE_SEARCH_PATH = \[.*?\];','',source,flags=re.S)
source=source.replace("require('wifi.iface')",'INPUT.wifi')
source=source.replace("let radio_operating = require('radio_operating');", "let REAL=require('radio_operating');let radio_operating={interfaces:()=>INPUT.raw,collect:(c,l,p,r)=>REAL.collect(c,l,p,r,(name,id)=>INPUT.status[name],()=>({source:'firmware',confirmed:true}))};")
source=source.replace("require('faults').snapshot()", "({active:INPUT.faults||[],monitoring:{storage:'available'}})")
pre=r'''
let INPUT=json(require('fs').readfile(ARGV[0])), REPORT, WRITTEN;
let libuci={cursor:()=>({load:()=>true,get:()=>null,get_all:name=>name=='wireless'?INPUT.config:{}})};
let libubus={connect:()=>({call:(object,method,args)=>{
 if(object=='network.interface')return {interface:[{interface:'up',data:{}}]};
 if(object=='network.wireless')return INPUT.live;
 if(object=='system')return {memory:{available:500,total:1000}};
 if(object=='ucentral'&&method=='health')REPORT=args;
 return {};}})};
let fs={stat:()=>null,glob:()=>[],readfile:()=>null,readlink:()=>null,popen:()=>null,open:()=>({write:data=>{WRITTEN=data;return true;},close:()=>true})};
let log=()=>null;
'''
fixture={'config':{'r':{'.type':'wifi-device','.name':'r','path':'fixture','band':'5g','ifname_prefix':'wlan'},'s':{'.type':'wifi-iface','device':'r','ssid':'Fixture','network':'up'}},'wifi':{'wlan0':{'ssid':'Fixture','mode':'ap','phy':9,'has_channel':True,'frequency':[5180]}},'live':{'r':{'up':True,'interfaces':[{'section':'s','ifname':'wlan0','config':{'ssid':'Fixture'}}]}},'raw':[{'ifname':'wlan0','iftype':3,'wiphy':9,'mac':'02:00:00:00:00:01','ssid':'Fixture','wiphy_freq':5180,'center_freq1':5210,'channel_width':3,'wiphy_tx_power_level':1700}], 'status':{'wlan0':{'state':'ENABLED','phy':'phy9','freq':'5180','channel':'36','ieee80211ax':'1','he_oper_chwidth':'1','he_oper_centr_freq_seg0_idx':'42','bss[0]':'wlan0','ssid[0]':'Fixture','bssid[0]':'02:00:00:00:00:01'}}}
def run(data):
 with tempfile.TemporaryDirectory(prefix='health-operating-') as tmp:
  root=pathlib.Path(tmp);(root/'input.json').write_text(json.dumps(data));(root/'program.uc').write_text(pre+source+"\nassert(sprintf('%J',REPORT)==sprintf('%J',WRITTEN),'persisted health must equal transmitted packet');print(sprintf('%J\\n',REPORT));\n")
  r=subprocess.run([a.ucode,'-L',str(a.modules/'*.uc'),str(root/'program.uc'),str(root/'input.json')],capture_output=True,text=True)
  assert r.returncode==0,r.stderr
  return json.loads(r.stdout)
checks=0
def check(value,label):
 global checks
 assert value,label;checks+=1
healthy=run(fixture);check(healthy['sanity']==100,'healthy legacy AP sanity unchanged');check(healthy['data']['radio_operating']['s']['status']=='confirmed','actual operating evidence in health packet')
broken=json.loads(json.dumps(fixture));broken['status']['wlan0']['channel']='1';r=run(broken)
check(r['sanity']<100,'stale channel is not green sanity');check(any(f['code']=='radio_operating_mismatch' and f['severity']=='critical' for f in r['data']['faults']['active']),'critical mismatch reaches actual sender')
missing=json.loads(json.dumps(fixture));missing['raw'][0].pop('wiphy_tx_power_level');r=run(missing)
check(r['sanity']==100 and r['data']['radio_operating']['s']['power']['status']=='unconfirmed','missing readback explicit without inventing radio failure')
power=json.loads(json.dumps(fixture));power['config']['r']['txpower']='0';r=run(power)
check(r['sanity']<100,'unapplied power target remains visible, not green')
check(r['data']['faults']['active']==[{'code':'radio_power_mismatch','resource':'s','severity':'warning','radio':'r'}],'power-only mismatch is warning in transmitted and persisted health')
combined=json.loads(json.dumps(power));combined['status']['wlan0']['channel']='1';r=run(combined)
check(any(f['severity']=='critical' for f in r['data']['faults']['active']),'channel plus power mismatch stays critical')
width=json.loads(json.dumps(power));width['status']['wlan0']['he_oper_chwidth']='2';r=run(width)
check(any(f['severity']=='critical' for f in r['data']['faults']['active']),'width plus power mismatch stays critical')
failed=json.loads(json.dumps(power));failed['status']['wlan0']['state']='DISABLED';r=run(failed)
check(any(f['severity']=='critical' for f in r['data']['faults']['active']),'failed radio stays critical')
storage=json.loads(json.dumps(power));storage['faults']=[{'code':'nand_ecc_failure','resource':'mtd2','severity':'critical'}];r=run(storage)
check(storage['faults'][0] in r['data']['faults']['active'],'NAND remains critical alongside power warning')
recovered=run(fixture);check(not recovered['data']['faults']['active'],'current mismatch clears after coherent evidence')
prior=json.loads(json.dumps(fixture));prior['faults']=[{'code':'nand_ecc_failure','resource':'mtd2','severity':'critical'}];r=run(prior)
check(r['data']['faults']['active']==prior['faults'],'pre-existing NAND fault preserved')
print(f'PASS {checks} actual full health sender/clear/persistence controls; transport/filesystem mocked, no AP I/O')
