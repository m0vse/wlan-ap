#!/usr/bin/env python3
import hashlib,json,pathlib,shutil,subprocess,tempfile
base=pathlib.Path('/home/phil/openwifi-cheetah-build');work=pathlib.Path(tempfile.mkdtemp(prefix='cheetah-runtime-contract.'));cases=[]
for route,source in [('stock',base/'outgoing-source/rootfs'),('preserve',pathlib.Path('/tmp/cheetah-image-check.dixkA1/rootfs'))]:
 suite=base/f'operator-{route}-minimum-r6';ledger=suite/'runtime-implementation.set'
 records=[line.split() for line in ledger.read_text().splitlines()]
 root=work/route;root.mkdir()
 for kind,value,path in records:
  dest=root/path.lstrip('/');src=source/path.lstrip('/');dest.parent.mkdir(parents=True,exist_ok=True)
  if kind in ('F','X'):shutil.copy2(src,dest)
  elif kind=='L':dest.symlink_to(value)
 def check(case,expected):
  result=subprocess.run(['sh','-c','. "$1"; ow_runtime_contract_check "$2" "$3"','fixture',str(suite/'runtime-implementation-contract.sh'),str(ledger),str(root)],capture_output=True,text=True)
  assert (result.returncode==0)==expected,(route,case,result.stderr)
  cases.append(dict(route=route,case=case,accepted=expected,passed=True))
 check('authenticated-tool-and-library-closure',True)
 selected=[('busybox','/bin/busybox'),('environment-tool',next(p for k,v,p in records if k in ('F','X') and p.endswith('fw_printenv'))),('ubi-tool',next(p for k,v,p in records if k in ('F','X') and p.endswith('ubiformat'))),('libc',next(p for k,v,p in records if k in ('F','X') and 'libc.so' in p))]
 if route=='preserve':selected += [('openssl',next(p for k,v,p in records if k in ('F','X') and p.endswith('/openssl'))),('ucode-uci-module','/usr/lib/ucode/uci.so')]
 for label,path in selected:
  target=root/path.lstrip('/');original=target.read_bytes();target.write_bytes(original+b'unknown-implementation');check('modified-'+label,False);target.write_bytes(original)
 link=next((k,v,p) for k,v,p in records if k=='L');target=root/link[2].lstrip('/');target.unlink();target.symlink_to('/unknown');check('changed-tool-link',False);target.unlink();target.symlink_to(link[1])
 absent=next((k,v,p) for k,v,p in records if k=='A' and '/usr/sbin/' in p);target=root/absent[2].lstrip('/');target.write_text('#!/bin/sh\nexit 0\n');check('new-command-path-override',False);target.unlink()
 target=root/'bin/busybox';mode=target.stat().st_mode;target.chmod(0o644);check('lost-executable-permission',False);target.chmod(mode)
 kind,value,path=next(r for r in records if r[2]=='/etc/ld-musl-aarch64.path');target=root/path.lstrip('/')
 if kind=='A':target.write_text('/unknown\n');check('new-loader-search-override',False);target.unlink()
 else:
  original=target.read_bytes();target.write_bytes(original+b'/unknown\n');check('changed-loader-search',False);target.write_bytes(original)
 check('restored-closure',True)
print(json.dumps(dict(passed=True,count=len(cases),cases=cases,fixture=str(work),scope='Actual shared ledger matcher, offline reviewed F/L/A tool and ELF dependency records; modified tool/library/module/link and extra lookup override controls. Target binaries not executed, no AP actions.'),indent=2))
