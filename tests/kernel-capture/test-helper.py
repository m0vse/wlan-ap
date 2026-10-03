"""Actual target ucode validation/apply/rollback with private synthetic configfs."""
from pathlib import Path
import json,re,subprocess,sys,tempfile
root,source=map(Path,sys.argv[1:3]);d=Path(tempfile.mkdtemp(prefix='netconsole-helper-'))
s=source.read_text();s=re.sub(r'^#!.*\n','',s);s=re.sub(r'^import .*\n','',s,flags=re.M);s=s.replace('exit(', 'mock_exit(')
base={'enabled':'1','device':'eth0','local_ip':'192.0.2.10','remote_ip':'192.0.2.20','remote_mac':'02:00:00:00:00:01','local_port':'6665','remote_port':'6666'}
cases=[('disabled',{'enabled':'0'},'apply',0),('valid',{},'apply',0),('validate-only',{},'validate',0),('bad-enable',{'enabled':'yes'},'apply',1),('bad-device',{'device':'../eth0'},'apply',1),('loopback',{'device':'lo'},'apply',1),('bad-ip',{'remote_ip':'999.0.0.1'},'apply',1),('multicast-ip',{'remote_ip':'224.0.0.1'},'apply',1),('leading-zero',{'local_ip':'192.000.2.10'},'apply',1),('bad-mac',{'remote_mac':'bad'},'apply',1),('multicast-mac',{'remote_mac':'01:00:00:00:00:01'},'apply',1),('zero-mac',{'remote_mac':'00:00:00:00:00:00'},'apply',1),('bad-port',{'remote_port':'0'},'apply',1),('huge-port',{'remote_port':'65536'},'apply',1),('wireless',{'wireless':True},'apply',1),('missing-device',{'no_device':True},'apply',1),('link-down',{'down':True},'apply',1),('no-carrier',{'no_carrier':True},'apply',1),('missing-dynamic',{'no_dynamic':True},'apply',1),('write-failure',{'fail':'remote_ip'},'apply',1),('stop',{'exists':True},'stop',0),('disabled-reload',{'enabled':'0','exists':True},'apply',0)]
h="""let c=json(ARGV[0]), writes=[],removed=false,exists=!!c.exists;ARGV=[c.op];
let libuci={cursor:()=>({load:()=>true,get_all:()=>c})};
let fs={stat:path=>{if(path=='/sys/kernel/config/netconsole/ucentral')return exists?{}:null;if(path=='/sys/kernel/config/netconsole')return c.no_dynamic?null:{};if(index(path,'/wireless')>=0)return c.wireless?{}:null;return c.no_device?null:{};},mkdir:()=>{exists=true;return true;},rmdir:()=>{removed=true;exists=false;return true;},readfile:path=>{if(index(path,'/flags')>=0)return c.down?'0x0':'0x1003';if(index(path,'/carrier')>=0)return c.no_carrier?'0':'1';return 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';},writefile:(path,value)=>{push(writes,{path,value});return c.fail&&substr(path,-length(c.fail))==c.fail?null:1;}};
function mock_exit(code){printf('%J\\n',{writes,removed});exit(code);}
"""
for name,changes,op,rc in cases:
 c={**base,**changes,'op':op};p=d/'fixture.uc';p.write_text(h+s+"\nmock_exit(0);\n")
 r=subprocess.run(['/usr/bin/qemu-aarch64','-L',str(root),str(root/'usr/bin/ucode'),str(p),json.dumps(c)],capture_output=True,text=True)
 assert r.returncode==rc,(name,r.stdout,r.stderr)
 out=json.loads(r.stdout);writes=out['writes']
 if name=='valid': assert writes[-2]['path'].endswith('/enabled') and writes[-2]['value']=='1\n' and writes[-1]['path']=='/dev/kmsg'
 elif name=='write-failure': assert writes[-1]['path'].endswith('/enabled') and writes[-1]['value']=='0\n' and not any(x['value']=='1\n' and x['path'].endswith('/enabled') for x in writes)
 elif name in ['stop','disabled-reload']: assert out['removed'] and writes[0]['value']=='0\n'
 else: assert not writes,(name,writes)
print(f'PASS {len(cases)} actual target capture-helper controls')
