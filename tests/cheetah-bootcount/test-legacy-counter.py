from pathlib import Path
import subprocess,tempfile,json,os,sys,shutil,shlex,hashlib
base=Path(__file__).resolve().parent
shell=shlex.split(os.environ.get('CHEETAH_TEST_SHELL','/bin/sh'))
repo=base.parents[1]
generated=None
if len(sys.argv)>1:
 candidate=Path(sys.argv[1])
else:
 generated=tempfile.TemporaryDirectory(prefix='cheetah-merged-counter-')
 tree=Path(generated.name)
 relatives=[
  'package/cambium/cambium-cheetah-support/files/cambium-ab-cheetah.sh',
  'package/cambium/cambium-cheetah-support/Makefile',
  'package/cambium/cambium-ab/files/cambium-ab-guard',
  'package/cambium/cambium-ab/Makefile',
 ]
 if os.environ.get('CHEETAH_GENERATED_SOURCE'):
  source=Path(os.environ['CHEETAH_GENERATED_SOURCE'])
  for relative in relatives:
   dest=tree/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source/relative,dest)
 else:
  # Materialize exact created files and replay their full prerequisite hunks.
  # Never synthesize release counters to hide a broken patch stack.
  initial=(repo/'patches-25.12/0124-qualcommax-add-Cambium-Jaguar-OpenWiFi-family.patch').read_text()
  for relative in relatives[2:]:
   section=initial.split('+++ b/'+relative+'\n',1)[1].split('\ndiff --git ',1)[0]
   dest=tree/relative;dest.parent.mkdir(parents=True,exist_ok=True)
   dest.write_text(''.join(line[1:]+'\n' for line in section.splitlines() if line.startswith('+')))
  for patch in sorted((repo/'patches-25.12').glob('*.patch')):
   if 124 < int(patch.name[:4]) < 187:
    subprocess.run(['git','apply',*['--include='+relative for relative in relatives],str(patch)],cwd=tree,check=True,capture_output=True)
 assert 'PKG_RELEASE:=19\n' in (tree/relatives[3]).read_text()
 assert 'PKG_RELEASE:=6\n' in (tree/relatives[1]).read_text()
 baseline_module=(tree/relatives[0]).read_text()
 baseline_guard=(tree/relatives[2]).read_text()
 patches=[
  (repo/'patches-25.12/0187-cambium-jaguar-neutralize-oem-bank-toggle-counter.patch',['--include=package/cambium/cambium-ab/*']),
  (repo/'patches-25.12/0188-cambium-cheetah-neutralize-oem-bank-toggle-counter.patch',[]),
 ]
 for patch,includes in patches:
  subprocess.run(['git','apply','--check',*includes,str(patch)],cwd=tree,check=True)
  subprocess.run(['git','apply',*includes,str(patch)],cwd=tree,check=True)
 assert 'PKG_RELEASE:=20\n' in (tree/relatives[3]).read_text()
 assert 'PKG_RELEASE:=7\n' in (tree/relatives[1]).read_text()
 candidate=tree/'candidate';candidate.mkdir()
 shutil.copy2(tree/relatives[0],candidate/'cambium-ab-cheetah.sh')
 shutil.copy2(tree/relatives[2],candidate/'cambium-ab-guard')
 (candidate/'baseline-module').write_text(baseline_module)
 (candidate/'baseline-guard').write_text(baseline_guard)
