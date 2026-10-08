#!/usr/bin/env python3
"""Build a privately served pilot installer with independent exact image pins."""
from pathlib import Path
import argparse,json,hashlib,shutil,subprocess
p=argparse.ArgumentParser();p.add_argument('--images',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--source-commit',required=True);p.add_argument('--installer-source-commit');p.add_argument('--prior-bundle',type=Path);p.add_argument('--with-enrolment',action='store_true');a=p.parse_args()
assert len(a.source_commit)==40 and all(c in '0123456789abcdef' for c in a.source_commit)
a.output.mkdir(parents=True,exist_ok=True);repo=Path(__file__).resolve().parents[3]
installer_commit=a.installer_source_commit or a.source_commit
assert len(installer_commit)==40 and all(c in '0123456789abcdef' for c in installer_commit)
files={};pins=[]
for slot in (0,1):
 for kind,suffix in [('kernel','kernel.itb'),('rootfs','rootfs.squashfs')]:
  candidates=list(a.images.glob(f'*cambiumnetworks_miami-persistent-slot{slot}-squashfs-{suffix}'))
  assert len(candidates)==1,(slot,kind,candidates)
  src=candidates[0];name=f'miami-persistent-slot{slot}-{suffix}';dst=a.output/name
  shutil.copyfile(src,dst);data=dst.read_bytes();assert data
  magic=bytes.fromhex('d00dfeed') if kind=='kernel' else b'hsqs';assert data[:4]==magic,(name,data[:4])
  digest=hashlib.sha256(data).hexdigest();files[name]={'sha256':digest,'bytes':len(data),'slot':slot,'kind':kind}
  pins.extend([f'{kind.upper()}{slot}={name}',f'{kind.upper()}{slot}_SHA={digest}',f'{kind.upper()}{slot}_SIZE={len(data)}'])
prior_receipt=None
if a.prior_bundle:
 prior_receipt=json.loads(a.prior_bundle.read_text())
 assert prior_receipt['source_commit'] in ('cc5bdc8c3074a4c37de5e525cf31d701f7050f25','c319093b6f54a710064c3fafac0209561e6a7459','204aee68e7a2ce847faf6a4f48f1e9b04aecef0b')
 assert (prior_receipt['family'],prior_receipt['model'],prior_receipt['certificate_lebs'],prior_receipt['vault_lebs'])==('miami','X7-35X',64,72)
 expected_kernel=['820e89d64d1ef8f089180a50abba13e01b6e00fa54a08690b618f326169192df','40d43dbbb6b099287341f31aa88f1010b58124ef2300e4de84bdf855fb6f4ea8']
 kernel_size=4856368;root_size=22499154;root_digest='3aab706eb51ccf0a0a7fa74e6a52a4bdce6df1f73288ac64b105f7d57488f87a'
 if prior_receipt['source_commit']=='c319093b6f54a710064c3fafac0209561e6a7459':
  expected_kernel=['eeb92abb5837ba33915a3c7a354c66afdd3e9796f1c44ea362f3c7bb01a97b06','339767a95dee1afd24d62898bbaba0480c5fd22b6c8e77bc44e9916b4d6e0dec']
  kernel_size=4856060;root_size=22498986;root_digest='955a1ef09e684b7bb73a6e8c0b245701f00df416a1a0abbb6e6bce3fa7c73ce1'
 if prior_receipt['source_commit']=='204aee68e7a2ce847faf6a4f48f1e9b04aecef0b':
  expected_kernel=['3ee7c62d3c51c5d9f73f8693fb186ec922fe890336e1178847a30a793c119fc7','59174989ff6e5536b482fd972467afe847e1ca43fb3f0852f317ba2c383fcff0']
  kernel_size=4856108;root_size=22501506;root_digest='8f9c83cc9c1e7952c793c39cbebe36122698aedf92aeb9322acb193e885cb886'
 for slot in (0,1):
  for kind,suffix,digest,size in [('kernel','kernel.itb',expected_kernel[slot],kernel_size),('rootfs','rootfs.squashfs',root_digest,root_size)]:
   item=prior_receipt['images'][f'miami-persistent-slot{slot}-{suffix}']
   assert (item['slot'],item['kind'],item['sha256'],item['bytes'])==(slot,kind,digest,size)
   pins.extend([f'PRIOR_{kind.upper()}{slot}_SHA={digest}',f'PRIOR_{kind.upper()}{slot}_SIZE={size}'])
source=(repo/'contrib/cambium/miami/miami-oem-persistent.sh.in').read_text().replace('R=${CAMBIUM_OEM_INSTALL_ROOT:-}', 'R=');assert source.startswith('#!/bin/sh\n')
common=(repo/'tools/oem-migration/recovery/scripts/lib/cambium-installer-settings.sh').read_text()
adapter=(repo/'contrib/cambium/miami/miami-enrolment-stage.sh').read_text()
contract=hashlib.sha256((source+common+adapter).encode()).hexdigest()
pins.append(f'SOURCE_CONTRACT_SHA={contract}')
pins.append(f'ENROLMENT_READY={int(a.with_enrolment)}')
if a.with_enrolment:
 for slot in (0,1):
  descriptor={'schema':'openwifi.paired-image-capsule.v1','family':'miami','model':'X7-35X',
   'source_slot':1-slot,'target_slot':slot,'required_device_contract_sha256':contract,
   'layout':{'bank_bytes':100663296,'leb_bytes':126976,'kernel_id':0,'rootfs_id':1,
             'overlay_id':2,'vault_id':3,'vault_lebs':72,'certificates_id':4,'certificates_lebs':64},
   'payloads':[]}
  for kind,suffix in [('kernel','kernel.itb'),('rootfs','rootfs.squashfs')]:
   name=f'miami-persistent-slot{slot}-{suffix}';item=files[name]
   descriptor['payloads'].append({'role':kind,'file':name,'size':item['bytes'],'sha256':item['sha256'],
    'target_geometry':{'volume_id':0 if kind=='kernel' else 1,'leb_bytes':126976,'lebs':(item['bytes']+126975)//126976}})
  name=f'miami-persistent-slot{slot}-pair.json'
  data=(json.dumps(descriptor,sort_keys=True,separators=(',',':'),ensure_ascii=True)+'\n').encode()
  (a.output/name).write_bytes(data);digest=hashlib.sha256(data).hexdigest()
  files[name]={'sha256':digest,'bytes':len(data)}
  pins.extend([f'PAIR{slot}={name}',f'PAIR{slot}_SHA={digest}',f'PAIR{slot}_SIZE={len(data)}'])
integration=common+'\n'+adapter+'\n' if a.with_enrolment else ''
script=a.output/'miami-oem-persistent-test.sh';script.write_text('#!/bin/sh\n# Private Miami OEM-preserving installer.\n# Firmware source '+a.source_commit+'\n'+'\n'.join(pins)+'\n'+integration+source[len('#!/bin/sh\n'):]);script.chmod(0o700)
subprocess.run(['sh','-n',str(script)],check=True)
files[script.name]={'sha256':hashlib.sha256(script.read_bytes()).hexdigest(),'bytes':script.stat().st_size}
receipt={'source_commit':a.source_commit,'installer_source_commit':installer_commit,'family':'miami','model':'X7-35X','device_id':'cambium_x7-35x','purpose':'unenrolled persistent storage qualification','oem_bank':'preserved','certificate_lebs':64,'vault_lebs':72,'rootfs_volume_id':1,'automatic_enrollment':False,'sysupgrade_admitted':False,'images':files,'hardware_qualified':False,'updater_admission':'exact new pair or independently pinned prior pair; preserve overlay/certificates/vault', 'prior_source_commit':prior_receipt['source_commit'] if prior_receipt else None}
if a.with_enrolment:
 receipt.update(purpose='OEM-preserving native enrolment test',automatic_enrollment=True,source_contract_sha256=contract)
(a.output/'persistent-bundle.json').write_text(json.dumps(receipt,indent=2)+'\n');(a.output/'SHA256SUMS').write_text(''.join(f'{v["sha256"]}  {k}\n' for k,v in files.items()))
print(json.dumps(receipt,indent=2))
