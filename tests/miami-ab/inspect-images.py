#!/usr/bin/env python3
"""Inspect actual built slot FIT, tar pairing, DT policy and RAM helper closure."""
from pathlib import Path
import argparse,subprocess,tempfile,tarfile,hashlib,re,json
p=argparse.ArgumentParser();p.add_argument('--images',type=Path,required=True);p.add_argument('--unsquashfs',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--firmware-commit',required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--firmware-version');a=p.parse_args()
def get(f,node,prop,kind='s'):
 return subprocess.check_output(['fdtget','-t',kind,str(f),node,prop],text=True).strip()
def nodes(f,node='/'):
 yield node
 for name in subprocess.check_output(['fdtget','-l',str(f),node],text=True).split():yield from nodes(f,node.rstrip('/')+'/'+name)
report={'status':'built-image-inspection','slots':{}}
with tempfile.TemporaryDirectory(prefix='miami-built-inspect-') as td:
 r=Path(td)
 for slot in (0,1):
  prefix=f'openwrt-ipq53xx-cambiumnetworks_miami-ab-slot{slot}-squashfs-'
  kernel=a.images/(prefix+'kernel.itb');root=a.images/(prefix+'rootfs.squashfs');image=a.images/(prefix+'sysupgrade.tar');config=f'config@mi01.6-acadia-ab-slot{slot}'
  assert get(kernel,'/configurations','default')==config
  fdt=get(kernel,'/configurations/'+config,'fdt');data=get(kernel,'/images/'+fdt,'data','bx');dt=r/f'slot{slot}.dtb';dt.write_bytes(bytes(int(x,16) for x in data.split()))
  assert get(dt,'/cambium-platform','storage-policy')=='ab' and get(dt,'/cambium-platform','upgrade-policy','x')=='1' and get(dt,'/cambium-platform','storage-slot','x')==str(slot)
  partitions={}
  for node in nodes(dt):
   props=subprocess.check_output(['fdtget','-p',str(dt),node],text=True).split()
   if 'label' in props and 'reg' in props:partitions[get(dt,node,'label')]={'read_only':'read-only' in props,'reg':get(dt,node,'reg','x')}
  assert partitions['rootfs']['reg']=='c0000 6000000' and partitions['rootfs_1']['reg']=='60c0000 6000000'
  assert not partitions['rootfs']['read_only'] and not partitions['rootfs_1']['read_only']
  for name,part in partitions.items():
   if name not in ('rootfs','rootfs_1','0:APPSBLENV'):assert part['read_only'],name
  with tarfile.open(image) as tar:
   directory=f'sysupgrade-cambiumnetworks_miami-ab-slot{slot}'
   assert tar.extractfile(directory+'/kernel').read()==kernel.read_bytes()
   tar_root=tar.extractfile(directory+'/root').read();separate_root=root.read_bytes()
   # SDK scripts/sysupgrade-tar.sh uses dd bs=1024 conv=sync for SquashFS.
   assert tar_root.startswith(separate_root) and len(tar_root)==(len(separate_root)+1023)//1024*1024 and not any(tar_root[len(separate_root):])
  out=r/f'root{slot}';subprocess.run([str(a.unsquashfs),'-no-progress','-d',str(out),str(root)],check=True,stdout=subprocess.DEVNULL)
  release=(out/'etc/openwrt_release').read_text();assert (a.firmware_version or 'TIP-devel-'+a.firmware_commit[:8]) in release
  if a.firmware_version:
   expected_tag=a.firmware_version.removeprefix('TIP-').removesuffix('-'+a.firmware_commit[:8])
   assert "DISTRIB_TIP_VERSION='"+expected_tag+"'" in release
  module=out/'lib/functions/cambium-ab-miami.sh';assert 'ab_miami_before_target_write()' in module.read_text()
  platform=(out/'lib/upgrade/platform.sh').read_text();assert ' ab_identity && ab_miami_upgrade_preflight || {' in platform;assert 'head tr readlink' in platform and '/lib/upgrade/cambium-ab-certificates.sh' in platform
  helpers=['lib/functions/cambium-ab.sh','lib/functions/cambium-ab-miami.sh','lib/upgrade/cambium-ab.sh','lib/upgrade/cambium-ab-certificates.sh','usr/sbin/miami-board-data','usr/sbin/cambium-ab-seed-confirm','lib/functions.sh','lib/functions/system.sh','usr/share/libubox/jshn.sh','lib/upgrade/stage2']
  for f in helpers:assert (out/f).is_file(),f
  stage2=(out/'lib/upgrade/stage2').read_text()
  assert '/lib/*.sh /lib/functions/*.sh' in stage2 and '/usr/share/libubox/jshn.sh' in stage2
  owned={'lib/upgrade/platform.sh':'feeds/qca-wifi-7/ipq53xx/base-files/lib/upgrade/platform.sh','lib/functions/cambium-ab-miami.sh':'feeds/tip/cambium-miami-persistent/files/cambium-ab-miami.sh','usr/sbin/cambium-ab-seed-confirm':'feeds/tip/cambium-miami-persistent/files/cambium-ab-seed-confirm','usr/sbin/miami-board-data':'feeds/tip/cambium-miami-radio/files/miami-board-data'}
  for installed,source in owned.items():assert (out/installed).read_bytes()==(a.source/source).read_bytes(),installed
  packages={}
  for block in (out/'lib/apk/db/installed').read_text().split('\n\n'):
   fields=dict(line.split(':',1) for line in block.splitlines() if ':' in line)
   if fields.get('P') in ('cambium-ab','cambium-miami-persistent','cambium-miami-radio'):packages[fields['P']]=fields.get('V')
  for name in ('cambium-miami-radio','cambium-miami-persistent'):
   expected=re.search(r'^PKG_RELEASE:=(\S+)',(a.source/f'feeds/tip/{name}/Makefile').read_text(),re.M).group(1)
   assert packages[name]==expected,(name,packages[name],expected)
  assert packages['cambium-ab']=='22'
  # stage2 copies its standard BusyBox and library globs plus explicit binaries.
  required='head tr readlink fw_printenv fw_setenv sha256sum cmp mktemp openssl jsonfilter ubiformat ubiattach ubidetach ubimkvol ubiupdatevol'.split()
  def resolve(path):
   for _ in range(12):
    if not path.is_symlink():return path
    target=path.readlink();path=out/str(target).lstrip('/') if target.is_absolute() else path.parent/target
   raise AssertionError('symlink loop')
  closure=[];visited=set()
  def library_closure(binary):
   binary=resolve(binary)
   if binary in visited:return
   visited.add(binary);assert binary.is_file(),binary
   needed=subprocess.check_output(['readelf','-d',str(binary)],text=True)
   for lib in re.findall(r'Shared library: \[(.*?)\]',needed):
    matches=[resolve(out/d/lib) for d in ('lib','usr/lib') if resolve(out/d/lib).is_file()];assert matches,lib
    library_closure(matches[0])
  for name in required:
   matches=[out/d/name for d in ('bin','sbin','usr/bin','usr/sbin') if (out/d/name).exists() or (out/d/name).is_symlink()];assert matches,name
   binary=resolve(matches[0]);assert binary.is_file(),name
   library_closure(binary)
   closure.append(name)
  report['slots'][str(slot)]={'fit':config,'release':release.strip(),'package_versions':packages,'protected_partitions':len(partitions)-3,'tar_kernel_matches_separate_payload':True,'tar_root_matches_with_zero_1024_byte_padding':True,'owned_helpers_match_source':True,'ram_binaries':closure,'recursive_elf_libraries':[str(f.relative_to(out)) for f in sorted(visited)],'helpers':{f:hashlib.sha256((out/f).read_bytes()).hexdigest() for f in helpers},'images':{f.name:{'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in (kernel,root,image)}}
a.output.write_text(json.dumps(report,indent=2)+'\n');print('PASS: both actual target FIT/DT policies, tar pairing, protected partitions, source-matched seed/radio helpers and recursive ELF libraries')
