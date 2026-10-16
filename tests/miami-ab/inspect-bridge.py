#!/usr/bin/env python3
"""Inspect actual bridge FIT/embedded DT/initramfs, without running its kernel."""
from pathlib import Path
import argparse,subprocess,tempfile,json,lzma,zlib,math
p=argparse.ArgumentParser();p.add_argument('--images',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
def get(f,node,prop,t='s'):return subprocess.check_output(['fdtget','-t',t,str(f),node,prop],text=True).strip()
def payload(f,node):return bytes(int(b,16) for b in get(f,node,'data','bx').split())
def cpio(data,start):
 at=start;files={}
 for _ in range(30000):
  assert data[at:at+6] in (b'070701',b'070702')
  fields=[int(data[at+6+i*8:at+14+i*8],16) for i in range(13)];size=fields[6];namesize=fields[11]
  assert 0<namesize<4096 and size<=len(data)
  name=data[at+110:at+110+namesize-1].decode();assert data[at+110+namesize-1]==0
  pos=(at+110+namesize+3)&~3;content=data[pos:pos+size];assert len(content)==size
  if name=='TRAILER!!!':return files
  files[name.lstrip('./')]={'mode':fields[1],'data':content};at=(pos+size+3)&~3
 raise AssertionError('cpio missing trailer')
def archive(kernel):
 at=0
 while True:
  at=kernel.find(b'070701',at)
  if at<0:break
  try:
   files=cpio(kernel,at)
   if 'bin/busybox' in files:return files,'raw-newc'
  except (ValueError,AssertionError,UnicodeDecodeError):pass
  at+=6
 at=0
 while True:
  at=kernel.find(b'\x1f\x8b\x08',at)
  if at<0:break
  try:
   unpacked=zlib.decompress(kernel[at:],wbits=31);files=cpio(unpacked,0)
   if 'bin/busybox' in files:return files,'gzip-newc'
  except (zlib.error,ValueError,AssertionError,UnicodeDecodeError):pass
  at+=3
 raise AssertionError('No actual embedded initramfs found')
report={'status':'bridge-image-inspection','slots':{}}
with tempfile.TemporaryDirectory(prefix='miami-bridge-inspect-') as td:
 r=Path(td)
 for slot in (0,1):
  image=a.images/f'openwrt-ipq53xx-cambiumnetworks_miami-bridge-slot{slot}-initramfs.itb';size=image.stat().st_size;lebs=math.ceil(size/126976);assert lebs+20<=180
  config=f'config@mi01.6-acadia-bridge-slot{slot}';assert get(image,'/configurations','default')==config
  fdt=get(image,'/configurations/'+config,'fdt');dt=r/f'slot{slot}.dtb';dt.write_bytes(payload(image,'/images/'+fdt))
  assert get(dt,'/cambium-platform','storage-policy')=='ab' and get(dt,'/cambium-platform','upgrade-policy','x')=='1' and get(dt,'/cambium-platform','storage-slot','x')==str(slot) and get(dt,'/cambium-platform','boot-mode')=='bridge'
  aliases={}
  def nodes(node='/'):
   yield node
   for name in subprocess.check_output(['fdtget','-l',str(dt),node],text=True).split():yield from nodes(node.rstrip('/')+'/'+name)
  for node in nodes():
   props=subprocess.check_output(['fdtget','-p',str(dt),node],text=True).split()
   if node.endswith(('/wifi@c0000000','/remoteproc@d100000','/pcie@18000000')):aliases[node]=get(dt,node,'status')
  assert len(aliases)==3 and set(aliases.values())=={'disabled'},aliases
  k=get(image,'/configurations/'+config,'kernel');compressed=payload(image,'/images/'+k);assert get(image,'/images/'+k,'compression')=='lzma';kernel=lzma.decompress(compressed,format=lzma.FORMAT_ALONE)
  files,compression=archive(kernel)
  required=['bin/busybox','sbin/init','lib/functions/cambium-ab.sh','lib/functions/cambium-ab-miami.sh','lib/functions/miami-ab-bridge.sh','lib/upgrade/cambium-ab.sh','lib/upgrade/cambium-ab-certificates.sh','usr/sbin/miami-ab-bridge-upgrade','usr/sbin/miami-board-data','usr/bin/openssl','usr/bin/jsonfilter','etc/config/network','etc/config/dhcp']
  for name in required:assert name in files,name
  assert b"option ignore '1'" in files['etc/config/dhcp']['data']
  assert not any('ath12k' in name and name.endswith('.ko') for name in files)
  assert b'cambium_ab_check_image' in files['usr/sbin/miami-ab-bridge-upgrade']['data']
  report['slots'][str(slot)]={'fit':config,'bytes':size,'bridge_lebs':lebs,'minimum_data_lebs':20,'source_available_lebs':180,'allocation_lebs_minimum':lebs+20,'actual_data_budget_checked_again_by_stage':True,'embedded_initramfs':compression,'required_files':required,'disabled_temporary_radios':aliases}
a.output.write_text(json.dumps(report,indent=2)+'\n');print('PASS: both actual bridge FIT/DT/embedded cpio/tools/no-radio-driver/minimum180-LEB allocation checks')
