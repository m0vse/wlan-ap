#!/usr/bin/env python3
"""Actual upgrade flow/source helpers, actual family boot renderers.

Storage, admission and durable-ENV boundaries are disposable fixtures. This
is not hardware, watchdog or interruption-inside-NOR-program qualification.
"""
from pathlib import Path
import argparse,json,os,subprocess,tempfile

repo=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--core',type=Path);a=p.parse_args()

def reconstruct_upgrade(root):
 """Replay only this file's real repository hunks; no SDK/private input."""
 relative='package/cambium/cambium-ab/files/cambium-ab-upgrade.sh'
 created=next((repo/'patches-25.12').glob('0124-*.patch'))
 section=created.read_text().split('+++ b/'+relative+'\n',1)[1].split('\ndiff --git ',1)[0]
 target=root/relative;target.parent.mkdir(parents=True)
 target.write_text(''.join(x[1:]+'\n' for x in section.splitlines() if x.startswith('+')))
 marker='--- a/'+relative+'\n'
 for path in sorted((repo/'patches-25.12').glob('*.patch')):
  if not created.name<path.name<'0184-':continue
  text=path.read_text()
  if marker not in text:continue
  fragment=marker+text.split(marker,1)[1]
  fragment=fragment.split('\ndiff --git ',1)[0].split('\n--- a/',1)[0].split('\n--- /dev/null',1)[0]
  patch=root/'component.patch';patch.write_text(fragment.rstrip()+'\n')
  subprocess.run(['patch','--batch','--fuzz=0','-p1','-i',str(patch)],cwd=root,check=True,capture_output=True)
 subprocess.run(['sh','-n',str(target)],check=True)
 return target.read_text()

