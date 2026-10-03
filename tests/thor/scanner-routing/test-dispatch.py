"""Execute production dispatcher guards under the actual target ucode runtime."""
from pathlib import Path
import re,subprocess,sys,tempfile
root,cmd,alternate=map(Path,sys.argv[1:4]);d=Path(tempfile.mkdtemp(prefix='thor-scan-dispatch-'))
s=cmd.read_text();m=re.search(r"if \(cmd.command == 'wifiscan'.*?cmd.command \+= '7';",s,re.S);assert m
scope="let board,has12,cmd;let fs={readfile:()=>board,stat:()=>has12};\n"
checks="""let count=0;
for(let c in [{board:'cambiumnetworks,xv3-8',has12:true,want:'wifiscan'},{board:'cambiumnetworks,xv3-8',has12:false,want:'wifiscan'},{board:'cambiumnetworks,xe3-4',has12:true,want:'wifiscan7'},{board:'cambiumnetworks,xe3-4',has12:false,want:'wifiscan'}]){board=c.board;has12=c.has12;cmd={command:'wifiscan'}; dispatch();assert(cmd.command==c.want,'wrong dispatch');count++;}
printf('PASS %d production dispatch controls\\n',count);
"""
p=d/'dispatch.uc';p.write_text(scope+'function dispatch(){'+m[0]+'}\n'+checks)
r=subprocess.run(['/usr/bin/qemu-aarch64','-L',str(root),str(root/'usr/bin/ucode'),str(p)],capture_output=True,text=True);assert r.returncode==0,r.stderr;print(r.stdout.strip())
prefix=alternate.read_text().split("import * as libubus",1)[0];assert 'cmd_wifiscan.uc' in prefix
prefix=prefix.replace('include(', 'mock_include(')
s="""let board,calls=0,args=null,ctx={},result_json=()=>null;let fs={readfile:()=>board};
function mock_include(file,scope){assert(file=='./cmd_wifiscan.uc'&&type(scope.args)=='object'&&scope.ctx==ctx&&scope.fs==fs,'redirect lost scope');calls++;}
function route(){"""+prefix+"\nreturn 'alternate';}\nboard='cambiumnetworks,xv3-8';assert(route()==null&&calls==1,'Thor explicit alternate not redirected');board='cambiumnetworks,xe3-4';assert(route()=='alternate'&&calls==1,'other board alternate changed');print('PASS 2 explicit alternate dispatch controls\\n');"
p=d/'alternate.uc';p.write_text(s)
r=subprocess.run(['/usr/bin/qemu-aarch64','-L',str(root),str(root/'usr/bin/ucode'),str(p)],capture_output=True,text=True);assert r.returncode==0,r.stderr;print(r.stdout.strip())
