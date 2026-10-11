"""Actual ARM ash helper with fixture sysfs: mapping, mutual exclusion and priority."""
from pathlib import Path
import subprocess,tempfile,sys,os
root,source=map(Path,sys.argv[1:3]);work=Path(tempfile.mkdtemp(prefix='led-helper-policy-'));count=0
maps=[('cambiumnetworks,x7-35x','blue:status','green:status',['orange:status','red:status']),('cambiumnetworks,xv3-8','blue:status','green:status',['orange:status','red:status']),('cambiumnetworks,xv2-21x','blue:status','green:status',['orange:status']),('cambium,e410','blue:status','green:status',['amber:status','red:status']),('cambiumnetworks,e410','blue:status','green:status',['amber:status','red:status']),('cambiumnetworks,e410b','blue:status','green:status',['amber:status','red:status']),('cambiumnetworks,xv2-2','jaguar:status:blue','jaguar:status:green',['jaguar:status:orange','jaguar:status:red']),('cambiumnetworks,xv2-2t1','jaguar:status:blue','jaguar:status:green',['jaguar:status:orange','jaguar:status:red']),('cambiumnetworks,xe3-4','jaguar:status:blue','jaguar:status:green',['jaguar:status:orange','jaguar:status:red'])]
def check(ok,name):
 global count
 assert ok,name;count+=1
