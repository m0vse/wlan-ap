#!/usr/bin/env python3
"""Verify the actual upload function against the existing cambium-serve.py."""
from pathlib import Path
import os,subprocess,tempfile,socket,time,hashlib,sys,shutil
repo=Path(__file__).resolve().parents[3]
source=(repo/'contrib/cambium/miami/miami-oem-bank-test.sh').read_text()
function=source[source.index('upload_backups() {'):source.index('case "$mode" in\nupload)')]
serve=Path(sys.argv[1]) if len(sys.argv)>1 else repo.parent/'cambium-openwrt-fork/cambium/site/cambium-serve.py'
assert serve.is_file(), 'pass the path to the stock cambium-serve.py'
with tempfile.TemporaryDirectory() as td:
 w=Path(td);web=w/'web';web.mkdir();d=w/'backup';d.mkdir();b=w/'bin';b.mkdir()
 for name,content in [('target-bank.bin',b'\0\xff\x01'*100000),('APPSBLENV.bin',b'\0'*65536),('environment.txt',b'bootcmd=bootipq\n'),('target',b'rootfs\n')]: (d/name).write_bytes(content)
 (d/'SHA256SUMS').write_text(''.join(hashlib.sha256((d/n).read_bytes()).hexdigest()+'  '+n+'\n' for n in ['target-bank.bin','APPSBLENV.bin','environment.txt','target']))
 (b/'wget').write_text('''#!/usr/bin/env python3
import sys,urllib.request,os
from pathlib import Path
if '--help' in sys.argv:print('--post-file --post-data');sys.exit()
a=sys.argv[1:];data=Path(a[a.index('--post-file')+1]).read_bytes() if '--post-file' in a else a[a.index('--post-data')+1].encode()
# Simulate BusyBox's C-string truncation: hex encoding must prevent NUL loss.
data=data.split(bytes([0]))[0]
reply=urllib.request.urlopen(urllib.request.Request(a[-1],data=data)).read().decode()
print('0'*64 if os.environ.get('BAD_REPLY') else reply,end='')
''');(b/'wget').chmod(0o755)
 sh=w/'upload.sh';sh.write_text('set -eu\nfail(){ echo "$*" >&2;exit 1; }\nDIR=$1;SLOT=0\n'+function+'\nupload_backups "$2"\n')
 sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
 server=subprocess.Popen(['python3',str(serve),str(port)],cwd=web,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:
  for i in range(50):
   try:
    s=socket.create_connection(('127.0.0.1',port),timeout=.1);s.close();break
   except OSError:time.sleep(.05)
  env=dict(os.environ,PATH=str(b)+':'+os.environ['PATH'])
  r=subprocess.run(['sh',str(sh),str(d),f'http://127.0.0.1:{port}'],env=env,capture_output=True,text=True)
  assert r.returncode==0,(r.stdout,r.stderr)
  prefix=(d/'upload-prefix').read_text().strip()
  for name in ['target-bank.bin','APPSBLENV.bin','environment.txt','target']:
   assert (web/'uploads'/f'{prefix}-{name}').read_bytes()==(d/name).read_bytes()
  for line in (web/'uploads'/f'{prefix}-SHA256SUMS').read_text().splitlines():
   digest,name=line.split();assert hashlib.sha256((web/'uploads'/name).read_bytes()).hexdigest()==digest
  (d/'uploaded').unlink()
  r=subprocess.run(['sh',str(sh),str(d),f'http://127.0.0.1:{port}'],env=dict(env,BAD_REPLY='1'),capture_output=True,text=True)
  assert r.returncode!=0 and not (d/'uploaded').exists()
  if shutil.which('curl'):
   # Force the real curl whole-file fallback by disabling wget's post support.
   (b/'wget').write_text('#!/bin/sh\necho no-post-support\n')
   r=subprocess.run(['sh',str(sh),str(d),f'http://127.0.0.1:{port}'],env=env,capture_output=True,text=True)
   assert r.returncode==0,(r.stdout,r.stderr)
   for name in ['target-bank.bin','APPSBLENV.bin']:
    assert (web/'uploads'/f'{prefix}-{name}').read_bytes()==(d/name).read_bytes()
  else:print('SKIP: real curl fallback (curl is not installed on this host)')
 finally:server.terminate();server.wait()
print('PASS: actual cambium-serve.py, NUL-containing multi-chunk backups, unique names/manifest, hash-error refusal; curl fallback checked when installed')
