from pathlib import Path
import copy,json,re,subprocess,sys,tempfile
p=Path(__file__).resolve().parent;runtime=sys.argv[1];checks=0
pre=r'''let INPUT=json(require('fs').readfile(ARGV[0]));
let global={wireless:INPUT.late_config?{}:INPUT.config,stats:{types:['ssids']},ubus:{call:()=>INPUT.live},telemetry:{},ports:INPUT.ports||{},devstats:{},ip4leases:{},snoop:{},macs:{},dyn_vlans:{},previous:{}};
let fs={glob:()=>[],readfile:()=>null};
let halow_module={process_halow_radio:()=>false,process_halow_ssid_chan_info:()=>false};
let telemetry_module={save_current_state:()=>null,stations_deltas:assoc=>({tx_bytes:assoc.tx_bytes,rx_bytes:assoc.rx_bytes}),ports_deltas:()=>({tx_bytes:10,rx_bytes:20})};
let fingerprint_module={get_fingerprint_for_mac:()=>null};
let network_module={lease_matches_iface:()=>true};
let regulatory={sample:()=>({}),telemetry:()=>null};
'''
def run(source,fixture,new):
 source='\n'.join(line for line in source.splitlines() if not line.startswith('import '));source=source.replace('export function ','function ')
 for name,var in [('wifi.phy','INPUT.phys'),('wifi.iface','INPUT.wifi'),('wifi.station','INPUT.stations'),('wifi.survey','{survey:[]}'),('wifi.mesh','{}')]:
  source=source.replace("require('"+name+"')",var)
 if new:source=source.replace('mlo_telemetry.sample(global.wireless)',"mlo_telemetry.sample(global.wireless,INPUT.raw||[],(name,id)=>require('mlo_health').fields(INPUT.status[id]),()=>9,r=>r.path=='pci'?9:null)")
 source+='''\nif(INPUT.late_config)global.wireless=INPUT.config;let state={},iface={name:'up'},error=null;try{collect_wifi_radios(state);}catch(e){error='radio_collection_failed';}let ssids=collect_wifi_ssids(iface);print(sprintf('%J\\n',{state,ssids,error}));\n'''
 with tempfile.TemporaryDirectory(prefix='mlo-statistics-') as temp:
  w=Path(temp);(w/'input.json').write_text(json.dumps(fixture));(w/'test.uc').write_text(pre+source)
  result=subprocess.run([runtime,'-L',str(p/'modules/*.uc'),str(w/'test.uc'),str(w/'input.json')],capture_output=True,text=True)
  assert result.returncode==0,result.stderr
  return json.loads(result.stdout)
def check(value,message):
 global checks
 assert value,message;checks+=1
base=(p/'wifi.uc').read_text();fixed=(p/'wifi-fixed.uc').read_text()
for family in ('Sage','Jaguar','Cheetah','Thor','Miami','Gambit'):
 for mode in ('ap','station','no_channel','no_client','disabled_first'):
  cfg={'r':{'.type':'wifi-device','path':'ordinary','band':'5g'},'s':{'.type':'wifi-iface','device':'r','ssid':family,'network':'up'}}
  fixture={'config':cfg,'live':{'r':{'config':{'path':'ordinary','band':'5g','country':'GB'},'interfaces':[{'ifname':'wlan0','section':'s','config':{'network':['up']}}]}},'phys':{'ordinary':{'band':['5G']}},'wifi':{'wlan0':{'ssid':family,'mode':'ap' if mode!='station' else 'station','bssid':'90:00:00:00:00:01','phy':9,'frequency':[5765,5755],'channel':[153,151],'ch_width':'40','tx_power':14,'has_channel':True}},'stations':{'wlan0':[{'station':'22:00:00:00:00:01','authorized':True,'tx_bytes':100,'rx_bytes':200}]},'ports':{'wlan0':{'counters':{'tx_bytes':1000,'rx_bytes':2000}}}}
  if mode=='no_channel':fixture['wifi']['wlan0'].update(frequency=[],channel=[],has_channel=False)
  if mode=='no_client':fixture['stations']={}
  if mode=='disabled_first':fixture['live']={'unused':{'config':{'path':'unused','band':'2g'},'interfaces':[]},**fixture['live']}
  check(run(base,fixture,False)==run(fixed,fixture,True),f'ordinary {family}/{mode} output unchanged')
