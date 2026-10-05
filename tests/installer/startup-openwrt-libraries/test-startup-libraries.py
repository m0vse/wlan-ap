#!/usr/bin/env python3
"""Actual packaged OpenWrt libraries, boot guard and init functions; no hardware."""
import hashlib,json,os,pathlib,shutil,subprocess,sys,tempfile
root=pathlib.Path(sys.argv[1]);candidate=pathlib.Path(sys.argv[2]);busybox=os.environ['OW_TEST_BUSYBOX']
work=pathlib.Path(tempfile.mkdtemp(prefix='startup-library-regression.'));bin=work/'bin';bin.mkdir();cases=[]
required=['lib/functions.sh','lib/functions/system.sh','lib/config/uci.sh','usr/share/libubox/jshn.sh']
files={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in required}
shutil.copytree(root/'lib/functions',work/'lib/functions');shutil.copytree(root/'lib/config',work/'lib/config');shutil.copytree(root/'usr/share/libubox',work/'usr/share/libubox');shutil.copyfile(root/'lib/functions.sh',work/'lib/functions.sh')
sysinfo=work/'sysinfo';sysinfo.mkdir();(sysinfo/'board_name').write_text(os.environ.get('OW_TEST_BOARD','cambiumnetworks,e410')+'\n')
dt=work/'dt/cambium-platform';dt.mkdir(parents=True);(dt/'board-sku').write_bytes(bytes.fromhex('00000002'))
mt=work/'mtd';mt.write_text('')
def redirect(s):
 for a,b in [('/lib/functions',str(work/'lib/functions')),('/lib/config',str(work/'lib/config')),('/usr/share/libubox',str(work/'usr/share/libubox')),('/tmp/sysinfo',str(sysinfo)),('/sbin/uci',str(bin/'uci'))]:s=s.replace(a,b)
 return s
for directory in [work/'lib',work/'usr/share/libubox']:
 for p in directory.rglob('*.sh'):p.write_text(redirect(p.read_text()))
def executable(name,text):p=bin/name;p.write_text('#!/bin/sh\n'+text);p.chmod(0o700);return p
executable('fw_printenv','exit 1\n');executable('fw_setenv','echo forbidden-write >&2\nexit 99\n')
executable('uci',"cat <<'EOF'\npackage 'ucentral'\nconfig 'ucentral' 'config'\noption 'serial' 'SYNTHETIC-E410'\noption 'debug' '0'\nEOF\n")
baseenv={'PATH':str(bin)+':/usr/bin:/bin','AB_ENV_CONFIG':str(work/'env.config'),'AB_DT':str(work/'dt'),'AB_PROC_MTD':str(mt),'CAMBIUM_AB_MODULES':str(work/'lib/functions'),'CAMBIUM_SAGE_LIB':str(work/'lib/functions/cambium-sage.sh')}
assert 'IPKG_INSTROOT' not in baseenv
old=work/'old-boot';old.write_text(redirect((root/'usr/libexec/ucentral-installer-boot').read_text()))
new=work/'new-boot';new.write_text(redirect(candidate.read_text()))
for op in ['prepare','check','pending']:
 p=subprocess.run([busybox,'ash',str(old),op],env=baseenv,capture_output=True,text=True)
 if 'set -eu\n' in (root/'usr/libexec/ucentral-installer-boot').read_text():
  assert p.returncode!=0 and 'IPKG_INSTROOT' in p.stderr,(op,p.returncode,p.stderr)
  cases.append('reproduced-packaged-nounset-failure-'+op)
 else:
  assert p.returncode==int(op=='pending') and 'parameter not set' not in p.stderr,(op,p.returncode,p.stderr)
  cases.append('fixed-packaged-unset-env-'+op)
for op,expected in [('prepare',0),('check',0),('pending',1)]:
 p=subprocess.run([busybox,'ash',str(new),op],env=baseenv,capture_output=True,text=True)
 assert p.returncode==expected,(op,p.returncode,p.stdout,p.stderr)
 assert 'parameter not set' not in p.stderr
 cases.append('actual-libraries-normal-unset-env-'+op)
