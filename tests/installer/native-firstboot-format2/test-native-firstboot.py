import pathlib,tempfile,subprocess,os,json,hashlib,ssl,http.server,threading,base64,re
base=pathlib.Path(os.environ['NATIVE_FIRSTBOOT_SOURCE_DIR']);work=pathlib.Path(tempfile.mkdtemp(prefix='native-firstboot.'));work.chmod(0o700)
serial='000000000001';shared='s'*64;requests=[];fail={'post':True}
def ossl(*args):
 p=subprocess.run(['openssl',*map(str,args)],capture_output=True);assert p.returncode==0,p.stderr;return p.stdout
https=work/'https.pem';https_key=work/'https.key';issuer=work/'issuer.pem';issuer_key=work/'issuer.key'
ossl('req','-x509','-newkey','rsa:2048','-nodes','-days',3,'-subj','/CN=HTTPS Fixture Root','-addext','subjectAltName=DNS:localhost','-keyout',https_key,'-out',https)
ossl('req','-x509','-newkey','rsa:2048','-nodes','-days',3,'-subj','/CN=Client Fixture Issuer','-keyout',issuer_key,'-out',issuer)
ca7=base64.b64encode(ossl('crl2pkcs7','-nocrl','-certfile',issuer,'-outform','DER'))
class EST(http.server.BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def respond(self,status,payload):self.send_response(status);self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
 def do_GET(self):assert self.path=='/.well-known/est/cacerts';self.respond(200,ca7)
 def do_POST(self):
  if self.path=='/.well-known/est/simpleenroll':assert self.headers['Authorization']=='Basic '+base64.b64encode((serial+':'+shared).encode()).decode()
  else:assert self.path=='/.well-known/est/simplereenroll' and self.connection.getpeercert() and self.headers.get('Authorization') is None
  csr=base64.b64decode(self.rfile.read(int(self.headers['Content-Length'])),validate=False);requests.append(hashlib.sha256(csr).hexdigest());request=work/'received.csr';request.write_bytes(csr)
  assert ossl('req','-inform','DER','-in',request,'-subject','-noout','-nameopt','RFC2253').strip()==('subject=CN='+serial).encode()
  if fail['post']:self.respond(503,b'');return
  ext=work/'client.ext';ext.write_text('basicConstraints=critical,CA:FALSE\nextendedKeyUsage=clientAuth\nkeyUsage=critical,digitalSignature\n')
  leaf=work/'issued.pem';ossl('x509','-req','-inform','DER','-in',request,'-CA',issuer,'-CAkey',issuer_key,'-CAcreateserial','-days',2,'-extfile',ext,'-out',leaf)
  self.respond(200,base64.b64encode(ossl('crl2pkcs7','-nocrl','-certfile',leaf,'-outform','DER')))
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),EST);tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(https,https_key);tls.load_verify_locations(issuer);tls.verify_mode=ssl.CERT_OPTIONAL;server.socket=tls.wrap_socket(server.socket,server_side=True);threading.Thread(target=server.serve_forever,daemon=True).start()
store=work/'store';runtime=work/'runtime';settings=work/'settings';proc=work/'proc';tmp=work/'tmp';bindir=work/'bin'
for d in [store,runtime,settings,proc,tmp,bindir]:d.mkdir(mode=0o700)
(proc/'sys/kernel/random').mkdir(parents=True);boot='12345678-1234-1234-1234-123456789abc';(proc/'sys/kernel/random/boot_id').write_text(boot+'\n')
context=work/'context';context.write_text(serial+'\tsage\tE410\t1\t1\t'+'b'*64+'\t'+'a'*64+'\n')
binding={'format':'2','serial':serial,'family':'sage','model':'E410','source_operation':'production-stock-openwrt-migration','source_release':'2026.09.29.0','source_contract_sha256':'c'*64,'source_slot':'0','target_slot':'1','image_sha256':'a'*64,'job_id':'b'*64}
(settings/'binding.tsv').write_text(''.join(k+'\t'+v+'\n' for k,v in binding.items()))
(settings/'est.json').write_text(json.dumps({'server':'localhost:'+str(server.server_port),'tls_ca':'/etc/ucentral/insta.pem'}))
(settings/'gateway.json').write_text(json.dumps({'server':'gateway.example','port':15002,'cert':'/etc/ucentral/operational.pem','ca':'/etc/ssl/certs/ca-certificates.crt','hostname_validate':1,'allow-self-signed':False,'valid':True}))
(settings/'est-bootstrap.conf').write_text('user = "'+serial+':'+shared+'"\n');(settings/'insta.pem').write_bytes(https.read_bytes())
(settings/'files.sha256').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.name+'\n' for f in sorted(settings.iterdir())))
for f in settings.iterdir():f.chmod(0o600)
store.chmod(0o755);runtime.chmod(0o755);(store/'.cambium-ab-manifest').touch();(store/'.cambium-ab-manifest').chmod(0o600)
root=os.environ['NATIVE_TEST_ROOT'];ucode=os.environ['NATIVE_TEST_UCODE']
curl=bindir/'curl';curl.write_text('#!/bin/sh\nexec /usr/bin/qemu-arm -L '+root+' '+root+'/usr/bin/curl "$@"\n');curl.chmod(0o700);os.environ['PATH']=str(bindir)+':'+os.environ['PATH']
# Execute the actual packaged mount helper against the isolated active-volume table.
mount_table=work/'mounts';mount_table.write_text('/dev/ubi7_4 '+str(store)+' ubifs rw,relatime 0 0\n')
mount_lib=work/'mountlib';mount_lib.write_text('');mount_core=work/'mountcore';mount_core.write_text('ab_family(){ AB_ENV=sage; AB_LAYOUT=pair; AB_ACTIVE_UBI=ubi7; }; ab_identity(){ AB_ACTIVE=1; }; ab_ubi_volume(){ echo ubi7_4; }; ab_getenv(){ case "$1" in *_target) echo 1;; *_job) echo '+('b'*64)+';; *_image) echo '+('a'*64)+';; esac; };\n')
mount_source=(base/'mount_certs').read_text().replace('/lib/functions.sh',str(mount_lib)).replace('/lib/functions/cambium-ab.sh',str(mount_core)).replace('/certificates',str(store)).replace('/etc/ucentral/',str(runtime)+'/').replace('/proc/mounts',str(mount_table));mount_actual=work/'mount-actual';mount_actual.write_text(mount_source)
mount_wrapper=bindir/'mount_certs';mount_wrapper.write_text('#!/bin/sh\nexec sh '+str(mount_actual)+' "$@"\n');mount_wrapper.chmod(0o700)
# Full native EST script executes its real dispatch, crypto and HTTPS code.
# Only filesystem locations, UCI serial and mount/store commands are isolated.
source=(base/'est_client').read_text().replace("import * as fs from 'fs';","import * as realfs from 'fs';").replace("import * as libuci from 'uci';","let libuci={cursor:()=>({get:()=> '"+serial+"'})};")
source=source.replace('system(', 'fixture_system(')
adapter="""function mapped(p){if(type(p)!='string')return p;for(let pair in [['/certificates',STORE],['/etc/ucentral',RUNTIME],['/tmp',TMP]]){if(p==pair[0]||index(p,pair[0]+'/')==0)return pair[1]+substr(p,length(pair[0]));}return p;}
function command(c){return replace(replace(replace(c,/\\/tmp\\//g,TMP+'/'),/\\/certificates/g,STORE),/\\/etc\\/ucentral/g,RUNTIME);}
function fixture_system(c){if(c=='store_certs')return 0;if(index(c,'mount_certs')==0)return system(c);return system(command(c));}
let fs={stat:(p)=>realfs.stat(mapped(p)),lstat:(p)=>realfs.lstat(mapped(p)),readfile:(p)=>realfs.readfile(mapped(p)),open:(p,...v)=>realfs.open(mapped(p),...v),popen:(c)=>realfs.popen(command(c)),rename:(a,b)=>realfs.rename(mapped(a),mapped(b)),unlink:(p)=>realfs.unlink(mapped(p))};
""".replace('STORE',json.dumps(str(store))).replace('RUNTIME',json.dumps(str(runtime))).replace('TMP',json.dumps(str(tmp)))
# Imports/declarations precede all actual native file reads.
position=source.index("let store_operational_pem");source=source[:position]+adapter+source[position:];native=work/'native-est.uc';native.write_text(source)
native_wrapper=bindir/'native-est-client';native_wrapper.write_text('#!/bin/sh\numask 077\nexec '+ucode+' '+str(native)+' "$@" >'+str(work/'native.log')+' 2>&1\n');native_wrapper.chmod(0o700)
text=(base/'ucentral-installer-identity').read_text().replace("const STORE = '/certificates';","const STORE = '"+str(store)+"';").replace("const RUNTIME = '/etc/ucentral';","const RUNTIME = '"+str(runtime)+"';").replace("const PROC = '/proc';","const PROC = '"+str(proc)+"';").replace("const SETTINGS = '/root/.cambium-installer-settings';","const SETTINGS = '"+str(settings)+"';")
status_file=work/'status.json';status_file.write_text('{}');status_file.chmod(0o600)
text=text.replace("import * as libubus from 'ubus';","let libubus={connect:()=>({call:()=>json(fs.readfile("+json.dumps(str(status_file))+"))})};")
text=re.sub(r'^const CONTEXT_COMMAND = .*$',"const CONTEXT_COMMAND = 'cat "+str(context)+"';",text,flags=re.M);text=re.sub(r'^const MOUNT_COMMAND = .*$',"const MOUNT_COMMAND = 'true';",text,flags=re.M)
text=text.replace('/tmp/ucentral-network.ready',str(work/'network.ready')).replace('/tmp/ntp.set',str(work/'clock.ready')).replace('/tmp/ucentral-installer-ready',str(work/'ready')).replace('/usr/bin/est_client',str(native_wrapper))
stable_file=work/'stable';stable_file.write_text('unconfirmed')
text=text.replace("if (system(command)) fail('Confirmed stable boot state has not been read back');","if (fs.readfile("+json.dumps(str(stable_file))+")!='confirmed') fail('Confirmed stable boot state has not been read back');")
text=text.replace("warn('Native first-boot operation refused.\\n');","warn('Synthetic first-boot refused: '+e+'\\n');")
helper=work/'firstboot.uc';helper.write_text(text)
def invoke(op,ok):
 p=subprocess.run([ucode,str(helper),op,str(settings)],capture_output=True,text=True);assert (p.returncode==0)==ok,(op,p.stdout,p.stderr,(work/'native.log').read_text() if (work/'native.log').exists() else '',len(requests),str(work));return p
