#!/usr/bin/env python3
"""Registry-complete Cheetah refusal with actual adapters and byte sentinels."""
from pathlib import Path
import os, subprocess, tempfile, json, shlex, hashlib
base=Path(__file__).resolve().parents[1]
fixture=json.loads((Path(__file__).parent/'family-cheetah-fixtures.json').read_text())
registry=Path(os.environ.get('OEM_TEST_MODELS',str(Path(__file__).resolve().parents[2]/'recovery/scripts/cambium-oem-models.tsv')))
registered={row.split('\t')[2] for row in registry.read_text().splitlines() if not row.startswith('#') and len(row.split('\t'))>=3 and row.split('\t')[1]=='cheetah'}
assert registered=={m['model'] for m in fixture['models']}
rows=[('unqualified-valid-model','XV2-21X','0','1'),('other-model','XV2-22H','0','1'),('other-outdoor','XV2-23T','1','0'),('model-conflict','XV2-21X-other','0','1'),('protected-overlap','XV2-21X','0','0'),('wrong-parent-alias','XV2-21X','ART','27')]
rows += [('actual-model-slot-'+str(slot),m['model'],str(slot),str(1-slot)) for m in fixture['models'] for slot in [0,1]]
cases=[]
with tempfile.TemporaryDirectory(prefix='cheetah-adapter-refusal.') as temp:
    root=Path(temp);trace=root/'forbidden';protected=root/'protected';protected.mkdir()
    for role in fixture['protected_byte_roles']:(protected/role).write_bytes(('synthetic-own-'+role).encode())
    def hashes():return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in protected.iterdir()}
    before=hashes();secret='SYNTHETIC-PRIVATE-INPUT-DO-NOT-PRINT'
    for flow in ['forward','restore','upgrade']:
        adapter=base/'adapters'/('restore-cheetah.sh' if flow=='restore' else 'cheetah.sh')
        phases=['boot_preflight'] if flow=='upgrade' else ['inspect','boot_preflight','preflight','recovery','migrate']
        for label,model,source,target in rows:
            for phase in phases:
                script=root/'driver.sh';script.write_text('''#!/bin/sh
. "$1"
shift
forbidden(){ echo forbidden >> "$TRACE"; return 99; }
flash_erase(){ forbidden; }; ubiformat(){ forbidden; }; ubiupdatevol(){ forbidden; }
ubirmvol(){ forbidden; }; ubirsvol(){ forbidden; }; ubimkvol(){ forbidden; }
ubiattach(){ forbidden; }; ubidetach(){ forbidden; }; nandwrite(){ forbidden; }
fw_setenv(){ forbidden; }; fw_printenv(){ forbidden; }; mount(){ forbidden; }
umount(){ forbidden; }; dd(){ forbidden; }; mtd(){ forbidden; }
read(){ forbidden; }; oem_prompt_key(){ forbidden; }; oem_adapter_backup(){ forbidden; }
reboot(){ forbidden; }; jffs2reset(){ forbidden; }; curl(){ forbidden; }; wget(){ forbidden; }
phase="$1"
case "$FLOW" in
forward) "oem_adapter_$phase" ;;
restore) "oem_restore_$phase" ;;
upgrade) "oem_upgrade_$phase" ;;
esac
rc=$?
if [ "$phase" = inspect ]; then
 [ -z "$OEM_SERIAL$OEM_SOURCE_RELEASE$OEM_SOURCE_SLOT$OEM_TARGET_SLOT" ] || exit 98
fi
if [ "$phase" = boot_preflight ]; then
 [ -z "$OEM_BOOT_PRIOR_SLOT$OEM_BOOT_TARGET_SLOT$OEM_BOOT_MODE$OEM_BOOT_WATCHDOG" ] || exit 97
fi
exit "$rc"
''')
                env={**os.environ,'TRACE':str(trace),'FLOW':flow,'OEM_MODEL':model,'OEM_SERIAL':'stale','OEM_SOURCE_RELEASE':'unqualified-new-version','OEM_SOURCE_SLOT':source,'OEM_TARGET_SLOT':target,'OEM_BOOT_PRIOR_SLOT':source,'OEM_BOOT_TARGET_SLOT':target,'OEM_BOOT_MODE':'persist-prior-before-load','OEM_BOOT_WATCHDOG':'verified','OEM_FORCE':'1','OEM_ALLOW_UNQUALIFIED':'1','OEM_BUNDLE':str(root/'wrong-bundle')}
                p=subprocess.run(shlex.split(os.environ.get('OEM_TEST_SHELL','sh'))+[str(script),str(adapter),phase],env=env,input=secret,text=True,capture_output=True)
                assert p.returncode==1,(flow,label,phase,p.returncode,p.stderr)
                assert not trace.exists(),(flow,label,phase)
                assert hashes()==before and secret not in p.stdout+p.stderr and not p.stdout
                cases.append({'flow':flow,'fixture':label,'model':model,'phase':phase,'passed':True})
print(json.dumps({'passed':True,'count':len(cases),'registry_models':sorted(registered),'protected_bytes_unchanged':True,'cases':cases,'writer_checkpoints':'Full launcher migration/restore remain disabled before writes; separate component and rendered-command tests exercise implemented source operations. No positive full migration or physical power-loss claim.','scope':'Actual assigned adapters under host/selected shell with per-model source/target contexts and synthetic protected-byte sentinels; no device, network, prompt or persistent writes.'},indent=2))