with tempfile.TemporaryDirectory(prefix='ab-prewrite-') as td:
 root=Path(td);files=root/'package/cambium/cambium-ab/files';files.mkdir(parents=True)
 original=a.core.read_text() if a.core else reconstruct_upgrade(root/'repository-source')
 core=files/'cambium-ab-upgrade.sh';core.write_text(original)
 recipe=files.parent/'Makefile'
 recipe.write_text('include $(TOPDIR)/rules.mk\n\nPKG_NAME:=cambium-ab\nPKG_RELEASE:=18\nPKG_LICENSE:=GPL-2.0-only\nPKG_MAINTAINER:=Phil Taylor <phil@m0vse.uk>\n\n')
 subprocess.run(['patch','--batch','--fuzz=0','-p1','-i',str(repo/'patches-25.12/0184-cambium-ab-preserve-working-source-before-write.patch')],cwd=root,check=True,capture_output=True)
 assert 'PKG_RELEASE:=19\n' in recipe.read_text()
 (root/'empty').write_text('')
 modules={}
 for family,prefix in [('jaguar','0124-'),('cheetah','0125a-'),('thor','0141-'),('gambit','0140-')]:
  patch=next((repo/'patches-25.12').glob(prefix+'*.patch')).read_text()
  marker=f'+++ b/package/cambium/cambium-{family}-support/files/cambium-ab-{family}.sh\n'
  section=patch.split(marker,1)[1].split('\ndiff --git ',1)[0]
  source=root/(family+'.sh');source.write_text(''.join(x[1:]+'\n' for x in section.splitlines() if x.startswith('+')))
  modules[family]=source
 # Test-only frozen renderer: the shared main tree does not admit Miami
 # firmware profiles. Prefer actual port source when it is present.
 miami=repo/'feeds/tip/cambium-miami-persistent/files/cambium-ab-miami.sh'
 modules['miami']=miami if miami.is_file() else Path(__file__).with_name('fixtures')/'miami-boot.sh'
 modules['sage']=repo/'tests/installer/sage-existing-openwifi-r2/modules/cambium-ab-sage.sh'
 cases=[('jaguar','cambiumnetworks,xv2-2',''),('cheetah','cambiumnetworks,xv2-21x',''),
        ('thor','cambiumnetworks,xv3-8',''),('gambit','cambiumnetworks,e400',''),
        ('miami','cambiumnetworks,x7-35x',''),('sage','cambiumnetworks,e410','squashfs'),
        ('sage','cambiumnetworks,e410','ubifs'),('sage','cambiumnetworks,e410b','squashfs')]
 renderer='''ab_getenv(){ echo 0; };ab_mtd_index(){ return 1; }
ab_bank_hex(){ printf '0x%x\n' $((0x$AB_BANK_SIZE)); }
. "$MODULE"
"ab_${FAMILY}_board" "$BOARD" || exit 1
AB_ACTIVE=$PRIOR
ab_sage_root_format(){ echo "$FORMAT"; }
"ab_${FAMILY}_boot_command" "$PRIOR"
'''
 tool=root/'env-tool.py';tool.write_text('''import json,os,sys
from pathlib import Path
p=Path(os.environ['ENV_FILE']);e=json.loads(p.read_text());op=sys.argv[1];fail=os.environ['FAIL']
trace=Path(os.environ['TRACE'])
def record(s):
 with trace.open('a') as f:f.write(s+'\\n')
if op=='get':
 k=sys.argv[2]
 if fail=='readback' and k=='bootcmd' and trace.read_text():print('changed');sys.exit()
 if fail=='source-changed' and k.endswith('_boot'+os.environ['PRIOR']) and trace.read_text():print('changed');sys.exit()
 print(e.get(k,''));sys.exit()
if op=='set':
 k,v=sys.argv[2:];record('set:'+k)
 if fail==k:sys.exit(1)
 e[k]=v;p.write_text(json.dumps(e));sys.exit()
if op=='batch':
 record('journal')
 for row in Path(sys.argv[2]).read_text().splitlines():
  k,_,v=row.partition(' ');e[k]=v
 p.write_text(json.dumps(e));sys.exit()
if op=='sync':
 record('sync')
 if fail=='sync':sys.exit(1)
 sys.exit()
if op=='target':
 record('target')
 assert e['bootcmd']=='run '+os.environ['FAMILY']+'_boot'+os.environ['PRIOR']
 assert e['image']==os.environ['PRIOR']
 if fail=='target':sys.exit(1)
 Path(os.environ['TARGET']).write_bytes(b'new verified candidate');sys.exit()
if op=='arm':
 record('arm')
 if fail=='arm':sys.exit(1)
 e['bootcmd']='one-shot-trial';p.write_text(json.dumps(e));sys.exit()
raise AssertionError(op)
''')
 driver='''. "$UPGRADE"
AB_ENV=$FAMILY AB_FAMILY=$FAMILY AB_ACTIVE=$PRIOR AB_TARGET=$((1-PRIOR)) AB_LAYOUT=banks AB_CERTIFICATE_LEBS=20
ab_upgrade_preflight(){ [ "$FAIL" != preflight ]; }
# Local image admission is a boundary here; the real ordered writer is used.
ab_image_extract(){ [ "$FAIL" != image-admission ]; }
ab_certificate_validate_snapshot(){ [ "$FAIL" != snapshot ]; }
ab_boot_command(){ [ "$FAIL" != render ] && printf '%s\n' "$SOURCE_COMMAND"; }
ab_getenv(){ python3 "$TOOL" get "$1"; }
ab_setenv(){ python3 "$TOOL" set "$1" "$2"; }
ab_setenv_batch(){ python3 "$TOOL" batch "$1"; }
sync(){ python3 "$TOOL" sync; }
ab_hook(){ [ "$1" = write_target ]; }
for name in sage jaguar cheetah thor gambit miami;do eval "ab_${name}_write_target(){ python3 \\\"\\$TOOL\\\" target; }";done
ab_certificate_restore(){ :; }
ab_arm_trial(){ python3 "$TOOL" arm; }
cambium_ab_do_upgrade "$LOCAL_IMAGE"
'''
 # A literal function avoids shell eval/escaping ambiguity in the fixture.
 driver=driver.replace('for name in sage jaguar cheetah thor gambit miami;do eval "ab_${name}_write_target(){ python3 \\\"\\$TOOL\\\" target; }";done',
                       '\n'.join(f'ab_{f}_write_target(){{ python3 "$TOOL" target; }}' for f in ('sage','jaguar','cheetah','thor','gambit','miami')))
 baseenv={**os.environ,'CAMBIUM_AB_LIB':str(root/'empty'),'CAMBIUM_AB_CERTIFICATE_LIB':str(root/'absent'),
          'TOOL':str(tool),'ENV_FILE':str(root/'env.json'),'TRACE':str(root/'trace'),
          'TARGET':str(root/'target'),'LOCAL_IMAGE':str(root/'already-staged-image'),
          'CAMBIUM_SAGE_LIB':str(repo/'tests/installer/sage-existing-openwifi-r2/cambium-sage.sh')}
 def execute(source,family,prior,command,failure):
  env={**baseenv,'UPGRADE':str(source),'FAMILY':family,'PRIOR':str(prior),'SOURCE_COMMAND':command,'FAIL':failure}
  stored=command if failure!='wrong-source' else 'unqualified incoming target command'
  before={family+'_boot'+str(prior):stored,'bootcmd':'run '+family+'_stable'+str(prior),'image':str(prior),
          'untouched_unique':'factory sentinel'}
  (root/'env.json').write_text(json.dumps(before));(root/'trace').write_text('');(root/'target').write_bytes(b'old inactive bank')
  r=subprocess.run(['sh','-c',driver],env=env,capture_output=True,text=True)
  trace=(root/'trace').read_text().splitlines();after=json.loads((root/'env.json').read_text())
  assert after['untouched_unique']==before['untouched_unique'] and after[family+'_boot'+str(prior)]==stored
  return r,trace,after
 count=0
 for family,board,fmt in cases:
  for prior in (0,1):
   command=subprocess.check_output(['sh','-c',renderer],env={**baseenv,'MODULE':str(modules[family]),'FAMILY':family,'BOARD':board,'PRIOR':str(prior),'FORMAT':fmt},text=True).strip()
   assert command
   for failure in ('preflight','image-admission','snapshot','render','wrong-source','bootcmd','image','sync','readback','source-changed'):
    r,trace,after=execute(core,family,prior,command,failure)
    assert r.returncode!=0 and 'target' not in trace and 'arm' not in trace,(family,prior,failure,r.stdout,r.stderr,trace)
    count+=1
   for failure in ('target','arm',''):
    r,trace,after=execute(core,family,prior,command,failure)
    assert 'target' in trace and trace.index('sync')<trace.index('target'),trace
    assert (r.returncode==0)==(failure==''),(failure,r.stdout,r.stderr)
    if failure:assert after['bootcmd']=='run '+family+'_boot'+str(prior)
    count+=1
 # Negative control: the actual old writer reaches target without prior-only
 # persistence and is rejected by the target boundary assertion.
 old=root/'old-upgrade.sh';old.write_text(original)
 r,trace,_=execute(old,'jaguar',0,'actual source command','')
 assert r.returncode!=0 and 'target' in trace and 'set:bootcmd' not in trace
 print(f'PASS: {count} ordered source-preservation fault/trace cases with actual family boot renderers; old writer negative control rejected')