(runtime/'discovery-policy.json').write_text(json.dumps({'mode':'default','default':'openwifi.wlan.local:15002'}));(runtime/'discovery-policy.json').chmod(0o644)
invoke('prepare-settings',True)
expected_policy={'mode':'default','default':'gateway.example:15002'}
for directory in [store,runtime]:assert json.loads((directory/'discovery-policy.json').read_text())==expected_policy
explicit_policy=json.dumps({'default':'operator.example:15002','allowed':['operator.example:15002']})
for directory in [store,runtime]:(directory/'discovery-policy.json').write_text(explicit_policy)
invoke('prepare-settings',True)
for directory in [store,runtime]:assert (directory/'discovery-policy.json').read_text()==explicit_policy;(directory/'discovery-policy.json').write_text(json.dumps(expected_policy))
assert not (store/'key.pem').exists() and not requests
invoke('enroll-settings',False);assert not (store/'key.pem').exists() and not requests
(work/'network.ready').touch();(work/'clock.ready').touch();invoke('enroll-settings',False)
key_before=hashlib.sha256((store/'key.pem').read_bytes()).hexdigest();csr_before=hashlib.sha256((store/'.installer-import/csr.pem').read_bytes()).hexdigest();assert (store/'.installer-import/issuance-intent.json').is_file()
# Candidate reboot during failed issuance restores the same persisted key/CSR.
for f in runtime.iterdir():f.unlink()
(proc/'sys/kernel/random/boot_id').write_text('32345678-1234-1234-1234-123456789abc\n')
invoke('prepare-settings',True)
# Missing/corrupt CSR after persisted intent must refuse without contacting EST.
csr_path=store/'.installer-import/csr.pem';saved_csr=csr_path.read_bytes();csr_path.unlink();invoke('enroll-settings',False);assert len(requests)==1
csr_path.write_bytes(b'corrupt\n');csr_path.chmod(0o600);invoke('enroll-settings',False);assert len(requests)==1
csr_path.write_bytes(saved_csr);csr_path.chmod(0o600)
fail['post']=False;invoke('enroll-settings',True);assert len(requests)==2 and len(set(requests))==1
assert key_before==hashlib.sha256((store/'key.pem').read_bytes()).hexdigest() and csr_before==hashlib.sha256((store/'.installer-import/csr.pem').read_bytes()).hexdigest()
invoke('check-settings',True);invoke('enroll-settings',True);assert len(requests)==2
# Reboot: only volatile runtime/ready and process bookkeeping change.
for f in runtime.iterdir():f.unlink()
(work/'ready').unlink();(proc/'sys/kernel/random/boot_id').write_text('22345678-1234-1234-1234-123456789abc\n')
invoke('prepare-settings',True);invoke('check-settings',False);invoke('enroll-settings',True);invoke('check-settings',True);assert len(requests)==2
assert key_before==hashlib.sha256((store/'key.pem').read_bytes()).hexdigest() and csr_before==hashlib.sha256((store/'.installer-import/csr.pem').read_bytes()).hexdigest()
# Actual confirmation helper: failed/stale/disconnected receipt must retain credentials.
pid=4321;pd=proc/str(pid);pd.mkdir();(pd/'exe').symlink_to('/usr/sbin/ucentral');(pd/'comm').write_text('ucentral\n');(pd/'cmdline').write_bytes(('ucentral\x00-h\x00-S\x00'+serial+'\x00-c\x00'+str(runtime/'operational.pem')+'\x00-C\x00/etc/ssl/certs/ca-certificates.crt\x00-s\x00gateway.example\x00-P\x0015002\x00').encode())
status={'connected':0,'client_pid':pid,'connection_generation':1,'config_received_sequence':2,'config_applied_sequence':2,'config_received_uuid':'18446744073709551615','config_applied_uuid':'18446744073709551615','latest':'18446744073709551615','active':'18446744073709551615'}
for field,value in [('disconnected',0),('client_pid',4322),('config_applied_sequence',1),('config_applied_uuid','1'),('active','1')]:
 bad=dict(status);bad[field]=value;status_file.write_text(json.dumps(bad));invoke('accepted',False);assert (store/'est-bootstrap.conf').exists()
