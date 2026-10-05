#!/usr/bin/env python3
"""Actual policy restoration and early boot shortcut, isolated filesystem only."""
import hashlib,json,os,pathlib,subprocess,tempfile
repo=pathlib.Path(os.environ['WLAN_AP_SOURCE_DIR'])
ucode=os.environ['NATIVE_TEST_UCODE']
assert os.getuid()==0,'Run with Root-owned synthetic fixtures'
source=repo/'feeds/tip/certificates/files'
module=repo/'feeds/tip/cloud_discovery/files/usr/share/ucentral/discovery_policy.uc'
work=pathlib.Path(tempfile.mkdtemp(prefix='managed-policy-restore.'));cases=[]
explicit='{"default":"operator.example:15002","allowed":["operator.example:15002"]}\n'
default='{"mode":"default","default":"fallback.example:15002"}\n'
malformed='{"mode":"default","allowed":[]}\n'
for name,current,saved,expected in [
 ('durable-explicit-over-packaged-default',default,explicit,explicit),
 ('durable-explicit-with-runtime-absent',None,explicit,explicit),
 ('archived-explicit-over-older-durable',explicit,default,explicit),
 ('archived-malformed-never-broadened','{broken',default,'{broken'),
 ('ambiguous-runtime-never-broadened',malformed,default,malformed),
 ('durable-malformed-remains-fail-closed',default,'{broken','{broken'),
 ('no-durable-leaves-packaged-default',default,None,default),
 ('durable-default-retains-installer-fallback',default,'{"mode":"default","default":"installer.example:16000"}', '{"mode":"default","default":"installer.example:16000"}'),
 ('no-policies',None,None,None),
 ('unsafe-durable-symlink',default,explicit,default),
 ('unsafe-runtime-symlink',default,explicit,default),
 ('unsafe-durable-hardlink',default,explicit,default),
 ('unsafe-durable-writable',default,explicit,default),
 ('interrupted-restore',default,explicit,explicit),
]:
 fixture=work/name;runtime=fixture/'runtime';store=fixture/'store';runtime.mkdir(parents=True);store.mkdir()
 r=runtime/'discovery-policy.json';s=store/'discovery-policy.json'
 for p,v in [(r,current),(s,saved)]:
  if v is not None:p.write_text(v);p.chmod(0o600)
 if name=='unsafe-durable-symlink':s.rename(store/'actual');s.symlink_to(store/'actual')
 if name=='unsafe-runtime-symlink':r.rename(runtime/'actual');r.symlink_to(runtime/'actual')
 if name=='unsafe-durable-hardlink':os.link(s,store/'other')
 if name=='unsafe-durable-writable':s.chmod(0o666)
 if name=='interrupted-restore':p=runtime/'discovery-policy.json.restore';p.write_text('interrupted');p.chmod(0o600)
 helper=fixture/'restore.uc';helper.write_text((source/'usr/libexec/ucentral-restore-discovery-policy').read_text().replace('/usr/share/ucentral/discovery_policy.uc',str(module)).replace("'/certificates'",repr(str(store))).replace("'/etc/ucentral'",repr(str(runtime))))
 p=subprocess.run([ucode,str(helper)],capture_output=True,text=True)
 assert (p.returncode!=0)==name.startswith('unsafe'),(name,p.stdout,p.stderr)
 assert (r.read_text() if r.exists() else None)==expected,name
 cases.append(name)
