from pathlib import Path
import json,re,subprocess,sys,tempfile
p=Path(__file__).resolve().parent;runtime=sys.argv[1];modules=p/'mlo-health-fixture'
pre=r'''let INPUT=json(require('fs').readfile(ARGV[0]));let REPORT;
let libuci={cursor:()=>({load:()=>true,get:()=>null,get_all:(name)=>name=='wireless'?INPUT.config:{}})};
let libubus={connect:()=>({call:(object,method,args)=>{
 if(object=='network.interface')return {interface:[{interface:'loopback'},{interface:'up',data:{}},{interface:'down',data:{}}]};
 if(object=='network.wireless')return INPUT.live||{};
 if(object=='system')return {memory:{available:500,total:1000}};
 if(object=='ucentral'&&method=='health')REPORT=args;return {};}})};
let fs={stat:()=>null,glob:()=>['/sys/devices/pci/ieee80211/phy9'],basename:p=>split(p,'/')[-1],
 readfile:p=>index(p,'/index')>=0?'9':null,readlink:()=>'/sys/class/ieee80211/phy9',
 open:()=>({write:data=>null,close:()=>null}),popen:()=>({read:()=>INPUT.cac||'',close:()=>0})};
let log=()=>null;
'''
def execute(source,fixture,new):
 source=re.sub(r'^#![^\n]*\n','',source)
 source='\n'.join(line for line in source.splitlines() if not line.startswith('import '))
 source=re.sub(r'REQUIRE_SEARCH_PATH = \[.*?\];','',source,flags=re.S)
 source=source.replace("require('wifi.iface')",'INPUT.wifi')
 if new:
  source=source.replace("let mlo_health = require('mlo_health');", "let IMPL=require('mlo_health');let mlo_health={collect:c=>IMPL.collect(c,(name,id)=>IMPL.fields(INPUT.status[id]),INPUT.raw||[],()=>9,r=>r.path=='pci'?9:null)};")
 else:source=source.replace("require('dfs_cac')","require('dfs_base')")
 source+='\nprint(sprintf(\'%J\\n\',REPORT));\n'
 with tempfile.TemporaryDirectory(prefix='mlo-health-golden-') as temp:
  w=Path(temp);(w/'input.json').write_text(json.dumps(fixture));(w/'program.uc').write_text(pre+source)
  result=subprocess.run([runtime,'-L',str(modules/'*.uc'),str(w/'program.uc'),str(w/'input.json')],capture_output=True,text=True)
  assert result.returncode==0,result.stderr
  return json.loads(result.stdout)
base=(p/'health.uc').read_text();fixed=(p/'health-fixed.uc').read_text()
checks=0
for family in ('Sage','Jaguar','Cheetah','Thor','Miami','Gambit'):
 for mode in ('healthy','missing','no_channel','disabled_radio','disabled_ssid','non_ap','fresh_cac','expired_cac'):
  cfg={'r':{'.type':'wifi-device','.name':'r','path':'pci','band':'5g','ifname_prefix':'phy5g'},
       's':{'.type':'wifi-iface','device':'r','ifname':'phy5g-ap0','ssid':'Ordinary '+family,'network':'up'}}
  wifi={'phy5g-ap0':{'ssid':cfg['s']['ssid'],'mode':'ap','phy':9,'has_channel':True,'frequency':[5765]}}
  if mode=='missing':wifi={}
  if mode=='no_channel':wifi['phy5g-ap0'].update(has_channel=False,frequency=[])
  if mode=='disabled_radio':cfg['r']['disabled']='1'
  if mode=='disabled_ssid':cfg['s']['disabled']='1'
  if mode=='non_ap':cfg['s']['mode']='sta'
  live={'r':{'interfaces':[{'section':'s','ifname':'phy5g-ap0','config':{'ssid':cfg['s']['ssid']}}]}}
  cac=''
  if mode.endswith('_cac'):
   wifi={};left=45 if mode=='fresh_cac' else 0
   cac=f"state=DFS\nphy=phy9\ncac_time_seconds=60\ncac_time_left_seconds={left}\nbss[0]=phy5g-ap0\nssid[0]=Ordinary {family}\n"
  fixture={'config':cfg,'wifi':wifi,'live':live,'cac':cac}
  old=execute(base,fixture,False);new=execute(fixed,fixture,True)
  assert old==new,(family,mode,old,new);checks+=1
# Real observed shared-primary shape: old health reports false 75; new validates both links.
cfg={'r5':{'.type':'wifi-device','.name':'r5','path':'pci','band':'5g','radio':'0','ifname_prefix':'phy5g'},'r6':{'.type':'wifi-device','.name':'r6','path':'pci','band':'6g','radio':'1','ifname_prefix':'phy6g'},
 'ml0_0':{'.type':'wifi-mld','ifname':'ml0_0','ssid':'Fixture'},
 's5':{'.type':'wifi-iface','device':'r5','mld':'ml0_0','ifname':'ml0_0','ssid':'Fixture','network':'up'},
 's6':{'.type':'wifi-iface','device':'r6','mld':'ml0_0','ifname':'ml0_0','ssid':'Fixture','network':'up'}}
raw=[{'ifname':'ml0_0','iftype':3,'ssid':'Fixture','wiphy':9,'mac':'90:00:00:00:00:01','mlo_links':[{'link_id':0,'mac':'90:00:00:00:00:01','wiphy_freq':5765},{'link_id':1,'mac':'92:00:00:00:00:01','wiphy_freq':6135}]}]
status=[f"state=ENABLED\nphy=phy09.{i}\nfreq={5765 if i==0 else 6135}\nbss[0]=ml0_0\nbssid[0]={'90' if i==0 else '92'}:00:00:00:00:01\nssid[0]=Fixture\nmld_addr[0]=90:00:00:00:00:01\nmld_link_id[0]={i}\ncac_time_seconds=60\ncac_time_left_seconds=N/A\n" for i in (0,1)]
f={'config':cfg,'wifi':{'ml0_0':{'ssid':'Fixture','mode':'ap','phy':9,'has_channel':True,'frequency':[5765,5755]}},'raw':raw,'status':status,'live':{}}
old=execute(base,f,False);new=execute(fixed,f,True)
assert old['sanity']==75 and new['sanity']==100,(old,new);checks+=1
raw[0]['mlo_links'].pop();lost=execute(fixed,f,True)
assert lost['sanity']<100 and lost['data']['radios']['r6']['failed_ssids']['Fixture']=='missing';checks+=1
print(f'PASS: {checks} full actual health golden cases across six families; false75→100 only with both proven links; lost secondary remains faulty')
