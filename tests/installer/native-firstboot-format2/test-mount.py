from pathlib import Path
import tempfile,subprocess,json,os
base=Path(os.environ['NATIVE_FIRSTBOOT_SOURCE_DIR']);w=Path(tempfile.mkdtemp(prefix='native-mount.'));store=w/'store';runtime=w/'runtime';store.mkdir();runtime.mkdir();table=w/'mounts';lib=w/'lib';lib.write_text('');core=w/'core';bin=w/'bin';bin.mkdir();trace=w/'trace'
mount=bin/'mount';mount.write_text('#!/bin/sh\necho mounted >> "'+str(trace)+'"\n[ "${FAIL_MOUNT:-0}" != 1 ] || exit 1\nprintf "/dev/ubi7_4 '+str(store)+' ubifs rw,relatime 0 0\\n" > "'+str(table)+'"\n');mount.chmod(0o700)
s=(base/'mount_certs').read_text().replace('/lib/functions.sh',str(lib)).replace('/lib/functions/cambium-ab.sh',str(core)).replace('/certificates',str(store)).replace('/etc/ucentral/',str(runtime)+'/').replace('/proc/mounts',str(table));script=w/'script';script.write_text(s)
def cfg(target='1',job='b'*64,image='a'*64):
 core.write_text('ab_family(){ AB_ENV=sage; AB_LAYOUT=pair; AB_ACTIVE_UBI=ubi7; }; ab_identity(){ AB_ACTIVE=1; }; ab_ubi_volume(){ echo ubi7_4; }; ab_getenv(){ case "$1" in *_target) echo '+target+';; *_job) echo '+job+';; *_image) echo '+image+';; esac; };\n')
report=[]
def test(name,line,arg='--installer-empty',ok=False,full=False,failmount=False,target='1',job='b'*64):
 cfg(target,job);table.write_text(line.replace('@',str(store)));trace.unlink(missing_ok=True)
 for n in ['cert.pem','key.pem']:
  (store/n).unlink(missing_ok=True)
  if full:(store/n).touch()
 env=dict(os.environ,PATH=str(bin)+':'+os.environ['PATH'],FAIL_MOUNT=str(int(failmount)));p=subprocess.run(['sh',str(script),arg],env=env,capture_output=True);assert (p.returncode==0)==ok,(name,p.stderr);report.append(name)
good='/dev/ubi7_4 @ ubifs rw,relatime 0 0\n'
test('empty-mounted-pending',good,ok=True);test('empty-new-mount-pending','',ok=True);test('wrong-volume','/dev/ubi6_4 @ ubifs rw 0 0\n');test('wrong-type','/dev/ubi7_4 @ ext4 rw 0 0\n');test('readonly','/dev/ubi7_4 @ ubifs ro 0 0\n');test('duplicate',good+good);test('child-cover',good+'/dev/x @/nested ubifs rw 0 0\n');test('fallback',good,target='0');test('malformed-job',good,job='bad');test('mount-failure','',failmount=True);test('ordinary-empty-refused',good,arg='');test('ordinary-full-unchanged',good,arg='',full=True,ok=True)
r={'passed':True,'cases':report,'scope':'Actual packaged mount_certs shell with isolated core/env/mount/table/files; genuine empty-store return1 reproduced; no real mount/AP/service.'};(base/'mount-regressions.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