status_file.write_text(json.dumps(status));invoke('accepted',True);assert not (store/'est-bootstrap.conf').exists() and not (runtime/'est-bootstrap.conf').exists();assert json.loads((store/'.installer-import/transaction.json').read_text())['accepted'] is True
# Confirmed cleanup is gated on stable ENV readback and resumes partial deletion.
context.write_text(serial+'\tsage\tE410\t1\t\t\t\n')
invoke('cleanup-confirmed',False);assert settings.exists()
stable_file.write_text('confirmed')
original_helper=helper.read_text();helper.write_text(original_helper.replace("for (let name in fs.lsdir(seed)) if (!fs.unlink(seed + '/' + name))", "for (let name in fs.lsdir(seed)) { if(name=='files.sha256') fail('Synthetic deletion interruption'); if (!fs.unlink(seed + '/' + name))").replace("fail('Confirmed seed cleanup failed');", "fail('Confirmed seed cleanup failed'); }"))
invoke('cleanup-confirmed',False);assert (store/'.installer-import/completion.json').exists()
helper.write_text(original_helper);invoke('cleanup-confirmed',True);assert not settings.exists();assert (store/'key.pem').exists() and (store/'operational.pem').exists()
invoke('cleanup-confirmed',True)
# Simulate a managed upgrade retaining stale birth selectors while the
# already-authorized durable operational activation remains on the store.
for d in [store,runtime]:(d/'gateway.default.json').unlink(missing_ok=True)
selected={'server':'gateway.example','port':15002,'cert':'/etc/ucentral/operational.pem','ca':'/etc/ucentral/operational.ca','hostname_validate':1,'valid':True}
(store/'gateway.json').write_text(json.dumps(selected));(store/'gateway.json').chmod(0o600)
old_selection={**selected,'cert':'/etc/ucentral/cert.pem','ca':'/etc/ucentral/server-ca.pem'}
for n in ['gateway.json','gateway.flash']:(runtime/n).write_text(json.dumps(old_selection));(runtime/n).chmod(0o600)
(runtime/'est.json').unlink(missing_ok=True)
activation_source=(base/'ucentral-restore-operational-gateway').read_text().replace('/usr/share/ucentral/discovery_policy.uc',str(base/'discovery_policy.uc')).replace("'/certificates'",repr(str(store))).replace("'/etc/ucentral'",repr(str(runtime)))
activation=work/'activation.uc';activation.write_text(activation_source)
# Map public serialized paths for the isolated replay and restore them before
# invoking the unchanged native EST dispatch against its production-path adapter.
for d,n in [(store,'gateway.json'),(runtime,'gateway.json'),(runtime,'gateway.flash'),(store,'est.json')]:
 p=d/n;p.write_text(p.read_text().replace('/etc/ucentral',str(runtime)))
