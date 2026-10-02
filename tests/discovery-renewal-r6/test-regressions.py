"""Actual discovery/EST functions with private file/process/network boundaries."""
import hashlib,json,os,pathlib,re,subprocess,sys,tempfile
package=pathlib.Path(sys.argv[1]).resolve()
ucode=os.environ['OW_TEST_UCODE']
daemon=(package/'files/usr/bin/cloud_discovery').read_text()
est=(package/'files/usr/bin/est_client').read_text()
work=pathlib.Path(tempfile.mkdtemp(prefix='discovery-renewal-regressions.'))
policy=package/'files/usr/share/ucentral/discovery_policy.uc'
body=daemon[daemon.index('const DISCOVER ='):daemon.index('\ndetect_certificate_type();')]
body=body.replace('system(', 'test_system(').replace('time()', 'test_time()')
setup='''import { select_controller } from POLICY;
let files={}; let commands=[]; let writes=[]; let connected=true;
let enroll_status=0; let reenroll_status=0; let expiry_status=0; let parse_status=0; let clock=1000; let write_failure=false;
let fs={readfile:(p)=>files[p]??null,stat:(p)=>exists(files,p)?{type:'file'}:null,writefile:(p,v)=>{if(write_failure)return null;files[p]=type(v)=='string'?v:sprintf('%J',v);push(writes,p);return length(files[p]);},unlink:(p)=>{delete files[p];return true;},popen:()=>({read:()=> 'issuer=OpenLAN Birth Issuing CA',close:()=>0}),mkdir:()=>true};
let libubus={connect:()=>({call:()=>({connected})})}; let libuci={cursor:()=>({get_all:()=>null})};let math={rand:()=>0};let uloop={init:()=>0};
let ULOG_SYSLOG=0;let ULOG_STDIO=0;let LOG_DAEMON=0;let LOG_INFO=0;function ulog_open(...v){}function ulog(...v){}function test_time(){return clock;}
function test_system(c){push(commands,c);if(c=='/usr/bin/est_client enroll')return enroll_status;if(c=='/usr/bin/est_client reenroll')return reenroll_status;if(index(c,'openssl x509 -checkend ')==0)return expiry_status;if(index(c,'openssl x509 -noout ')==0)return parse_status;return 0;}
let count=0;let cases=[];function check(n,v){if(!v)die('FAIL '+n+'\\n');push(cases,{case:n,passed:true});count++;}
function put(p,v){files[p]=type(v)=='string'?v:sprintf('%J',v);}
function old_gateway(){let g={server:'old.example',port:15002,valid:true,cert:'/etc/ucentral/operational.pem',ca:'/etc/ucentral/operational.ca'};put('/etc/ucentral/gateway.json',g);put(g.cert,'synthetic');put(g.ca,'synthetic');return g;}
function hint(){put('/tmp/cloud.json',{lease:true,dhcp_server:'new.example',dhcp_port:15002});}
'''.replace('POLICY',json.dumps(str(policy)))
cases='''
function reset(){files={};commands=[];writes=[];connected=true;enroll_status=0;reenroll_status=0;expiry_status=0;parse_status=0;write_failure=false;clock=1000;state=ONLINE;gateway_before_validation=null;discovery_block_list=[];interval={set:()=>0};files['/tmp/ntp.set']='ready';}
reset();old_gateway();expiry_handler();check('fresh-certificate-90-day-window',index(commands,'openssl x509 -checkend 7776000 -noout -in /etc/ucentral/operational.pem')>=0&&!length(writes)&&index(commands,'/usr/bin/est_client reenroll')<0);
reset();old_gateway();delete files['/etc/ucentral/operational.pem'];expiry_handler();check('missing-leaf-even-with-ca-no-renewal',!length(commands)&&!length(writes));
reset();old_gateway();parse_status=1;expiry_handler();check('malformed-leaf-not-expiry-event',length(commands)==1&&!length(writes));
reset();let g=old_gateway();g.cert='/etc/ucentral/cert.pem';put(g.cert,'manual');put('/etc/ucentral/gateway.json',g);expiry_handler();check('manual-bootstrap-not-auto-renewed',!length(commands));
reset();old_gateway();let before=files['/etc/ucentral/gateway.json'];reenroll_status=1;trigger_reenroll();check('failed-renewal-preserves-working-client-and-gateway',files['/etc/ucentral/gateway.json']==before&&state==ONLINE&&length(commands)==1);
reset();old_gateway();before=files['/etc/ucentral/gateway.json'];trigger_reenroll();check('successful-renewal-restarts-same-client-no-discovery',files['/etc/ucentral/gateway.json']==before&&state==ONLINE&&index(commands,'/etc/init.d/ucentral restart')>=0&&index(commands,'/etc/init.d/ucentral stop')<0);
reset();old_gateway();before=files['/etc/ucentral/gateway.json'];set_state(DISCOVER);check('discovery-state-keeps-working-gateway',files['/etc/ucentral/gateway.json']==before);
reset();old_gateway();before=files['/etc/ucentral/gateway.json'];hint();enroll_status=1;check('failed-dhcp-est-candidate-not-published',!discover_dhcp()&&files['/etc/ucentral/gateway.json']==before&&index(commands,'/etc/init.d/ucentral restart')<0);
reset();old_gateway();before=files['/etc/ucentral/gateway.json'];hint();check('successful-est-with-missing-credential-files-refused',!discover_dhcp()&&files['/etc/ucentral/gateway.json']==before&&index(commands,'/etc/init.d/ucentral restart')<0);
reset();old_gateway();hint();put('/etc/ucentral/new.example.pem','candidate');put('/etc/ucentral/new.example.ca','candidate');check('ready-unpinned-candidate-enters-validation',discover_dhcp()&&gateway_load().server=='new.example'&&state==VALIDATING&&gateway_before_validation?.server=='old.example');clock+=121;interval_handler();check('validation-timeout-restores-last-working-gateway',gateway_load().server=='old.example'&&state==OFFLINE);
reset();g=old_gateway();put('/etc/ucentral/gateway.flash',g);hint();before=files['/etc/ucentral/gateway.json'];check('explicit-flash-pin-refuses-dhcp-est-override',!discover_dhcp()&&!length(commands)&&files['/etc/ucentral/gateway.json']==before);
reset();g=old_gateway();put('/etc/ucentral/discovery-policy.json',{default:'old.example:15002',allowed:['old.example:15002']});hint();check('daemon-consumes-allowed-policy-not-arbitrary-hint',!discover_dhcp()&&!length(commands));state=DISCOVER;interval_handler();check('ready-local-policy-identity-skips-public-est',state==ONLINE&&index(commands,'/usr/bin/est_client enroll')<0);
reset();g=old_gateway();g.cert='/etc/ucentral/cert.pem';put(g.cert,'manual');put('/etc/ucentral/gateway.json',g);put('/etc/ucentral/discovery-policy.json',{default:'old.example:15002',allowed:['old.example:15002']});check('same-controller-hint-cannot-substitute-missing-cert-paths',!gateway_write({server:'old.example',port:15002,cert:'/etc/ucentral/old.example.pem',ca:'/etc/ucentral/old.example.ca'})&&gateway_load().cert==g.cert);
reset();old_gateway();put('/etc/ucentral/discovery-policy.json','{broken');hint();state=DISCOVER;interval_handler();check('malformed-policy-fails-closed-no-public-est',index(commands,'/usr/bin/est_client enroll')<0&&gateway_load().server=='old.example');
reset();old_gateway();put('/etc/ucentral/discovery-policy.json','null');hint();check('explicit-null-policy-not-unrestricted',!discover_dhcp()&&!length(commands));
reset();old_gateway();put('/tmp/cloud.json',{lease:false});ubus_methods.renew.call();check('lease-loss-retains-destination-and-identity',state==OFFLINE&&gateway_load().server=='old.example');
reset();old_gateway();write_failure=true;check('candidate-write-error-not-success',!gateway_write({server:'new.example',port:15002,valid:false}));
reset();detect_certificate_type();check('production-renewal-window-is-90-days',timeouts.expiry_threshold==7776000);
reset();old_gateway();delete files['/tmp/ntp.set'];expiry_handler();check('unready-clock-does-not-renew',!length(commands));
reset();old_gateway();reenroll_status=1;check('ubus-reenroll-propagates-error-preserving-gateway',ubus_methods.reenroll.call()==1&&state==ONLINE&&gateway_load().server=='old.example');
reset();old_gateway();delete files['/etc/ucentral/operational.ca'];check('startup-missing-ca-not-ready',!gateway_available());
reset();old_gateway();check('incomplete-replacement-cannot-be-written',!gateway_write({cert:'/etc/ucentral/absent.pem'})&&gateway_load().cert=='/etc/ucentral/operational.pem');
reset();fs.popen=()=>({read:()=> 'issuer=OpenLAN Demo Birth CA',close:()=>0});detect_certificate_type();check('demo-three-day-window-preserved',timeouts.expiry_threshold==259200);
printf('%.J\\n',{passed:true,count,cases});
'''
driver=work/'daemon.uc';driver.write_text(setup+body+cases)
p=subprocess.run([ucode,str(driver)],capture_output=True,text=True)
assert p.returncode==0,(p.stdout,p.stderr)
report=json.loads(p.stdout[p.stdout.index('{'):])
def function(name):
    return re.search(r'(?ms)^function '+name+r'\(.*?^\}',est).group()
