"""Actual ARM ash helper with fixture sysfs: mapping, mutual exclusion and priority."""
from pathlib import Path
import subprocess,tempfile,sys,os
root,source=map(Path,sys.argv[1:3]);work=Path(tempfile.mkdtemp(prefix='led-helper-policy-'));count=0
maps=[('cambiumnetworks,xv3-8','blue:status','green:status',['orange:status','red:status']),('cambiumnetworks,xv2-21x','blue:status','green:status',['orange:status']),('cambium,e410','blue:status','green:status',['amber:status','red:status']),('cambiumnetworks,e410','blue:status','green:status',['amber:status','red:status']),('cambiumnetworks,e410b','blue:status','green:status',['amber:status','red:status']),('cambiumnetworks,xv2-2','jaguar:status:blue','jaguar:status:green',['jaguar:status:orange','jaguar:status:red']),('cambiumnetworks,xv2-2t1','jaguar:status:blue','jaguar:status:green',['jaguar:status:orange','jaguar:status:red']),('cambiumnetworks,xe3-4','jaguar:status:blue','jaguar:status:green',['jaguar:status:orange','jaguar:status:red'])]
def check(ok,name):
 global count
 assert ok,name;count+=1
for i,(board,blue,green,phase) in enumerate(maps):
 d=work/str(i);d.mkdir();led=d/'leds';led.mkdir()
 for name in [blue,green,*phase]:
  p=led/name;p.mkdir();(p/'brightness').write_text('0');(p/'trigger').write_text('[none] timer heartbeat default-on');(p/'max_brightness').write_text('255')
 stub=d/'functions.sh';stub.write_text('board_name() { printf "%s" "$TEST_BOARD"; }\nuci() { printf "%s" "$TEST_OFF"; }\n')
 script=d/'helper.sh';script.write_text(source.read_text().replace('/lib/functions.sh',str(stub)).replace('/sys/class/leds',str(led)).replace('/tmp/ucentral-led-phase',str(d/'phase')))
 def run(op,off='0'):
  env=os.environ.copy();env.update(TEST_BOARD=board,TEST_OFF=off,PHASE_LED_PATHS='/do-not-inherit',RUNNING_LED_PATH='/do-not-inherit')
  return subprocess.run(['/usr/bin/qemu-aarch64','-0','ash','-L',str(root),str(root/'bin/busybox'),str(script),op],env=env,capture_output=True,text=True)
 def val(name,prop='brightness'):return (led/name/prop).read_text().strip()
 def put(name,prop,v):(led/name/prop).write_text(v)
 check(run('managed').returncode==0,board+' mapped');check(run('running').stdout.strip()==green,board+' running node without DT label');check(run('phase').returncode==1,board+' no phase')
 put(green,'brightness','255');put(green,'trigger','none timer [default-on]')
 check(run('on').returncode==0 and val(blue)=='255' and val(green)=='0' and val(green,'trigger')=='none',board+' connected exclusive')
 check(run('off').returncode==0 and val(blue)=='0' and val(green)=='255' and val(green,'trigger')=='none',board+' disconnected steady exclusive')
 check(run('on','1').returncode==0 and val(blue)=='0' and val(green)=='0',board+' global off')
 check(run('on').returncode==0 and val(blue)=='255' and val(green)=='0',board+' global off reversible')
 before={str(p.relative_to(led)):p.read_bytes() for p in led.rglob('*') if p.is_file()};check(run('managed').returncode==0 and before=={str(p.relative_to(led)):p.read_bytes() for p in led.rglob('*') if p.is_file()},board+' read-only capability')
 for ph in phase:
  put(ph,'brightness','255');before=val(ph,'trigger')
  check(run('on').returncode==0 and val(ph)=='255' and val(ph,'trigger')==before and val(blue)=='0' and val(green)=='0',board+' boot flash recovery '+ph)
  put(ph,'brightness','0');put(ph,'trigger','none [heartbeat] timer')
  check(run('off').returncode==0 and val(ph)=='0' and '[heartbeat]' in val(ph,'trigger') and val(blue)=='0' and val(green)=='0',board+' dark part of phase cycle '+ph)
  put(ph,'trigger','none [timer] heartbeat');put(blue,'trigger','none [timer]');put(green,'trigger','none [timer]')
  check(run('on').returncode==0 and '[timer]' in val(blue,'trigger') and '[timer]' in val(green,'trigger'),board+' identify timer priority')
  check(run('disabled').returncode==0 and all(val(n)=='0' and val(n,'trigger')=='none' for n in [blue,green,*phase]),board+' kill beats phase/pattern')
  check(run('on').returncode==0 and val(blue)=='0' and val(green)=='0' and val(ph,'trigger')=='timer',board+' phase ownership survives global off '+ph)
  check(run('phase-done').returncode==0 and run('phase').returncode==1,board+' explicit phase completion '+ph)
 check(run('on').returncode==0,board+' prepattern connected');check(run('pattern').returncode==0 and val(blue)=='0' and val(green)=='0',board+' relinquish before pattern')
 put(green,'trigger','none [timer]');put(green,'brightness','255');check(run('on').returncode==0 and '[timer]' in val(green,'trigger'),board+' repeated update preserves reset pattern')
 check(run('restore-on').returncode==0 and val(blue)=='255' and val(green)=='0' and val(green,'trigger')=='none',board+' reset timeout connected')
 put(green,'trigger','none [timer]');check(run('restore-off').returncode==0 and val(blue)=='0' and val(green)=='255' and val(green,'trigger')=='none',board+' reset timeout disconnected')
 put(phase[0],'trigger','none [timer]');put(green,'trigger','none [timer]')
 check(run('disabled-pattern').returncode==0 and run('on').returncode==0 and val(blue)=='255',board+' cancelled identify does not become boot phase')
 # Explicit diagnostic lifecycle, including the dark interval of a timer.
 put(phase[0],'trigger','none [timer]');put(phase[0],'brightness','0')
 put(phase[0],'delay_on','100');put(phase[0],'delay_off','200')
 check(run('phase-upgrade').returncode==0 and val(blue)=='0' and val(green)=='0',board+' upgrade takes normal colors')
 check(run('on','1').returncode==0 and val(phase[0])=='0' and val(phase[0],'trigger')=='none',board+' upgrade globally suppressed')
 put(phase[0],'delay_on','500');put(phase[0],'delay_off','500')
 check(run('on').returncode==0 and val(blue)=='0' and val(green)=='0' and val(phase[0],'trigger')=='timer' and val(phase[0],'delay_on')=='100' and val(phase[0],'delay_off')=='200',board+' restore timer cadence without ending upgrade')
 check(run('on','1').returncode==0 and run('phase-connect','1').returncode==0 and all(val(n)=='0' for n in [blue,green,*phase]) and run('phase').returncode==1,board+' completion under global off stays dark')
 check(run('off').returncode==0 and val(green)=='255' and val(blue)=='0',board+' disconnected resumes after explicit completion')
 # Missing channels cannot leave stale connected blue; no unqualified sibling enablement.
 (led/green/'max_brightness').unlink();(led/green/'brightness').unlink();(led/green/'trigger').unlink();(led/green).rmdir()
 check(run('off').returncode==0 and val(blue)=='0',board+' missing green clears blue')
 for excluded in ['cambiumnetworks,xv2-22h','cambiumnetworks,e600','cambiumnetworks,xe5-8','example,board']:
  board=excluded;before={str(p.relative_to(led)):p.read_bytes() for p in led.rglob('*') if p.is_file()}
  check(run('managed').returncode==1 and run('on').returncode==0 and before=={str(p.relative_to(led)):p.read_bytes() for p in led.rglob('*') if p.is_file()},excluded+' no guessed mapping')
