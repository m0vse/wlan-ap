#!/usr/bin/env python3
"""Actual shared mount helper: exact Miami64 opt-in and empty-store fences."""
from pathlib import Path
import tempfile,subprocess,os
repo=Path(__file__).resolve().parents[3]
with tempfile.TemporaryDirectory(prefix='miami-cert-mount-') as td:
 w=Path(td);store=w/'store';store.mkdir();runtime=w/'runtime';runtime.mkdir();table=w/'mounts';lib=w/'lib';lib.write_text('');core=w/'core';b=w/'bin';b.mkdir();trace=w/'trace';sys=w/'ubi';(sys/'ubi7_4').mkdir(parents=True);size=sys/'ubi7_4/reserved_ebs';size.write_text('64\n')
 mount=b/'mount';mount.write_text('#!/bin/sh\necho mounted >> "'+str(trace)+'"\n[ "${FAIL_MOUNT:-0}" != 1 ] || exit 1\nprintf "/dev/ubi7_4 '+str(store)+' ubifs rw,relatime 0 0\\n" > "'+str(table)+'"\n');mount.chmod(0o700)
 s=(repo/'feeds/tip/certificates/files/usr/bin/mount_certs').read_text().replace('/lib/functions/system.sh',str(lib)).replace('/lib/functions.sh',str(lib)).replace('/lib/functions/cambium-ab.sh',str(core)).replace('/certificates',str(store)).replace('/etc/ucentral/',str(runtime)+'/').replace('/proc/mounts',str(table));script=w/'script';script.write_text(s)
 def run(family='miami',model='X7-35X',lebs=64,context=True,line=None,arg='--installer-empty',target='1',job='b'*64,full=False,ok=False,failmount=False):
  core.write_text(f"""ab_family(){{ AB_ENV=miami; AB_FAMILY={family}; AB_MODEL={model}; AB_LAYOUT=banks; AB_CERTIFICATE_LEBS={lebs}; AB_ACTIVE_UBI=ubi7; }}
ab_identity(){{ AB_ACTIVE=1; }}
ab_miami_storage_context(){{ return {0 if context else 1}; }}
ab_miami_certificate_mount(){{ awk -v dev="/dev/ubi7_4" -v path="{store}" '$2==path {{n++;if($1==dev&&$3=="ubifs"&&("," $4 ",")~/,rw,/)good++}} index($2,path "/")==1{{child++}} END{{exit !(n==1&&good==1&&!child)}}' "{table}"; }}
ab_ubi_volume(){{ echo ubi7_4; }}
ab_getenv(){{ case "$1" in *_target) echo {target};; *_job) echo {job};; *_image) echo {'a'*64};; esac; }}
""")
  good=f'/dev/ubi7_4 {store} ubifs rw,relatime 0 0\n';table.write_text(good if line is None else line.replace('@',str(store)));trace.unlink(missing_ok=True)
  for n in ['cert.pem','key.pem']:
   (store/n).unlink(missing_ok=True)
   if full:(store/n).touch()
  env=dict(os.environ,PATH=str(b)+':'+os.environ['PATH'],AB_UBI_SYS=str(sys),FAIL_MOUNT=str(int(failmount)))
  q=subprocess.run(['sh',str(script),arg],env=env,capture_output=True);assert (q.returncode==0)==ok,(q.stderr,family,lebs,arg)
  return trace.exists()
 run(ok=True);run(line='',ok=True)
 run(context=False,line='');assert not trace.exists()
 size.write_text('20\n');run(line='');assert not trace.exists();size.write_text('64\n')
 for line in ['/dev/ubi9_4 @ ubifs rw 0 0\n','/dev/ubi7_4 @ ext4 rw 0 0\n','/dev/ubi7_4 @ ubifs ro 0 0\n','/dev/ubi7_4 @ ubifs rw 0 0\n/dev/ubi7_2 @/child ubifs rw 0 0\n']:run(line=line)
 run(target='0');run(job='bad');run(failmount=True,line='')
 run(arg='') # no special unprovisioned-success exception for storage pilot
 run(arg='',full=True,ok=True)
 # Other qualified families keep their existing 20-LEB path.
 run(family='jaguar',model='XV2-2',lebs=20,ok=True)
print('PASS: actual mount_certs exact Miami64 context/capacity; active pending empty success; ordinary empty remains failure; wrong bank/type/RO/child/foreign job and mount failures refuse; Jaguar20 unchanged')
