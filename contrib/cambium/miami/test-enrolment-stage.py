#!/usr/bin/env python3
"""Run real shared seed preparation and Miami staging with isolated UBI mounts."""
from pathlib import Path
import hashlib, os, stat, subprocess, tempfile
repo=Path(__file__).resolve().parents[3]
with tempfile.TemporaryDirectory(prefix='miami-enrolment-stage-') as td:
 w=Path(td).resolve();r=w/'root';b=w/'bin';b.mkdir()
 for d in ('tmp','etc','dev','sys/ubi9','sys/ubi9_2'):(r/d).mkdir(parents=True,exist_ok=True)
 (r/'etc/version').write_text('VERSION=7.1-r1\n')
 (r/'sys/ubi9/mtd_num').write_text('3');(r/'sys/ubi9_2/name').write_text('rootfs_data')
 pair=r/'tmp/pair.json';pair.write_bytes(b'{"fixture":"sealed kernel and root pair"}\n')
 sha=hashlib.sha256(pair.read_bytes()).hexdigest();mounts=w/'mounts';mounts.write_text('')
 overlay=w/'overlay';overlay.mkdir();envfile=w/'environment';envfile.write_text('')
 for name,body in {
  'get_esn':'#!/bin/sh\nprintf "020000000001\\n"\n[ "${FAIL_ESN:-0}" = 0 ]\n',
  'ls':'#!/usr/bin/env python3\nimport os,stat,sys\np=sys.argv[-1];s=os.lstat(p);print(stat.filemode(s.st_mode),s.st_nlink,s.st_uid,s.st_gid,s.st_size,"Jan 1 00:00",p)\n',
  'mount':'#!/usr/bin/env python3\nfrom pathlib import Path\nimport os,sys,shutil\np=Path(sys.argv[-1]); source=Path(os.environ["FIXTURE_OVERLAY"])\nfor entry in source.iterdir():shutil.copytree(entry,p/entry.name)\nPath(os.environ["OW_SETTINGS_MOUNTS"]).write_text(sys.argv[-2]+" "+str(p)+" ubifs rw 0 0\\n")\n',
  'umount':'#!/usr/bin/env python3\nfrom pathlib import Path\nimport os,sys,shutil\np=Path(sys.argv[-1]);dest=Path(os.environ["FIXTURE_OVERLAY"])\nfor entry in dest.iterdir():shutil.rmtree(entry)\nfor entry in p.iterdir():shutil.copytree(entry,dest/entry.name)\nPath(os.environ["OW_SETTINGS_MOUNTS"]).write_text("")\n'}.items():
  f=b/name;f.write_text(body);f.chmod(0o700)
 driver=w/'driver.sh';driver.write_text('''#!/bin/sh
. "$LIB"
. "$ADAPTER"
fail() { echo 'Fixture staging refused' >&2; exit 1; }
volume() { [ "$1" = rootfs_data ] && echo ubi9_2; }
fetch() { [ "$(sha256sum "$R/tmp/$1" | cut -d ' ' -f1)" = "$2" ]; }
get() { awk -v k="$1" '$1==k {v=$2;n++} END{if(n!=1)exit 1;print v}' "$ENV_FILE"; }
put() { old=$(get "$1" || true); [ -z "$old" ] || [ "$old" = "$2" ] || exit 1; [ -n "$old" ] || printf '%s %s\\n' "$1" "$2" >> "$ENV_FILE"; }
miami_enrolment_stage "$1"
''')
 env={**os.environ,'CAMBIUM_ENROLMENT_SERVER':'controller.example.test','PATH':str(b)+':'+os.environ['PATH'],'R':str(r),'LIB':str(repo/'tools/oem-migration/recovery/scripts/lib/cambium-installer-settings.sh'),'ADAPTER':str(repo/'contrib/cambium/miami/miami-enrolment-stage.sh'),
 'ENROLMENT_READY':'1','SLOT':'0','img':'1','T':'3','PAIR0':'pair.json','PAIR0_SHA':sha,'PAIR0_SIZE':str(pair.stat().st_size),'SOURCE_CONTRACT_SHA':'a'*64,
 'OW_SETTINGS_OWNER':str(os.getuid()),'OW_SETTINGS_SYS':str(r/'sys'),'OW_SETTINGS_MOUNTS':str(mounts),'OW_SETTINGS_DEV':str(r/'dev'),'FIXTURE_OVERLAY':str(overlay),'ENV_FILE':str(envfile)}
 def run(key):
  p=subprocess.run(['sh',str(driver),key],env=env,capture_output=True,text=True)
  assert 'X'*64 not in p.stdout+p.stderr
  return p
 p=run('short');assert p.returncode!=0 and not envfile.read_text()
 env['FAIL_ESN']='1';p=run('X'*64);assert p.returncode!=0 and not envfile.read_text()
 env.pop('FAIL_ESN')
 for controller in ['', 'controller.example.test;bad', 'https://controller.example.test', '.example.test', 'example.test.']:
  env['CAMBIUM_ENROLMENT_SERVER']=controller
  p=run('X'*64);assert p.returncode!=0 and not envfile.read_text()
 env['CAMBIUM_ENROLMENT_SERVER']='controller.example.test'
 p=run('X'*64);assert p.returncode==0,(p.stdout,p.stderr)
 seed=overlay/'upper/root/.cambium-installer-settings'
 assert seed.is_dir() and seed.stat().st_mode&0o777==0o700
 binding=dict(row.split('\t') for row in (seed/'binding.tsv').read_text().splitlines())
 assert binding['serial']=='020000000001' and binding['source_slot']=='1' and binding['target_slot']=='0' and binding['image_sha256']==sha
 before={p.name:p.read_bytes() for p in seed.iterdir()};state=envfile.read_bytes()
 p=run('X'*64);assert p.returncode==0,(p.stdout,p.stderr)
 assert envfile.read_bytes()==state and {p.name:p.read_bytes() for p in seed.iterdir()}==before
 p=run('Y'*64);assert p.returncode!=0
 assert envfile.read_bytes()==state and {p.name:p.read_bytes() for p in seed.iterdir()}==before
 assert not mounts.read_text()
 print('PASS: native protected key staging; exact Miami identity/slot/pair; stable same-job retry; foreign-key refusal; no secret output')
