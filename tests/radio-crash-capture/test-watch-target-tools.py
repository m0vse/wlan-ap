"""Watch startup closure using target executables; never host PATH providers.

Run as root: ROOT PROVIDER_DIRECTORY DISPATCHER. PROVIDER_DIRECTORY must
contain actual target stat, flock and timeout binaries from the candidate.
Absent providers fail this check; frozen roots are not silently substituted.
"""
from pathlib import Path
import os, shlex, subprocess, sys, tempfile
root, providers, source=map(Path,sys.argv[1:])
assert os.geteuid()==0, 'Use root-owned private fixtures'
work=Path(tempfile.mkdtemp(prefix='radio-watch-closure.')); commands=work/'bin';commands.mkdir()
config=work/'config';config.mkdir();classdir=work/'class';classdir.mkdir();run=work/'run'
qemu=os.environ.get('TEST_QEMU','/usr/bin/qemu-aarch64')
q=[qemu,'-L',str(root)]
def wrapper(name, argv):
 p=commands/name;p.write_text('#!/bin/sh\nexec '+shlex.join(argv)+' "$@"\n');p.chmod(0o700)
for name in ['stat','flock','timeout']:
 p=providers/name
 assert p.is_file() and p.read_bytes()[:4]==b'\x7fELF', f'missing actual target provider: {p}'
 wrapper(name,q+[str(p)])
for name in ['mkdir','readlink','rm','rmdir','sleep']:
 wrapper(name,q+[str(root/'bin/busybox'),name])
wrapper('uci',q+[str(root/'sbin/uci'),'-c',str(config)])
script=work/'dispatch'
text=source.read_text().replace('/sys/class/devcoredump',str(classdir)).replace('/var/run/ucentral-radio-crash',str(run))
assert text.count('sleep 2')==1
# One empty scan proves startup tools without leaving an unattended watcher.
script.write_text(text.replace('sleep 2','break'))
checks=0
def invoke(enabled):
 (config/'radio-crash').write_text("config capture 'main'\n option enabled '"+enabled+"'\n")
 return subprocess.run(q+['-0','ash',str(root/'bin/busybox'),str(script),'watch'],env=dict(os.environ,PATH=str(commands)),capture_output=True,text=True,timeout=10)
def check(ok):
 global checks
 assert ok;checks+=1
r=invoke('0');check(r.returncode==0 and not run.exists())
r=invoke('1');check(r.returncode==0);check(run.is_dir() and (run/'.lock').exists() is False and (run/'worker.lock').is_file())
check(run.stat().st_mode&0o777==0o700)
r=invoke('1');check(r.returncode==0) # Retained run directory does not break restart.
run.chmod(0o755);r=invoke('1');check(r.returncode!=0);run.chmod(0o700)
# Verify timeout is the target provider even though this empty scan needs none.
r=subprocess.run(q+[str(providers/'timeout'),'--version'],capture_output=True,text=True);check(r.returncode==0)
print(f'PASS {checks} target-only watch/provider closure controls; fixture {work}')