for i,(board,blue,green,phase) in enumerate(maps):
 d=work/str(i);d.mkdir();(d/'faults').mkdir(mode=0o700);led=d/'leds';led.mkdir()
 for name in [blue,green,*phase]:
  p=led/name;p.mkdir();(p/'brightness').write_text('0');(p/'trigger').write_text('[none] timer heartbeat default-on');(p/'max_brightness').write_text('255')
 stub=d/'functions.sh';stub.write_text('board_name() { printf "%s" "$TEST_BOARD"; }\nuci() { printf "%s" "$TEST_OFF"; }\n')
 script=d/'helper.sh';script.write_text(source.read_text().replace('/lib/functions.sh',str(stub)).replace('/sys/class/leds',str(led)).replace('/tmp/ucentral-led-phase',str(d/'phase')).replace('/tmp/ucentral-faults',str(d/'faults')))
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
 # Actual helper fault output and recovery, before missing-channel tests.
 check(run('fault-supported').returncode==0,board+' fault capability')
 check(run('fault-orange').returncode==0 and val(phase[0])=='255' and val(blue)=='0' and val(green)=='0',board+' fault orange/amber exclusive')
 check(run('phase').returncode==1,board+' owned fault is not boot phase')
 check(run('fault-blue').returncode==0 and val(blue)=='255' and val(phase[0])=='0',board+' alternating blue')
 check(run('fault-clear').returncode==0 and val(phase[0])=='0' and run('restore-on').returncode==0 and val(blue)=='255',board+' recovery restores connected')
 check(run('fault-orange','1').returncode==0 and all(val(n)=='0' for n in [blue,green,*phase]),board+' global off suppresses fault')
 put(phase[0],'trigger','none [timer]');put(phase[0],'brightness','0');run('phase-upgrade')
 before={str(p):p.read_bytes() for p in led.rglob('*') if p.is_file()}
 check(run('fault-orange').returncode==0 and before=={str(p):p.read_bytes() for p in led.rglob('*') if p.is_file()},board+' upgrade outranks fault')
 run('phase-done');put(green,'trigger','none [timer]');before=val(green,'trigger')
 check(run('fault-orange').returncode==0 and val(green,'trigger')==before and val(phase[0])=='0',board+' identify outranks fault')
 run('restore-on')
 # Owned DFS timer, color and priority through the actual ARM helper.
 run('restore-on')
 check(run('dfs-on').returncode==0 and val(blue,'trigger')=='timer' and val(blue,'delay_on')=='1900' and val(blue,'delay_off')=='100' and val(green)=='0',board+' positive CAC connected blue wink')
 before={str(p):p.read_bytes() for p in led.rglob('*') if p.is_file()}
 check(run('dfs-on').returncode==0 and before=={str(p):p.read_bytes() for p in led.rglob('*') if p.is_file()},board+' repeated CAC preserves cadence')
 check(run('restore-dfs-on').returncode==0 and before=={str(p):p.read_bytes() for p in led.rglob('*') if p.is_file()},board+' restoration refresh preserves owned cadence')
 check(run('dfs-off').returncode==0 and val(green,'trigger')=='timer' and val(green,'delay_on')=='1900' and val(green,'delay_off')=='100' and val(blue)=='0',board+' CAC disconnected green wink')
 check(run('off').returncode==0 and val(green,'trigger')=='none' and val(green)=='255' and not (d/'faults/dfs-led-owner').exists(),board+' CAC end restores steady color')
 run('dfs-on');check(run('fault-orange').returncode==0 and val(phase[0])=='255' and val(blue)=='0' and val(blue,'trigger')=='none',board+' critical fault interrupts DFS timer')
 before={str(p):p.read_bytes() for p in led.rglob('*') if p.is_file()}
 check(run('dfs-on').returncode==0 and before=={str(p):p.read_bytes() for p in led.rglob('*') if p.is_file()},board+' owned critical fault outranks DFS')
 check(run('restore-dfs-on').returncode==0 and run('restore-dfs-off').returncode==0 and before=={str(p):p.read_bytes() for p in led.rglob('*') if p.is_file()},board+' owned fault outranks restoring DFS')
 run('fault-clear');run('dfs-on');check(run('pattern').returncode==0 and val(blue,'trigger')=='none' and not (d/'faults/dfs-led-owner').exists(),board+' identify clears DFS ownership')
 put(green,'trigger','none [timer]');put(green,'delay_on','100');put(green,'delay_off','100')
 check(run('dfs-on').returncode==0 and '[timer]' in val(green,'trigger') and val(green,'delay_on')=='100' and val(blue)=='0',board+' identify timer outranks DFS')
 run('restore-on');run('dfs-on');check(run('disabled','1').returncode==0 and all(val(n)=='0' for n in [blue,green,*phase]) and not (d/'faults/dfs-led-owner').exists(),board+' global off clears DFS timer')
 run('dfs-on');put(phase[0],'trigger','timer');put(phase[0],'delay_on','200');put(phase[0],'delay_off','200')
 check(run('phase-upgrade').returncode==0 and not (d/'faults/dfs-led-owner').exists() and val(blue)=='0',board+' phase interrupts DFS')
 before={str(p):p.read_bytes() for p in led.rglob('*') if p.is_file()}
 check(run('dfs-on').returncode==0 and before=={str(p):p.read_bytes() for p in led.rglob('*') if p.is_file()},board+' phase outranks DFS')
 run('phase-done');run('restore-on')
 # Missing channels cannot leave stale connected blue; no unqualified sibling enablement.
 [(led/green/prop).unlink(missing_ok=True) for prop in ('max_brightness','brightness','trigger','delay_on','delay_off')];(led/green).rmdir()
 check(run('off').returncode==0 and val(blue)=='0',board+' missing green clears blue')
 for excluded in ['cambiumnetworks,xv2-22h','cambiumnetworks,e600','cambiumnetworks,xe5-8','example,board']:
  board=excluded;before={str(p.relative_to(led)):p.read_bytes() for p in led.rglob('*') if p.is_file()}
  check(run('managed').returncode==1 and run('on').returncode==0 and before=={str(p.relative_to(led)):p.read_bytes() for p in led.rglob('*') if p.is_file()},excluded+' no guessed mapping')
# Frozen Gambit source behavior only; no hardware acceptance or new phase map.
d=work/'gambit';d.mkdir();(d/'faults').mkdir(mode=0o700);led=d/'leds';led.mkdir()
for n in ('green:status','amber:status'):
 p=led/n;p.mkdir();(p/'brightness').write_text('0');(p/'trigger').write_text('none');(p/'max_brightness').write_text('1')
stub=d/'functions.sh';stub.write_text('board_name() { echo cambiumnetworks,e400; }\nuci() { printf "%s" "$TEST_OFF"; }\n')
script=d/'helper.sh';script.write_text(source.read_text().replace('/lib/functions.sh',str(stub)).replace('/sys/class/leds',str(led)).replace('/tmp/ucentral-led-phase',str(d/'phase')).replace('/tmp/ucentral-faults',str(d/'faults')))
for op,off,g,a in [('on','0','1','0'),('off','0','0','1'),('on','1','0','0'),('off','1','0','0'),('unknown','0','0','0')]:
 env=os.environ.copy();env['TEST_OFF']=off
 r=subprocess.run(['/usr/bin/qemu-aarch64','-0','ash','-L',str(root),str(root/'bin/busybox'),str(script),op],env=env,capture_output=True,text=True)
 check(r.returncode==0 and (led/'green:status/brightness').read_text().strip()==g and (led/'amber:status/brightness').read_text().strip()==a and all((led/n/'trigger').read_text().strip()=='none' for n in ('green:status','amber:status')),'frozen Gambit '+op+off)
