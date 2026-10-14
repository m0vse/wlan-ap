#!/usr/bin/env python3
"""Generated seed configuration and admission tests; no device or firmware build."""
from pathlib import Path
import hashlib,json,os,struct,subprocess,sys,tempfile,unittest
HERE=Path(__file__).resolve().parent

def fit(config,default=None):
 strings=b'default\0';body=b''
 def node(name):return struct.pack('>I',1)+(name.encode()+b'\0'+b'\0'*3)[:(len(name)+4)&~3]
 body+=node('')+node('configurations')
 value=(default or config).encode()+b'\0';body+=struct.pack('>III',3,len(value),0)+value+b'\0'*((-len(value))%4)
 body+=node(config)+struct.pack('>III',2,2,2)+struct.pack('>I',9)
 off=56;size=off+len(body)+len(strings)
 return struct.pack('>10I',0xd00dfeed,size,off,off+len(body),40,17,16,0,len(strings),len(body))+b'\0'*16+body+strings

def prior():
 images={}
 for slot,k in enumerate(('9c22c101aad1325ca0e1cfac9c52a3d84b3c3a5bfc46a99667dc491c3765712b','dcf685056218b88a8685ea2c60c8cc0fceef5a39dcc168691541f9fb90e4a255')):
  for kind,suffix,h,size in [('kernel','kernel.itb',k,4855880),('rootfs','rootfs.squashfs','1ecd75a5487c1a014d05adce627bf746b163df7b3f275deff258c77d9564dae9',22502074)]:images[f'miami-persistent-slot{slot}-{suffix}']={'slot':slot,'kind':kind,'sha256':h,'bytes':size}
 return {'source_commit':'b6d1a26f8aec83e9c8e87eb67e440fc7376a0245','family':'miami','model':'X7-35X','certificate_lebs':64,'vault_lebs':72,'images':images}