# Frozen Gambit source behavior only; no hardware acceptance or new phase map.
d=work/'gambit';d.mkdir();led=d/'leds';led.mkdir()
for n in ('green:status','amber:status'):
 p=led/n;p.mkdir();(p/'brightness').write_text('0');(p/'trigger').write_text('none');(p/'max_brightness').write_text('1')
stub=d/'functions.sh';stub.write_text('board_name() { echo cambiumnetworks,e400; }\nuci() { printf "%s" "$TEST_OFF"; }\n')
script=d/'helper.sh';script.write_text(source.read_text().replace('/lib/functions.sh',str(stub)).replace('/sys/class/leds',str(led)).replace('/tmp/ucentral-led-phase',str(d/'phase')))
for op,off,g,a in [('on','0','1','0'),('off','0','0','1'),('on','1','0','0'),('off','1','0','0'),('unknown','0','0','0')]:
 env=os.environ.copy();env['TEST_OFF']=off
 r=subprocess.run(['/usr/bin/qemu-aarch64','-0','ash','-L',str(root),str(root/'bin/busybox'),str(script),op],env=env,capture_output=True,text=True)
 check(r.returncode==0 and (led/'green:status/brightness').read_text().strip()==g and (led/'amber:status/brightness').read_text().strip()==a and all((led/n/'trigger').read_text().strip()=='none' for n in ('green:status','amber:status')),'frozen Gambit '+op+off)
before={str(p):p.read_bytes() for p in led.rglob('*') if p.is_file()};r=subprocess.run(['/usr/bin/qemu-aarch64','-0','ash','-L',str(root),str(root/'bin/busybox'),str(script),'managed'],capture_output=True,text=True);check(r.returncode==1 and before=={str(p):p.read_bytes() for p in led.rglob('*') if p.is_file()},'Gambit keeps generic arbitration')
print('PASS '+str(count)+' actual ARM helper controls across '+str(len(maps))+' qualified board mappings')
