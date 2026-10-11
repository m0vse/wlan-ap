from pathlib import Path
import subprocess,tempfile,time,json,sys,os
source=Path(sys.argv[1]);checks=0
with tempfile.TemporaryDirectory(prefix='dfs-led-collector-') as tmp:
 w=Path(tmp);d=w/'result';fake=w/'fake-collector';fake.write_text('#!/bin/sh\ncase "$MODE" in active) echo \'{"sampled":1,"pending":true}\';; idle) echo \'{"sampled":1,"pending":false}\';; fail) exit 1;; slow) sleep 30;; esac\n');fake.chmod(0o700)
 script=w/'collector';script.write_text(source.read_text().replace('/tmp/ucentral-dfs-led',str(d)).replace('/usr/libexec/timeout-coreutils','/usr/bin/timeout').replace('/usr/bin/ucode /usr/share/ucentral/dfs_led.uc',str(fake)))
 def run(mode):
  global checks
  env=os.environ.copy();env['MODE']=mode;start=time.monotonic();r=subprocess.run(['/bin/sh',str(script)],env=env,capture_output=True,text=True);return r,time.monotonic()-start
 for mode in ('active','idle'):
  r,elapsed=run(mode);assert r.returncode==0 and json.loads((d/'sample.json').read_text())['pending']==(mode=='active');checks+=1
  assert d.stat().st_mode&0o777==0o700 and (d/'sample.json').stat().st_mode&0o777==0o600;checks+=1
 r,elapsed=run('fail');assert r.returncode!=0 and not (d/'sample.json').exists() and not (d/'sample.new').exists();checks+=1
 run('active');r,elapsed=run('slow');assert r.returncode!=0 and 4.5<=elapsed<7 and not (d/'sample.json').exists() and not (d/'sample.new').exists();checks+=1
 d.chmod(0o755);r,elapsed=run('active');assert r.returncode!=0;checks+=1
print(f'PASS {checks} whole-collector timeout/result/permissions controls; no AP operations')
