let m=require('mlo_health'),dfs=require('dfs_cac');let n=0;
function check(value,name){assert(value,name);n++;}
let cfg={r5:{'.type':'wifi-device',radio:'3',band:'5g',path:'pci'},r6:{'.type':'wifi-device',radio:'7',band:'6g',path:'pci'},
 ml0_0:{'.type':'wifi-mld',ifname:'ml0_0',ssid:'Fixture'},
 s5:{'.type':'wifi-iface',device:'r5',mld:'ml0_0',ifname:'ml0_0',ssid:'Fixture',network:'up'},
 s6:{'.type':'wifi-iface',device:'r6',mld:'ml0_0',ifname:'ml0_0',ssid:'Fixture',network:'up'}};
let root={ifname:'ml0_0',iftype:3,ssid:'Fixture',wiphy:9,mac:'90:00:00:00:00:01',mlo_links:[{link_id:0,mac:'90:00:00:00:00:01',wiphy_freq:5765},{link_id:1,mac:'92:00:00:00:00:01',wiphy_freq:6135}]};
function status(id){return m.fields('state=ENABLED\nphy=phy09.'+(id?7:3)+'\nfreq='+(id?6135:5765)+'\nbss[0]=ml0_0\nbssid[0]='+(id?'92':'90')+':00:00:00:00:01\nssid[0]=Fixture\nmld_addr[0]=90:00:00:00:00:01\nmld_link_id[0]='+id+'\ncac_time_seconds=60\ncac_time_left_seconds=N/A\n');}
function run(c,raw,q){return m.collect(c||cfg,q||((ifname,id)=>status(id)),raw||[root],name=>name=='phy09'?9:10,r=>r.path=='pci'?9:null);}
let ready=run();check(ready.sections.s5==0&&ready.sections.s6==0,'both exact links healthy');
let template=getenv('MLO_GROUP_TEMPLATE');assert(template,'actual SSID group template required');
let generated=render(template,{mlo_plan:{group:'ml0_0'},ssid:{name:'Fixture',encryption:{key:'synthetic-test-only'}},s:v=>sprintf("'%s'",v)});
let generated_group={};
for(let line in split(generated,'\n')){
 if(line=='set wireless.ml0_0=wifi-mld')generated_group['.type']='wifi-mld';
 let field=match(line,/^set wireless\.ml0_0\.([a-z_]+)='(.*)'$/);
 if(field)generated_group[field[1]]=field[2];
}
check(generated_group['.type']=='wifi-mld'&&generated_group.ssid=='Fixture'&&!exists(generated_group,'ifname'),'actual template emits implicit group name, not a fabricated ifname');
let rendered_cfg={...cfg,ml0_0:generated_group},rendered_ready=run(rendered_cfg);
check(rendered_ready.sections.s5==0&&rendered_ready.sections.s6==0,'actual rendered MLD group accepted on both links');
check(run({...rendered_cfg,ml0_0:{...generated_group,ifname:'another'}}).sections.s6==1,'explicit contradictory group name still refused');
check(ready.links.s5.radio_index==3&&ready.links.s6.radio_index==7&&ready.links.s6.link_id==1,'link ID not assumed radio index');
check(!length(ready.pending.sections),'enabled links never CAC');
let primary={...root,mlo_links:[root.mlo_links[0]]};check(run(null,[primary]).sections.s6==1,'missing secondary not credited primary');
let nochan={...root,mlo_links:[root.mlo_links[0],{...root.mlo_links[1],wiphy_freq:0}]};check(run(null,[nochan]).sections.s6==-1,'secondary no channel reported');
let disabled={...root,mlo_links:[root.mlo_links[0],{...root.mlo_links[1],mlo_link_disabled:true}]};check(run(null,[disabled]).sections.s6==-1,'disabled secondary genuinely fails');
for(let bad in [{phy:'phy09.3'},{phy:'phy10.7'},{freq:'5765'},{'bssid[0]':'94:00:00:00:00:01'},{'mld_addr[0]':'94:00:00:00:00:01'},{'mld_link_id[0]':'0'},{'ssid[0]':'Other'},{'bss[0]':'another'}]){
 let result=run(null,null,(name,id)=>id?{...status(id),...bad}:status(id));check(result.sections.s5==0&&result.sections.s6==1,'wrong identity does not clear secondary failure');}
check(run(null,null,(name,id)=>id?null:status(id)).sections.s6==1,'socket failure retains failure');
let stopped=run(null,null,(name,id)=>({...status(id),state:id?'DISABLED':'ENABLED'}));check(stopped.sections.s6==-1,'stopped secondary not credited');
let cac=run(null,null,(name,id)=>({...status(id),state:id?'ENABLED':'DFS',cac_time_left_seconds:'45'}));
check(cac.sections.s5==-1&&cac.sections.s6==0&&cac.pending.sections.s5&&!cac.pending.sections.s6,'only positively pending link exempt');
for(let left in ['0','N/A','61','4294967296','-1'])check(!length(run(null,null,(name,id)=>({...status(id),state:'DFS',cac_time_left_seconds:left})).pending.sections),'expired or invalid CAC not exempt');
let disabled_cac=run(null,[disabled],(name,id)=>({...status(id),state:'DFS',cac_time_left_seconds:'45'}));check(!disabled_cac.pending.sections.s6,'disabled link never CAC exemption');
let report=dfs.collect(cfg,{},null,null,cac);check(report.sections.s5&&!report.sections.s6,'actual DFS helper selects precise BSS');
check(dfs.has_wifi_failures({data:{radios:{r6:{failed_ssids:{Fixture:'missing'}}}}},cfg,report),'secondary fault not suppressed by primary CAC');
check(!dfs.has_wifi_failures({data:{radios:{r5:{failed_ssids:{Fixture:'no_channel'}}}}},cfg,report),'exact fresh primary CAC defers only its failure');
check(m.fields('state=ENABLED\nstate=DFS\n')==null,'duplicate status keys rejected');
let off={...cfg,r6:{...cfg.r6,disabled:'1'}};check(!exists(run(off).sections,'s6'),'disabled configured radio excluded');
let nonap={...cfg,s6:{...cfg.s6,mode:'sta'}};check(!exists(run(nonap).sections,'s6'),'non-AP configured section excluded');
let badgroup={...cfg,s6:{...cfg.s6,mld:'another'}};check(run(badgroup).sections.s6==1,'wrong group not credited');
let dup={...root,mlo_links:[root.mlo_links[0],{...root.mlo_links[1],link_id:0}]};check(run(null,[dup]).sections.s5==1,'duplicate link IDs fail closed');
let wrongphy={...root,wiphy:10};check(run(null,[wrongphy]).sections.s6==1,'wrong physical PHY not credited');
let ordinary={r:{'.type':'wifi-device'},s:{'.type':'wifi-iface',device:'r',ssid:'Ordinary'}};
check(!length(m.collect(ordinary,()=>die('ordinary must not query MLO')).sections),'ordinary path makes no MLO calls');
let parsed=dfs.parse_status('state=DFS\nphy=phy09.7\ncac_time_seconds=60\ncac_time_left_seconds=45\n');
check(parsed.phy=='phy09'&&parsed.radio_index==7,'grouped ordinary DFS PHY preserved and normalized');
print(sprintf('PASS: %d actual per-link health and DFS identity/disabled/lost-link controls\n',n));