cfg={'r5':{'.type':'wifi-device','path':'pci','band':'5g','radio':'3'},'r6':{'.type':'wifi-device','path':'pci','band':'6g','radio':'7'},'ml0_0':{'.type':'wifi-mld','ifname':'ml0_0','ssid':'Fixture'},'s5':{'.type':'wifi-iface','device':'r5','mld':'ml0_0','ifname':'ml0_0','ssid':'Fixture','network':'up'},'s6':{'.type':'wifi-iface','device':'r6','mld':'ml0_0','ifname':'ml0_0','ssid':'Fixture','network':'up'}}
raw=[{'ifname':'ml0_0','iftype':3,'ssid':'Fixture','wiphy':9,'mac':'90:00:00:00:00:01','mlo_links':[{'link_id':0,'mac':'90:00:00:00:00:01','wiphy_freq':5765,'center_freq1':5755,'channel_width':2,'wiphy_tx_power_level':1400},{'link_id':1,'mac':'92:00:00:00:00:01','wiphy_freq':6135,'center_freq1':6185,'channel_width':5,'wiphy_tx_power_level':2300}]}]
status=[f"state=ENABLED\nphy=phy09.{3 if i==0 else 7}\nfreq={5765 if i==0 else 6135}\nbss[0]=ml0_0\nbssid[0]={'90' if i==0 else '92'}:00:00:00:00:01\nssid[0]=Fixture\nmld_addr[0]=90:00:00:00:00:01\nmld_link_id[0]={i}\ncac_time_seconds=60\ncac_time_left_seconds=N/A\n" for i in (0,1)]
assoc={'station':'22:00:00:00:00:01','authorized':True,'bssid':'90:00:00:00:00:01','tx_bytes':100,'rx_bytes':200,'mlo':{'mld_address':'22:00:00:00:00:01','links':[{'link_id':0,'address':'44:00:00:00:00:01'},{'link_id':1,'address':'66:00:00:00:00:01'}],'counters_scope':'mld'}}
f={'config':cfg,'raw':raw,'status':status,'live':{'unused':{'config':{'path':'unused','band':'2g'},'interfaces':[]},'r5':{'config':{**cfg['r5'],'country':'GB'},'interfaces':[{'section':'s5','ifname':'ml0_0','config':{'network':['up']}}]},'r6':{'config':{**cfg['r6'],'country':'GB'},'interfaces':[{'section':'s6','ifname':'ml0_0','config':{'network':['up']}}]}},'phys':{'pci+3:5G':{'band':['5G'],'radio_index':3,'radio_index_source':'driver','wiphy_name':'phy09'},'pci+7:6G':{'band':['6G'],'radio_index':7,'radio_index_source':'driver','wiphy_name':'phy09'}},'wifi':{'ml0_0':{'ssid':'Fixture','mode':'ap','bssid':'90:00:00:00:00:01','phy':9,'frequency':[5765,5755],'channel':[153,151],'ch_width':'40','tx_power':14,'has_channel':True}},'stations':{'ml0_0':[assoc]},'ports':{'ml0_0':{'counters':{'tx_bytes':1000,'rx_bytes':2000}}}}
r=run(fixed,f,True);check(r['error'] is None and len(r['state']['radios'])==2,'both real logical radios reported')
check(r['state']['radios'][0]['frequency']==[5765,5755] and r['state']['radios'][1]['frequency']==[6135,6185],'per-link actual frequency/centers')
check([x['channel_width'] for x in r['state']['radios']]==[40,160],'per-link widths')
check([x['tx_power'] for x in r['state']['radios']]==[14,23],'per-link reported powers')
check([s['radio']['$ref'] for s in r['ssids']]==['#/radios/0','#/radios/1'],'exact returned-array refs despite skipped earlier radio')
check([s['bssid'] for s in r['ssids']]==['90:00:00:00:00:01','92:00:00:00:00:01'],'own BSSID each logical SSID')
check(sum(len(s.get('associations',[])) for s in r['ssids'])==1,'one canonical peer record, no aggregate duplication')
check(sum('counters' in s for s in r['ssids'])==1,'one MLD aggregate port-counter owner')
peer=r['ssids'][0]['associations'][0];check(peer['mlo']['mld_address']==peer['station'] and peer['mlo']['counters_scope']=='mld','agreed genuine peer contract')
check([l['frequency'] for l in peer['mlo']['links']]==[5765,6135] and [l['bssid'] for l in peer['mlo']['links']]==['90:00:00:00:00:01','92:00:00:00:00:01'],'peer link IDs joined to actual AP links')
empty=copy.deepcopy(f);empty['live']={'empty':{'config':{'path':'empty','band':'2g'},'interfaces':[{'ifname':'empty','section':'empty','config':{}}]},**f['live']};empty['wifi']['empty']={}
check([s['radio']['$ref'] for s in run(fixed,empty,True)['ssids']]==['#/radios/0','#/radios/1'],'empty earlier view cannot shift MLO references')
lost=copy.deepcopy(f);lost['raw'][0]['mlo_links'].pop();x=run(fixed,lost,True)
check(len(x['ssids'])==1 and len(x['ssids'][0]['associations'])==1 and 'mlo' not in x['ssids'][0]['associations'][0],'lost secondary retains client without manufacturing rich MLO')
legacy=copy.deepcopy(f);legacy['stations']['ml0_0']=[{k:v for k,v in assoc.items() if k!='mlo'}]
check(sum(len(s.get('associations',[])) for s in run(fixed,legacy,True)['ssids'])==1,'ordinary peer on MLD interface retained exactly once')
late=copy.deepcopy(f);late['late_config']=True;check(run(fixed,late,True)==run(fixed,f,True),'native import before global configuration yields same correct result')
missing=copy.deepcopy(f);del missing['raw'][0]['mlo_links'][1]['wiphy_tx_power_level']
check(run(fixed,missing,True)['state']['radios'][1]['tx_power'] is None,'missing secondary power remains unavailable, not synthetic zero')
zero=copy.deepcopy(f);zero['raw'][0]['mlo_links'][1]['wiphy_tx_power_level']=0
check(run(fixed,zero,True)['state']['radios'][1]['tx_power']==0,'actual zero dBm remains zero')
negative=copy.deepcopy(f);negative['raw'][0]['mlo_links'][1]['wiphy_tx_power_level']=4294967196
check(run(fixed,negative,True)['state']['radios'][1]['tx_power']==-1,'signed negative mBm normalized in actual telemetry')
(p/'native-telemetry-fixture.json').write_text(json.dumps(r,indent=2)+'\n')
print(f'PASS: {checks} actual radio/SSID collector cases, older-family golden outputs, real per-link views and canonical counter ownership')
