#!/usr/bin/env python3
"""Execute actual patched capability-country branch with isolated fs boundary."""
from pathlib import Path
import argparse,subprocess,tempfile,json
p=argparse.ArgumentParser();p.add_argument('--ucode',required=True);p.add_argument('--source',type=Path,required=True);a=p.parse_args();repo=Path(__file__).resolve().parents[3]
with tempfile.TemporaryDirectory(prefix='miami-country-policy-') as td:
 root=Path(td);f=root/'system/capabilities.uc';f.parent.mkdir();f.write_text(a.source.read_text())
 r=subprocess.run(['patch','--fuzz=0','-p1','-i',str(repo/'feeds/ucentral/ucentral-schema/patches/098-miami-unenrolled-country-policy.patch')],cwd=root,capture_output=True,text=True);assert r.returncode==0,(r.stdout,r.stderr)
 old=a.source.read_text();new=f.read_text()
 def block(s):return s[s.index("// Persistent Miami keeps") if '// Persistent Miami keeps' in s else s.index("if (fs.stat('/tmp/squashfs')) {"):s.index("capa.country =")]
 def run(miami,store=None,status=0,original=False,unknown=False):
  files={'/tmp/sysinfo/board_name':'cambiumnetworks,x7-35x' if miami else 'other,family'}
  if store is not None:files['/certificates/ucentral.defaults']=json.dumps({'country':store})
  if unknown:files['/certificates/unknown']='unchanged'
  mock='''let files=FILES;let initial=sprintf('%J',files);let writes={};let default_config={country:'US'};
let fs={
 stat:p=>p=='/proc/device-tree/cambium-platform/storage-slot'?MIAMI:exists(files,p),
 readfile:p=>files[p],
 writefile:function(p,v){writes[p]=v;files[p]=sprintf('%J',v);return true;},
 popen:()=>({read:()=> 'GB',close:()=>STATUS})
};
'''.replace('FILES',json.dumps(files)).replace('MIAMI',json.dumps(miami)).replace('STATUS',str(status))
  script=root/'test.uc';script.write_text(mock+block(old if original else new)+"printf('%J\\n',{files,writes,country:default_config.country});\n")
  q=subprocess.run([a.ucode,str(script)],capture_output=True,text=True)
  if status and miami:assert q.returncode!=0;return
  assert q.returncode==0,(q.stdout,q.stderr);v=json.loads(q.stdout)
  if miami and not original:
   assert v['country']=='GB' and set(v['writes'])=={'/etc/ucentral/ucentral.defaults'},v
   for path in ['/certificates/ucentral.defaults','/certificates/unknown']:
    assert v['files'].get(path)==files.get(path),v
  return v
 run(True);run(True,unknown=True);run(True,store='GB');run(True,status=1)
 for store in [None,'GB','US']:
  assert run(False,store=store)==run(False,store=store,original=True)
print('PASS: actual zero-fuzz capability patch; persistent Miami GB overlay/runtime policy without STORE creation, unknown/existing store preserved, failed context refusal; non-Miami behavior matches baseline')
