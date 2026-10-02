"""Actual renewal validation with real synthetic CA/leaf/key material only."""
import hashlib,json,os,pathlib,re,subprocess,sys,tempfile
source=pathlib.Path(sys.argv[1]);ucode=os.environ['OW_TEST_UCODE']
text=source.read_text();function=re.search(r'(?ms)^function valid_renewal_candidate\(.*?^\}',text).group()
work=pathlib.Path(tempfile.mkdtemp(prefix='renewal-crypto.'));store=work/'etc/ucentral';store.mkdir(parents=True);(work/'tmp').mkdir()
def run(*args):
    subprocess.run(['openssl',*args],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
run('req','-x509','-newkey','rsa:2048','-nodes','-days','3650','-subj','/CN=Fixture CA','-keyout',str(work/'ca.key'),'-out',str(store/'operational.ca'))
run('genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:2048','-out',str(store/'key.pem'))
run('genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:2048','-out',str(work/'other.key'))
def leaf(name,key,cn='30cbc75d92f3',days=365,trusted=True):
    csr=work/(name+'.csr');cert=work/'tmp'/(name+'.pem')
    run('req','-new','-key',str(key),'-subj','/CN='+cn,'-out',str(csr))
    signing=['-CA',str(store/'operational.ca'),'-CAkey',str(work/'ca.key'),'-CAcreateserial'] if trusted else ['-signkey',str(key)]
    run('x509','-req','-in',str(csr),*signing,'-days',str(days),'-out',str(cert))
    return cert
old=leaf('previous',store/'key.pem');(store/'operational.pem').write_bytes(old.read_bytes())
leaf('valid',store/'key.pem');leaf('wrong-key',work/'other.key');leaf('wrong-subject',store/'key.pem',cn='other-device');leaf('untrusted',store/'key.pem',trusted=False);leaf('expired',store/'key.pem',days=0)
(work/'tmp/malformed.pem').write_text('not a certificate')
setup='''import * as realfs from 'fs';let root=ARGV[0];
function mapped(p){return root+p;}function command(c){return replace(replace(c,/\\/tmp\\//g,root+'/tmp/'),/\\/etc\\/ucentral\\//g,root+'/etc/ucentral/');}
let fs={stat:(p)=>realfs.stat(mapped(p)),popen:(c)=>realfs.popen(command(c))};
function test_system(c){assert(index(c,'openssl ')==0,'unexpected command');return system(command(c));}
'''
driver=work/'crypto.uc';driver.write_text(setup+function.replace('system(','test_system(')+'''let cases=[];
for(let c in [['valid',true],['wrong-key',false],['wrong-subject',false],['untrusted',false],['expired',false],['malformed',false]]){
 let accepted=valid_renewal_candidate('/tmp/'+c[0]+'.pem','/etc/ucentral/operational.pem','/etc/ucentral/operational.ca');assert(!!accepted==c[1],c[0]);push(cases,{case:c[0],passed:true,accepted:!!accepted});}
assert(!valid_renewal_candidate('/tmp/valid.pem','/etc/ucentral/operational.pem','/etc/ucentral/absent.ca'),'absent CA');push(cases,{case:'absent-ca',passed:true});
assert(!valid_renewal_candidate('/tmp/valid.pem','/etc/ucentral/operational.pem','/etc/ucentral/../unsafe.ca'),'unsafe CA path');push(cases,{case:'unsafe-ca-path',passed:true});
printf('%.J\\n',{passed:true,count:length(cases),cases});
''')
p=subprocess.run([ucode,str(driver),str(work)],capture_output=True,text=True);assert p.returncode==0,(p.stdout,p.stderr)
report=json.loads(p.stdout[p.stdout.index('{'):])
year=subprocess.run(['openssl','x509','-checkend','31536000','-noout','-in',str(store/'operational.pem')],capture_output=True)
ninety=subprocess.run(['openssl','x509','-checkend','7776000','-noout','-in',str(store/'operational.pem')],capture_output=True)
assert year.returncode!=0 and ninety.returncode==0
report['cases'].append({'case':'fresh-one-year-leaf-renews-not-immediately-at-90-days','passed':True});report['count']+=1
report['source_sha256']=hashlib.sha256(text.encode()).hexdigest()
report['scope']='Actual validation function/native OpenSSL with synthetic CA/keys/leaves; filesystem and command literals mapped into private fixture. No EST, AP identity, trust activation, credential persistence or service operations.'
print(json.dumps(report,indent=2))