module=candidate/'cambium-ab-cheetah.sh';guard=candidate/'cambium-ab-guard'
rows=[]
with tempfile.TemporaryDirectory() as tmp:
 work=Path(tmp);(work/'empty').write_text('')
 script=work/'test.sh'
 script.write_text('''
. "$MODULE"
. "$GUARD"
AB_FAMILY=cheetah AB_STOCK_BOOTCMD=bootipq AB_MARKER=1 AB_FIT=config@mp03.3-ocelot AB_SLOT0_OFFSET=0x80000 AB_SLOT1_OFFSET=0x6080000
ab_bank_hex() { echo 0x6000000; }
ab_running_slot() { echo "$SLOT"; }
ab_guarded_command() { ab_cheetah_guarded_command "$@"; }
ab_hook() { command -v "ab_${AB_FAMILY}_$1" >/dev/null; }
wait_healthy() { [ "$HEALTH" = yes ]; }
log() { :; }
do_reboot() { echo REBOOT; }
READ_PHASE=before
sync() { [ "$FAIL" != sync ]; }
ab_getenv() {
 case "$1" in
 bootcmd) echo "$BOOTCMD" ;;
 image) [ "$FAIL" != image-read ] || return 1; echo "$IMAGE" ;;
 bootcount) [ "$FAIL" != count-read ] || return 1; echo "$COUNT" ;;
 esac
 [ "$FAIL" != "$READ_PHASE-$1-read-status" ]
}
ab_setenv() {
 echo "SET:$1:$2"
 case "$1" in
 bootcount)
  [ "$FAIL" != count-write ] || return 1
  [ "$FAIL" = count-mismatch ] || COUNT=$2
  [ "$FAIL" != image-mutates ] || IMAGE=$SLOT
  [ "$FAIL" != bootcmd-mutates ] || BOOTCMD=unreviewed
  READ_PHASE=after
  ;;
 bootcmd) BOOTCMD=$2 ;;
 esac
}
if [ "$MODE" = command ]; then ab_cheetah_guarded_command "$SLOT"; else legacy_guard; fi
''')
 common={**os.environ,'MODULE':str(module.resolve()),'GUARD':str(guard.resolve()),'CAMBIUM_SYSTEM_FUNCTIONS':str(work/'empty'),'CAMBIUM_AB_LIB':str(work/'empty'),'CAMBIUM_INSTALLER_HEALTH_LIB':str(work/'absent'),'AB_GUARD_SOURCE_ONLY':'1','BOOTCMD':'bootipq','MODE':'guard'}
 def run(slot,health,count,fail='',image=None,bootcmd='bootipq'):
  env={**common,'SLOT':str(slot),'HEALTH':health,'COUNT':count,'FAIL':fail,'IMAGE':str(1-slot) if image is None else str(image),'BOOTCMD':bootcmd}
  r=subprocess.run(shell+[str(script)],env=env,text=True,capture_output=True)
  success=not fail and image is None and bootcmd=='bootipq'
  assert (r.returncode==0)==success,(env,r.stdout,r.stderr,r.returncode)
  if success:
   assert 'SET:bootcount:0' in r.stdout
   if health=='yes':assert r.stdout.index('SET:bootcount:0')<r.stdout.index('SET:bootcmd:') and 'REBOOT' not in r.stdout
   else:assert r.stdout.index('SET:bootcount:0')<r.stdout.index('REBOOT') and 'SET:bootcmd:' not in r.stdout
  else:
   assert 'REBOOT' not in r.stdout and 'SET:bootcmd:' not in r.stdout
   if fail.startswith('before-'): assert 'SET:bootcount' not in r.stdout,r.stdout
  rows.append({'slot':slot,'health':health,'counter':count,'fault':fail or ('wrong-image' if image is not None else 'independent-bootcmd' if bootcmd!='bootipq' else ''),'passed':True})
 for slot in [0,1]:
  for health in ['yes','no']:
   for counter in ['','0','1','7','8','9','90','garbage']:run(slot,health,counter)
   for fault in ['count-write','count-read','count-mismatch','image-read','image-mutates','bootcmd-mutates','sync',
                 'before-bootcmd-read-status','before-image-read-status','before-bootcount-read-status',
                 'after-bootcmd-read-status','after-image-read-status','after-bootcount-read-status']:run(slot,health,'9',fault)
   run(slot,health,'9',image=slot);run(slot,health,'9',bootcmd='independent')
  env={**common,'MODE':'command','SLOT':str(slot)}
  r=subprocess.run(shell+[str(script)],env=env,text=True,capture_output=True);assert r.returncode==0
  cmd=r.stdout.strip();assert cmd.startswith('if setenv bootcount 0 && setenv image '+str(1-slot)+' && ')
  assert '&& saveenv; then ' in cmd and '; bootipq; else echo OEM_ENV_UNSAFE_STOP_AT_PROMPT; fi' in cmd
  rows.append({'slot':slot,'guarded_save_failure_gated':True,'passed':True})
  for fault in ['', 'bootcount', 'image', 'bootcmd', 'changing_bootcmd', 'saveenv']:
   harness="""
# Failed prefix writes affect RAM only; old persisted count9 remains unsafe.
DURABLE_COUNT=9; DURABLE_IMAGE=$OEM_SLOT; RUNTIME_COUNT=9; RUNTIME_IMAGE=$TARGET_SLOT
setenv() {
 echo SET:$1; [ "$FAIL_STAGE" != "$1" ] || return 1
 case "$1" in bootcount) RUNTIME_COUNT=$2;; image) RUNTIME_IMAGE=$2;; esac
}
saveenv() {
 echo SAVE; [ "$FAIL_STAGE" != saveenv ] || return 1
 DURABLE_COUNT=$RUNTIME_COUNT; DURABLE_IMAGE=$RUNTIME_IMAGE
 echo SAVED:$DURABLE_IMAGE:$DURABLE_COUNT
}
nand() { echo NAND; }
ubi() { echo UBI; }
bootm() { echo FIT_RETURN; return 1; }
bootipq() { echo OEM_RETURN:$DURABLE_IMAGE:$DURABLE_COUNT; }
reset() { echo RESET_WITH_DURABLE:$DURABLE_IMAGE:$DURABLE_COUNT; }
"""+cmd+'\necho DURABLE_FINAL:$DURABLE_IMAGE:$DURABLE_COUNT\n'
   r=subprocess.run(shell+['-c',harness],env={**os.environ,'FAIL_STAGE':fault,'OEM_SLOT':str(1-slot),'TARGET_SLOT':str(slot)},text=True,capture_output=True)
   assert r.returncode==0,(fault,r.stdout,r.stderr)
   if fault:
    assert 'OEM_ENV_UNSAFE_STOP_AT_PROMPT' in r.stdout and 'RESET' not in r.stdout and 'NAND' not in r.stdout and 'OEM_RETURN' not in r.stdout,(fault,r.stdout)
    assert f'DURABLE_FINAL:{1-slot}:9' in r.stdout and 'SAVED:' not in r.stdout,(fault,r.stdout)
   else:
    assert r.stdout.index('SET:bootcount')<r.stdout.index('SAVED:')<r.stdout.index('NAND')<r.stdout.index('OEM_RETURN')
    assert f'SAVED:{1-slot}:0' in r.stdout and f'OEM_RETURN:{1-slot}:0' in r.stdout and 'RESET' not in r.stdout,r.stdout
   rows.append({'slot':slot,'actual_rendered_prefix_fault':fault,'passed':True})

 for slot in [0,1]:
  for health in ['yes','no']:
   other=script.read_text().replace('AB_FAMILY=cheetah','AB_FAMILY=other')
   otherfile=work/'other.sh';otherfile.write_text(other)
   r=subprocess.run(shell+[str(otherfile)],env={**common,'SLOT':str(slot),'HEALTH':health,'COUNT':'9','FAIL':'','IMAGE':str(1-slot)},text=True,capture_output=True)
   assert r.returncode==0 and 'SET:bootcount:' not in r.stdout,(r.stdout,r.stderr)
   assert ('REBOOT' in r.stdout)==(health=='no')
   rows.append({'family_without_optional_hook':True,'slot':slot,'health':health,'passed':True})
 for slot in ['','2','garbage']:
  r=subprocess.run(shell+[str(script)],env={**common,'MODE':'command','SLOT':slot},text=True,capture_output=True);assert r.returncode!=0
  rows.append({'invalid_slot':slot,'passed':True})

 # The opposite-OEM hook must never enter converted A/B orchestration.
 for slot in [0,1]:
  converted=r'''
AB_ENV=cheetah AB_ACTIVE=$SLOT AB_LAYOUT=pair
ab_identity() { return 0; }
ab_getenv() {
 case "$1" in
 cheetah_ab_state) echo "$STATE";;
 cheetah_ab_target|cheetah_ab_confirmed) echo "$SLOT";;
 esac
}
ab_cheetah_prepare_oem_return() { echo FORBIDDEN_LEGACY_HOOK; return 1; }
save_network_health() { :; }
record_rollback() { echo ROLLBACK; }
commit_trial() { echo COMMIT; }
ab_guard
'''
  source=script.read_text().replace('if [ "$MODE" = command ]; then ab_cheetah_guarded_command "$SLOT"; else legacy_guard; fi',converted)
  converted_file=work/'converted.sh';converted_file.write_text(source)
  for state,health in [('confirmed','yes'),('trial-started','yes'),('trial-started','no')]:
   r=subprocess.run(shell+[str(converted_file)],env={**common,'SLOT':str(slot),'STATE':state,'HEALTH':health,'COUNT':'9','FAIL':'','IMAGE':str(slot)},text=True,capture_output=True)
   assert r.returncode==0 and 'FORBIDDEN_LEGACY_HOOK' not in r.stdout and 'SET:bootcount' not in r.stdout,(r.stdout,r.stderr)
   assert ('COMMIT' in r.stdout)==(state=='trial-started' and health=='yes'),r.stdout
   assert ('REBOOT' in r.stdout)==(state=='trial-started' and health=='no'),r.stdout
   rows.append({'converted_ab_route':state,'slot':slot,'health':health,'passed':True})
  dispatch=source.replace('ab_guard\n','''ab_family() { :; }
ab_converted() { return 0; }
ab_guard() { echo CONVERTED_DISPATCH; }
legacy_guard() { echo WRONG_LEGACY_DISPATCH; return 1; }
main
''')
  converted_file.write_text(dispatch)
  r=subprocess.run(shell+[str(converted_file)],env={**common,'SLOT':str(slot),'HEALTH':'yes','FAIL':''},text=True,capture_output=True)
  assert r.returncode==0 and 'CONVERTED_DISPATCH' in r.stdout and 'WRONG_LEGACY_DISPATCH' not in r.stdout,r.stdout
  rows.append({'converted_main_dispatch':True,'slot':slot,'passed':True})
 if (candidate/'baseline-module').exists():
  import re
  baseline=(candidate/'baseline-module').read_text()
  current=module.read_text()
  pattern=r'(?ms)^ab_cheetah_boot_command\(\) \{.*?^\}'
  assert re.search(pattern,baseline).group()==re.search(pattern,current).group()
  old_guard=(candidate/'baseline-guard').read_text();new_guard=guard.read_text()
  for function in ['ab_guard','commit_trial','main']:
   pattern=r'(?ms)^'+function+r'\(\) \{.*?^\}'
   assert re.search(pattern,old_guard).group()==re.search(pattern,new_guard).group(),function
  rows.append({'converted_renderer_and_orchestration_unchanged':True,'passed':True})

print(json.dumps({'passed':True,'cases':len(rows),'results':rows,'candidate_module_sha256':hashlib.sha256(module.read_bytes()).hexdigest(),'scope':'Actual candidate shell functions, synthetic environment/write/reboot boundaries. No AP writes or bootloader hardware acceptance.'},indent=2))
