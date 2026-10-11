#!/usr/bin/env python3
"""Cheetah mapping/profile contract and actual shared LED helper in fake sysfs."""
from pathlib import Path
import os,json,tempfile,subprocess,shlex,hashlib
here=Path(__file__).resolve().parent;source=Path(os.environ.get('CHEETAH_LED_SOURCE',str(here.parents[1]/'feeds/ucentral/ucentral-client/files/usr/libexec/ucentral-led.sh')));shell=shlex.split(os.environ.get('OEM_TEST_SHELL','sh'));cases=[]
profile=json.loads(Path(os.environ.get('CHEETAH_PROFILE_SOURCE',str(here.parents[1]/'feeds/ucentral/ucentral-state/files/storage-canary.json'))).read_text());assert 'cambiumnetworks,xv2-21x' in profile and len(profile['cambiumnetworks,xv2-21x'])==2
for spec,name in zip(profile['cambiumnetworks,xv2-21x'],['rootfs','rootfs_1']):
 assert spec['name']==name and spec['size']==100663296 and spec['erase']==131072
 points=list(map(int,spec['samples'].split(',')));assert len(set(points))==len(points)<=8 and all(0<=p<768 for p in points)
 cases.append({'case':'bounded known-bank profile '+name,'passed':True})
with tempfile.TemporaryDirectory(prefix='cheetah-fault-led.') as td:
 w=Path(td).resolve();led=w/'leds';led.mkdir();fault=w/'faults';fault.mkdir(mode=0o700)
 for name in ['blue:status','green:status','orange:status']:
  p=led/name;p.mkdir();(p/'brightness').write_text('0');(p/'max_brightness').write_text('1');(p/'trigger').write_text('none')
 funcs=w/'functions';funcs.write_text('board_name(){ printf "%s" "$TEST_BOARD"; }\nuci(){ printf "%s" "$TEST_OFF"; }\n'+('stat(){ case "$2" in %u) /usr/bin/stat -f %u "$3";; %a) /usr/bin/stat -f %Lp "$3";;esac; }\n' if os.uname().sysname=='Darwin' else ''))
 helper=w/'helper';helper.write_text(source.read_text().replace('/lib/functions.sh',str(funcs)).replace('/sys/class/leds',str(led)).replace('/tmp/ucentral-led-phase',str(w/'phase')).replace('/tmp/ucentral-faults',str(fault)))
 def run(op,off='0',board='cambiumnetworks,xv2-21x'):
  p=subprocess.run(shell+[str(helper),op],env={**os.environ,'TEST_BOARD':board,'TEST_OFF':off},text=True,capture_output=True);assert p.returncode==0,(op,p.returncode,p.stderr)
 def value(c):return (led/(c+':status')/'brightness').read_text().strip()
 def values():return [value(c) for c in ['blue','green','orange']]
 def check(ok,name):assert ok,name;cases.append({'case':name,'passed':True})
 run('fault-supported');check(True,'existing mapped blue/orange capability')
 run('fault-blue');check(values()==['1','0','0'],'fault blue exclusive')
 run('fault-orange');check(values()==['0','0','1'],'fault orange exclusive')
 run('fault-blue');check(values()==['1','0','0'],'orange fault ownership does not become boot phase')
 run('fault-clear');run('off');check(values()==['0','1','0'],'recovery restores disconnected green')
 run('fault-blue','1');check(values()==['0','0','0'],'global off suppresses fault channels')
 run('fault-orange','1');check(values()==['0','0','0'],'global off remains reversible and dark')
 run('on');check(values()==['1','0','0'],'connected display resumes after suppression')
 (led/'orange:status'/'brightness').write_text('1');(led/'orange:status'/'trigger').write_text('timer\n');(led/'orange:status'/'delay_on').write_text('100');(led/'orange:status'/'delay_off').write_text('200')
 run('phase-upgrade');before={str(p):p.read_bytes() for p in led.rglob('*') if p.is_file()};run('fault-blue');check(before=={str(p):p.read_bytes() for p in led.rglob('*') if p.is_file()},'upgrade phase retains priority')
 run('phase-done');run('off');(led/'blue:status'/'trigger').write_text('none [timer] heartbeat\n');before={str(p):p.read_bytes() for p in led.rglob('*') if p.is_file()};run('fault-orange');check(before=={str(p):p.read_bytes() for p in led.rglob('*') if p.is_file()},'identify timer retains priority')
 before={str(p):p.read_bytes() for p in led.rglob('*') if p.is_file()};run('fault-blue',board='cambiumnetworks,xv2-22h');check(before=={str(p):p.read_bytes() for p in led.rglob('*') if p.is_file()},'unqualified sibling gets no guessed LED mapping')
print(json.dumps({'passed':True,'count':len(cases),'cases':cases,'tested_helper_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'scope':'Actual shared helper with Cheetah sysfs fixtures and bounded profile contract. No GPIO or AP writes, firmware build or hardware acceptance.'},indent=2))
