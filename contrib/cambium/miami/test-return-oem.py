#!/usr/bin/env python3
"""Actual rendered helper: missing/unproven return hooks change no boot state.

Callbacks are synthetic interface boundaries, not OEM boot qualification.
"""
from pathlib import Path
import os,subprocess,tempfile
repo=Path(__file__).resolve().parents[3]
text=(repo/'patches-25.12/0164-cambium-ab-miami-certificate-capacity.patch').read_text()
section=text.split('+++ b/package/cambium/cambium-ab/files/cambium-return-oem\n',1)[1]
source=''.join(line[1:]+'\n' for line in section.splitlines() if line.startswith('+'))
with tempfile.TemporaryDirectory(prefix='miami-return-') as td:
 root=Path(td);(root/'system').write_text('')
 core=root/'core';calls=root/'calls'
 core.write_text('''AB_FAMILY=miami
ab_identity(){ [ "${TEST_IDENTITY:-1}" = 1 ]; }
ab_converted(){ [ "${TEST_CONVERTED:-0}" = 1 ]; }
ab_hook(){ command -v "ab_${AB_FAMILY}_$1" >/dev/null 2>&1; }
ab_miami_oem_return_ready(){ [ "${TEST_RETAINED:-1}" = 1 ]; }
ab_setenv(){ echo unexpected-env-write >> "$CALLS";return 1; }
if [ "${TEST_HOOKS:-0}" = 1 ];then
 ab_miami_oem_return_trial_ready(){ echo trial-check >> "$CALLS";[ "${TEST_TRIAL_VALID:-1}" = 1 ]; }
 ab_miami_oem_return_arm_trial(){ echo trial-arm >> "$CALLS";[ "${TEST_ARM_SUCCESS:-1}" = 1 ]; }
fi
''')
 guard=root/'guard';guard.write_text('#!/bin/sh\necho unexpected-guard-stop >> "$CALLS"\n');guard.chmod(0o700)
 helper=root/'helper';helper.write_text(source.replace('/lib/functions/system.sh',str(root/'system')).replace('/lib/functions/cambium-ab.sh',str(core)).replace('/etc/init.d/cambium-ab-guard',str(guard)))
 def run(args,code,want_calls,**extra):
  calls.write_text('')
  p=subprocess.run(['sh',str(helper),*args],env={**os.environ,'CALLS':str(calls),**extra},capture_output=True,text=True)
  assert p.returncode==code and calls.read_text().splitlines()==want_calls,(p.stdout,p.stderr,calls.read_text())
 run(['--check'],0,[])
 run(['--arm'],1,[])
 run(['--arm'],1,[],TEST_IDENTITY='0')
 run(['--arm'],1,[],TEST_RETAINED='0')
 run(['--arm'],1,[],TEST_CONVERTED='1',TEST_HOOKS='1')
 run(['--check'],0,[],TEST_HOOKS='1')
 run(['--arm'],1,['trial-check'],TEST_HOOKS='1',TEST_TRIAL_VALID='0')
 run(['--arm'],1,['trial-check','trial-arm'],TEST_HOOKS='1',TEST_ARM_SUCCESS='0')
 run(['--arm'],0,['trial-check','trial-arm'],TEST_HOOKS='1')
 run([],2,[])
 run(['--arm','extra'],2,[])
 print('PASS: 11 actual helper cases; --check read-only; unsupported arm refuses before guard/ENV side effects; hook simulation is not hardware proof')
