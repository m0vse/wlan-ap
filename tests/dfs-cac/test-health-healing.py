#!/usr/bin/env python3
"""Actual health/healing functions, boundaries redirected to private fixtures."""
import hashlib,json,os,pathlib,re,subprocess,tempfile
base=pathlib.Path(os.environ['OW_DFS_SOURCE']);ucode=os.environ['OW_TEST_UCODE']
work=pathlib.Path(tempfile.mkdtemp(prefix='cac-health-healing.'))
(work/'dfs_cac.uc').write_bytes((base/'system/dfs_cac.uc').read_bytes())
health=(base/'system/health.uc').read_text();daemon=(base/'ucentral-state').read_text()
functions=[]
for name in ('find_ssid','find_ssid_on_phy','iface_in_band','find_ssid_by_prefix','find_ssid_on_phy_band','find_ssid_for_radio','get_radio_match_info','iface_section_enabled','check_radio_health','check_wifi_health'):
 match=re.search(r'(?ms)^function '+name+r'\(.*?^\}',health);assert match,name;functions.append(match.group())
bands=re.search(r'(?ms)^let band_freq_ranges = \{.*?^\};',health).group()
healer=re.search(r'(?ms)^function self_healing\(\).*?^\}',daemon).group()
healer=healer.replace("require('dfs_cac')",'test_cac_module').replace('time()','test_time()').replace('system(', 'test_system(')
driver=work/'test.uc'
setup='''REQUIRE_SEARCH_PATH=[ARGV[0]+'/*.uc',...REQUIRE_SEARCH_PATH];
let cac=require('dfs_cac'); let count=0;
function check(name,result){if(!result)die('FAIL '+name+'\\n');count++;}
let config={radio0:{'.name':'radio0','.type':'wifi-device',path:'platform/soc/wifi+0'},radio1:{'.name':'radio1','.type':'wifi-device',path:'platform/soc/wifi+1'},bss0:{'.name':'bss0','.type':'wifi-iface',device:'radio0',mode:'ap',ssid:'Shine Systems',network:'up0v0'},bss1:{'.name':'bss1','.type':'wifi-iface',device:'radio1',mode:'ap',ssid:'Shine Systems',network:'up0v0'}};
let runtime={radio0:{interfaces:[{section:'bss0',ifname:'wlan0',config:{ssid:'Shine Systems'}}]},radio1:{interfaces:[{section:'bss1',ifname:'wlan1',config:{ssid:'Shine Systems'}}]}};
let response;let clock=0;let last_restart=0;let actions=[];let logs=[];let snapshot;
function status(left,state){return cac.parse_status('state='+(state??'DFS')+'\\nphy=phy0\\ncac_time_seconds=600\\ncac_time_left_seconds='+left+'\\nbss[0]=wlan0\\nssid[0]=Shine Systems\\n');}
let test_cac_module={collect:(c,r)=>cac.collect(c,r,(name)=>name=='wlan0'?response:null,(name)=>name=='wlan0'?'phy0':'phy1'),has_wifi_failures:cac.has_wifi_failures};
let cac_pending={sections:{},radios:{}};
let fs={glob:(path)=>['/sys/devices/platform/soc/wifi/ieee80211/phy0','/sys/devices/platform/soc/wifi/ieee80211/phy1'],basename:(path)=>split(path,'/')[length(split(path,'/'))-1],readfile:(path)=>path=='/tmp/ucentral.health'?sprintf('%J',snapshot):path=='/tmp/ucentral.nw_restart_ts'?''+last_restart:index(path,'phy0/index')>=0?'0\\n':'1\\n',stat:()=>null,open:()=>({write:(v)=>{last_restart=int(v);},close:()=>0})};
let uci={load:()=>true,get_all:()=>config};let ubus={call:(object)=>object=='network.wireless'?runtime:{}};
let LOG_INFO=1;function ulog(level,message){push(logs,message);}function test_time(){return clock;}function test_system(command){push(actions,command);return 0;}
function radius_probe(){return 1;}
let wifi_state={wlan1:{ssid:'Shine Systems',phy:1,has_channel:true,frequency:[2412]}};
'''
cases='''
for(let elapsed in [120,240,360,480,599]){
 clock=elapsed;response=status(600-elapsed);cac_pending=test_cac_module.collect(config,runtime);
 let radios=check_radio_health(config,wifi_state);check('health suppresses only CAC radio '+elapsed,!length(radios.issues));
 check('healthy 2G remains checked '+elapsed,radios.checked==1);
 snapshot={sanity:75,data:{radios:{radio0:{failed_ssids:{'Shine Systems':'missing'}}}}};
 actions=[];self_healing();check('fresh CAC prevents stale missing heal '+elapsed,!length(actions));
}
clock=600;response=status(0);actions=[];self_healing();check('expired CAC genuine failure heals',length(actions)==1&&actions[0]=='/etc/init.d/network restart');
last_restart=0;response=status('N/A');actions=[];self_healing();check('aborted CAC genuine failure heals',length(actions)==1);
last_restart=0;response=null;actions=[];self_healing();check('unavailable runtime retains heal',length(actions)==1);
last_restart=0;response=status(480);snapshot.data.radios.radio1={failed_ssids:{'Shine Systems':'missing'}};actions=[];self_healing();check('independent mixed radio failure heals during CAC',length(actions)==1);
snapshot={sanity:100,data:{}};actions=[];self_healing();check('healthy completed radios no heal',!length(actions));
response=status(480);cac_pending=test_cac_module.collect(config,runtime);config.radio1.disabled='1';wifi_state={};
check('standalone CAC interface SSID not missing',!check_wifi_health({interface:'up0v0'},config,wifi_state).health.ssids);
config.bss0.auth_server='server';config.bss0.auth_port=1812;config.bss0.auth_secret='fixture';config.bss0.health_username='fixture';config.bss0.health_password='fixture';
check('independent radius failure retained during CAC',!!check_wifi_health({interface:'up0v0'},config,wifi_state).health.radius);
cac_pending={sections:{},radios:{}};check('no CAC evidence detects real missing SSID',!!check_wifi_health({interface:'up0v0'},config,wifi_state).health.ssids);
printf('%.J\\n',{passed:true,count,scope:'Actual health matching and self-healing functions; filesystem/ubus/clock/process boundaries stubbed, actual positive-CAC helper injected. No AP, network restart or RADIUS traffic.'});
'''
driver.write_text(setup+bands+'\n'+'\n'.join(functions)+'\n'+healer+'\n'+cases)
p=subprocess.run([ucode,str(driver),str(work)],capture_output=True,text=True)
assert p.returncode==0,(p.stdout,p.stderr)
result=json.loads(p.stdout);result['health_sha256']=hashlib.sha256(health.encode()).hexdigest();result['healer_sha256']=hashlib.sha256(daemon.encode()).hexdigest()
print(json.dumps(result,indent=2))
