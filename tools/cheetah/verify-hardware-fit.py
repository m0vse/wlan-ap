#!/usr/bin/env python3
"""Inspect the actual embedded qualified DTB, without a running kernel."""
import json,struct,sys
from pathlib import Path
def fdt(blob):
 magic,total,off,strings,*_=struct.unpack_from('>10I',blob)
 assert magic==0xd00dfeed and total<=len(blob)
 stack=[];nodes={};i=off
 while True:
  token=struct.unpack_from('>I',blob,i)[0];i+=4
  if token==1:
   end=blob.index(b'\0',i);stack.append(blob[i:end].decode());i=(end+4)&~3
   nodes['/'+ '/'.join(stack[1:])]={}
  elif token==2: stack.pop()
  elif token==3:
   length,name=struct.unpack_from('>II',blob,i);i+=8
   start=strings+name;end=blob.index(b'\0',start)
   nodes['/'+ '/'.join(stack[1:])][blob[start:end].decode()]=blob[i:i+length]
   i=(i+length+3)&~3
  elif token==4: pass
  elif token==9: return nodes
  else: raise ValueError(token)
def cells(b): return list(struct.unpack('>'+str(len(b)//4)+'I',b))
def text(b): return b.rstrip(b'\0').decode()
fit=fdt(Path(sys.argv[1]).read_bytes())
nodes=fdt(fit['/images/fdt@mp03.3-ocelot']['data'])
assert text(nodes['/']['model'])=='Cambium Networks XV2-21X'
assert text(nodes['/']['compatible']).split('\0')[0]=='cambiumnetworks,xv2-21x'
mem=[p for p in nodes.values() if p.get('device_type')==b'memory\0']
assert len(mem)==1 and cells(mem[0]['reg'])==[0,0x40000000,0,0x40000000]
assert any(cells(p['reg'])==[0,0x4b000000,0,0x3500000] for path,p in nodes.items() if path.startswith('/reserved-memory/') and 'reg' in p)
geometry={'0:TRAINING':[0,0x80000],'rootfs':[0x80000,0x6000000],'rootfs_1':[0x6080000,0x6000000],'0:NVRAM':[0xc080000,0x2f80000],'crashLog':[0xf000000,0x1000000],'0:ART':[0x330000,0x70000],'0:APPSBLENV':[0x3b0000,0x10000]}
for label,reg in geometry.items():
 matches=[p for p in nodes.values() if p.get('label')==(label+'\0').encode()]
 assert len(matches)==1 and cells(matches[0]['reg'])==reg,label
 assert ('read-only' in matches[0])==(label not in ('rootfs','rootfs_1','0:APPSBLENV')),label
lan=[(path,p) for path,p in nodes.items() if p.get('label')==b'lan\0']
assert len(lan)==1 and cells(lan[0][1]['reg'])[0]==0x39c00000 and lan[0][1]['status']==b'okay\0'
assert text(nodes['/aliases']['label-mac-device'])==lan[0][0]
assert any(cells(p['switch_mac_mode'])==[15] for p in nodes.values() if 'switch_mac_mode' in p)
variants=[p for p in nodes.values() if 'qcom,ath11k-calibration-variant' in p]
assert sorted(text(p['qcom,ath11k-calibration-variant']) for p in variants)==['Cambium-XV2-21X','Cambium-XV2-21X-5G']
assert all(p['status']==b'okay\0' for p in variants)
assert len({tuple(cells(p['qcom,rproc'])) for p in variants})==2
print(json.dumps({'model':'XV2-21X','passed':True,'ram_bytes':0x40000000,'q6_reserved_bytes':0x3500000,'physical_management_port':'lan','ess_switch_mac_mode':15,'serving_radio_calibration_variants':sorted(text(p['qcom,ath11k-calibration-variant']) for p in variants),'flash_geometry':geometry,'hardware_runtime_acceptance':False},indent=2))
