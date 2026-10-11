#!/usr/bin/env python3
"""Execute production selection against independently recorded physical geometry."""
from pathlib import Path
import argparse,json,subprocess,tempfile,re
p=argparse.ArgumentParser();p.add_argument('--runtime-root',type=Path,required=True);p.add_argument('--repo',type=Path,required=True);a=p.parse_args()
base=a.repo/'feeds/ucentral/ucentral-state/files';module=(base/'faults.uc').read_text();module=re.sub(r'^import .*;\n','',module,flags=re.M).replace('return { evaluate, snapshot, radio_facts, select_banks };','');profiles=json.loads((base/'storage-canary.json').read_text())
# References independently checked in native DTS or retained device-tree decode.
refs={'cambiumnetworks,x7-35x':[('rootfs',786432,100663296),('rootfs_1',101449728,100663296)],'cambiumnetworks,xv2-21x':[('rootfs',524288,100663296),('rootfs_1',101187584,100663296)],'cambiumnetworks,xv3-8':[('rootfs',0,100663296),('rootfs_1',100663296,100663296)],'cambiumnetworks,xv2-2':[('rootfs',0,54525952),('rootfs_1',54525952,54525952)],'cambiumnetworks,xv2-2t1':[('rootfs',0,100663296),('rootfs_1',100663296,100663296)],'cambiumnetworks,xe3-4':[('rootfs',0,100663296),('rootfs_1',100663296,100663296)],'cambiumnetworks,e400':[('rootfs0',4194304,46137344),('rootfs1',54525952,46137344)]}
for b in ('cambium,e410','cambiumnetworks,e410','cambiumnetworks,e410b'):refs[b]=[('fs',0,134217728)]
cases=[]
for board,rows in refs.items():
 records=[dict(index=2+i,name=n,type='nand',offset=o,size=s,erase=131072,write=2048,paired_ubi=True) for i,(n,o,s) in enumerate(rows)]
 for n,o,s in rows:
  matches=[r for r in profiles[board] if r['name']==n];assert len(matches)==1 and matches[0]['offset']==o and matches[0]['size']==s
  assert all(0<=int(x)<s//131072 for x in matches[0]['samples'].split(','))
 cases.append(dict(board=board,records=records,status='qualified'))
 bad=[dict(r) for r in records];bad[0]['offset']+=131072;cases.append(dict(board=board,records=bad,status='unavailable'))
# E400 OEM YAFFS root partitions have 3MiB kernels/45MiB roots, not converted UBI geometry.
cases.append(dict(board='cambiumnetworks,e400',records=[dict(index=7+i,name=f'rootfs{i}',type='nand',offset=o,size=47185920,erase=131072,write=2048) for i,o in enumerate((3145728,53477376))],status='unavailable'))
for board in ('cambiumnetworks,e500','cambiumnetworks,e600','cambiumnetworks,xv2-22h','example,unknown'):cases.append(dict(board=board,records=[],status='unsupported'))
code='let fs={};\n'+module+'\nlet profiles='+json.dumps(profiles)+';let cases='+json.dumps(cases)+r''';let checks=0;for(let c in cases){let result=select_banks(profiles,c.board,c.records);assert(result.status==c.status,c.board+' expected '+c.status);checks++;}printf('PASS %d all-family independent geometry controls\n',checks);'''
with tempfile.TemporaryDirectory(prefix='all-family-geometry-') as tmp:
 f=Path(tmp)/'test.uc';f.write_text(code);r=subprocess.run(['/usr/bin/qemu-aarch64','-L',str(a.runtime_root),str(a.runtime_root/'usr/bin/ucode'),str(f)],capture_output=True,text=True);print(r.stdout,r.stderr);raise SystemExit(r.returncode)