class SeedTests(unittest.TestCase):
 def generate(self,config='ab',extra=(),changed_prior=False,wrong_default=False,prior_input=None):
  temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name);images=root/'images';images.mkdir()
  for slot in (0,1):
   prefix=f'openwrt-ipq53xx-cambiumnetworks_miami-ab-slot{slot}-squashfs-' if '--ab-seed' in extra else f'cambiumnetworks_miami-persistent-slot{slot}-squashfs-'
   name=f'config@mi01.6-acadia-'+('ab-' if config=='ab' else '')+f'slot{slot}'
   (images/(prefix+'kernel.itb')).write_bytes(fit(name,'config@other' if wrong_default else None))
   (images/(prefix+'rootfs.squashfs')).write_bytes(b'hsqs fixture')
  p=prior() if prior_input is None else prior_input
  if changed_prior:p['images']['miami-persistent-slot0-rootfs.squashfs']['sha256']='0'*64
  receipt=root/'prior.json';receipt.write_text(json.dumps(p));out=root/'out'
  result=subprocess.run([sys.executable,str(HERE/'build-persistent-bundle.py'),'--images',str(images),'--output',str(out),'--source-commit','a'*40,'--prior-bundle',str(receipt),*extra],capture_output=True,text=True)
  return result,out
 def test_seed_generates_exact_both_bank_pins_without_enrolment(self):
  result,out=self.generate(extra=('--ab-seed',));self.assertEqual(result.returncode,0,result.stderr)
  script=(out/'miami-oem-persistent-test.sh').read_text();self.assertIn('AB_SEED=1',script);self.assertIn('ENROLMENT_READY=0',script)
  for slot in (0,1):
   self.assertIn(f'FIT{slot}=config@mi01.6-acadia-ab-slot{slot}',script)
   descriptor=json.loads((out/f'miami-ab-seed-slot{slot}-pair.json').read_text());self.assertEqual(descriptor['target_slot'],slot);self.assertEqual(descriptor['target_fit_config'],f'config@mi01.6-acadia-ab-slot{slot}');self.assertEqual(descriptor['layout']['certificates_lebs'],64);self.assertEqual(descriptor['layout']['vault_lebs'],72)
  for args in (['arm','--yes','--enrolment-key','X'*64],['install','--yes','--replace-inactive-bank','--backed-up'],['check','--fresh-enrolment']):
   r=subprocess.run(['sh',str(out/'miami-oem-persistent-test.sh'),*args],capture_output=True,text=True);self.assertNotEqual(r.returncode,0);self.assertIn('existing enrolment is retained',r.stderr)
 def test_wrong_fit_default_and_prior_refuse(self):
  for options in ({'config':'legacy'},{'wrong_default':True},{'changed_prior':True}):
   result,_=self.generate(extra=('--ab-seed',),**options);self.assertNotEqual(result.returncode,0)
 def test_legacy_default_and_seed_enrolment_incompatibility(self):
  result,out=self.generate(config='legacy');self.assertEqual(result.returncode,0,result.stderr);script=(out/'miami-oem-persistent-test.sh').read_text();self.assertIn('FIT0=config@mi01.6-acadia-slot0',script);self.assertIn('AB_SEED=0',script)
  result,_=self.generate(extra=('--ab-seed','--with-enrolment'));self.assertNotEqual(result.returncode,0)
 def test_actual_selection_refuses_cross_bank_fit(self):
  source=(HERE/'miami-oem-persistent.sh.in').read_text();select=source[source.index('select_payload() {'):source.index('fetch() {')]
  for slot in (0,1):
   env={**os.environ,'AB_SEED':'1','SLOT':str(slot),'FIT0':'config@mi01.6-acadia-ab-slot0','FIT1':'config@mi01.6-acadia-ab-slot1'}
   for s in (0,1):
    for kind in ('KERNEL','ROOTFS'):env.update({f'{kind}{s}':'payload',f'{kind}{s}_SHA':'a'*64,f'{kind}{s}_SIZE':'1'})
   cmd='fail(){ echo "$*" >&2;exit 1; };'+select+'\nselect_payload;printf "%s" "$FIT"'
   r=subprocess.run(['sh','-c',cmd],env=env,capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(r.stdout,env[f'FIT{slot}'])
   env[f'FIT{slot}']=env[f'FIT{1-slot}'];r=subprocess.run(['sh','-c',cmd],env=env,capture_output=True,text=True);self.assertNotEqual(r.returncode,0)
 def test_standalone_seed_arm_rechecks_and_saves_exact_oem_slot(self):
  source=(HERE/'miami-oem-persistent.sh.in').read_text();start=source.index(" restore='setenv bootcount 0 && setenv bootcmd bootipq");end=source.index(' load=',start);block=source[start:end]
  for slot in (0,1):
   for fault in ('','image','bootcmd'):
    env={**os.environ,'AB_SEED':'1','img':str(slot),'observed_image':str(1-slot) if fault=='image' else str(slot),'observed_bootcmd':'wrong' if fault=='bootcmd' else 'bootipq'}
    driver='fail(){ echo "$*" >&2;exit 1; };get(){ case "$1" in image) printf "%s" "$observed_image";;bootcmd) printf "%s" "$observed_bootcmd";;esac; };'+block+'\nprintf "%s" "$restore"'
    r=subprocess.run(['sh','-c',driver],env=env,capture_output=True,text=True)
    self.assertEqual(r.returncode==0,fault=='',r.stderr)
    if not fault:self.assertEqual(r.stdout,f'setenv bootcount 0 && setenv bootcmd bootipq && setenv image {slot} && setenv changing_bootcmd && saveenv')
 def test_exact_969_seed_prior_labels_and_pins(self):
  images={}
  for slot,k in enumerate(('e412f1ed0ff9c82d53d6860cf6a7175eca75ab0f07b65f53279fc82c11281fa4','7ee74bca278d8bc3f06eb7344a65edcb10e727467935b4067db0cdd39dc8f8db')):
   for kind,suffix,h,size in [('kernel','kernel.itb',k,4856224),('rootfs','rootfs.squashfs','e52215b6e7437bfed2e6efefae9097a40eb5c7eab4e5cfb6b23e8562b4f66bb6',22506674)]:images[f'miami-ab-seed-slot{slot}-{suffix}']={'slot':slot,'kind':kind,'sha256':h,'bytes':size}
  receipt={'source_commit':'9699910d9cf5c6a51aac564189ade97a0363d38d','family':'miami','model':'X7-35X','certificate_lebs':64,'vault_lebs':72,'ab_seed':True,'images':images}
  result,out=self.generate(extra=('--ab-seed',),prior_input=receipt);self.assertEqual(result.returncode,0,result.stderr)
  script=(out/'miami-oem-persistent-test.sh').read_text();self.assertIn('PRIOR_KERNEL0_SHA='+images['miami-ab-seed-slot0-kernel.itb']['sha256'],script);self.assertIn('PRIOR_ROOTFS1_SIZE=22506674',script)
  for fault in ('slot','root','kind','size','labels','source','model','seed'):
   changed=json.loads(json.dumps(receipt));row=changed['images']['miami-ab-seed-slot0-rootfs.squashfs']
   if fault=='slot':row['slot']=1
   elif fault=='root':row['sha256']='0'*64
   elif fault=='kind':row['kind']='kernel'
   elif fault=='size':row['bytes']-=1
   elif fault=='labels':changed['images']['miami-persistent-slot0-rootfs.squashfs']=changed['images'].pop('miami-ab-seed-slot0-rootfs.squashfs')
   elif fault=='source':changed['source_commit']='f'*40
   elif fault=='model':changed['model']='other'
   else:changed['ab_seed']=False
   result,_=self.generate(extra=('--ab-seed',),prior_input=changed);self.assertNotEqual(result.returncode,0,fault)
if __name__=='__main__':unittest.main()
