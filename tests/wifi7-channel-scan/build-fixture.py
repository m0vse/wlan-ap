from pathlib import Path
import sys
# Extract the actual prepared handler; run the generated fixture with native ucode.
s=Path(sys.argv[1]).read_text()
freq=s[s.index('function frequency_to_channel('):s.index('function hostapd_dev(')]
host=s[s.index('function hostapd_dev('):s.index('function override_dfs(')]
trigger=s[s.index('function trigger_scan() {'):s.index('\n\noverride_dfs();')]
finish=s[s.index('let failed = length(scan_failures)'):]
harness=r'''
let fs=require('fs');
let test=+ARGV[0];
let args={active:test==6||test>=11,verbose:test==6,override_dfs:false,periodic:test==7||test==8};
let def={NL80211_CMD_GET_INTERFACE:1,NL80211_CMD_GET_SCAN:2,NLM_F_DUMP:4};
let scan=[];let scan_failures=[];let scan_radios=0;let commands=[];let dumps=[];let result;
let map={'phy2g-ap0':0,'phy2g-ap1':0,'phy5g-ap0':1,'phy6g-ap0':2};
let objects=['hostapd','hostapd.phy2g-ap0','hostapd.phy5g-ap0','hostapd.phy6g-ap0'];
if(test==1) push(objects,'hostapd.phy2g-ap1');
if(test==3) objects=['hostapd'];
if(test==11) objects=['hostapd.phy2g-ap0'];
if(test==12) objects=['hostapd.phy2g-ap0','hostapd.phy5g-ap0'];
if(test==13) objects=['hostapd.phy6g-ap0'];
let ubus={list:()=>objects};
let nl={request:(cmd,flags,p)=>{
 let phy=map[p.dev];
 if(cmd==1) return test==4&&phy==1?false:{wiphy:phy,wiphy_freq:[2412,5180,5955][phy]};
 push(dumps,phy);
 if(test==5&&phy==2)return false;
 if(test==10||test==9&&phy==2)return null;
 return [{bss:{bssid:'00:00:00:00:00:01',frequency:[2412,5180,5955][phy],signal_mbm:-5000,beacon_ies:[{type:0,data:'fixture'},{type:61,data:'ht'}]}}];
}};
let system=(cmd)=>{
 let dev=split(cmd,' ')[2];push(commands,dev);
 let passive=!args.active||map[dev]==2;
 if(!passive && index(cmd,"ssid ''")<0)die('active flag missing for 2/5 GHz');
 if(passive && index(cmd,'passive')<0)die('passive discovery missing');
 return (test==2||test==8)&&map[dev]==1?1:0;
};
let result_json=(s)=>{result=s;};
let ctx={call:(obj,method,p)=>{result={error:p.params.error||0,scan:p.params.data,periodic:true};}};
'''
# Place the actual final-result code in a function so its periodic return is local.
run='function run() {\ntrigger_scan();\n'+finish+'\n}\nrun();\n'
checks=r'''
let expected_error=(test==2||test==3||test==4||test==5||test==8)?1:0;
let expected_count=test==3||test==10?0:test==11||test==13?1:test==12||test==9||expected_error?2:3;
if(result.error!=expected_error||length(result.scan)!=expected_count)die(sprintf('case%d result mismatch\n',test));
if(test==1&&(length(commands)!=3||length(dumps)!=3))die('duplicate PHY scanned');
if(test==11&&length(commands)!=1)die('2 GHz-only AP scanned absent bands');
if(test==12&&length(commands)!=2)die('dual-band AP scanned absent 6 GHz');
if(test==13&&length(commands)!=1)die('6 GHz-only AP scanned absent bands');
if((test==2||test==8)&&index(dumps,1)>=0)die('failed scan fetched stale cache');
if(test==6&&!result.scan[0].ht_oper)die('verbose HT information missing');
if(test!=7&&test!=8&&result.resultCode!=(expected_error?0:1))die('resultCode mismatch');
printf('PASS case%d records=%d error=%d\n',test,length(result.scan),result.error);
'''
Path(sys.argv[2]).write_text(harness+freq+host+trigger+run+checks)
