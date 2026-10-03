"""Run target ash dispatcher with private producer bindings and harmless commands."""
from pathlib import Path
import json, os, subprocess, sys, tempfile
root, source=map(Path,sys.argv[1:]); w=Path(tempfile.mkdtemp(prefix='radio-dispatch-test.'))
classdir=w/'class'; classdir.mkdir(); devices=w/'devices';devices.mkdir(); bus=w/'bus';bus.mkdir();tools=w/'bin';tools.mkdir();log=w/'calls'
def command(n,s):
 p=tools/n;p.write_text('#!/bin/sh\n'+s);p.chmod(0o700)
command('uci','echo "$TEST_ENABLED"\n')
command('timeout','printf "%s\\n" "$*" >> "$TEST_LOG"\nexit "${TEST_RESULT:-0}"\n')
command('logger','printf "LOG %s\\n" "$*" >> "$TEST_LOG"\n')
script=w/'dispatch';script.write_text(source.read_text().replace('/sys/class/devcoredump',str(classdir)).replace('/sys/devices/',str(devices)+'/').replace('/sys/bus/',str(bus)+'/').replace('/var/run/ucentral-radio-crash',str(w/'run')))
checks=0
def check(ok):
 global checks
 assert ok;checks+=1
def run(enabled='1',result='0'):
 log.write_text('');r=subprocess.run(['/usr/bin/qemu-aarch64','-0','ash','-L',str(root),str(root/'bin/busybox'),str(script),'once'],env=dict(os.environ,PATH=str(tools)+':'+os.environ['PATH'],TEST_ENABLED=enabled,TEST_RESULT=result,TEST_LOG=str(log)),capture_output=True,text=True)
 assert r.returncode==0,r.stderr
 return log.read_text()
def producer(name,driver,remote=False):
 d=devices/name;d.mkdir();bind=bus/('platform' if remote else 'pci')/'drivers'/driver;bind.mkdir(parents=True,exist_ok=True)
 if remote:
  r=d/'remoteproc'/'remoteproc0';r.mkdir(parents=True);(d/'driver').symlink_to(bind);sub=bus/'remoteproc';sub.mkdir(exist_ok=True);(r/'subsystem').symlink_to(sub);device=r
 else:(d/'driver').symlink_to(bind);device=d
 p=classdir/name;p.mkdir();(p/'failing_device').symlink_to(device)
producer('devcd0','unreviewed')
check(run()=='' and run('0')=='')
producer('devcd1','ath11k_pci')
check('-k 1 2 /usr/libexec/ucentral-radio-crash-capture devcd1' in run())
producer('devcd2','qcom-wcss-secure-pil',True)
check('devcd2' in run())
producer('devcd3','qcom-q6-mpd',True)
check('devcd3' not in run())
producer('devcd16','qcom-q6v5-wcss-pil',True)
check('devcd16' not in run())
producer('devcdBAD','ath11k_pci')
check('devcdBAD' not in run())
check('spool full' in run(result='5') and run(result='5').count('-k 1 2')==1)
check('insufficient free space' in run(result='6'))
check('original dump retained' in run(result='124'))
for i in range(4,16):producer('devcd'+str(i),'ath11k_pci')
check(run().count('-k 1 2')==8)
print(f'PASS {checks} actual target dispatcher controls; fixture {w}')
