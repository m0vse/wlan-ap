#!/usr/bin/env python3
"""Run actual RRM power setter/getter/action methods with simulated netlink ACKs."""
import argparse
import pathlib
import subprocess
import tempfile

p=argparse.ArgumentParser()
p.add_argument('--repo',type=pathlib.Path,required=True)
p.add_argument('--ucode',required=True)
a=p.parse_args()
base=a.repo/'feeds/ucentral/rrmd/files/usr/share/rrmd'
def method(path,signature):
    text=(base/path).read_text()
    start=text.index(signature)+len(signature)
    end=text.index('\n\t},',start)
    return text[start:end]+'\n}'
setter=method('phy.uc','\ttxpower: ')
getter=method('local.uc','\ttxpower: ')
command=(base/'command.uc').read_text()
local=(base/'local.uc').read_text()
resolver=local[local.index('function resolve_power_target('):local.index('\nreturn {',local.index('function resolve_power_target('))]
harness=r'''
let calls=[],ack=true,current={mac:'02:00:00:00:00:01',wiphy_tx_power_level:1700};
let global={nl80211:{const:{NL80211_CMD_GET_INTERFACE:1,NL80211_CMD_SET_WIPHY:2,NLM_F_ACK:4},request:(cmd,flags,attrs)=>{push(calls,{cmd,flags,attrs});return cmd==1?current:ack;}},local:{},event:{send:()=>null}};
let interfaces={fixture:{bssid:'02:00:00:00:00:02'}};
function sleep(ms){}
'''
checks=r'''
let n=0;function check(v,name){assert(v,name);n++;}
let first='02:00:00:00:00:01',second='02:00:00:00:00:02';
let msg={bssid:first,level:17};
check(setter(msg)===true&&calls[-1].attrs.wiphy_tx_power_level==1700&&calls[-1].attrs.mlo_link_id==null,'ordinary fresh MAC, no MLO selector');
ack=false;check(setter(msg)===false,'false ACK rejected');ack=null;check(setter(msg)===false,'null ACK rejected');ack={};check(setter(msg)===false,'unexpected object rejected');ack=true;
check(calls[0].flags==0&&calls[1].flags==4,'SET explicitly requests kernel ACK');
check(setter({...msg,level:0})===true&&calls[-1].attrs.wiphy_tx_power_level==0,'zero dBm valid');
check(setter({...msg,level:101})===false&&setter({...msg,level:'17'})===false,'bad power rejected');
current={mac:first,mlo_links:[{link_id:0,mac:first,wiphy_tx_power_level:1400},{link_id:7,mac:second,wiphy_tx_power_level:2300}]};
check(setter(msg)===true&&calls[-1].attrs.mlo_link_id===0,'first link selected explicitly including zero, despite cached secondary BSSID');
check(setter({...msg,bssid:second})===true&&calls[-1].attrs.mlo_link_id===7,'second link selected explicitly');
check(getter(first)===1400&&getter(second)===2300,'fresh per-link readbacks for both BSSIDs');
check(setter({...msg,bssid:uc(first)})===true,'case normalized');
let count=length(filter(calls,c=>c.cmd==2));
check(setter({...msg,bssid:'02:00:00:00:00:03'})===false,'unknown link rejected');
check(length(filter(calls,c=>c.cmd==2))==count,'unknown link sends no SET');
current={mac:first,mlo_links:[]};check(setter(msg)===false&&getter(first)==null,'empty MLO list never falls back to default MAC');
for (let malformed in [null,'bad',{},[null]]) {current={mac:first,mlo_links:malformed};check(setter(msg)===false,'malformed MLO snapshot fails closed');}
for (let bad in [{link_id:'0',mac:first},{link_id:-1,mac:first},{link_id:0,mac:42},{link_id:0}]) {current={mac:first,mlo_links:[bad]};check(setter(msg)===false,'invalid MLO identity types');}
current={mlo_links:[{link_id:16,mac:first}]};check(setter(msg)===false,'invalid link ID');
current={mlo_links:[{link_id:0,mac:first},{link_id:1,mac:first}]};check(setter(msg)===false&&getter(first)==null,'duplicate links rejected');
current={mac:first,wiphy_tx_power_level:1700};interfaces.duplicate={bssid:first};check(setter(msg)===false,'duplicate interface identity rejected');delete interfaces.duplicate;
current={mac:first,wiphy_tx_power_level:0};check(getter(first)===0,'legacy real zero');
current={mac:first};check(getter(first)==null,'legacy missing readback unavailable');
current=false;check(setter(msg)===false&&getter(first)==null,'failed GET cannot use cached identity');
check(setter({...msg,bssid:'invalid'})===false&&getter('')==null,'malformed target refused');
current={mlo_links:[{link_id:7,mac:second}],wiphy_tx_power_level:2400};check(getter(second)==null,'missing link readback cannot use default');
global.phy={txpower:()=>true};global.local.txpower=()=>null;
let result=command.handle({...msg,action:'tx_power'});
check(result.error==0&&result.level==null&&result.verification=='unconfirmed','ACK without readback unconfirmed');
global.local.txpower=()=>0;result=command.handle({...msg,action:'tx_power'});check(result.level===0,'command real zero');
global.phy.txpower=()=>false;check(command.handle({...msg,action:'tx_power'}).error==1,'request error');
print(sprintf('PASS %d actual RRM identity/setter/getter/action controls; netlink transport simulated, codec tested separately\n',n));
'''
with tempfile.TemporaryDirectory(prefix='rrm-power-test-') as temp:
    script=pathlib.Path(temp)/'test.uc'
    script.write_text(harness+'\n'+resolver+'\nglobal.local.txpower_target=resolve_power_target;\nlet setter='+setter+';\nlet getter='+getter+';\nlet command=(function(){\n'+command+'\n})();\n'+checks)
    subprocess.run([a.ucode,str(script)],check=True)
