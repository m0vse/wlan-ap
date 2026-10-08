import pathlib,subprocess,tempfile,json,os,hashlib,sys,shlex
health=pathlib.Path(sys.argv[1]);miami=pathlib.Path(sys.argv[2]);core=pathlib.Path(sys.argv[3]);work=pathlib.Path(tempfile.mkdtemp(prefix='native-completion-review.'))
cases=[]
def run(name,env,op,want):
 d=work/name;d.mkdir();seed=d/'seed';seed.mkdir();state=d/'env';state.mkdir();calls=d/'calls';calls.touch()
 values={'miami_installer_target':'1','miami_installer_job':'b'*64,'miami_installer_image':'a'*64,'image':'0','changing_bootcmd':'1','bootcmd':'guarded'}
 values.update(env.get('VALUES',{}))
 for k,v in values.items():(state/k).write_text(v)
 (seed/'binding.tsv').write_text('job_id\t'+env.get('SEED_JOB','b'*64)+'\nimage_sha256\t'+'a'*64+'\ntarget_slot\t1\n')
 accept=d/'accept';accept.write_text('#!/bin/sh\nprintf "%s\\n" "$1" >> "$CALLS"\ncase "$1" in accepted) exit "${FAIL_ACCEPT:-0}";;cleanup-confirmed) exit "${FAIL_CLEANUP:-0}";;esac\n');accept.chmod(0o700)
 script=d/'run';script.write_text('''. "$CORE"
. "$MIAMI"
. "$HEALTH"
AB_ENV=miami AB_FAMILY=miami AB_MODEL=X7-35X AB_ACTIVE=1
AB_INSTALLER_INCOMING_SEED="$SEED" AB_INSTALLER_ACCEPT="$ACCEPT"
ab_getenv(){ test -f "$ENV/$1" || return 1; cat "$ENV/$1"; }
ab_miami_storage_context(){ return "${FAIL_STORAGE:-0}"; }
ab_miami_certificate_mount(){ return "${FAIL_MOUNT:-0}"; }
ab_miami_guarded_command(){ echo guarded; }
sync(){ return "${FAIL_SYNC:-0}"; }
ab_setenv_batch(){ echo write >> "$CALLS"; test "${FAIL_WRITE:-0}" = 0 || return 1; while read -r key; do test "${STALE_READBACK:-0}" = 0 || continue; : > "$ENV/$key"; done < "$1"; }
''' + op+'\n')
 settings={**os.environ,'CORE':str(core),'CAMBIUM_AB_MODULES':str(work/'no-autoload'),'MIAMI':str(miami),'HEALTH':str(health),'SEED':str(seed),'ACCEPT':str(accept),'ENV':str(state),'CALLS':str(calls)}
 settings.update({k:str(v) for k,v in env.items() if k not in ['VALUES','SEED_JOB']})
 p=subprocess.run(shlex.split(os.environ.get('REVIEW_SHELL','/bin/sh'))+[str(script)],env=settings,capture_output=True,text=True)
 assert (p.returncode==0)==(want==0),(name,p.returncode,p.stderr)
 trace=calls.read_text().splitlines();pending=(state/'miami_installer_target').read_text()
 if want!=0:assert 'cleanup-confirmed' not in trace or name=='cleanup-failure-resumable'
 if name=='success':assert trace==['accepted','accepted','write','cleanup-confirmed'] and pending==''
 if name in ['accept-failure','context-storage-failure','context-mount-failure','write-failure','stale-readback','wrong-seed-job']:assert pending=='1'
 if name=='fallback-bank-noop':assert not trace and pending=='0'
 cases.append({'name':name,'exit':p.returncode,'trace':trace,'pending_target':pending,'passed':True})
