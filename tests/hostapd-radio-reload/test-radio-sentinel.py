from pathlib import Path
import tempfile,subprocess,json,sys,os,hashlib
source=Path(sys.argv[2]); common=Path(sys.argv[3])
host=source.read_text();comm=common.read_text()
restart=host[host.index('function iface_restart('):host.index('\nfunction array_to_obj',host.index('function iface_restart('))]
phy=comm[comm.index('function phy_open('):comm.index('\nconst vlist_proto',comm.index('function phy_open('))]
cases=[]
with tempfile.TemporaryDirectory(prefix='hostapd-radio-peer-review.') as t:
 root=Path(t)
 for fixed in [False,True]:
  assert 'hostapd.remove_iface(phy, phydev.radio ?? -1);' in restart
  body=restart if fixed else restart.replace('hostapd.remove_iface(phy, phydev.radio ?? -1);', 'hostapd.remove_iface(phy, phydev.radio);')
  for radio in [-1,0,1,None]:
   text='''let calls=[]; let phy_proto={}; function proto(d,p){return d;} function readfile(p){return '0';}
let hostapd={data:{pending_config:{}}, remove_iface:(phy,radio)=>push(calls,{phy,radio}),printf:(...args)=>null};
function iface_remove(...args){} function iface_macaddr_init(...args){} function iface_config_macaddr_list(...args){return [];}
function iface_pending_init(...args){}
'''+phy+'\n'+body+'\nlet p=phy_open("phy0",'+json.dumps(radio)+');iface_restart(p,{bss:[{ifname:"ap0"}]},{});print(sprintf("%J",calls));\n'
   script=root/'test.uc';script.write_text(text)
   result=subprocess.run([sys.argv[1],str(script)],env=os.environ,capture_output=True,text=True);assert result.returncode==0,result.stderr
   data=json.loads(result.stdout);passed= data[0]['radio']==(radio if radio is not None and radio>=0 else -1)
   assert passed if fixed or radio in [0,1] else not passed,data
   cases.append({'variant':'fixed-source' if fixed else 'regression-source','requested_radio':radio,'removal_radio':data[0]['radio'],'API_sentinel_preserved':passed})
print(json.dumps({'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'common_sha256':hashlib.sha256(common.read_bytes()).hexdigest(),'cases':cases,'scope':'Source phy_open and iface_restart on supplied ucode. Removal boundary captures arguments; regression variant demonstrates NULL/-1 failure. No hardware or daemon actions.'},indent=2))
