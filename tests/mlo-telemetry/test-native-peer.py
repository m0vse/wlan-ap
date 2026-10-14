from pathlib import Path
import copy,json,subprocess,sys,tempfile
p=Path(__file__).resolve().parent;runtime=sys.argv[1];checks=0
auth=(p/'station_authorization.uc').read_text().replace('export function','function')
def run(source,data):
 source='\n'.join(line for line in source.splitlines() if not line.startswith('import '));source=source.replace('let nl = require("nl80211");','let nl=MO_NL;',1).replace('return lookup_stations();',"print(sprintf('%J\\n',lookup_stations()));")
 pre="let INPUT=json(require('fs').readfile(ARGV[0]));let global={tid_stats:false};let MO_NL={const:{NL80211_CMD_GET_INTERFACE:1,NL80211_CMD_GET_STATION:2,NLM_F_DUMP:4},request:(cmd)=>cmd==1?INPUT.interfaces:INPUT.rows};\n"+auth+'\n'
 with tempfile.TemporaryDirectory(prefix='native-peer-mlo-') as temp:
  w=Path(temp);(w/'input.json').write_text(json.dumps(data));(w/'test.uc').write_text(pre+source)
  result=subprocess.run([runtime,str(w/'test.uc'),str(w/'input.json')],capture_output=True,text=True)
  assert result.returncode==0,result.stderr
  return json.loads(result.stdout)
def check(value,name):
 global checks
 assert value,name;checks+=1
base=(p/'station.uc').read_text();fixed=(p/'station-fixed.uc').read_text()
row={'mac':'22:00:00:00:00:01','sta_info':{'sta_flags':[2,2],'rx_bytes64':200,'tx_bytes64':100,'connected_time':120}}
f={'interfaces':[{'ifname':'wlan0','mac':'90:00:00:00:00:01'}],'rows':[row]}
for family in ('Sage','Jaguar','Cheetah','Thor','Miami','Gambit'):
 for flags in ([2,2],[2,0],None,[0,0],[3,2]):
  x=copy.deepcopy(f);x['rows'][0]['sta_info']['sta_flags']=flags
  check(run(base,x)==run(fixed,x),f'{family} authorization/ordinary peer output unchanged')
m=copy.deepcopy(f);m['interfaces'][0]['ifname']='ml0_0';m['interfaces'][0]['mlo_links']=[{'link_id':0},{'link_id':1}]
m['rows'][0]['mlo_links']=[{'link_id':0,'mac':'44:00:00:00:00:01'},{'link_id':1,'mac':'66:00:00:00:00:01'}]
r=run(fixed,m)['ml0_0'][0]
check(r['mlo']['mld_address']==r['station'] and len(r['mlo']['links'])==2,'actual negotiated peer links exported')
check(r['mlo']['counters_scope']=='mld' and r['tx_bytes']==100 and r['rx_bytes']==200,'unchanged single aggregate counters')
no_auth=copy.deepcopy(m);no_auth['rows'][0]['sta_info']['sta_flags']=[2,0];check(run(fixed,no_auth)=={},'unauthorized MLO peer dropped')
unknown=copy.deepcopy(m);unknown['rows'][0]['sta_info']['sta_flags']=None;check('mlo' not in run(fixed,unknown)['ml0_0'][0],'unknown authorization not converted into proved MLO')
for links in ([],[{'link_id':0,'mac':'44:00:00:00:00:01'},{'link_id':0,'mac':'66:00:00:00:00:01'}],[{'link_id':0,'mac':'44:00:00:00:00:01'},{'link_id':1,'mac':'44:00:00:00:00:01'}],[{'link_id':0,'mac':'ff:ff:ff:ff:ff:ff'},{'link_id':1,'mac':'66:00:00:00:00:01'}],[{'link_id':-1,'mac':'44:00:00:00:00:01'},{'link_id':1,'mac':'66:00:00:00:00:01'}]):
 x=copy.deepcopy(m);x['rows'][0]['mlo_links']=links;check('mlo' not in run(fixed,x)['ml0_0'][0],'invalid peer metadata cannot manufacture MLO')
single=copy.deepcopy(m);single['rows'][0]['mlo_links']=[{'link_id':1,'mac':'66:00:00:00:00:01'}];r=run(fixed,single)['ml0_0'][0]
check('mlo' not in r and r['mlo_link_id']==1,'genuine one-link metadata attributes ordinary peer without falsely labelling MLO')
bad=copy.deepcopy(single);bad['rows'][0]['mlo_links'][0]['mac']='ff:ff:ff:ff:ff:ff';check('mlo_link_id' not in run(fixed,bad)['ml0_0'][0],'single-link hint needs valid negotiated MAC too')
for average in (-49,0,-49.5,None,'-49'):
 x=copy.deepcopy(m);x['rows'][0]['sta_info'].update(signal=0,signal_avg=average)
 out=run(fixed,x)['ml0_0'][0]
 check(out['rssi']==0,'raw instantaneous signal preserved')
 check(('rssi_avg' in out)==(isinstance(average,(int,float))),'average exported only actual numeric presence')
 if isinstance(average,(int,float)):check(out['rssi_avg']==average,'actual average value unchanged')
ordinary_average=copy.deepcopy(f);ordinary_average['rows'][0]['sta_info'].update(signal=-55,signal_avg=-49)
check(run(fixed,ordinary_average)==run(base,ordinary_average),'ordinary RSSI and shape unchanged even with native average present')
(p/'native-peer-fixture.json').write_text(json.dumps(run(fixed,m),indent=2)+'\n')
print(f'PASS: {checks} actual native peer authorization/legacy/negotiated-MLO cases, with unchanged counters')