run('success',{},'ab_installer_legacy_complete 1',0)
run('accept-failure',{'FAIL_ACCEPT':1},'ab_installer_legacy_complete 1',1)
run('context-storage-failure',{'FAIL_STORAGE':1},'ab_installer_legacy_complete 1',1)
run('context-mount-failure',{'FAIL_MOUNT':1},'ab_installer_legacy_complete 1',1)
run('write-failure',{'FAIL_WRITE':1},'ab_installer_legacy_complete 1',1)
run('stale-readback',{'STALE_READBACK':1},'ab_installer_legacy_complete 1',1)
run('wrong-seed-job',{'SEED_JOB':'c'*64},'ab_installer_legacy_complete 1',1)
run('fallback-bank-noop',{'VALUES':{'miami_installer_target':'0'}},'ab_installer_legacy_complete 1',0)
run('bad-marker',{'VALUES':{'changing_bootcmd':'0'}},'ab_installer_confirmed_context',1)
run('bad-guarded-command',{'VALUES':{'bootcmd':'bootipq'}},'ab_installer_confirmed_context',1)
run('bad-opposite-oem-slot',{'VALUES':{'image':'1'}},'ab_installer_confirmed_context',1)
run('converted-marker-blocks-oem',{'VALUES':{'miami_ab_version':'1'}},'ab_installer_confirmed_context',1)
run('converted-three-checks-preserved',{'VALUES':{'miami_ab_confirmed':'1','miami_ab_state':'confirmed','bootcmd':'run miami_stable1'},'FAIL_STORAGE':1},'ab_installer_confirmed_context',0)
run('converted-mismatch-no-hook',{'VALUES':{'miami_ab_confirmed':'0','miami_ab_state':'confirmed','bootcmd':'run miami_stable1'}},'unset -f ab_miami_installer_confirmed_context; ab_installer_confirmed_context',1)
run('cleanup-failure-resumable',{'FAIL_CLEANUP':1},'ab_installer_legacy_complete 1',1)
run('cleared-pending-resume-cleanup',{'VALUES':{'miami_installer_target':'','miami_installer_job':'','miami_installer_image':''}},'ab_installer_legacy_complete 1',0)
run('sync-failure-stops-cleanup',{'FAIL_SYNC':1},'ab_installer_legacy_complete 1',1)
run('invalid-active-slot',{},'ab_installer_legacy_complete 2',1)
run('non-miami-fallback-rejected',{},'AB_ENV=sage AB_FAMILY=sage; ab_sage_installer_confirmed_context(){ return 0; }; ab_installer_confirmed_context',1)
run('converted-state-mismatch',{'VALUES':{'miami_ab_confirmed':'1','miami_ab_state':'trial-started','bootcmd':'run miami_stable1'}},'unset -f ab_miami_installer_confirmed_context; ab_installer_confirmed_context',1)
run('converted-bootcmd-mismatch',{'VALUES':{'miami_ab_confirmed':'1','miami_ab_state':'confirmed','bootcmd':'bootipq'}},'unset -f ab_miami_installer_confirmed_context; ab_installer_confirmed_context',1)
run('missing-conversion-api-refused',{},'unset -f ab_converted; ab_installer_confirmed_context',1)
run('unknown-conversion-marker-refused',{'VALUES':{'miami_ab_version':'unexpected'}},'ab_installer_confirmed_context',1)
run('zero-conversion-marker-refused',{'VALUES':{'miami_ab_version':'0'}},'ab_installer_confirmed_context',1)
run('wrong-miami-model-refused',{},'AB_MODEL=X7-55X; ab_installer_confirmed_context',1)
run('wrong-family-with-miami-env-refused',{},'AB_FAMILY=sage; ab_installer_confirmed_context',1)
run('owned-hook-invalid-active-slot-refused',{},'AB_ACTIVE=2; ab_miami_installer_confirmed_context',1)
print(json.dumps({'passed':True,'count':len(cases),'core_sha256':hashlib.sha256(core.read_bytes()).hexdigest(),'health_sha256':hashlib.sha256(health.read_bytes()).hexdigest(),'miami_sha256':hashlib.sha256(miami.read_bytes()).hexdigest(),'cases':cases,'fixture':str(work),'scope':'Actual generated core20 sourced, real ab_converted and ab_hook implementations (no invented ab_mode). Exact shared shell helper and Miami confirmed hook; mount/storage/guard command and ENV write/accepted helper boundaries mocked; no real ENV, MTD, AP, issuer or firmware build. Not hardware storage/power-loss acceptance.'},indent=2))
