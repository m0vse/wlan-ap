#!/usr/bin/env python3
"""Verify normal FIT kernels, external squashfs and exact persistent closure."""
from pathlib import Path
import argparse,struct,hashlib,json,lzma,zlib,subprocess,tempfile
p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--source-commit',required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--with-enrolment',action='store_true');a=p.parse_args();ow=a.repo/'openwrt';images=ow/'bin/targets/ipq53xx/generic'
def fdt(data):
 h=struct.unpack_from('>10I',data);assert h[0]==0xd00dfeed and h[1]<=len(data);strings=data[h[3]:h[3]+h[8]];pos=h[2];stack=[];nodes={}
 while True:
  token,=struct.unpack_from('>I',data,pos);pos+=4
  if token==1:
   end=data.index(b'\0',pos);stack.append(data[pos:end].decode());pos=(end+4)&~3;nodes['/'.join(stack)]={}
  elif token==2:stack.pop()
  elif token==3:
   n,o=struct.unpack_from('>II',data,pos);pos+=8;name=strings[o:strings.index(b'\0',o)].decode();nodes['/'.join(stack)][name]=data[pos:pos+n];pos=(pos+n+3)&~3
  elif token==4:pass
  elif token==9:break
  else:raise AssertionError(token)
 return nodes
def text(v):return v.rstrip(b'\0').decode()
def num(v):return int.from_bytes(v,'big')
report={'source_commit':a.source_commit,'hardware_qualified':False,'automatic_enrollment':a.with_enrolment,'sysupgrade_admitted':False,'slots':{}}
for slot in (0,1):
 pattern=f'*cambiumnetworks_miami-persistent-slot{slot}-squashfs-'
 kernels=list(images.glob(pattern+'kernel.itb'));roots=list(images.glob(pattern+'rootfs.squashfs'));assert len(kernels)==len(roots)==1,(kernels,roots)
 kernel,root=kernels[0],roots[0];data=kernel.read_bytes();tree=fdt(data);config=f'config@mi01.6-acadia-slot{slot}';conf=tree['/configurations/'+config]
 assert text(tree['/configurations']['default'])==config and 'ramdisk' not in conf
 kn=tree['/images/'+text(conf['kernel'])];dn=tree['/images/'+text(conf['fdt'])]
 assert text(kn['type'])=='kernel' and text(kn['compression'])=='lzma' and text(kn['arch'])=='arm64' and text(kn['os'])=='linux'
 assert num(kn['load'])==num(kn['entry'])==0x41000000
 for kind in ['kernel','fdt']:
  n='/images/'+text(conf[kind]);payload=tree[n]['data'];hashes=[v for k,v in tree.items() if k.startswith(n+'/') and 'algo' in v];assert hashes
  for v in hashes:
   algo=text(v['algo']);digest=struct.pack('>I',zlib.crc32(payload)&0xffffffff) if algo=='crc32' else hashlib.new(algo,payload).digest();assert digest==v['value']
 raw=lzma.decompress(kn['data']);assert raw[56:60]==b'ARM\x64';image_size=struct.unpack_from('<Q',raw,16)[0];assert max(len(raw),image_size)<=0x484ef000-0x41000000
 cfg=zlib.decompress(raw[raw.index(b'IKCFG_ST')+8:],31).decode();assert 'CONFIG_INITRAMFS_SOURCE=""' in cfg,cfg[cfg.find('CONFIG_INITRAMFS_SOURCE'):cfg.find('CONFIG_INITRAMFS_SOURCE')+200]
 for key in ['CONFIG_MTD_UBI','CONFIG_MTD_UBI_BLOCK','CONFIG_SQUASHFS','CONFIG_UBIFS_FS','CONFIG_OVERLAY_FS','CONFIG_MTD_NAND_QCOM']:assert key+'=y' in cfg,key
 assert b'Miami UserPD bootinfo v2 pid=2' in raw
 board=fdt(dn['data']);assert b'cambiumnetworks,x7-35x\0' in board['']['compatible'];assert num(board['/cambium-platform']['storage-slot'])==slot
 assert text(board['']['model'])=='Cambium Networks X7-35X'
 assert text(board['/aliases']['label-mac-device'])=='/soc@0/dp1'
 assert struct.unpack('>4I',board['/memory@40000000']['reg'])==(0,0x40000000,0,0x40000000)
 parts=[v for k,v in board.items() if '/partition@' in k];assert len(parts)==26
 writable={text(v['label']) for v in parts if 'read-only' not in v};assert writable=={'0:APPSBLENV','rootfs' if slot==0 else 'rootfs_1'},writable
 assert {text(board['/leds/led-'+c]['label']) for c in ['red','green','orange','blue']}=={'red:status','green:status','orange:status','blue:status'}
 rprocs=[v for v in board.values() if b'qcom,ipq5332-q6-mpd\0' in v.get('compatible',b'')];assert len(rprocs)==1 and num(rprocs[0]['qcom,bootargs_version'])==2
 assert not any(b'qcom,ipq5332-wcss-ahb-mpd\0' in v.get('compatible',b'') for v in board.values())
 with tempfile.TemporaryDirectory(prefix='miami-squashfs-') as td:
  fs=Path(td)/'root';subprocess.run([str(ow/'staging_dir/host/bin/unsquashfs4'),'-no-progress','-excludes','-d',str(fs),str(root),'dev'],check=True,stdout=subprocess.DEVNULL)
  pairs=[('feeds/tip/cambium-miami-radio/files/miami-board-data','usr/sbin/miami-board-data'),('feeds/tip/cambium-miami-persistent/files/cambium-ab-miami.sh','lib/functions/cambium-ab-miami.sh'),('feeds/tip/cambium-miami-persistent/files/miami-country-defaults','usr/libexec/miami-country-defaults'),('feeds/tip/certificates/files/usr/bin/mount_certs','usr/bin/mount_certs'),('feeds/qca-wifi-7/wifi-scripts/files/lib/netifd/wireless/mac80211.sh','lib/netifd/wireless/mac80211.sh'),('feeds/ucentral/ucentral-schema/files/usr/libexec/ucentral-network','usr/libexec/ucentral-network')]
  for source,target in pairs:assert (fs/target).read_bytes()==(a.repo/source).read_bytes(),target
  if a.with_enrolment:
   assert (fs/'etc/ucentral/discovery-policy.json').stat().st_mode & 0o777 == 0o644
   for rel in ['usr/libexec/ucentral-installer-identity','usr/libexec/ucentral-installer-boot','usr/libexec/ucentral-installer-firstboot','lib/functions/cambium-installer-health.sh','etc/init.d/early_boot']:
    assert (fs/rel).read_bytes()==(a.repo/'feeds/tip/certificates/files'/rel).read_bytes(),rel
   for rel in ['usr/bin/est_client','etc/init.d/cloud_discover']:
    assert (fs/rel).read_bytes()==(a.repo/'feeds/tip/cloud_discovery/files'/rel).read_bytes(),rel
   assert b"binding.family == 'miami' && binding.model == 'X7-35X'" in (fs/'usr/libexec/ucentral-installer-identity').read_bytes()
   assert b'ab_installer_legacy_complete "$slot"' in (fs/'usr/sbin/cambium-ab-guard').read_bytes()
   assert b'ab_miami_installer_confirmed_context()' in (fs/'lib/functions/cambium-ab-miami.sh').read_bytes()
   assert (fs/'etc/rc.d/S09early_boot').is_symlink()
   assert (fs/'etc/rc.d/S98cloud_discover').is_symlink()
  assert (fs/'usr/libexec/ucentral-led.sh').read_bytes()==(a.repo/'feeds/ucentral/ucentral-client/files/usr/libexec/ucentral-led.sh').read_bytes()
  assert (fs/'usr/sbin/cambium-return-oem').read_bytes()==(ow/'package/cambium/cambium-ab/files/cambium-return-oem').read_bytes()
  assert (fs/'etc/init.d/cambium-ab-guard').exists() and (fs/'usr/sbin/cambium-ab-guard').exists()
  assert b'firmware_class/parameters/path' not in (fs/'usr/sbin/miami-board-data').read_bytes()
  assert (fs/'ini/global.ini').is_file() and (fs/'ini/IPQ5332.ini').is_file()
  assert b'echo -n "/ini"' in (fs/'etc/init.d/ath12k_dyn_dbg_enable.sh').read_bytes()
  assert b'kind != "ubi"' in (fs/'lib/functions/cambium-ab.sh').read_bytes()
  assert (fs/'etc/ucentral/compatible').read_text()=='cambium_x7-35x\n'
  assert (fs/'etc/ucentral/platform').read_text()=='ap\n' and (fs/'etc/ucentral/country').read_text().strip()=='GB'
  assert not (fs/'root/.cambium-installer-settings').exists()
  assert (fs/'etc/ucentral/ucentral.cfg.0000000001').stat().st_size>0
  assert list((fs/'certificates').iterdir())==[],list((fs/'certificates').iterdir())
  release=(fs/'etc/openwrt_release').read_bytes();assert b'25.12.5' in release and a.source_commit[:8].encode() in release,release
  assert b'mem_profile=low' not in (fs/'etc/modules.conf').read_bytes()
  assert b'Validated Miami deployment country unavailable' in (fs/'usr/share/ucentral/capabilities.uc').read_bytes()
  module=next(fs.glob('lib/modules/*/ath12k.ko'));assert b'parmtype=mem_profile:charp' in module.read_bytes()
  assert b'function phy_name(phy)' in (fs/'usr/share/ucentral/wifi/phy.uc').read_bytes()
  assert 'lib/firmware/ath12k/IPQ5332/hw1.0/q6_fw0.mdt' not in [str(p.relative_to(fs)) for p in fs.rglob('*')]
  versions=(images/'openwrt-ipq53xx.manifest').read_text()
  expected={'cambium-miami-radio':8,'cambium-miami-persistent':5,'cambium-ab':20,'certificates':19,'cloud_discovery':13} if a.with_enrolment else {'cambium-miami-radio':7,'cambium-miami-persistent':2,'cambium-ab':19,'certificates':16}
  for package,version in expected.items():assert f'{package} - {version}\n' in versions,(package,versions)
  assert 'ucentral-client - ' in versions and 'ucentral-schema - ' in versions
 report['slots'][str(slot)]={'kernel':{'name':kernel.name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()},'rootfs':{'name':root.name,'bytes':root.stat().st_size,'sha256':hashlib.sha256(root.read_bytes()).hexdigest()},'fit_config':config,'external_squashfs':True,'embedded_initramfs':False,'writable_partitions':sorted(writable),'protected_partitions':24,'certificate_store':'empty64LEB bank-local','vault':'own-unit72LEB read-only access','kernel_builtin_storage':'verified','source_package_closure':'verified'}
a.report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
