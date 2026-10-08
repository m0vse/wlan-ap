#!/usr/bin/env python3
"""Exercise unsupported Cheetah phases with write/prompt boundaries trapped."""
from pathlib import Path
import os, subprocess, tempfile, json, shlex
adapter=Path(__file__).resolve().parents[1]/'adapters/cheetah.sh'
phases=['inspect','preflight','recovery','migrate']
cases=[]
with tempfile.TemporaryDirectory(prefix='cheetah-adapter-refusal.') as temp:
    root=Path(temp); trace=root/'forbidden'; stdin='SYNTHETIC-PRIVATE-INPUT-DO-NOT-PRINT'
    fixtures=[('exact-model-unqualified','XV2-21X','2','3'),('other-known-model','XV2-22H','2','3'),('other-outdoor-model','XV2-23T','2','3'),('unknown-model','XV2-21X-other','2','3'),('overlapping-unique-ART','XV2-21X','2','2'),('wrong-parent-MTD','XV2-21X','ART','27')]
    for label,model,source,target in fixtures:
        for phase in phases:
            script=root/'driver.sh'
            script.write_text('#!/bin/sh\n. "$1"\nshift\n# Any probe, write, backup, key prompt or boot arm is an error for a disabled model.\nforbidden(){ echo forbidden >> "$TRACE"; return 99; }\nflash_erase(){ forbidden; }; ubiformat(){ forbidden; }; ubiupdatevol(){ forbidden; }\nubirmvol(){ forbidden; }; ubirsvol(){ forbidden; }; ubimkvol(){ forbidden; }\nfw_setenv(){ forbidden; }; fw_printenv(){ forbidden; }; mount(){ forbidden; }\numount(){ forbidden; }; dd(){ forbidden; }; mtd(){ forbidden; }\nread(){ forbidden; }; oem_prompt_key(){ forbidden; }; oem_adapter_backup(){ forbidden; }\nphase="$1"\n"oem_adapter_$phase"\nrc=$?\nif [ "$phase" = inspect ]; then\n [ -z "$OEM_SERIAL$OEM_SOURCE_RELEASE$OEM_SOURCE_SLOT$OEM_TARGET_SLOT" ] || exit 98\nfi\nexit "$rc"\n')
            env={**os.environ,'TRACE':str(trace),'OEM_MODEL':model,'OEM_SERIAL':'stale-serial','OEM_SOURCE_RELEASE':'stale-release','OEM_SOURCE_SLOT':source,'OEM_TARGET_SLOT':target,'OEM_ALLOW_UNQUALIFIED':'1','OEM_FORCE':'1','OEM_BUNDLE':str(root/'wrong-bundle'),'OEM_CONTROLLER':'controller.invalid','OEM_DOWNLOAD_URL':'https://invalid.example/never-fetch'}
            p=subprocess.run(shlex.split(os.environ.get('OEM_TEST_SHELL','sh'))+[str(script),str(adapter),phase],env=env,input=stdin,text=True,capture_output=True)
            assert p.returncode==1,(label,phase,p.returncode,p.stderr)
            assert not trace.exists(),(label,phase)
            assert stdin not in p.stdout+p.stderr
            assert not p.stdout
            cases.append({'fixture':label,'phase':phase,'passed':True})
print(json.dumps({'passed':True,'count':len(cases),'cases':cases,'scope':'Unsupported-model refusal at every ABI phase; no hardware probes, private prompt, writes, backups or boot changes. Overlap/wrong-device requests remain denied, not qualified.'},indent=2))