pem=(store/'operational.ca').read_bytes();size=223727;bundle=pem*(size//len(pem))+b'\n'*(size%len(pem))
for d in [store,runtime]:(d/'operational.ca').write_bytes(bundle)
identity_before={n:hashlib.sha256((runtime/n).read_bytes()).hexdigest() for n in ['key.pem','operational.pem','operational.ca']}
for replay in range(2):
 p=subprocess.run([ucode,str(activation)],capture_output=True,text=True);assert p.returncode==0,(p.stdout,p.stderr)
 for n in ['gateway.json','gateway.flash']:assert json.loads((runtime/n).read_text())['cert']==str(runtime/'operational.pem')
 assert (runtime/'est.json').read_bytes()==(store/'est.json').read_bytes()
assert {n:hashlib.sha256((runtime/n).read_bytes()).hexdigest() for n in identity_before}==identity_before
for d,n in [(store,'gateway.json'),(runtime,'gateway.json'),(runtime,'gateway.flash'),(store,'est.json'),(runtime,'est.json')]:
 p=d/n;p.write_text(p.read_text().replace(str(runtime),'/etc/ucentral'))
# Native mTLS renewal after confirmed enrollment has consumed the batch credential.
old_leaf=hashlib.sha256((store/'operational.pem').read_bytes()).hexdigest()
fail['post']=True;p=subprocess.run([str(native_wrapper),'reenroll'],capture_output=True,text=True);assert p.returncode!=0
assert hashlib.sha256((store/'operational.pem').read_bytes()).hexdigest()==old_leaf and hashlib.sha256((runtime/'operational.pem').read_bytes()).hexdigest()==old_leaf
fail['post']=False;p=subprocess.run([str(native_wrapper),'reenroll'],capture_output=True,text=True);assert p.returncode==0,(p.stdout,p.stderr,(work/'native.log').read_text())
assert hashlib.sha256((store/'operational.pem').read_bytes()).hexdigest()!=old_leaf and (store/'operational.pem').read_bytes()==(runtime/'operational.pem').read_bytes()
assert hashlib.sha256((store/'key.pem').read_bytes()).hexdigest()==key_before
# An already-selected expired identity still reaches native reenroll; failed
# server mTLS validation must retain its key, leaf and operational selector.
valid_leaf=(store/'operational.pem').read_bytes();expired=work/'expired-native.pem'
from datetime import datetime,timedelta,timezone
expired_csr=work/'expired.csr';ossl('req','-inform','DER','-in',work/'received.csr','-out',expired_csr)
database=work/'expired.index';database.write_text('');serial_file=work/'expired.serial';serial_file.write_text('20\n')
ca_config=work/'expired-ca.config';ca_config.write_text('[ca]\ndefault_ca=fixture\n[fixture]\ndatabase='+str(database)+'\nserial='+str(serial_file)+'\nnew_certs_dir='+str(work)+'\ncertificate='+str(issuer)+'\nprivate_key='+str(issuer_key)+'\ndefault_md=sha256\npolicy=subject\n[subject]\ncommonName=supplied\n')
start=datetime.now(timezone.utc)-timedelta(days=2);end=start+timedelta(days=1)
ossl('ca','-batch','-notext','-config',ca_config,'-in',expired_csr,'-startdate',start.strftime('%y%m%d%H%M%SZ'),'-enddate',end.strftime('%y%m%d%H%M%SZ'),'-extfile',work/'client.ext','-out',expired)
for d in [store,runtime]:(d/'operational.pem').write_bytes(expired.read_bytes())
expired_hash=hashlib.sha256(expired.read_bytes()).hexdigest()
p=subprocess.run([str(native_wrapper),'reenroll'],capture_output=True,text=True);assert p.returncode!=0
for d in [store,runtime]:assert hashlib.sha256((d/'operational.pem').read_bytes()).hexdigest()==expired_hash
assert hashlib.sha256((store/'key.pem').read_bytes()).hexdigest()==key_before
for n in ['gateway.json','gateway.flash']:assert json.loads((runtime/n).read_text())['cert']=='/etc/ucentral/operational.pem'
for d in [store,runtime]:(d/'operational.pem').write_bytes(valid_leaf)
server.shutdown()
report={'passed':True,'cases':['firstboot-generated-fallback-policy','firstboot-preserves-explicit-operator-policy','settings-stage-no-key-no-network','network-clock-gate-before-key','native-EST-503-preserves-key-CSR-intent','native-EST-retry-identical-CSR','reboot-during-503-retains-key-CSR','post-intent-missing-corrupt-CSR-refuses-contact','independent-HTTPS-and-client-issuer-trust','validated-durable-native-leaf','completed-retry-no-reissue','reboot-restores-current-durable-identity','reboot-retains-key-and-CSR','failed-stale-disconnected-config-refuses-confirmation','fresh-applied-config-consumes-bootstrap','actual-packaged-empty-store-mount','cleanup-stable-env-gate','cleanup-partial-delete-resume-retains-identity','managed-operational-selector-and-EST-restored-with-223727-byte-CA-bundle','second-replay-retains-operational-selection','native-mTLS-renewal-without-bootstrap','failed-renewal-retains-current-leaf','successful-renewal-retains-key-and-persists-leaf','expired-selected-native-mTLS-renewal-failure-retains-key-leaf-selector'],'helper_sha256':hashlib.sha256((base/'ucentral-installer-identity').read_bytes()).hexdigest(),'native_est_sha256':hashlib.sha256((base/'est_client').read_bytes()).hexdigest(),'activation_restore_sha256':hashlib.sha256((base/'ucentral-restore-operational-gateway').read_bytes()).hexdigest(),'scope':'Full actual native EST dispatch, target curl, host OpenSSL and first-boot helper, synthetic localhost HTTPS, Root temporary identities; hardware/mount/context/UCI/storage boundaries isolated. No outgoing firmware crypto, AP, real issuer or services.'}
(base/'firstboot-native-protocol-tests.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
