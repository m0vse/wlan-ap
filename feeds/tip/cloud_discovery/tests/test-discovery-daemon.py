#!/usr/bin/env python3
"""Exercise actual discovery daemon functions with isolated filesystem boundaries."""
from pathlib import Path
import os
import subprocess
import tempfile
base=Path(os.environ['WLAN_AP_SOURCE_DIR']) if 'WLAN_AP_SOURCE_DIR' in os.environ else Path(__file__).resolve().parents[4]
files=base/'feeds/tip/cloud_discovery/files'
policy=(files/'usr/share/ucentral/discovery_policy.uc').read_text().replace('export function','function')
cloud=(files/'usr/bin/cloud_discovery').read_text()
def fn(name):
 start=cloud.index('function '+name+'(');a=cloud.index('{',start);depth=1;i=a+1
 while depth:
  depth+=(cloud[i]=='{')-(cloud[i]=='}');i+=1
 return cloud[start:i]+'\n'
stubs='''let files={},last=null;
let fs={readfile:(p)=>files[p],stat:(p)=>p in files?{type:'file'}:null,writefile:(p,v)=>{files[p]=v;return true;}};
const DISCOVER_DEFAULT='DEFAULT',DISCOVER_DHCP='DHCP',LOG_INFO=1,VALIDATING=1;
function ulog(...v){} function system(c){return 0;} function gateway_write(g){last=g;return true;}
function dnsmasq_rebind_allow(v){} function client_start(){} function set_state(v){}
function check(v,message){if(!v)die(message);}
'''
tests='''let fallback={mode:'default',default:'fallback.example:15002'};
check(default_policy(fallback),'default marker');
for(let option in ['other.example','other.example:16000']){let r=select_controller('ignored.example',option,fallback);check(r.dhcp_server=='other.example'&&r.no_validation===false,'valid224');}
for(let value in [null,'','https://other.example','x:0','x:65536','x..y','x:abc','x:']){let r=select_controller('ignored.example',value,fallback);check(r.dhcp_server=='fallback.example'&&r.no_validation===false,'malformed fallback/no138');}
let explicit={default:'fallback.example:15002',allowed:['fallback.example:15002','approved.example:17000']};
check(select_controller(null,'other.example',explicit).dhcp_server=='fallback.example','explicit refusal');
check(select_controller(null,'approved.example:17000',explicit).dhcp_server=='approved.example','explicit approved');
check(select_controller('ignored.example',null,null)==null,'no138 unrestricted');
check(select_controller(null,'other.example',{mode:'default',default:'fallback.example',allowed:[]})==null,'ambiguous marker closed');
check(select_controller(null,'other.example',{mode:'default',default:'https://bad'})==null,'bad policy closed');
files['/etc/ucentral/discovery-policy.json']=sprintf('%J',fallback);
let gateway={server:'fallback.example',port:15002,cert:'/etc/ucentral/operational.pem',ca:'/etc/ssl/certs/ca-certificates.crt',hostname_validate:1,valid:true};
files[gateway.cert]='leaf';files[gateway.ca]='trust';files['/etc/ucentral/gateway.json']=sprintf('%J',gateway);
check(pinned_gateway()==null,'legacy operational default not pin');
files['/tmp/cloud.json']=sprintf('%J',select_controller(null,'legacy-other.example:16000',fallback));
check(discover_dhcp()&&last.server=='legacy-other.example'&&last.cert==gateway.cert&&last.ca==gateway.ca,'legacy default credentials reused with strict TLS');
files['/etc/ucentral/gateway.default.json']=sprintf('%J',gateway);
files['/tmp/cloud.json']=sprintf('%J',select_controller(null,'other.example:16000',fallback));
check(discover_dhcp()&&last.server=='other.example'&&last.port==16000&&last.hostname_validate==1&&last.cert==gateway.cert&&last.ca==gateway.ca,'actualdaemon valid224 overrides default strictTLS');
delete files['/etc/ucentral/gateway.default.json'];
files['/etc/ucentral/custom.ca']='custom trust';
files['/etc/ucentral/gateway.json']=sprintf('%J',{server:'explicit.example',port:15002,cert:gateway.cert,ca:'/etc/ucentral/custom.ca',hostname_validate:1});
check(pinned_gateway()!=null&&!discover_dhcp(),'explicit custom CA gateway remains pinned');
files['/etc/ucentral/gateway.json']=sprintf('%J',gateway);
files['/etc/ucentral/gateway.default.json']=sprintf('%J',gateway);
files['/etc/ucentral/gateway.flash']=sprintf('%J',gateway);check(pinned_gateway()!=null&&!discover_dhcp(),'flash pin wins');delete files['/etc/ucentral/gateway.flash'];
files['/etc/ucentral/gateway.json']=sprintf('%J',{server:'fallback.example',port:15002,cert:'/etc/ucentral/cert.pem',ca:gateway.ca});files['/etc/ucentral/cert.pem']='birth';check(pinned_gateway()!=null,'manual birth pin wins');
files['/etc/ucentral/gateway.json']=sprintf('%J',gateway);files['/etc/ucentral/discovery-policy.json']=sprintf('%J',explicit);check(!controller_allowed('other.example',16000),'actualdaemon explicit allowedlist');
printf('DHCP224 default/explicit policy and actual daemon cases PASS\\n');
'''
with tempfile.TemporaryDirectory(prefix='discovery-daemon-') as directory:
 script=Path(directory)/'test.uc'
 script.write_text(policy+stubs+''.join(fn(n) for n in ['readjsonfile','discovery_policy','controller_allowed','gateway_credentials_ready','installer_default','pinned_gateway','discover_dhcp'])+tests)
 subprocess.run([os.environ.get('NATIVE_TEST_UCODE', 'ucode'),str(script)],check=True)
