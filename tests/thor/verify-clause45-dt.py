#!/usr/bin/env python3
"""Verify compiled Clause45 flag and single-property semantic delta vs frozen .9."""
from pathlib import Path
import struct,json,sys
new_extract,old_extract,new_images,old_images=map(Path,sys.argv[1:5]);results=[]
node='/soc@0/ess-instance/ess-switch@3a000000/qcom,port_phyinfo/port@6';flag='ethernet-phy-ieee802.3-c45'
def properties(data):
 h=struct.unpack_from('>10I',data);assert h[0]==0xd00dfeed
 pos=h[2];strings=data[h[3]:h[3]+h[8]];stack=[];props={}
 while True:
  token=struct.unpack_from('>I',data,pos)[0];pos+=4
  if token==1:
   end=data.index(b'\0',pos);stack.append(data[pos:end].decode());pos=(end+4)&~3
   props['/'+('/'.join(s for s in stack if s))]={}
  elif token==2:stack.pop()
  elif token==3:
   length,offset=struct.unpack_from('>II',data,pos);pos+=8
   name=strings[offset:strings.index(b'\0',offset)].decode()
   props['/'+('/'.join(s for s in stack if s))][name]=data[pos:pos+length];pos=(pos+length+3)&~3
  elif token==4:pass
  elif token==9:break
  else:raise AssertionError(token)
 return props

def compare(label,new,old):
 a,b=properties(new),properties(old)
 assert flag not in b[node],('negative frozen .9 control',label)
 assert a[node][flag]==b'',('missing/nonboolean flag',label)
 assert a[node]['port_id']==struct.pack('>I',6)
 assert a[node]['phy_address']==struct.pack('>I',8)
 assert a[node]['port_mac_sel']==b'QGMAC_PORT\0'
 del a[node][flag]
 assert a==b,('unexpected additional DT semantic delta',label)
 results.append({'case':label,'passed':True,'only_semantic_change':node+'/'+flag})
for bank in (0,1):compare(f'persistent-bank{bank}',(new_extract/f'bank{bank}.dtb').read_bytes(),(old_extract/f'bank{bank}.dtb').read_bytes())
for mode in ('persistent','installer','recovery'):
 filename=f'openwrt-qualcommax-ipq807x-cambiumnetworks_thor-{mode}-initramfs-uImage.itb'
 a,b=properties((new_images/filename).read_bytes()),properties((old_images/filename).read_bytes())
 dt_nodes=[key for key,value in a.items() if key.startswith('/images/') and value.get('type')==b'flat_dt\0']
 assert dt_nodes,(mode,'no DT images')
 for key in dt_nodes:
  assert key in b
  compare(mode+'-RAM-'+key.rsplit('/',1)[-1],a[key]['data'],b[key]['data'])
print(json.dumps({'passed':True,'count':len(results),'cases':results,'scope':'Compiled bank0/bank1 and every RAM FIT DT; complete semantic property comparison against immutable .9, exactly one Clause45 boolean added. No PHY/RX/DHCP hardware acceptance.'},indent=2))
