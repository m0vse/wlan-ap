#!/usr/bin/env python3
"""Exact .8 incoming source consumers on inert writer archives/ENV.
Only host shell runs. No target ELF, init service, physical device or TLS call.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import unittest

HERE=Path(__file__).resolve().parents[1]
PREFIX=HERE/'tests/fixtures/jaguar-2026.10.05.8-'
PINS={'cambium-board-data.sh':'1f8f29ce91310cdcacdb6077df1061637211207ee245041604376ea055428c43',
 'identity.source':'54651cd16550464842b15915344f8f28fdc16741adfc27bbd5b829bc75832a82',
 'health.source':'84c24614ee914427fa6543fe12ddacec4f7c53fae5650e77cf3ac5b356e31ec7',
 'boot.source':'61d68123f627528771704c6a1482b98c5ec8064c707c7a1a47b47fa991e93619',
 'mount.source':'9f171a5a28cc435a8b982079d43e043b219639cf35e3014a400ef056bb683696'}
def source(name):
 data=Path(str(PREFIX)+name).read_bytes()
 if hashlib.sha256(data).hexdigest()!=PINS[name]:raise AssertionError('actual image consumer fixture changed')
 return data.decode()
def functions(text,names):
 return '\n'.join(re.search(r'^'+re.escape(name)+r'\(\) \{\n.*?^\}',text,re.M|re.S)[0] for name in names)

def check_incoming_context(root,model,sku,slot):
 """Replay actual identity CONTEXT_COMMAND, pending boot and health/cleanup.
 Library paths and hardware getters alone are inert, not the consumer logic.
 Full Ucode validation/crypto/enrollment acceptance is not executed here.
 """
 identity=source('identity.source');health=source('health.source');boot=source('boot.source');mount=source('mount.source')
 command=json.loads(re.search(r'^const CONTEXT_COMMAND = (".*");$',identity,re.M)[1])
 seed=root/'staged-upper/root/.cambium-installer-settings'
 binding=dict(row.split('\t',1) for row in (seed/'binding.tsv').read_text().splitlines())
 with tempfile.TemporaryDirectory() as directory:
  work=Path(directory);env=json.loads((root/'env.json').read_text())
  env['__serial']=binding['serial'];env['__model']=model;env['__active']=str(1-slot)
  state=work/'env';state.write_text(''.join(k+'='+v+'\n' for k,v in env.items()))
  system=work/'system.sh';system.write_text('get_mac_label_dt() { echo "$SERIAL"; }; get_mac_label() { echo "$SERIAL"; }\n')
  ab=work/'ab.sh';ab.write_text('ab_family() { AB_ENV=jaguar; }; ab_identity() { ab_family; AB_FAMILY=jaguar; AB_MODEL=$MODEL; AB_ACTIVE=$ACTIVE; }; ab_getenv() { sed -n "s/^$1=//p" "$STATE"; }\n')
  command=command.replace('/lib/functions/system.sh',str(system)).replace('/lib/functions/cambium-ab.sh',str(ab))
  contextenv=dict(os.environ,SERIAL=binding['serial'],MODEL=model,ACTIVE=str(1-slot),STATE=str(state))
  result=subprocess.run(['sh','-c',command],env=contextenv,capture_output=True,text=True)
  if result.returncode or result.stdout.strip().split('\t')!=[binding['serial'],'jaguar',model,str(1-slot),binding['target_slot'],binding['job_id'],binding['image_sha256']]:raise AssertionError('incoming exact context rejects writer metadata: '+result.stderr)
  # These are the comparisons in the actual Ucode trusted_context function.
  for required in ('parts[4] != b.target_slot','parts[5] != b.job_id','parts[6] != b.image_sha256'):
   if required not in identity:raise AssertionError('incoming context ABI changed')
  boot=boot.replace('/lib/functions/system.sh',str(system)).replace('/lib/functions/cambium-ab.sh',str(ab))
  result=subprocess.run(['sh','-c',boot,'incoming','pending'],env=contextenv,capture_output=True,text=True)
  if result.returncode:raise AssertionError('incoming pending boot rejects writer triplet: '+result.stderr)
  mount_block=re.search(r'^\t\tif \[ "\$\{1:-\}" = --installer-empty \]; then\n.*?^\t\tfi$',mount,re.M|re.S)[0]
  mounts=work/'mounts';mounts.write_text('/dev/ubi0_4 /certificates ubifs rw 0 0\n')
  mount_block=mount_block.replace('/proc/mounts',str(mounts))
  result=subprocess.run(['sh','-c',f'. "{ab}"; ab_identity; cert_volume=ubi0_4; '+mount_block,'incoming','--installer-empty'],env=contextenv,capture_output=True,text=True)
  if result.returncode:raise AssertionError('incoming empty-store mount guard rejects writer triplet: '+result.stderr)
  accept=work/'accept';accept.write_text('#!/bin/sh\n[ "$1" = accepted ] || [ "$1" = cleanup-confirmed ]\n');accept.chmod(0o755)
  script=f'. "{ab}"; ab_identity; '+health+'\nab_installer_health && ab_installer_clear_pending "$CLEAR"'
  contextenv.update(AB_INSTALLER_INCOMING_SEED=str(seed),AB_INSTALLER_ACCEPT=str(accept),CLEAR=str(work/'clear'))
  result=subprocess.run(['sh','-c',script],env=contextenv,capture_output=True,text=True)
  if result.returncode or (work/'clear').read_text().splitlines()!=['jaguar_installer_target','jaguar_installer_job','jaguar_installer_image']:raise AssertionError('incoming health/clear_pending rejects writer: '+result.stderr)
  # Valid-looking foreign metadata must fail binding, not merely length checks.
  for key in ('jaguar_installer_job','jaguar_installer_image'):
   original=state.read_text();state.write_text(re.sub(r'^'+key+r'=.*$',key+'='+'f'*64,original,flags=re.M))
   if subprocess.run(['sh','-c',f'. "{ab}"; ab_identity; '+health+'\nab_installer_health'],env=contextenv,capture_output=True).returncode==0:raise AssertionError('foreign incoming metadata accepted')
   state.write_text(original)
  for key in ('jaguar_installer_target','jaguar_installer_job','jaguar_installer_image'):
   original=state.read_text();state.write_text(re.sub(r'^'+key+r'=.*\n','',original,flags=re.M))
   result=subprocess.run(['sh','-c',boot,'incoming','pending'],env=contextenv,capture_output=True)
   if result.returncode==0:raise AssertionError('partial incoming boot metadata accepted')
   state.write_text(original)
  # Actual confirmed cleanup uses the same three deletions and stable selector.
  state.write_text(''.join(k+'='+v+'\n' for k,v in {**env,'jaguar_installer_target':'','jaguar_installer_job':'','jaguar_installer_image':'','jaguar_ab_confirmed':str(1-slot),'jaguar_ab_state':'confirmed','bootcmd':f'run jaguar_stable{1-slot}'}.items()))
  result=subprocess.run(['sh','-c',f'. "{ab}"; ab_identity; '+health+'\nab_installer_cleanup_confirmed "unused" "$AB_ACTIVE"'],env=contextenv,capture_output=True,text=True)
  if result.returncode:raise AssertionError('incoming confirmed cleanup ABI mismatch: '+result.stderr)

class ConsumerTests(unittest.TestCase):
 def fixture(self,model='XV2-2T1',slot=0,prepare=True):
  spec=importlib.util.spec_from_file_location('jag_forward_fixture',HERE/'tests/test-jaguar-forward.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  holder=module.ForwardTests();case=holder.fixture(model,slot);self.addCleanup(holder.doCleanups)
  root,bundle,work,bin,model,sku=case
  if not prepare:return case
  # Darwin tar's AppleDouble sidecars are not produced by native Linux tar.
  env=dict(os.environ,COPYFILE_DISABLE='1',PATH=str(bin)+':'+os.environ['PATH'],FIXTURE=str(root),HERE=str(HERE),OEM_SYS_ROOT=str(root),OEM_BUNDLE=str(bundle),OEM_WORK=str(work),OEM_FAMILY='jaguar',OEM_MODEL=model,OEM_SKU=sku,OEM_SUPPORTED_RELEASE='7.2-r1')
  script='. "$HERE/lib/common.sh"; . "$HERE/lib/protection.sh"; . "$HERE/adapters/jaguar.sh"; oem_adapter_inspect && oem_adapter_preflight && oem_jaguar_vault_prepare'
  result=subprocess.run(['sh','-c',script],env=env,capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)
  return case
 def consume(self,case,directory=None,board=None):
  root,_,work,_,model,sku=case
  script=functions(source('cambium-board-data.sh'),('sha256','board_files','manifest_value','vault_check'))+'\nboard_name() { echo "$BOARD"; }; ab_dt_sku() { echo "$SKU"; }; art_hash() { sha256 "$ART"; }; VAULT_FORMAT=1; vault_check "$VAULT"'
  return subprocess.run(['sh','-c',script],env=dict(os.environ,BOARD=board or 'cambiumnetworks,'+model.lower(),SKU=sku,ART=str(root/'dev/mtd3ro'),VAULT=str(directory or work/'jaguar-vault')),capture_output=True,text=True)
 def test_actual_writer_archives_three_models_consumer_and_shrink_safe(self):
  for model in ('XV2-2','XV2-2T1','XE3-4'):
   case=self.fixture(model);root,_,work,_,_,_=case
   self.assertEqual(self.consume(case).returncode,0)
   self.assertIn('nvram_sha256_at_capture unknown',(work/'jaguar-vault/MANIFEST').read_text())
   archive=work/'jaguar-vault.tar';data=archive.read_bytes();blocks=(len(data)+126975)//126976
   with tarfile.open(archive) as tar:
    files=[m.name for m in tar.getmembers() if m.isfile()]
    self.assertEqual(len(files),3 if model=='XE3-4' else 2,files)
    self.assertEqual(len([m for m in tar.getmembers() if m.issym() or m.islnk()]),0)
   for size in (8*126976,blocks*126976):
    raw=work/f'raw-{size}.tar';raw.write_bytes(data+b'\0'*(size-len(data)))
    unpacked=work/f'read-{size}';unpacked.mkdir()
    subprocess.run(['tar','-xf',str(raw),'-C',str(unpacked)],check=True)
    self.assertEqual(raw.read_bytes()[:len(data)],data)
    self.assertEqual(self.consume(case,unpacked).returncode,0)
   if model=='XV2-2':self.assertLessEqual(369+blocks+20,392)
 def test_actual_consumer_rejects_wrong_board_sku_art_path_size_hash(self):
  for fault in ('board','sku','art','path','size','hash'):
   case=self.fixture();root,_,work,_,model,sku=case;manifest=work/'jaguar-vault/MANIFEST'
   if fault=='board':manifest.write_text(manifest.read_text().replace('cambiumnetworks,','cambium,'))
   if fault=='sku':manifest.write_text(manifest.read_text().replace('sku '+sku,'sku 00000020'))
   if fault=='art':(root/'dev/mtd3ro').write_bytes(b'other device ART')
   asset=next(p for p in (work/'jaguar-vault/files').rglob('*') if p.is_file())
   if fault=='path':asset.unlink()
   if fault=='size':asset.write_bytes(b'wrong size')
   if fault=='hash':asset.write_bytes(b'C'*asset.stat().st_size)
   self.assertNotEqual(self.consume(case).returncode,0,fault)
 def test_writer_refuses_controller_or_generic_board_alias_before_env(self):
  for board in ('cambium,xv2-2t1','cambiumnetworks,jaguar'):
   case=self.fixture(prepare=False);root,bundle,work,bin,model,sku=case
   (bundle/f'profiles/{model}/vault-board').write_text(board+'\n')
   (bundle/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(bundle))+'\n' for p in sorted(bundle.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'))
   env=dict(os.environ,PATH=str(bin)+':'+os.environ['PATH'],FIXTURE=str(root),HERE=str(HERE),OEM_SYS_ROOT=str(root),OEM_BUNDLE=str(bundle),OEM_WORK=str(work),OEM_RECOVERY_DIR=str(work/'critical'),OEM_FAMILY='jaguar',OEM_MODEL=model,OEM_SKU=sku,OEM_SUPPORTED_RELEASE='7.2-r1',OEM_CONTROLLER='controller.invalid')
   script='. "$HERE/lib/common.sh"; . "$HERE/lib/protection.sh"; . "$HERE/lib/critical-backup.sh"; . "$HERE/adapters/jaguar.sh"; IFS= read -r input < "$FIXTURE/key";oem_adapter_migrate "$input"'
   result=subprocess.run(['sh','-c',script],env=env,capture_output=True,text=True)
   self.assertNotEqual(result.returncode,0)
   events=(root/'events').read_text() if (root/'events').exists() else ''
   for mutation in ('SOURCE ','ARM ','ubiupdatevol ','ubirmvol '):self.assertNotIn(mutation,events)

if __name__=='__main__':unittest.main()
