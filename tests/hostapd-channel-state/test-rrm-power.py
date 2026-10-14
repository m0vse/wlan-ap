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
harness=r'''
let calls=[],ack=true,current={wiphy_tx_power_level:1700};
let global={nl80211:{const:{NL80211_CMD_GET_INTERFACE:1,NL80211_CMD_SET_WIPHY:2},request:(cmd,flags,attrs)=>{push(calls,{cmd,attrs});return cmd==1?current:ack;}},local:{bssid_to_ifname:()=> 'fixture'},event:{send:()=>null}};
let interfaces={fixture:{bssid:'02:00:00:00:00:01'}};
function sleep(ms){}
'''
checks=r'''
let n=0;function check(v,name){assert(v,name);n++;}
let msg={bssid:'02:00:00:00:00:01',level:17};
check(setter(msg)===true&&calls[-1].attrs.wiphy_tx_power_level==1700,'ordinary accepted ACK');
ack=false;check(setter(msg)===false,'false ACK rejected');ack=null;check(setter(msg)===false,'null ACK rejected');ack=true;
check(setter({...msg,level:0})===true&&calls[-1].attrs.wiphy_tx_power_level==0,'zero dBm is valid');
check(setter({...msg,level:101})===false&&setter({...msg,level:'17'})===false,'bad power rejected');
current={mlo_links:[{link_id:7,mac:msg.bssid,wiphy_tx_power_level:1700}]};
check(setter(msg)===true&&calls[-1].attrs.mlo_link_id==7,'exact MLO link selected');
let before=length(calls);current={mlo_links:[{link_id:0,mac:'04:00:00:00:00:01'}]};
check(setter(msg)===false&&length(calls)==before+1,'missing BSSID cannot set default link');
current={mlo_links:[{link_id:16,mac:msg.bssid}]};check(setter(msg)===false,'invalid link ID refused');
current={mlo_links:[{link_id:0,mac:msg.bssid},{link_id:1,mac:msg.bssid}]};check(setter(msg)===false,'ambiguous link identity refused');
current={wiphy_tx_power_level:0};check(getter(msg.bssid)===0,'real zero readback preserved');
current={};check(getter(msg.bssid)==null,'missing readback never zero');
current=false;check(getter(msg.bssid)==null,'failed GET unavailable');
current={mlo_links:[{link_id:7,mac:msg.bssid,wiphy_tx_power_level:1900}]};check(getter(msg.bssid)===1900,'MLO readback from matching link');
current={mlo_links:[{link_id:7,mac:'04:00:00:00:00:01',wiphy_tx_power_level:1900}],wiphy_tx_power_level:2400};check(getter(msg.bssid)==null,'MLO unavailable cannot use default link power');
check(getter('06:00:00:00:00:01')==null,'unknown BSSID unavailable');
global.phy={txpower:()=>true};global.local.txpower=()=>null;
let result=command.handle({...msg,action:'tx_power'});
check(result.error==0&&result.level==null&&result.verification=='unconfirmed','accepted request without readback not claimed confirmed');
global.local.txpower=()=>0;result=command.handle({...msg,action:'tx_power'});
check(result.level===0&&result.verification=='driver_reported','action preserves real zero');
global.phy.txpower=()=>false;check(command.handle({...msg,action:'tx_power'}).error==1,'failed request returns action error');
print(sprintf('PASS %d actual RRM power controls; netlink mocked, no AP I/O\n',n));
'''
with tempfile.TemporaryDirectory(prefix='rrm-power-test-') as temp:
    script=pathlib.Path(temp)/'test.uc'
    script.write_text(harness+'\nlet setter='+setter+';\nlet getter='+getter+';\nlet command=(function(){\n'+command+'\n})();\n'+checks)
    subprocess.run([a.ucode,str(script)],check=True)
