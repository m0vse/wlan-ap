#!/usr/bin/env python3
"""Actual renderer/UCI -> qualified health proof -> rrmd cache/events, offline."""
from pathlib import Path
import argparse,json,tempfile,subprocess,shutil,re,os
p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--generated',type=Path);p.add_argument('--baseline-local',type=Path);a=p.parse_args();repo=a.repo.resolve();root=a.root.resolve();output=a.output.resolve();output.mkdir(parents=True,exist_ok=True)
def run(cmd,**kw):return subprocess.run([str(x)for x in cmd],check=True,text=True,**kw)
with tempfile.TemporaryDirectory(prefix='rrm-mlo-reporting-')as temp:
 w=Path(temp)
 base=['qemu-aarch64','-L',root,root/'usr/bin/ucode','-L',root/'usr/lib/ucode','-L',str(root/'usr/share/ucentral/*.uc')]
 if a.generated:cfg=json.loads(a.generated.read_text())
 else:
  w=Path(temp);shadow=w/'runtime';shadow.mkdir()
  for rel in ['lib','sbin','etc','usr/bin','usr/lib']:
   q=shadow/rel;q.parent.mkdir(parents=True,exist_ok=True);q.symlink_to(root/rel,target_is_directory=True)
  share=shadow/'usr/share/ucentral';shutil.copytree(root/'usr/share/ucentral',share)
  # Existing suite deliberately needs a pre109 negative control. Keep exact
  # new runtime/libraries; reverse ONLY109 in this disposable renderer copy.
  run(['patch','--batch','-R','-F0','-p2','-i',repo/'feeds/ucentral/ucentral-schema/patches/109-unique-ssid-sections-for-shared-band-phys.patch'],cwd=share,stdout=subprocess.DEVNULL)
  rendered=run(['python3',repo/'tests/shared-band-ssid/run-tests.py','--root',shadow],capture_output=True);(output/'renderer.log').write_text(rendered.stdout+rendered.stderr)
  fixture=Path(re.search(r'^work (.+)$',rendered.stdout,re.M)[1]);stage=max(fixture.glob('uci-*'),key=lambda f:f.stat().st_mtime_ns)
  base=['qemu-aarch64','-L',root,root/'usr/bin/ucode','-L',root/'usr/lib/ucode','-L',str(root/'usr/share/ucentral/*.uc')]
  extract="let c=require('uci').cursor(ARGV[0],ARGV[1]);printf('%J',c.get_all('wireless'));"
  cfg=json.loads(run([*base,'-e',extract,stage/'config',stage/'saved'],capture_output=True).stdout)
 assert cfg['ml0_0']['.type']=='wifi-mld'and'ifname'not in cfg['ml0_0']
 (output/'generated-wireless.synthetic.json').write_text(json.dumps(cfg,indent=2)+'\n')
 # Compile/run the actual complete local module and view helper. Only external
 # IO/timer/ubus/native boundaries are injected; qualified health is unchanged.
 event=(repo/'feeds/ucentral/rrmd/files/usr/share/rrmd/event.uc').read_text();module=(repo/'feeds/ucentral/rrmd/files/usr/share/rrmd/mlo_views.uc').read_text();local=(a.baseline_local or repo/'feeds/ucentral/rrmd/files/usr/share/rrmd/local.uc').read_text()
 phy=(repo/'feeds/ucentral/rrmd/files/usr/share/rrmd/phy.uc').read_text();start=phy.index('\ttxpower: ')+len('\ttxpower: ');setter=phy[start:phy.index('\n\t},',start)]+'\n}'
 pre=r'''
let fs=require('fs'),health=require('mlo_health'),wireless=json(fs.readfile(ARGV[0]));
let checks=0;function check(v,n){assert(v,n);checks++;}
let sections=filter(keys(wireless),k=>wireless[k]['.type']=='wifi-iface'&&wireless[k].mld=='ml0_0');
check(length(sections)==2,'real generated config has two MLO sections');
let five=filter(sections,k=>wireless[wireless[k].device].band=='5g')[0],six=filter(sections,k=>wireless[wireless[k].device].band=='6g')[0];
let ssid=wireless[five].ssid,first='02:00:00:00:00:11',second='02:00:00:00:00:22',mld='02:00:00:00:00:10';
let link0={link_id:0,mac:first,wiphy_freq:5745,channel_width:2,center_freq1:5755,wiphy_tx_power_level:1400},link7={link_id:7,mac:second,wiphy_freq:6275,channel_width:5,center_freq1:6345,wiphy_tx_power_level:2300};
let raw={ifname:'ml0_0',iftype:3,wiphy:1,mac:mld,ssid,mlo_links:[link0,link7]};
let cfg=wireless,events=[],calls=[],listeners={},subscribes=[],notifications=[],timers=[],clock=100,native_failure=false,status_failure=false,queries=0,config_reads=0;
function time(){return clock;}
function ulog_info(...v){}function ulog_err(...v){}function ulog_warn(...v){}
let status={ssid,bssid:second,freq:6275,channel:65,op_class:134,uci_section:six,phy:'phy01.'+wireless[wireless[six].device].radio};
let native={const:{NL80211_CMD_GET_INTERFACE:1,NL80211_CMD_SET_WIPHY:2,NLM_F_ACK:4},request:(cmd,flags,attrs)=>{push(calls,{cmd,flags,attrs});if(cmd==1){if(native_failure)die('native failure');return raw;}let selected=filter(raw.mlo_links||[],l=>l.link_id===attrs.mlo_link_id);if(attrs.dev!='ml0_0'||length(selected)!=1)return false;selected[0].wiphy_tx_power_level=attrs.wiphy_tx_power_level;return true;}};
modules.nl80211=native;
let global={nl80211:native,config:{station_stats_interval:0},event:{send:(type,payload)=>push(events,{type,payload})},neighbor:{local_del:()=>null,local_add:()=>null,update:()=>null},scan:{add_wdev:(dev,phy)=>check(dev=='ml0_0'||dev=='wlan0','scan always receives real transport')},uloop:{timer:(ms,cb)=>{let t={ms,cancelled:false};t.cb=()=>{t.cancelled=true;cb();};t.cancel=()=>{t.cancelled=true;};push(timers,t);return t;}},ubus:{conn:{call:(path,method,args)=>{check(path=='ucentral'||path=='hostapd.ml0_0'||path=='hostapd.wlan0','no invented hostapd transport');if(path=='ucentral'){check(method=='event'&&type(args.type)=='string'&&type(args.payload)=='object','actual native event wrapper contract');push(events,args);return null;}if(method=='get_status')return status;if(method=='rrm_nr_get_own')return {value:[status.bssid,status.ssid,'synthetic']};return null;},subscriber:(cb)=>{push(notifications,cb);return {subscribe:path=>push(subscribes,path)};},listener:(type,cb)=>{listeners[type]=cb;},list:()=>['hostapd.ml0_0']}}};
let uci={get_all:(name,section)=>name=='wireless'?cfg:{}};modules.uci={cursor:()=>{config_reads++;return uci;}};
'''
 io=r'''
let original_collect=views.collect;
views.collect=(transports,config,io)=>{
 io.health=health;io.phy_index=name=>name=='phy01'?1:null;io.radio_phy=r=>1;
 io.status=(dev,id)=>{queries++;if(status_failure)return null;let section=id==0?five:six,radio=wireless[wireless[section].device].radio,link=id==0?link0:link7;
 return health.fields('state=ENABLED\nphy=phy01.'+radio+'\nfreq='+link.wiphy_freq+'\nchannel='+(id==0?(link.wiphy_freq==5785?157:149):65)+'\nop_class='+(id==0?116:134)+'\nbss[0]=ml0_0\nbssid[0]='+link.mac+'\nssid[0]='+health.encoded_ssid(ssid)+'\nmld_addr[0]='+mld+'\nmld_link_id[0]='+id+'\n');};
 return original_collect(transports,config,io);
};modules.mlo_views=views;
'''
 checks=r'''
global.local.init();
let rows=global.local.status();check(length(rows)==1&&exists(rows,'ml0_0'),'transport key remains real interface');
check(length(rows.ml0_0.mlo_links)==2,'interfaces method itself exposes both proven links');
let bss=global.local.bsses();check(length(bss)==2&&bss[first].ifname=='ml0_0'&&bss[second].ifname=='ml0_0','both BSS views retain one actual transport');
check(bss[first].phy=='phy01.'+wireless[wireless[five].device].radio&&bss[second].phy=='phy01.'+wireless[wireless[six].device].radio,'driver radio indexes from per-link status and actual generated UCI');
check(bss[first].mlo_link_id===0&&bss[second].mlo_link_id===7,'link IDs not assumed radio indexes; zero preserved');
check(bss[first].band=='5G'&&bss[first].freq==5745&&bss[first].channel==149&&bss[second].band=='6G'&&bss[second].channel==65,'per-link band/frequency/channel');
check(bss[first].wiphy_tx_power_level==1400&&bss[second].wiphy_tx_power_level==2300,'per-link real power metadata');
check(!bss[first].rrm_nr&&bss[second].rrm_nr[0]==second,'secondary neighbor report never copied to first');
check(length(filter(events,e=>e.type=='rrm.bss.add'))==2&&!exists(bss,mld),'two adds; no phantom MLD/parent BSS');
check(length(subscribes)==1&&queries==2,'one real subscription and one bounded status read per link');
let n=length(calls),nconfig=config_reads;global.local.status();global.local.bsses();check(length(calls)==n&&config_reads==nconfig,'repeated status within refresh interval cached');
global.local.reload();check(length(events)==2&&length(subscribes)==1,'reload produces no duplicate BSS events/subscriptions');
check(global.local.bssid_to_ifname(first)=='ml0_0'&&global.local.bssid_to_ifname(second)=='ml0_0','both BSSID lookups use real transport');
check(global.local.bssid_to_phy(first)==1&&global.local.bssid_to_phy(second)==1,'both BSSID physical identities');
// Simulated native SET applies only the explicit link selector. Observe the
// complete rrmd readback after each change; this is not an RF hardware test.
for (let step in [{bssid:first,level:12,own:1200,peer:2300},{bssid:first,level:14,own:1400,peer:2300},{bssid:second,level:20,own:2000,peer:1400},{bssid:second,level:23,own:2300,peer:1400}]) {
 let peer=step.bssid==first?second:first, prior=global.local.bsses()[peer];
 let request_count=length(calls);check(setter(step)===true,'scoped power step acknowledged');
 let sent=filter(slice(calls,request_count),c=>c.cmd==2);
 check(length(sent)==1&&sent[0].flags===4&&sent[0].attrs.dev=='ml0_0'&&sent[0].attrs.mlo_link_id===(step.bssid==first?0:7)&&sent[0].attrs.wiphy_tx_power_level==step.own,'one SET selects exact link including zero and encodes mBm');
 global.local.reload();let now=global.local.bsses();
 check(now[step.bssid].wiphy_tx_power_level==step.own&&now[peer].wiphy_tx_power_level==step.peer,'selected power changes and peer power retained');
 check(now[peer].freq==prior.freq&&now[peer].channel==prior.channel&&now[peer].mlo_link_id===prior.mlo_link_id&&length(now)==2,'peer identity/channel and both proven links retained');
}
calls=filter(calls,c=>c.cmd!=2);
let before=length(calls);check(global.local.switch_chan({bssid:first,channel:36})===false&&global.local.switch_chan({bssid:second,channel:1})===false,'shared unscoped channel command fails closed on either link');
check(!length(filter(calls,c=>c.cmd==2)),'reporting and channel refusal send no SET');
check(setter({bssid:first,level:12})===true&&calls[-1].attrs.dev=='ml0_0'&&calls[-1].attrs.mlo_link_id===0&&calls[-1].flags===4,'existing exact first-link setter/ACK preserved');
check(setter({bssid:second,level:20})===true&&calls[-1].attrs.mlo_link_id===7&&calls[-1].attrs.wiphy_tx_power_level==2000,'existing second-link setter preserved');
check(global.local.txpower(first)==1200&&global.local.txpower(second)==2000,'fresh native setter readback stays per-link');
link0.wiphy_tx_power_level=1400;link7.wiphy_tx_power_level=2300;
link0.wiphy_freq=5785;link0.center_freq1=5795;events=[];
let notice={type:'channel-switch',data:{bssid:first,freq:5785},reply:()=>null};notifications[0](notice);
check(length(events)==1&&events[0].type=='rrm.bss.channel-switch'&&events[0].payload.bssid==first&&events[0].payload.freq==5785,'coherent first-link change emits one scoped event');
check(global.local.bsses()[first].channel==157&&global.local.bsses()[second].freq==6275,'channel event refresh preserves peer');
notifications[0](notice);check(length(events)==1,'same channel notification not duplicated');
link0.wiphy_freq=5745;link0.center_freq1=5755;global.local.reload();
let reduced={...wireless};delete reduced[five];cfg=reduced;events=[];let before_config=config_reads;global.local.reload();
check(config_reads>before_config&&length(global.local.bsses())==1&&global.local.bsses()[second],'reload obtains fresh generated UCI and retains surviving section');
check(length(events)==1&&events[0].type=='rrm.bss.del'&&events[0].payload.bssid==first,'removed generated section withdraws only matching BSS');
cfg=wireless;events=[];global.local.reload();check(length(events)==1&&events[0].type=='rrm.bss.add'&&events[0].payload.bssid==first,'restored generated section publishes one link');
raw.mlo_links=[link7];events=[];global.local.reload();check(length(global.local.status().ml0_0.mlo_links)==1&&global.local.bsses()[second],'removed first link keeps survivor');
check(length(events)==1&&events[0].type=='rrm.bss.del'&&events[0].payload.bssid==first,'one deletion only for removed link');
global.local.reload();check(length(events)==1,'repeated removal does not repeat deletion');
raw.mlo_links=[link7,link0];events=[];global.local.reload();check(length(events)==1&&events[0].type=='rrm.bss.add'&&events[0].payload.bssid==first,'reordered re-add adds only missing peer');
check(global.local.status().ml0_0.mlo_links[0].mlo_link_id===0,'stable explicit link ordering');
status_failure=true;events=[];global.local.reload();check(length(global.local.bsses())==0&&length(global.local.status().ml0_0.mlo_links)==0,'failed link proof withdraws stale views without parent fallback');
check(length(events)==2&&length(filter(events,e=>e.type=='rrm.bss.del'))==2,'one del per stale link');
global.local.reload();check(length(events)==2,'repeated proof failure no duplicate deletions');
status_failure=false;events=[];global.local.reload();check(length(events)==2&&length(global.local.bsses())==2,'recovery restores two exact BSSs');
raw.mlo_links=[link0,{...link7,link_id:0}];global.local.reload();check(length(global.local.bsses())==0,'duplicate native IDs fail closed');
raw.mlo_links=[link0,{...link7,mac:first}];global.local.reload();check(length(global.local.bsses())==0,'duplicate native BSSIDs fail closed');
raw.mlo_links=[link0,link7];global.local.reload();native_failure=true;global.local.reload();check(length(global.local.bsses())==0,'native failure never publishes stale/default BSS');native_failure=false;global.local.reload();
let active=filter(timers,t=>!t.cancelled);check(length(active)==1&&active[0].ms==5000,'one bounded read-only MLO refresh timer');
raw.mlo_links=[link7];events=[];active[0].cb();check(length(events)==1&&events[0].payload.bssid==first,'timer handles link removal without object removal/reload');
events=[];listeners['ubus.object.remove']('ubus.object.remove',{path:'hostapd.ml0_0'});check(length(events)==1&&events[0].payload.bssid==second,'object removal deletes remaining link once');
check(length(global.local.status())==0&&length(global.local.bsses())==0,'object removal clears transport and BSS views');
// Legacy-only instance requires neither MLO helper/status IO nor native dump.
cfg={};status={ssid:'Legacy fixture',bssid:'02:00:00:00:01:01',freq:2412,channel:1,op_class:81,uci_section:'legacy',phy:'phy0'};raw={ifname:'wlan0',mac:status.bssid,wiphy:0,wiphy_tx_power_level:1700};events=[];let old_queries=queries,old_calls=length(calls);
listeners['ubus.object.add']('ubus.object.add',{path:'hostapd.wlan0'});let legacy=global.local.status().wlan0;
check(legacy.ssid==status.ssid&&legacy.bssid==status.bssid&&legacy.phy=='phy0'&&legacy.band=='2G'&&!exists(legacy,'mlo_links'),'legacy interface fields and key preserved');
check(queries==old_queries&&length(calls)==old_calls,'legacy reporting invokes no MLO/native sampling');
check(length(events)==1&&events[0].type=='rrm.bss.add'&&events[0].payload.bssid==status.bssid&&!exists(events[0].payload,'mlo_link_id'),'legacy single add unchanged');
global.local.reload();check(length(events)==1,'legacy reload deduplicated');
check(!length(filter(timers,t=>!t.cancelled)),'legacy-only state has no MLO refresh timer');
check(global.local.switch_chan({bssid:status.bssid,channel:6})===true,'ordinary non-MLO channel path retained');
listeners['ubus.object.remove']('ubus.object.remove',{path:'hostapd.wlan0'});check(events[-1].type=='rrm.bss.del'&&events[-1].payload.bssid==status.bssid,'legacy deletion contains BSSID string not whole object');
for(let legacy_band in [{freq:5745,channel:149,band:'5G',phy:'phy1'},{freq:6275,channel:65,band:'6G',phy:'phy2'}]) {
 status={ssid:'Legacy fixture',bssid:'02:00:00:00:01:01',freq:legacy_band.freq,channel:legacy_band.channel,op_class:81,uci_section:'legacy',phy:legacy_band.phy};
 raw={ifname:'wlan0',mac:status.bssid,wiphy:0,wiphy_tx_power_level:1700};events=[];let q=queries,c=length(calls);
 listeners['ubus.object.add']('ubus.object.add',{path:'hostapd.wlan0'});
 check(global.local.status().wlan0.band==legacy_band.band&&!exists(global.local.status().wlan0,'mlo_links'),'ordinary '+legacy_band.band+' row unchanged');
 check(queries==q&&length(calls)==c,'ordinary '+legacy_band.band+' has no native/MLO sampler');
 check(length(events)==1&&events[0].type=='rrm.bss.add','ordinary '+legacy_band.band+' single event');
 listeners['ubus.object.remove']('ubus.object.remove',{path:'hostapd.wlan0'});
}
print(sprintf('PASS %d actual generated-UCI / qualified-health / complete rrmd cache-event lifecycle controls; external IO injected, no AP changes\n',checks));
'''
 program=w/'test.uc';program.write_text(pre+'\nglobal.event=(function(){\n'+event+'\n})();\nlet views=(function(){\n'+module+'\n})();\n'+io+'\nglobal.local=(function(){\n'+local+'\n})();\nlet setter='+setter+';\n'+checks)
 (output/'test-program.synthetic.uc').write_text(program.read_text())
 result=subprocess.run([str(x)for x in [*base,program,output/'generated-wireless.synthetic.json']],capture_output=True,text=True);(output/'reporting-tests.log').write_text(result.stdout+result.stderr);print(result.stdout,end='')
 if a.baseline_local:
  assert result.returncode!=0 and 'interfaces method itself exposes both proven links' in result.stderr,(result.stdout,result.stderr)
  print('PASS actual installed pre-fix source negative control: second MLO interface view missing')
 else:
  assert result.returncode==0,(result.stdout,result.stderr)
  run(['python3',repo/'tests/rrm-mlo-reporting/default-loader.py','--repo',repo,'--root',root,'--generated',output/'generated-wireless.synthetic.json','--output',output/'default-loader'])