est_setup='''let files={};let actions=[];let missing=false;let call_status=0;let persist_status=0;let validate=true;let command_status=0;let rename_ok=true;let prefix='operational';let gateway={cert:'/etc/ucentral/operational.pem',ca:'/etc/ucentral/operational.ca'};
let cert_prefix='operational';let LOG_INFO=0;function ulog(...v){}function cert_prefix_determine(){return prefix;}function call_est_server(...v){push(actions,'est');return call_status;}function valid_renewal_candidate(...v){push(actions,'validate');return validate;}function store_operational_cert(...v){push(actions,'persist');return persist_status;}function test_system(c){push(actions,c);return command_status;}
let fs={stat:()=>missing?null:{type:'file'},readfile:()=>sprintf('%J',gateway),rename:()=>rename_ok};let count=0;let cases=[];function check(n,v){if(!v)die('FAIL '+n+'\\n');push(cases,{case:n,passed:true});count++;}function reset(){actions=[];missing=false;call_status=0;persist_status=0;validate=true;command_status=0;rename_ok=true;prefix='operational';gateway={cert:'/etc/ucentral/operational.pem',ca:'/etc/ucentral/operational.ca'};}
'''
est_cases='''
reset();missing=true;check('absent-operational-candidate-is-error',simplereenroll()==1&&!length(actions));
reset();gateway.cert='/etc/ucentral/cert.pem';check('manual-bootstrap-prefix-not-renewable',simplereenroll()==1&&!length(actions));
reset();gateway.cert='/etc/ucentral/bad;command.pem';check('unsafe-prefix-is-error',simplereenroll()==1&&!length(actions));
reset();gateway.cert='/etc/ucentral/cert.pem';check('candidate-not-current-controller-identity-is-error',simplereenroll()==1&&!length(actions));
reset();call_status=1;check('est-error-no-persist-or-activation',simplereenroll()==1&&length(actions)==1);
reset();validate=false;check('invalid-replacement-no-persist-or-activation',simplereenroll()==1&&index(actions,'persist')<0);
reset();persist_status=1;check('persist-error-no-runtime-activation',simplereenroll()==1&&length(actions)==4);
reset();rename_ok=false;check('runtime-rename-error-not-success',simplereenroll()==1);
reset();check('validated-persisted-replacement-only-success',simplereenroll()==0&&index(actions,'validate')<index(actions,'persist'));
reset();prefix='wrong-dhcp.example';check('renew-configured-identity-not-transient-dhcp-prefix',simplereenroll()==0&&cert_prefix=='operational');
printf('%.J\\n',{passed:true,count,cases});
'''
driver=work/'est.uc';driver.write_text(est_setup+function('simplereenroll').replace('system(','test_system(')+est_cases)
p=subprocess.run([ucode,str(driver)],capture_output=True,text=True);assert p.returncode==0,(p.stdout,p.stderr)
est_report=json.loads(p.stdout)
print(json.dumps({'passed':True,'count':report['count']+est_report['count'],'daemon':report,'est':est_report,
 'daemon_sha256':hashlib.sha256(daemon.encode()).hexdigest(),'est_sha256':hashlib.sha256(est.encode()).hexdigest(),
 'scope':'Actual daemon functions/ubus methods and actual simplereenroll with filesystem, clock, EST/process/persistence boundaries private stubs; actual discovery policy module. No AP, network, service start, live trust or certificate modification.'},indent=2))
