#!/usr/bin/env python3
"""Execute the real Miami package install, RAM hook and radio-ready helper."""
from pathlib import Path
import argparse,json,os,re,stat,subprocess,tempfile
p=argparse.ArgumentParser();p.add_argument('--jsonfilter',required=True);p.add_argument('--repo',type=Path);a=p.parse_args()
repo=a.repo or Path(__file__).resolve().parents[3];pkg=repo/'feeds/tip/cambium-miami-radio';make=(pkg/'Makefile').read_text()
body=make.split('define Package/cambium-miami-radio/install\n',1)[1].split('\nendef',1)[0]
with tempfile.TemporaryDirectory(prefix='miami-package-') as td:
 root=Path(td)/'root';root.mkdir()
 commands=body.replace('$(1)',str(root))
 for name,value in [('INSTALL_DIR','install -d -m0755'),('INSTALL_DATA','install -m0644'),('INSTALL_BIN','install -m0755')]:commands=commands.replace('$('+name+')',value)
 subprocess.run(['sh','-ec',commands],cwd=pkg,check=True)
 assert (root/'etc/ucentral/platform').read_text()=='ap\n'
 assert (root/'etc/ucentral/compatible').read_text()=='cambium_x7-35x\n'
 assert '+jsonfilter' in make
 assert not (root/'etc/ucentral/country').exists()
 assert not (root/'etc/ucentral/ucentral.defaults').exists()
 assert not (root/'certificates/ucentral.defaults').exists()
 assert not (root/'etc/modules.conf').exists()
 for path in ['tmp/sysinfo','proc','etc/ucentral','rom/etc/ucentral','bin']:(root/path).mkdir(parents=True,exist_ok=True)
 (root/'tmp/sysinfo/board_name').write_text('cambiumnetworks,x7-35x\n')
 (root/'proc/mounts').write_text('tmpfs / tmpfs rw 0 0\n')
 factory=root/'etc/ucentral/ucentral.cfg.0000000001';factory.write_text('{"uuid":1,"interfaces":[]}\n')
 hook=(root/'etc/uci-defaults/01-miami-ram-bootstrap').read_text()
 paths=['/tmp/sysinfo','/proc/mounts','/rom/etc/ucentral','/etc/ucentral']
 hook=re.sub('|'.join(re.escape(s) for s in paths),lambda m:str(root/m.group().lstrip('/')),hook)
 subprocess.run(['sh','-ec',hook],check=True)
 assert (root/'etc/ucentral/platform').read_text()=='ap\n'
 snapshot=root/'rom/etc/ucentral/ucentral.cfg.0000000001'
 assert snapshot.read_bytes()==factory.read_bytes() and stat.S_IMODE(snapshot.stat().st_mode)==0o444
 # Platform is installed for persistent images too; the RAM hook skips their ROM.
 snapshot.unlink();(root/'proc/mounts').write_text('/dev/root / squashfs ro 0 0\n')
 subprocess.run(['sh','-ec',hook],check=True);assert not snapshot.exists() and (root/'etc/ucentral/platform').read_text()=='ap\n'
 helper=(root/'usr/libexec/miami-radio-ready').read_text().replace('/etc/ucentral/capabilities.json',str(root/'etc/ucentral/capabilities.json'))
 ready=root/'ready.sh';ready.write_text(helper)
 wrapper=root/'bin/jsonfilter';wrapper.write_text('#!/bin/sh\nexec '+a.jsonfilter+' "$@"\n');wrapper.chmod(0o755)
 env=dict(os.environ,PATH=str(root/'bin')+':'+os.environ['PATH'])
 def check(doc,expected):
  f=root/'etc/ucentral/capabilities.json';f.write_text(doc if isinstance(doc,str) else json.dumps(doc))
  q=subprocess.run(['sh',str(ready)],env=env,capture_output=True,text=True)
  assert (q.returncode==0)==expected,(doc,q.stdout,q.stderr)
 check({'wifi':{p:{'band':[b]} for p,b in [('ahb','2G'),('pci','5G'),('pci+1','6G')]}},True)
 for doc in [{},{'wifi':{}},{'wifi':{'ahb':{'band':['2G']}}},{'wifi':{'ahb':{'band':['2G']},'pci':{'band':['5G']}}},{'wifi':{'one':{'band':['2G','5G','6G']}}},{'wifi':{str(i):{'band':['5G']} for i in range(3)}},'not JSON']:
  check(doc,False)
print('PASS: real package install owns platform=ap for factory/persistent/RAM; real immutable snapshot hook; three-radio readiness rejects partial/invalid capability inventory; no packaged site country/defaults/modules override')
