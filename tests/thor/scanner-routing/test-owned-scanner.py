"""Run the real scanner handler under ARM ucode with netlink/sysfs boundaries mocked."""
from pathlib import Path
import subprocess,json,tempfile,sys
root,source=map(Path,sys.argv[1:]);w=Path(tempfile.mkdtemp(prefix='thor-owned-scan-'))
s=source.read_text().replace('require("nl80211")','mock_nl').replace('require("rtnl")','mock_rtnl').replace('sleep(', 'mock_sleep(');(w/'handler.uc').write_text(s)
cases=[('dual',{}),('single-renumbered',{'ids':[7,11,17],'drivers':{'17':'ath10k_pci'},'want':[17]}),('missing',{'drivers':{},'error':True}),('ambiguous',{'drivers':{'1':'ath10k_pci','3':'ath10k_pci'},'error':True}),('near-driver',{'drivers':{'3':'ath10k_pci_extra'},'error':True}),('other-board',{'board':'cambiumnetworks,xe3-4','want':[0,1,2,3]}),('create-owned',{'no_iface':True}),('legacy-scan-name-on-serving',{'no_iface':True,'legacy_name':True}),('owned-name-on-serving-refused',{'collision':True,'error':True}),('reuse-owned',{'owned':True}),('reuse-agent-station',{'agent':True}),('scanner-ap-not-reconfigured',{'ap':True}),('create-fails',{'no_iface':True,'create_fail':True,'error':True}),('ownership-unverified',{'no_iface':True,'wrong_owner':True,'error':True}),('link-fails',{'no_iface':True,'link_fail':True,'error':True}),('trigger-fails',{'trigger_fail':True,'error':True}),('timeout',{'timeout':True,'error':True}),('aborted',{'aborted':True,'error':True}),('disabled-frequencies-filtered',{'disabled':True}),('periodic',{'periodic':True}),('fragments',{'ids':[0,3,3,None],'want':[3,3]})]
h=r'''let c=json(ARGV[0]);let calls=[],status=null,sent=false,scanned=[];let selected=keys(c.drivers)[0];let scanner=+selected;
let ifaces=map(filter(c.ids,i=>i!=null),i=>({wiphy:i,iftype:2,dev:'fixture'+i,ifname:'fixture'+i,channel_width:1,wiphy_freq:5180}));
if(c.no_iface||c.ap)ifaces=filter(ifaces,i=>i.wiphy!=scanner);
if(c.ap)push(ifaces,{wiphy:scanner,iftype:3,dev:'scannerAP',ifname:'scannerAP',wiphy_freq:5260});
if(c.legacy_name)push(ifaces,{wiphy:0,iftype:3,dev:'scan',ifname:'scan'});
if(c.collision)push(ifaces,{wiphy:0,iftype:2,dev:'thor-scan',ifname:'thor-scan'});
if(c.owned||c.agent){ifaces=filter(ifaces,i=>i.wiphy!=scanner);push(ifaces,{wiphy:scanner,iftype:2,dev:c.owned?'thor-scan':'rrm-agent',ifname:c.owned?'thor-scan':'rrm-agent',channel_width:1});}
let defs={NL80211_CMD_GET_WIPHY:1,NL80211_CMD_GET_INTERFACE:2,NL80211_CMD_TRIGGER_SCAN:3,NL80211_CMD_GET_SCAN:4,NL80211_CMD_NEW_SCAN_RESULTS:5,NL80211_CMD_SCAN_ABORTED:6,NLM_F_DUMP:7,NL80211_CMD_NEW_INTERFACE:8,NL80211_CMD_DEL_INTERFACE:9};
let mock_nl={const:defs,error:()=>'',waitfor:()=>c.timeout?null:{cmd:c.aborted?6:5},request:(cmd,flags,p)=>{push(calls,{cmd,p});if(cmd==1)return map(c.ids,i=>({wiphy:i,wiphy_bands:[{freqs:[{freq:2412},{freq:2484,disabled:true},{freq:5180,dfs_state:1}]}]}));if(cmd==2)return ifaces;if(cmd==8){if(c.create_fail)return false;push(ifaces,{wiphy:c.wrong_owner?0:p.wiphy,iftype:2,dev:p.ifname,ifname:p.ifname,channel_width:1});return true;}if(cmd==9){ifaces=filter(ifaces,i=>i.dev!=p.dev);return true;}if(cmd==3)return c.trigger_fail?false:true;if(cmd==4){let iface=filter(ifaces,i=>i.dev==p.dev)[0];push(scanned,iface.wiphy);return [];}return true;}};
let mock_rtnl={const:{RTM_NEWLINK:10},request:(cmd,flags,p)=>{push(calls,{cmd,p});return c.link_fail?false:true;}};
let fs={readfile:()=>c.board,readlink:path=>{let m=match(path,/phy([0-9]+)/);return '/sys/bus/pci/drivers/'+(c.drivers[m[1]]||'ath11k');},stat:()=>null};let ctx={call:(obj,method,p)=>{if(obj=='ucentral'&&method=='send'){sent=true;return {};}assert(c.board!='cambiumnetworks,xv3-8','scanner tried AP channel change');return {};}};let args={override_dfs:true,periodic:c.periodic||false};let mock_sleep=()=>null;
include(ARGV[1],{mock_nl,mock_rtnl,fs,ctx,args,mock_sleep,result_json:r=>{status=r;}});
if(c.error){assert(status.error==1,'missing failure');assert(!length(scanned),'failure returned cached results');assert(!sent,'failure sent success');}else{assert(sprintf('%J',scanned)==sprintf('%J',c.want),'wrong scanned PHYs');assert(c.periodic?sent:status.error==0,'missing success');}
if(c.board=='cambiumnetworks,xv3-8')for(let call in calls){if(call.cmd==8)assert(call.p.wiphy==scanner&&call.p.ifname=='thor-scan','create touched serving PHY');if(call.cmd==9)assert(call.p.dev=='thor-scan','delete touched another interface');if(call.cmd==10)assert(call.p.dev=='thor-scan','link mutation outside owned scanner');if(call.cmd==3&&type(call.p.scan_frequencies)=='array')assert(length(call.p.scan_frequencies)==1&&call.p.scan_frequencies[0]==2412,'requested unsupported 2G frequency');}
if(c.collision||c.wrong_owner)assert(!length(filter(calls,i=>i.cmd==9||i.cmd==10||i.cmd==3)),'unverified interface mutated');
if(c.legacy_name)assert(length(filter(ifaces,i=>i.dev=='scan'))==1,'serving scan-name deleted');
if(c.agent)assert(length(filter(ifaces,i=>i.dev=='rrm-agent'))==1,'existing agent iface deleted');
printf('PASS %s
',c.name);
'''
(w/'test.uc').write_text(h)
for name,options in cases:
 c={'name':name,'board':'cambiumnetworks,xv3-8','ids':[0,1,2,3],'drivers':{'3':'ath10k_pci'},'want':[3],**options}
 r=subprocess.run(['/usr/bin/qemu-aarch64','-L',str(root),str(root/'usr/bin/ucode'),str(w/'test.uc'),json.dumps(c),str(w/'handler.uc')],capture_output=True,text=True)
 if r.returncode:raise SystemExit(name+'\n'+r.stdout+r.stderr)
 print(r.stdout.strip().splitlines()[-1])
print('PASS '+str(len(cases))+' owned scanner ARM controls; no live scan or AP changes')