# Execute actual early_boot saved identity branch. Preserve keys/leaf bytes.
for supported,label in [(True,'saved-identity-restores-durable-policy'),(False,'other-board-saved-identity-no-mount')]:
 fixture=work/label;runtime=fixture/'runtime';store=fixture/'store';runtime.mkdir(parents=True);store.mkdir()
 for f in ['key.pem','operational.pem']:(runtime/f).write_text('synthetic '+f)
 (runtime/'discovery-policy.json').write_text(default);(store/'discovery-policy.json').write_text(explicit)
 for p in [runtime/'discovery-policy.json',store/'discovery-policy.json']:p.chmod(0o600)
 helper=fixture/'restore.uc';helper.write_text((source/'usr/libexec/ucentral-restore-discovery-policy').read_text().replace('/usr/share/ucentral/discovery_policy.uc',str(module)).replace("'/certificates'",repr(str(store))).replace("'/etc/ucentral'",repr(str(runtime))))
 wrapper=fixture/'restore';wrapper.write_text('#!/bin/sh\nexec '+ucode+' '+str(helper)+'\n');wrapper.chmod(0o700)
 core=fixture/'core';core.write_text('ab_family(){ return '+str(0 if supported else 1)+'; }\n')
 mount=fixture/'mount';mount.write_text('#!/bin/sh\necho mounted >> '+str(fixture/'mount.log')+'\n');mount.chmod(0o700)
 prepare=fixture/'prepare';prepare.write_text('#!/bin/sh\nexit 0\n');prepare.chmod(0o700)
 boot=(source/'etc/init.d/early_boot').read_text().replace('/usr/libexec/ucentral-restore-operational-gateway',str(prepare)).replace('/usr/libexec/ucentral-installer-boot',str(prepare)).replace('/usr/libexec/ucentral-restore-discovery-policy',str(wrapper)).replace('/usr/bin/mount_certs',str(mount)).replace('/lib/functions/cambium-ab.sh',str(core)).replace('/etc/ucentral',str(runtime)).replace('/certificates',str(store))
 script=fixture/'boot';script.write_text(boot+'\nboard_name(){ echo cambiumnetworks,e410; }\nboot\n')
 p=subprocess.run(['sh',str(script)],capture_output=True,text=True)
 assert p.returncode==0,(label,p.stderr)
 assert (runtime/'discovery-policy.json').read_text()==explicit,label
 assert (fixture/'mount.log').exists()==supported,label
 for f in ['key.pem','operational.pem']:assert (runtime/f).read_text()=='synthetic '+f
 cases.append(label)
 if supported:
  (runtime/'discovery-policy.json').write_text(default)
  mount.write_text('#!/bin/sh\nexit 1\n')
  wrapper.write_text('#!/bin/sh\necho called > '+str(fixture/'restore-called')+'\nexec '+ucode+' '+str(helper)+'\n')
  p=subprocess.run(['sh',str(script)],capture_output=True,text=True)
  assert p.returncode!=0,p.stderr
  assert not (fixture/'restore-called').exists()
  assert (runtime/'discovery-policy.json').read_text()==default
  for f in ['key.pem','operational.pem']:assert (runtime/f).read_text()=='synthetic '+f
  cases.append('saved-identity-mount-failure-before-restore-preserves-files')
 # Execute the full durable identity restore path as well; saved runtime
 # explicit policy must win rather than being overwritten by copy_certificates.
 (runtime/'discovery-policy.json').write_text(explicit)
 (store/'discovery-policy.json').write_text(default)
 for f in ['key.pem','operational.pem']:(store/f).write_text('restored synthetic '+f)
 full=fixture/'copy';full.write_text(boot.replace('/etc/modules.conf',str(fixture/'modules.conf'))+'\nchown(){ :; }\njsonfilter(){ :; }\ncopy_certificates\n')
 p=subprocess.run(['sh',str(full)],capture_output=True,text=True)
 assert p.returncode==0,(label,p.stderr)
 assert (runtime/'discovery-policy.json').read_text()==explicit,label
 assert (runtime/'operational.pem').read_text()=='restored synthetic operational.pem'
 cases.append(label+'-full-copy-preserves-runtime-explicit')
print(json.dumps({'passed':True,'cases':cases,'count':len(cases),'helper_sha256':hashlib.sha256((source/'usr/libexec/ucentral-restore-discovery-policy').read_bytes()).hexdigest(),'early_boot_sha256':hashlib.sha256((source/'etc/init.d/early_boot').read_bytes()).hexdigest(),'scope':'Actual ucode helper and early_boot shortcut, Root synthetic files. Mount/hardware/installer boundaries isolated; no AP/service/trust writes.'},indent=2))
