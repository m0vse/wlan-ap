"""Actual EST selection/persistence functions; isolated failure boundaries."""
import json,os,pathlib,re,subprocess,sys,tempfile
source=pathlib.Path(sys.argv[1]).read_text();ucode=os.environ['OW_TEST_UCODE']
def function(n):return re.search(r'(?ms)^function '+n+r'\(.*?^\}',source).group().replace('system(','test_system(')
setup='''let LOG_INFO=0;function ulog(...v){};let est_server_override=null;let est_server='est.certificates.open-lan.org';let caa=null;let issuer='issuer=Unknown Test CA';let issuer_status=0;
function discover_est_server_via_caa(){return caa;}
let commands=[];let failure='';let rename_ok=true;let renamed=[];
let fs={popen:()=>({read:()=>issuer,close:()=>issuer_status}),rename:(s,d)=>{if(rename_ok)push(renamed,d);return rename_ok;}};
function test_system(c){push(commands,c);return (failure && index(c,failure)==0)?1:0;}
let cases=[];function check(n,v){assert(v,n);push(cases,{case:n,passed:true});}function reset(){est_server_override=null;est_server='est.certificates.open-lan.org';caa=null;issuer='issuer=Unknown Test CA';issuer_status=0;commands=[];failure='';rename_ok=true;renamed=[];}
'''
cases='''
reset();check('unknown-issuer-no-implicit-public-est',set_est_server()==1&&est_server=='est.certificates.open-lan.org');
reset();est_server_override='configured.example';check('existing-explicit-est-override-retained',set_est_server()==0&&est_server=='configured.example');
reset();issuer='issuer=OpenLAN Birth Issuing CA';check('stock-production-issuer-selection-preserved',set_est_server()==0);
reset();issuer='issuer=OpenLAN Demo Birth CA';check('stock-demo-issuer-selection-preserved',set_est_server()==0&&est_server=='qaest.certificates.open-lan.org:8001');
reset();issuer='issuer=OpenLAN Demo Birth CA';issuer_status=1;check('issuer-reader-error-not-est-success',set_est_server()==1);
reset();failure='mount_certs';check('mount-failure-refuses-persistence',store_operational_cert('/tmp/candidate.pem','operational.pem')==1&&length(commands)==1&&!length(renamed));
reset();failure='cp ';check('stage-copy-failure-refuses-persistence',store_operational_cert('/tmp/candidate.pem','operational.pem')==1&&!length(renamed));
reset();rename_ok=false;check('durable-rename-failure-is-error',store_operational_cert('/tmp/candidate.pem','operational.pem')==1);
reset();failure='sync';check('durable-sync-failure-is-error',store_operational_cert('/tmp/candidate.pem','operational.pem')==1);
reset();check('unsafe-store-target-refused-before-command',store_operational_cert('/tmp/candidate.pem','../key.pem')==1&&!length(commands));
reset();check('durable-single-file-success-propagated',store_operational_cert('/tmp/candidate.pem','operational.pem')==0&&renamed[0]=='/certificates/operational.pem');
printf('%.J\\n',{passed:true,count:length(cases),cases,scope:'Actual EST selection/persistence functions; file/process boundaries stubbed, no network or live credential operations.'});
'''
work=pathlib.Path(tempfile.mkdtemp(prefix='est-boundary-tests.'));driver=work/'test.uc';driver.write_text(setup+function('set_est_server')+function('store_operational_cert')+cases)
p=subprocess.run([ucode,str(driver)],capture_output=True,text=True);assert p.returncode==0,(p.stdout,p.stderr)
print(json.dumps(json.loads(p.stdout),indent=2))
