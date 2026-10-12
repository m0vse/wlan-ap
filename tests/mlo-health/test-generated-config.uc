// Identity fields captured from Miami's actual generated UCI, 12 October 2026.
// Secrets/site values removed; SSID and MACs replaced. Never add group.ifname.
import * as fs from 'fs';
let m=require('mlo_health'),cfg=json(fs.readfile(ARGV[0])),n=0;
function check(v,msg){assert(v,msg);n++;}
check(!exists(cfg.ml0_0,'ifname'),'generated wifi-mld has no explicit ifname');
let root={ifname:'ml0_0',iftype:3,ssid:'Generated fixture',wiphy:1,mac:'90:00:00:00:00:01',mlo_links:[
 {link_id:0,mac:'90:00:00:00:00:01',wiphy_freq:5320},
 {link_id:1,mac:'92:00:00:00:00:01',wiphy_freq:6015}]};
function status(id){return m.fields('state=ENABLED\nphy=phy01.'+id+'\nfreq='+(id?6015:5320)+'\nbss[0]=ml0_0\nbssid[0]='+(id?'92':'90')+':00:00:00:00:01\nssid[0]=Generated fixture\nmld_addr[0]=90:00:00:00:00:01\nmld_link_id[0]='+id+'\ncac_time_seconds='+(id?0:60)+'\ncac_time_left_seconds=N/A\n');}
function run(c,roots,q){return m.collect(c,q||((name,id)=>status(id)),roots||[root],name=>name=='phy01'?1:null,r=>r.path==cfg.radio1_band0.path?1:null);}
let report=run(cfg);
check(report.sections.up0v0_1_1_1==0&&report.sections.up0v0_1_2_1==0,'actual generated identity clears both healthy links');
check(report.links.up0v0_1_1_1.frequency==5320&&report.links.up0v0_1_2_1.frequency==6015,'actual per-link channels retained');
check(!length(report.pending.sections),'enabled links are not DFS exemptions');
let explicit={...cfg,ml0_0:{...cfg.ml0_0,ifname:'ml0_0'}};
check(run(explicit).sections.up0v0_1_2_1==0,'explicit matching ifname stays compatible');
for(let bad in ['another','',false,0]){
 let c={...cfg,ml0_0:{...cfg.ml0_0,ifname:bad}};
 check(run(c).sections.up0v0_1_1_1==1,'explicit wrong ifname is never ignored');
}
let missing={...cfg};delete missing.ml0_0;
check(run(missing).sections.up0v0_1_1_1==1,'missing group still fails');
let lost=run(cfg,[{...root,mlo_links:[root.mlo_links[0]]}]);
check(lost.sections.up0v0_1_1_1==0&&lost.sections.up0v0_1_2_1==1,'genuine missing secondary still fails');
let ordinary={radio0:cfg.radio0,plain:{'.type':'wifi-iface',device:'radio0',ssid:'Ordinary'}};
check(!length(m.collect(ordinary,()=>die('non-MLO must not query MLO')).sections),'older/non-MLO path unchanged');
print(sprintf('PASS %d actual-generated-config MLO identity controls\n',n));
