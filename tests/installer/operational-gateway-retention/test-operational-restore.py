#!/usr/bin/env python3
"""Actual durable activation replay, early boot, discovery pin and client argv."""
import hashlib,json,os,pathlib,shutil,subprocess,tempfile
repo=pathlib.Path(os.environ['WLAN_AP_SOURCE_DIR']);ucode=os.environ['NATIVE_TEST_UCODE'];target=pathlib.Path(os.environ['OW_TEST_ROOT'])
assert os.getuid()==0
src=repo/'feeds/tip/certificates/files';module=repo/'feeds/tip/cloud_discovery/files/usr/share/ucentral/discovery_policy.uc';work=pathlib.Path(tempfile.mkdtemp(prefix='operational-replay.'));cases=[]
def openssl(*args):subprocess.run(['openssl',*map(str,args)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
ca=work/'issuer.pem';cakey=work/'issuer.key';key=work/'key.pem';leaf=work/'leaf.pem';csr=work/'leaf.csr';ext=work/'leaf.ext'
openssl('req','-x509','-newkey','ec','-pkeyopt','ec_paramgen_curve:prime256v1','-nodes','-days',3,'-subj','/CN=Synthetic Replay Issuer','-keyout',cakey,'-out',ca)
openssl('req','-new','-newkey','ec','-pkeyopt','ec_paramgen_curve:prime256v1','-nodes','-subj','/CN=SYNTHETIC-AP','-keyout',key,'-out',csr)
ext.write_text('basicConstraints=critical,CA:FALSE\nextendedKeyUsage=clientAuth\nkeyUsage=critical,digitalSignature\n')
openssl('x509','-req','-in',csr,'-CA',ca,'-CAkey',cakey,'-CAcreateserial','-days',2,'-extfile',ext,'-out',leaf)
birth_ca=work/'birth-ca.pem';birth_key=work/'birth-ca.key';birth_leaf=work/'birth-leaf.pem'
openssl('req','-x509','-newkey','ec','-pkeyopt','ec_paramgen_curve:prime256v1','-nodes','-days',3,'-subj','/CN=Synthetic Old Test CA','-keyout',birth_key,'-out',birth_ca)
openssl('x509','-req','-in',csr,'-CA',birth_ca,'-CAkey',birth_key,'-CAcreateserial','-days',2,'-extfile',ext,'-out',birth_leaf)
dates={}
for label,days in [('expired-leaf',-1),('not-yet-valid-leaf',1)]:
 from datetime import datetime,timedelta,timezone
 database=work/(label+'.index');database.write_text('');serialfile=work/(label+'.serial');serialfile.write_text('10\n')
 config=work/(label+'.config');config.write_text('[ca]\ndefault_ca=fixture\n[fixture]\ndatabase='+str(database)+'\nserial='+str(serialfile)+'\nnew_certs_dir='+str(work)+'\ncertificate='+str(ca)+'\nprivate_key='+str(cakey)+'\ndefault_md=sha256\npolicy=subject\n[subject]\ncommonName=supplied\n')
 start=datetime.now(timezone.utc)+timedelta(days=days);end=start+timedelta(hours=12)
 dated=work/(label+'.pem');openssl('ca','-batch','-notext','-config',config,'-in',csr,'-startdate',start.strftime('%y%m%d%H%M%SZ'),'-enddate',end.strftime('%y%m%d%H%M%SZ'),'-extfile',ext,'-out',dated);dates[label]=dated
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for name in ['archived-birth-to-durable-operational','custom-endpoint','custom-ca-pin','TLS-policy-conflict','discovery-policy-conflict','durable-policy-conflict','runtime-EST-conflict','runtime-key-mismatch','invalid-leaf','expired-leaf','expired-active-operational','not-yet-valid-leaf','runtime-issuer-mismatch','invalid-EST','unsafe-store-gateway','fresh-F2-default','no-durable-gateway','fault-EST','fault-flash','fault-gateway']:
 f=work/name;r=f/'runtime';s=f/'store';r.mkdir(parents=True);s.mkdir()
 for d in [r,s]:
  for n,p in [('key.pem',key),('operational.pem',leaf),('operational.ca',ca),('insta.pem',ca),('server-ca.pem',birth_ca)]:shutil.copyfile(p,d/n);(d/n).chmod(0o600)
  (d/'cert.pem').write_bytes(birth_leaf.read_bytes());(d/'cert.pem').chmod(0o600)
 operational={'server':'gateway.example','port':15002,'cert':str(r/'operational.pem'),'ca':str(r/'operational.ca'),'hostname_validate':1,'valid':True}
 birth={**operational,'cert':str(r/'cert.pem'),'ca':str(r/'server-ca.pem')}
 est={'server':'est.example:2443','tls_ca':str(r/'insta.pem')}
 for p,value in [(s/'gateway.json',operational),(r/'gateway.json',birth),(r/'gateway.flash',birth),(s/'est.json',est),(r/'discovery-policy.json',{'mode':'default','default':'fallback.example:15002'})]:p.write_text(json.dumps(value));p.chmod(0o600)
 # These runtime selectors represent the older updater's explicit archive.
 if name=='archived-birth-to-durable-operational':
  archive=f/'old-upgrade.tar';subprocess.run(['tar','cf',str(archive),'-C',str(r),'gateway.json','gateway.flash','key.pem','operational.pem','operational.ca'],check=True)
  for n in ['gateway.json','gateway.flash','key.pem','operational.pem','operational.ca']:(r/n).unlink()
  subprocess.run(['tar','xf',str(archive),'-C',str(r)],check=True)
 if name=='custom-endpoint':birth['server']='operator.example'
 if name=='custom-ca-pin':birth['ca']=str(r/'custom.ca');(r/'custom.ca').write_bytes(ca.read_bytes())
 if name=='TLS-policy-conflict':birth['hostname_validate']=0
 if name in ['custom-endpoint','custom-ca-pin','TLS-policy-conflict']:
  for p in [r/'gateway.json',r/'gateway.flash']:p.write_text(json.dumps(birth))
 if name=='discovery-policy-conflict':(r/'discovery-policy.json').write_text(json.dumps({'default':'operator.example:15002','allowed':['operator.example:15002']}))
 if name=='runtime-EST-conflict':(r/'est.json').write_text(json.dumps({**est,'server':'operator-est.example'}));(r/'est.json').chmod(0o600)
 if name=='durable-policy-conflict':(s/'discovery-policy.json').write_text(json.dumps({'default':'operator.example:15002','allowed':['operator.example:15002']}));(s/'discovery-policy.json').chmod(0o600)
 if name=='expired-active-operational':
  for d in [r,s]:(d/'operational.pem').write_bytes(dates['expired-leaf'].read_bytes())
  for n in ['gateway.json','gateway.flash']:(r/n).write_text(json.dumps(operational))
 if name in dates:
  for d in [r,s]:(d/'operational.pem').write_bytes(dates[name].read_bytes())
 if name=='runtime-key-mismatch':(r/'key.pem').write_text('different synthetic key')
 if name=='invalid-leaf':
  for d in [r,s]:(d/'operational.pem').write_text('invalid synthetic leaf')
 if name=='runtime-issuer-mismatch':(r/'operational.ca').write_text('different synthetic issuer')
 if name=='invalid-EST':(s/'est.json').write_text(json.dumps({**est,'server':'https://invalid.example'}))
 if name=='unsafe-store-gateway':(s/'gateway.json').rename(s/'actual');(s/'gateway.json').symlink_to(s/'actual')
 if name=='fresh-F2-default':(r/'gateway.default.json').write_text(json.dumps(operational))
 if name=='no-durable-gateway':(s/'gateway.json').unlink()
 helper=(src/'usr/libexec/ucentral-restore-operational-gateway').read_text().replace('/usr/share/ucentral/discovery_policy.uc',str(module)).replace("'/certificates'",repr(str(s))).replace("'/etc/ucentral'",repr(str(r)))
 normal=f/'restore.uc';normal.write_text(helper)
 faulty=f/'faulty.uc';faulty.write_text(helper.replace("import * as fs from 'fs';","import * as realfs from 'fs';\nlet fs={...realfs,rename:(a,b)=>b==getenv('RESTORE_FAULT')?false:realfs.rename(a,b)};"))
 wrapper=f/'restore';wrapper.write_text('#!/bin/sh\nexec '+ucode+' '+str(faulty if name.startswith('fault-') else normal)+'\n');wrapper.chmod(0o700)
 core=f/'core';core.write_text('ab_family(){ return 0; }\n');mount=f/'mount';mount.write_text('#!/bin/sh\nexit 0\n');mount.chmod(0o700)
 prepare=f/'prepare';prepare.write_text('#!/bin/sh\nexit 0\n');prepare.chmod(0o700)
 policy_source=(src/'usr/libexec/ucentral-restore-discovery-policy').read_text().replace('/usr/share/ucentral/discovery_policy.uc',str(module)).replace("'/certificates'",repr(str(s))).replace("'/etc/ucentral'",repr(str(r)))
 policy_program=f/'policy.uc';policy_program.write_text(policy_source)
 policy=f/'policy';policy.write_text('#!/bin/sh\nexec '+ucode+' '+str(policy_program)+'\n');policy.chmod(0o700)
 boot=(src/'etc/init.d/early_boot').read_text()
 for a,b in [('/usr/libexec/ucentral-installer-boot',str(prepare)),('/usr/libexec/ucentral-restore-operational-gateway',str(wrapper)),('/usr/libexec/ucentral-restore-discovery-policy',str(policy)),('/usr/bin/mount_certs',str(mount)),('/lib/functions/cambium-ab.sh',str(core)),('/etc/ucentral',str(r)),('/certificates',str(s))]:boot=boot.replace(a,b)
 program=f/'boot';program.write_text(boot+'\nboard_name(){ echo cambiumnetworks,e410; }\nboot\n')
 identity={str(p):sha(p) for d in [r,s] for p in d.iterdir() if p.suffix in ['.pem','.ca']}
 before={n:(r/n).read_bytes() if (r/n).exists() else None for n in ['gateway.json','gateway.flash','est.json']}
 env=os.environ.copy()
 if name.startswith('fault-'):env['RESTORE_FAULT']=str(r/({'fault-EST':'est.json','fault-flash':'gateway.flash','fault-gateway':'gateway.json'}[name]))
 p=subprocess.run(['sh',str(program)],env=env,capture_output=True,text=True)
 invalid=name in ['runtime-key-mismatch','invalid-leaf','expired-leaf','expired-active-operational','not-yet-valid-leaf','runtime-issuer-mismatch','invalid-EST','unsafe-store-gateway']
 assert (p.returncode!=0)==(invalid or name.startswith('fault-')),(name,p.returncode,p.stdout,p.stderr)
 if name.startswith('fault-'):
  wrapper.write_text('#!/bin/sh\nexec '+ucode+' '+str(normal)+'\n')
  p=subprocess.run(['sh',str(program)],capture_output=True,text=True);assert p.returncode==0,(name,p.stderr)
 if name=='archived-birth-to-durable-operational' or name.startswith('fault-'):
  for n in ['gateway.json','gateway.flash']:assert json.loads((r/n).read_text())==operational,(name,n)
  assert (r/'est.json').read_bytes()==(s/'est.json').read_bytes()
  final={n:sha(r/n) for n in ['gateway.json','gateway.flash','est.json']}
  p=subprocess.run(['sh',str(program)],capture_output=True,text=True);assert p.returncode==0,p.stderr
  assert {n:sha(r/n) for n in final}==final
 else:
  assert {n:(r/n).read_bytes() if (r/n).exists() else None for n in before}==before,name
 assert {str(p):sha(p) for d in [r,s] for p in d.iterdir() if p.suffix in ['.pem','.ca']}==identity,name
 if name=='archived-birth-to-durable-operational' or name.startswith('fault-'):
  cloud=(repo/'feeds/tip/cloud_discovery/files/usr/bin/cloud_discovery').read_text()
  def function(n):
   start=cloud.index('function '+n+'(');a=cloud.index('{',start);depth=1;i=a+1
   while depth:depth+=(cloud[i]=='{')-(cloud[i]=='}');i+=1
   return cloud[start:i]+'\n'
  selected=f/'selected.uc';selected.write_text("import * as fs from 'fs';\nimport {select_controller,default_policy} from '"+str(module)+"';\n"+''.join(function(n) for n in ['readjsonfile','discovery_policy','controller_allowed','gateway_credentials_ready','installer_default','pinned_gateway']).replace('/etc/ucentral',str(r))+"let g=pinned_gateway();if(g?.cert!=ARGV[0]||g?.ca!=ARGV[1])die('wrong active pin');\n")
  subprocess.run([ucode,str(selected),str(r/'operational.pem'),str(r/'operational.ca')],check=True)
  # Execute the actual native init's argument construction against restored JSON.
  native=(target/'etc/init.d/ucentral').read_text();native=native[native.index('start_service()'):]
  functions=f/'functions';functions.write_text('config_load(){ :; }; config_get(){ eval "$1=${4:-0}"; };\n')
  config=f/'config';config.mkdir();shadow=f/'shadow';shadow.mkdir();(shadow/'ucentral').write_text('synthetic config')
  for n,v in [('capabilities.json','{}'),('platform','ap'),('version','synthetic-version')]: (r/n).write_text(v)
  ready=f/'network.ready';ready.touch();binary=f/'bin';binary.mkdir()
  jf=binary/'jsonfilter';jf.write_text("#!/usr/bin/python3\nimport json,sys\nv=json.load(sys.stdin).get(sys.argv[2].split(chr(34))[1],'')\nprint(str(v).lower() if isinstance(v,bool) else v)\n");jf.chmod(0o700)
  for a,b in [('/usr/libexec/ucentral-installer-boot','fixture_boot'),('/usr/libexec/ucentral-boot-report','fixture_report'),('/lib/functions.sh',str(functions)),('/tmp/ucentral-network.ready',str(ready)),('/etc/ucentral',str(r)),('/tmp/ucentral.version',str(r/'version')),('/etc/config-shadow',str(shadow)),('/etc/config/',str(config)+'/'),('/tmp/ucentral/',str(f/'daemon')+'/')]:native=native.replace(a,b)
  shim='PROG=/usr/sbin/ucentral; fixture_boot(){ return 0; }; fixture_report(){ :; }; mount(){ :; }; procd_open_instance(){ :; }; procd_set_param(){ echo param:$*; }; procd_append_param(){ echo append:$*; }; procd_close_instance(){ :; };\n'
  driver=f/'native-init';driver.write_text(shim+native+'\nstart_service\n')
  p=subprocess.run(['sh',str(driver)],env={**os.environ,'PATH':str(binary)+':'+os.environ['PATH']},capture_output=True,text=True)
  assert p.returncode==0 and 'append:command -c '+str(r/'operational.pem')+' -C '+str(r/'operational.ca') in p.stdout,(p.stdout,p.stderr)
 if name=='expired-active-operational':
  cloud=(repo/'feeds/tip/cloud_discovery/files/usr/bin/cloud_discovery').read_text()
  start=cloud.index('function expiry_handler()');end=cloud.index('let ubus_methods',start);expired=cloud[start:end].replace('system(','fixture_system(')
  expiry=f/'expiry.uc';expiry.write_text("import * as realfs from 'fs';let called=0;let timeouts={expiry_threshold:86400};let fs={stat:(p)=>p=='/tmp/ntp.set'?{type:'file'}:realfs.stat(replace(p,'/etc/ucentral',ARGV[0]))};function gateway_load(){return {cert:'/etc/ucentral/operational.pem'};}function ulog(...v){}let LOG_INFO=1;function trigger_reenroll(){called++;return 1;}function fixture_system(c){return system(replace(c,'/etc/ucentral',ARGV[0])+' >/dev/null 2>&1');}\n"+expired+"expiry_handler();if(called!=1)die('expired active identity did not reach existing renewal path');\n")
  subprocess.run([ucode,str(expiry),str(r)],check=True)
  assert {str(p):sha(p) for d in [r,s] for p in d.iterdir() if p.suffix in ['.pem','.ca']}==identity
  cases.append('expired-active-identity-retains-existing-renewal-attempt')
 cases.append(name)
print(json.dumps({'passed':True,'count':len(cases),'cases':cases,'helper_sha256':sha(src/'usr/libexec/ucentral-restore-operational-gateway'),'early_boot_sha256':sha(src/'etc/init.d/early_boot'),'scope':'Actual target ucode with host OpenSSL and early_boot saved-identity path; actual old-selector tar replay, second boot and interrupted atomic publication. Synthetic Root files only; mount/installer boundaries isolated. No AP/trust/ENV/build writes.'},indent=2))
