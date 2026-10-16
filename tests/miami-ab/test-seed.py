#!/usr/bin/env python3
"""Actual seed context/late converted marker; synthetic ENV and device facts."""
from pathlib import Path
import tempfile,subprocess,os,json
repo=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='miami-seed-') as td:
 r=Path(td);dt=r/'dt/cambium-platform';dt.mkdir(parents=True);boot=r/'boot';boot.write_text('12345678-1234-1234-1234-123456789abc\n');state=r/'state';tools=r/'bin';tools.mkdir()
 a=tools/'envactor';a.write_text('''#!/usr/bin/env python3
import os,json,sys
from pathlib import Path
p=Path(os.environ['STATE']);e=json.loads(p.read_text());a=sys.argv[1:]
if len(a)==1:print(e.get(a[0],''))
else:e[a[0]]=a[1];p.write_text(json.dumps(e))
''');a.chmod(0o755)
 driver='''. "$MODULE"
AB_FAMILY=miami AB_MODEL=X7-35X AB_SKU=0000002c AB_ACTIVE=$SLOT AB_TARGET=$((1-SLOT)) AB_SLOT0_OFFSET=0xc0000 AB_SLOT1_OFFSET=0x60c0000
ab_miami_ab_profile(){ [ "$PROFILE" = ab ]; }
ab_running_slot(){ echo "$SLOT"; }
ab_getenv(){ envactor "$1"; };ab_setenv(){ envactor "$1" "$2"; }
ab_converted(){ [ "$(ab_getenv miami_ab_version)" = 1 ]; }
ab_miami_seed_context || exit 1
AB_MIAMI_FIRST_UPGRADE_VALIDATED=seed
ab_miami_first_upgrade || exit 1
[ "$WRITE" != yes ] || ab_miami_upgrade_written
'''
 n=0
 for slot in (0,1):
  prior=subprocess.check_output(['sh','-c','. "$1";AB_SLOT0_OFFSET=0xc0000 AB_SLOT1_OFFSET=0x60c0000;ab_miami_slot_command "$2" ab','fixture',str(repo/'feeds/tip/cambium-miami-persistent/files/cambium-ab-miami.sh'),str(slot)],text=True).strip()
  original={'miami_ab_confirmed':str(slot),'miami_ab_state':'confirmed','miami_ab_seed_boot_id':boot.read_text().strip(),f'miami_boot{slot}':prior,'bootcmd':f'run miami_boot{slot}','image':str(slot)}
  env={**os.environ,'PATH':str(tools)+':'+os.environ['PATH'],'MODULE':str(repo/'feeds/tip/cambium-miami-persistent/files/cambium-ab-miami.sh'),'AB_DT':str(dt.parent),'AB_BOOT_ID':str(boot),'SLOT':str(slot),'STATE':str(state),'PROFILE':'ab','WRITE':'no'}
  for change,good in [({},True),({'miami_ab_seed_boot_id':'old-boot'},False),({'miami_ab_confirmed':str(1-slot)},False),({'miami_ab_version':'1'},False),({'miami_ab_state':'armed'},False),({'bootcmd':'bootipq'},False),({'image':str(1-slot)},False),({f'miami_boot{slot}':prior.replace('ab-slot','slot')},False)]:
   state.write_text(json.dumps({**original,**change}));p=subprocess.run(['sh','-c',driver],env=env,capture_output=True,text=True);assert (p.returncode==0)==good,(p.stdout,p.stderr);assert 'miami_ab_version' not in json.loads(state.read_text()) or 'miami_ab_version' in change;n+=1
  state.write_text(json.dumps({**original,'miami_ab_state':'writing'}));p=subprocess.run(['sh','-c',driver],env={**env,'WRITE':'yes'},capture_output=True,text=True);assert p.returncode==0,(p.stdout,p.stderr);e=json.loads(state.read_text());assert e['miami_ab_version']=='1' and 'miami_bridge_state' not in e;n+=1
  guarded={**original,'miami_persistent_restore':f'setenv bootcmd bootipq && setenv image {1-slot} && setenv changing_bootcmd && saveenv','miami_persistent_load':prior+'; reset','miami_persistent_slot':str(slot)}
  state.write_text(json.dumps(guarded));guard_driver=driver.split('ab_miami_seed_context || exit 1')[0]+'ab_miami_guarded_command "$SLOT"\n';p=subprocess.run(['sh','-c',guard_driver],env=env,capture_output=True,text=True);assert p.returncode==0,(p.stdout,p.stderr);n+=1
  guarded['miami_persistent_restore']='setenv bootcmd bootipq && setenv changing_bootcmd && saveenv';state.write_text(json.dumps(guarded));assert subprocess.run(['sh','-c',guard_driver],env=env,capture_output=True).returncode!=0;n+=1
  state.write_text(json.dumps(original));(dt/'boot-mode').write_text('bridge\0');assert subprocess.run(['sh','-c',driver],env=env,capture_output=True).returncode!=0;(dt/'boot-mode').unlink();n+=1
 print(f'PASS: {n} exact healthy-seed/current-boot/source-route/late-version cases, both slots; device facts/ENV are actors')