before={str(p):p.read_bytes() for p in led.rglob('*') if p.is_file()};r=subprocess.run(['/usr/bin/qemu-aarch64','-0','ash','-L',str(root),str(root/'bin/busybox'),str(script),'managed'],capture_output=True,text=True);check(r.returncode==0 and before=={str(p):p.read_bytes() for p in led.rglob('*') if p.is_file()},'Gambit joins common arbitration')
print('PASS '+str(count)+' actual ARM helper controls across '+str(len(maps))+' qualified board mappings')

def grun(op,off='0'):
 env=os.environ.copy();env['TEST_OFF']=off
 return subprocess.run(['/usr/bin/qemu-aarch64','-0','ash','-L',str(root),str(root/'bin/busybox'),str(script),op],env=env,capture_output=True,text=True)
def gv(c,p='brightness'):return (led/(c+':status')/p).read_text().strip()
def gp(c,p,v):(led/(c+':status')/p).write_text(v)
check(grun('fault-supported').returncode==0,'Gambit existing pair fault support')
check(grun('fault-orange').returncode==0 and gv('green')=='0' and gv('amber')=='1','Gambit amber fault')
check(grun('fault-blue').returncode==0 and gv('green')=='0' and gv('amber')=='0','Gambit alternate dark, no invented blue')
check(grun('fault-clear').returncode==0 and grun('restore-on').returncode==0 and gv('green')=='1' and gv('amber')=='0','Gambit fault clear restores connected green')
check(grun('restore-off').returncode==0 and gv('green')=='0' and gv('amber')=='1','Gambit restore disconnected amber')
gr=grun('pattern');gp('green','trigger','none [timer]');gp('green','brightness','1')
check(gr.returncode==0 and grun('phase').returncode==1 and grun('fault-orange').returncode==0 and gv('green','trigger')=='none [timer]','Gambit identify owns timer')
check(grun('restore-on').returncode==0 and gv('green')=='1' and gv('green','trigger')=='none','Gambit identify timeout restores')
gp('green','trigger','none [timer]');gp('green','delay_on','100');gp('green','delay_off','200')
check(grun('phase-upgrade').returncode==0 and gv('green','trigger')=='none [timer]','Gambit shared-channel upgrade keeps timer')
check(grun('fault-orange').returncode==0 and gv('green','trigger')=='none [timer]' and gv('amber')=='0','Gambit upgrade outranks fault')
check(grun('on','1').returncode==0 and gv('green')=='0' and gv('amber')=='0','Gambit global off suppresses phase')
check(grun('on').returncode==0 and gv('green','trigger')=='timer' and gv('green','delay_on')=='100' and gv('green','delay_off')=='200','Gambit phase restored after global off')
check(grun('phase-done').returncode==0 and grun('restore-off').returncode==0 and gv('amber')=='1' and gv('green')=='0','Gambit phase completion restores disconnected')
grun('restore-on');check(grun('dfs-on').returncode==0 and gv('green','trigger')=='timer' and gv('green','delay_on')=='1900' and gv('green','delay_off')=='100','Gambit keeps connected green while CAC')
check(grun('restore-dfs-on').returncode==0 and gv('green','trigger')=='timer','Gambit restore preserves own timer')
check(grun('dfs-off').returncode==0 and gv('amber','trigger')=='timer' and gv('green')=='0','Gambit keeps disconnected amber while CAC')
check(grun('fault-orange').returncode==0 and gv('amber','trigger')=='none' and gv('amber')=='1','Gambit critical interrupts DFS')
gr_before={str(p):p.read_bytes() for p in led.rglob('*') if p.is_file()}
check(grun('restore-dfs-on').returncode==0 and gr_before=={str(p):p.read_bytes() for p in led.rglob('*') if p.is_file()},'Gambit fault outranks restoring DFS')
grun('fault-clear');grun('restore-on')
(led/'amber:status').rename(led/'amber-missing')
check(grun('fault-supported').returncode==1,'Gambit missing channels unavailable')
print('PASS Gambit common phase/identify/clear/global-off controls; total '+str(count))
