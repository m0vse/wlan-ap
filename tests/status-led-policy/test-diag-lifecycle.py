"""Exercise the patched real diagnostic lifecycle with the actual target ash/helper."""
from pathlib import Path
import os,subprocess,sys,tempfile
root,source,patch=map(Path,sys.argv[1:4]);d=Path(tempfile.mkdtemp(prefix='diag-led-phase-'))
target=d/'package/base-files/files/etc/diag.sh';target.parent.mkdir(parents=True);target.write_bytes((root/'etc/diag.sh').read_bytes())
subprocess.run(['patch','--fuzz=0','-p1','-d',str(d),'-i',str(patch.resolve())],check=True,capture_output=True)
led=d/'leds';led.mkdir()
for name in ['blue:status','green:status','orange:status','red:status']:
 p=led/name;p.mkdir()
 for prop,v in [('trigger','none'),('brightness','0'),('max_brightness','255'),('delay_on','0'),('delay_off','0')]: (p/prop).write_text(v)
f=d/'functions.sh';f.write_text('board_name() { echo cambiumnetworks,xv3-8; }\nuci() { echo "$TEST_OFF"; }\n')
helper=d/'helper';helper.write_text(source.read_text().replace('/lib/functions.sh',str(f)).replace('/sys/class/leds',str(led)).replace('/tmp/ucentral-led-phase',str(d/'phase')))
q=['/usr/bin/qemu-aarch64','-0','ash','-L',str(root),str(root/'bin/busybox')]
# The real diagnostic shell invokes the helper through a harmless test wrapper.
import shlex
wrapper=d/'invoke-helper';wrapper.write_text('#!/bin/sh\nexec '+shlex.join(q+[str(helper)])+' "$@"\n');wrapper.chmod(0o700)
lib=d/'leds.sh';lib.write_text('''get_dt_led() { case "$1" in boot|upgrade) echo orange:status ;; failsafe) echo red:status ;; running) echo green:status ;; esac; }
status_led_off() { echo none > "$TEST_LEDS/$status_led/trigger"; echo 0 > "$TEST_LEDS/$status_led/brightness"; }
status_led_on() { echo 255 > "$TEST_LEDS/$status_led/brightness"; }
status_led_restore_trigger() { :; }
status_led_set_heartbeat() { echo heartbeat > "$TEST_LEDS/$status_led/trigger"; }
status_led_blink_preinit() { echo timer > "$TEST_LEDS/$status_led/trigger"; echo 255 > "$TEST_LEDS/$status_led/brightness"; }
status_led_blink_preinit_regular() { status_led_blink_preinit; }
status_led_blink_failsafe() { status_led_blink_preinit; }
''')
script=d/'diag';script.write_text(target.read_text().replace('/lib/functions/leds.sh',str(lib)).replace('/usr/libexec/ucentral-led.sh',str(wrapper))+'\nset_state "$1"\n')
def run(file,op,off='0'):
 r=subprocess.run(q+[str(file),op],env=dict(os.environ,TEST_OFF=off,TEST_LEDS=str(led)),capture_output=True,text=True);assert r.returncode==0,r.stderr
count=0
def check(ok):
 global count
 assert ok;count+=1
def val(n,p='brightness'):return (led/n/p).read_text().strip()
for phase in ['preinit','preinit_regular','failsafe','upgrade','reboot']:
 run(script,phase)
 check((d/'phase').is_dir())
 run(helper,'on','1');check(all(val(n)=='0' for n in ['blue:status','green:status','orange:status','red:status']))
 run(helper,'on');check(val('blue:status')=='0' and val('green:status')=='0')
 run(script,'connect','1');check(not (d/'phase').exists() and val('green:status')=='0')
 run(helper,'on');check(val('blue:status')=='255' and val('green:status')=='0')
run(script,'upgrade');run(script,'done');run(helper,'off');check(val('blue:status')=='0' and val('green:status')=='255' and not (d/'phase').exists())
print(f'PASS {count} actual diagnostic lifecycle integration controls')
