#!/usr/bin/env python3
"""Actual managed-upgrade archive/flag logic with network/upgrade blocked."""
import hashlib,json,os,pathlib,re,subprocess,sys,tempfile
root=pathlib.Path(sys.argv[1]);ucode=os.environ['OW_TEST_UCODE']
source=(root/'usr/share/ucentral/cmd_upgrade.uc').read_text()
work=pathlib.Path(tempfile.mkdtemp(prefix='managed-upgrade-command-tests.'));cases=[]
for name,flags in [('omitted',{}),('both-false',{'keep_redirector':False,'keep_config':False}),('redirector-only',{'keep_redirector':True,'keep_config':False}),('config-only',{'keep_redirector':False,'keep_config':True})]:
 fixture=work/name;runtime=fixture/'etc/ucentral';runtime.mkdir(parents=True)
 (fixture/'tmp').mkdir();(fixture/'etc/config').mkdir();(fixture/'etc/config-shadow').mkdir()
 (fixture/'etc/config/network').write_text('fixture rendered management config\n')
 (fixture/'etc/config-shadow/network').write_text('fixture complete baseline network\n')
 (fixture/'etc/config-shadow/system').write_text('fixture complete baseline system\n')
 for f in ('key.pem','cert.pem','operational.pem','operational.ca','server-ca.pem','insta.pem','custom-server.ca','discovery-policy.json'):
  (runtime/f).write_text('synthetic fixture '+f+'\n')
 (runtime/'gateway.json').write_text(json.dumps({'ca':str(runtime/'custom-server.ca')}))
 active=runtime/'ucentral.cfg.0000000123';active.write_text('{"uuid":123,"interfaces":[{"name":"managed"}]}\n')
 (runtime/'ucentral.active').symlink_to(active)
 args={'uri':'https://example.invalid/never-contacted.bin',**flags}
 text=re.sub(r'(?<![A-Za-z0-9_])/(?:etc|tmp)(?=/|[\s"\'])',lambda m:str(fixture)+m.group(),source)
 text=text.replace('/upgrade.tgz',str(fixture/'upgrade.tgz'))
 text=text.replace('system(', 'test_system(').replace('sleep(2000);','')
 setup='''import * as libfs from 'fs';
let calls=[];let replies=[];let args=json(ARGV[0]);let restrict={};
let fs={...libfs,popen:(command)=>{assert(index(command,'curl -L ')==0,'unexpected subprocess');push(calls,{kind:'download-stub'});return {read:()=> '200',close:()=>0};}};
let ctx={call:(object,method,input)=>{assert(object=='system'&&method=='validate_firmware_image','unexpected ubus');push(calls,{kind:'validator-stub'});return {valid:true};}};
function result(...values){push(replies,values);}function result_json(value){push(replies,value);}function warn(...values){}function include(...values){}
function test_system(command){if(type(command)=='array'){assert(command[0]=='tar','unexpected argv execution');push(calls,{kind:'actual-private-tar'});return system(command);}push(calls,{kind:'blocked-command',command});return 0;}
'''
 program=fixture/'driver.uc';program.write_text(setup+'function run_command() {\n'+text+'\n}\nrun_command();\nprintf("%.J\\n",{calls,replies});\n')
 p=subprocess.run([ucode,str(program),json.dumps(args)],capture_output=True,text=True)
 assert p.returncode==0,(name,p.stdout,p.stderr)
 record=json.loads(p.stdout);assert record['replies']==[[0,'Triggering FW upgrade']],record
 archive=fixture/'upgrade.tgz';assert archive.is_file()
 listing=subprocess.run(['tar','-tzf',str(archive)],capture_output=True,text=True,check=True).stdout
 for required in ('etc/config/network','etc/config-shadow/network','etc/config-shadow/system','etc/ucentral/key.pem','etc/ucentral/operational.pem','etc/ucentral/custom-server.ca','etc/ucentral/ucentral.active','etc/ucentral/ucentral.cfg.0000000123'):
  assert required in listing,(name,required,listing)
 scheduled=[c['command'] for c in record['calls'] if c['kind']=='blocked-command' and 'sysupgrade ' in c['command']]
 assert len(scheduled)==1 and 'sysupgrade -f ' in scheduled[0] and 'sysupgrade -n' not in scheduled[0],scheduled
 cases.append({'case':name,'passed':True,'config_and_shadow_preserved':True,'active_symlink_and_document_preserved':True,'identity_and_custom_gateway_ca_preserved':True,'sysupgrade_explicit_archive_without_n':True})
print(json.dumps({'passed':True,'count':len(cases),'cases':cases,'command_sha256':hashlib.sha256(source.encode()).hexdigest(),
 'scope':'Actual frozen cmd_upgrade.uc archive and flag logic with filesystem literals redirected to private fixtures; actual tar only. Download/ubus validation/daemon-stop/network-stop/sysupgrade/reboot boundaries blocked. Actual firmware validation and A/B certificate/RAM closure are separate receipts; not physical upgrade proof.'},indent=2))
