#!/usr/bin/env python3
"""Check compiled FIT/DTB against the IPQ5332 SDK EDMA driver contract."""
from pathlib import Path
import struct,sys,copy

def fdt(data):
 h=struct.unpack_from('>10I',data);assert h[0]==0xd00dfeed
 strings=data[h[3]:h[3]+h[8]];pos=h[2];stack=[];nodes={}
 while True:
  token,=struct.unpack_from('>I',data,pos);pos+=4
  if token==1:
   end=data.index(b'\0',pos);stack.append(data[pos:end].decode());pos=(end+4)&~3;nodes['/'.join(stack)]={}
  elif token==2:stack.pop()
  elif token==3:
   size,off=struct.unpack_from('>II',data,pos);pos+=8
   name=strings[off:strings.index(b'\0',off)].decode();nodes['/'.join(stack)][name]=data[pos:pos+size];pos=(pos+size+3)&~3
  elif token==4:pass
  elif token==9:return nodes
  else:raise AssertionError(token)

def cells(value):return struct.unpack('>'+str(len(value)//4)+'I',value)
def validate(tree):
 node=tree['/soc@0/edma@3ab00000']
 assert node['compatible']==b'qcom,edma\0'
 scalar={'qcom,txdesc-ring-start':4,'qcom,txdesc-rings':12,'qcom,txcmpl-ring-start':4,'qcom,txcmpl-rings':12,'qcom,rxfill-ring-start':4,'qcom,rxfill-rings':4,'qcom,rxdesc-ring-start':12,'qcom,rxdesc-rings':4,'qcom,tx-map-priority-level':1,'qcom,rx-map-priority-level':1,'qcom,ppeds-num':2,'qcom,rx-queue-start':0}
 for prop,want in scalar.items():assert cells(node[prop])==(want,),prop
 assert cells(node['qcom,txdesc-map'])[:12]==(8,9,10,11,12,13,14,15,4,5,6,7)
 assert cells(node['qcom,txdesc-fc-grp-map'])==(1,2,3,4,5)
 assert cells(node['qcom,rxfill-map'])==(4,5,6,7)
 assert cells(node['qcom,rxdesc-map'])==(12,13,14,15)
 assert cells(node['qcom,rx-ring-queue-map'])==tuple(i+8*j for i in range(8) for j in range(4))
 assert cells(node['qcom,ppeds-map'])==(1,1,1,1,32,8,2,2,2,2,40,8)
 interrupts=cells(node['interrupts']);assert len(interrupts)%3==0
 irq=interrupts[1::3]
 assert irq[:12]==tuple(range(163,175)) and irq[12:16]==tuple(range(139,143))
 assert irq[16:27]==(191,155,156,157,158,160,128,152,161,129,153)
 assert all(x==0 for x in interrupts[0::3]) and all(x==4 for x in interrupts[2::3])
 dp=tree['/soc@0/dp1'];assert cells(dp['qcom,id'])==(1,) and cells(dp['qcom,phy-mdio-addr'])==(28,)
 assert cells(dp['reg'])==(0x3a500000,0x4000)
 assert tree['']['compatible'].startswith(b'cambiumnetworks,x7-35x\0')
 return scalar

for name in sys.argv[1:]:
 tree=fdt(Path(name).read_bytes())
 if '/configurations/config@mi01.6-acadia' in tree:
  conf=tree['/configurations/config@mi01.6-acadia'];dtname=conf['fdt'].rstrip(b'\0').decode();tree=fdt(tree['/images/'+dtname]['data'])
 props=validate(tree)
 for prop in props:
  bad=copy.deepcopy(tree);bad['/soc@0/edma@3ab00000'].pop(prop)
  try:validate(bad)
  except (AssertionError,KeyError):pass
  else:raise AssertionError('missing property admitted: '+prop)
 print('PASS:',Path(name).name,'compiled SDK EDMA rings/maps/IRQs, Miami physical port, and missing-property rejection')