# Keep the actual A/B library and family selection; isolate only identity
# hardware reads and the installer identity subprocess for pending trials.
core=work/'lib/functions/cambium-ab.sh'
core.write_text(core.read_text()+'\nab_identity(){ AB_ACTIVE=${FIXTURE_ACTIVE:-1}; };\n')
executable('fw_printenv', 'case "$4" in *_installer_target) printf %s "${FIXTURE_TARGET:-}";; *_installer_job) printf %s "${FIXTURE_JOB:-}";; *_installer_image) printf %s "${FIXTURE_IMAGE:-}";; *) exit 1;; esac\n')
identity=executable('identity', 'echo "$*" >> '+str(work/'identity.log')+'\nexit "${FIXTURE_IDENTITY_FAILURE:-0}"\n')
new.write_text(new.read_text().replace('/usr/libexec/ucentral-installer-identity',str(identity)).replace('/root/.cambium-installer-settings',str(work/'settings')))
pending={**baseenv,'FIXTURE_TARGET':'1','FIXTURE_JOB':'b'*64,'FIXTURE_IMAGE':'a'*64}
for label,values,op,expected in [
 ('pending-guard-valid',pending,'pending',0),
 ('pending-prepare-valid',pending,'prepare',0),
 ('pending-check-valid',pending,'check',0),
 ('pending-check-not-ready',{**pending,'FIXTURE_IDENTITY_FAILURE':'1'},'check',1),
 ('fallback-guard',{**pending,'FIXTURE_ACTIVE':'0'},'pending',1),
 ('fallback-check-normal',{**pending,'FIXTURE_ACTIVE':'0'},'check',0),
 ('malformed-job-refused',{**pending,'FIXTURE_JOB':'bad'},'check',1),
 ('malformed-target-refused',{**pending,'FIXTURE_TARGET':'2'},'pending',1),
]:
 p=subprocess.run([busybox,'ash',str(new),op],env=values,capture_output=True,text=True)
 assert p.returncode==expected,(label,p.returncode,p.stdout,p.stderr)
 assert 'parameter not set' not in p.stderr
 cases.append(label)
# Invoke the actual packaged procd init functions through the real boot helper.
bootwrapper=executable('fixture-boot','exec '+busybox+' ash '+str(new)+' "$@"\n')
ready=work/'ready';ready.touch();runtime=work/'runtime';runtime.mkdir();(runtime/'capabilities.json').write_text('{}')
(runtime/'gateway.json').write_text(json.dumps({'server':'gateway.example','port':15002,'cert':str(runtime/'operational.pem'),'ca':str(runtime/'server-ca.pem'),'hostname_validate':1}))
for n in ['key.pem','operational.pem','server-ca.pem']:(runtime/n).write_text('synthetic '+n)
(runtime/'platform').write_text('ap');(runtime/'version').write_text('synthetic-version')
shadow=work/'config-shadow';shadow.mkdir();(shadow/'ucentral').write_text('synthetic config')
config=work/'config';config.mkdir()
executable('jsonfilter',"case \"$*\" in *server*) echo gateway.example;; *port*) echo 15002;; *hostname_validate*) echo 1;; *cert*) echo '"+str(runtime/'operational.pem')+"';; *ca*) echo '"+str(runtime/'server-ca.pem')+"';; esac\n")
report=executable('boot-report','echo collected\n');executable('mount','exit 0\n');executable('logger','exit 0\n')
for init in ['cloud_discover','ucentral']:
 path='etc/init.d/'+init
 s=(root/path).read_text();s=s[s.index('service_triggers()'):];s=redirect(s)
 for a,b in [('/usr/libexec/ucentral-installer-boot',str(bootwrapper)),('/usr/libexec/ucentral-boot-report',str(report)),('/tmp/ucentral-network.ready',str(ready)),('/etc/ucentral',str(runtime)),('/tmp/ucentral.version',str(runtime/'version')),('/etc/config-shadow',str(shadow)),('/etc/config/',str(config)+'/'),('/tmp/ucentral/',str(work/'daemon-state')+'/')]:s=s.replace(a,b)
 shim="PROG=/usr/"+('bin/cloud_discovery' if init=='cloud_discover' else 'sbin/ucentral')+"; procd_open_instance(){ echo instance; }; procd_set_param(){ echo param:$*; }; procd_append_param(){ echo append:$*; }; procd_close_instance(){ echo closed; }; est_client(){ return 0; };\n"
 program=work/(init+'.sh');program.write_text(shim+s+'\nstart_service\n')
 p=subprocess.run([busybox,'ash',str(program)],env=baseenv,capture_output=True,text=True)
 assert p.returncode==0 and 'param:command '+('/usr/bin/cloud_discovery' if init=='cloud_discover' else '/usr/sbin/ucentral') in p.stdout,(init,p.returncode,p.stdout,p.stderr)
 assert 'parameter not set' not in p.stderr
 cases.append('actual-'+init+'-init-starts-with-unset-env')
 p=subprocess.run([busybox,'ash',str(program)],env={**pending,'FIXTURE_IDENTITY_FAILURE':'1'},capture_output=True,text=True)
 if init=='cloud_discover':
  assert p.returncode==0 and 'param:command /usr/libexec/ucentral-installer-firstboot' in p.stdout,(p.stdout,p.stderr)
 else:
  assert p.returncode!=0 and 'param:command /usr/sbin/ucentral' not in p.stdout,(p.stdout,p.stderr)
 cases.append('actual-'+init+'-init-pending-unready-guard')
for n in ['key.pem','operational.pem','server-ca.pem']:assert (runtime/n).read_text()=='synthetic '+n
print(json.dumps({'passed':True,'cases':cases,'count':len(cases),'packaged_library_sha256':files,'candidate_sha256':hashlib.sha256(candidate.read_bytes()).hexdigest(),'scope':'Actual packaged OpenWrt libraries and boot/init functions under BusyBox ash with IPKG_INSTROOT unset. Synthetic filesystem only; fw_printenv/UCI/jsonfilter/procd and hardware boundaries isolated; no AP/services/ENV/trust writes.'},indent=2))
