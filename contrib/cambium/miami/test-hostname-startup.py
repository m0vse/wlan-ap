#!/usr/bin/env python3
"""Run hostname setup under target ash with the real OpenWrt libraries."""
from pathlib import Path
import sys,subprocess,tempfile,os
root,source=map(Path,sys.argv[1:3])
with tempfile.TemporaryDirectory(prefix='miami-hostname-startup-') as td:
 w=Path(td);calls=w/'calls';script=w/'hostname'
 s=source.read_text().replace('. /lib/functions/system.sh', '''. /lib/functions/system.sh
# Hardware label identity is covered by the separate active-bank context test.
get_mac_label() { printf '%s' "$TEST_MAC"; }
uci() { printf '%s\\n' "$*" >> "$TEST_CALLS"; }
logger() { :; }
''')
 script.write_text(s)
 env=dict(os.environ,TEST_CALLS=str(calls));env.pop('IPKG_INSTROOT',None)
 for mac,ok in [('02:00:00:00:00:01',True),('',False),('bad',False)]:
  calls.write_text('');p=subprocess.run(['/usr/bin/qemu-aarch64','-0','ash','-L',str(root),str(root/'bin/busybox'),str(script)],env=dict(env,TEST_MAC=mac),capture_output=True,text=True)
  assert (p.returncode==0)==ok,(p.returncode,p.stdout,p.stderr)
  if ok:assert calls.read_text().splitlines()==['set system.@system[-1].mac=02:00:00:00:00:01','set system.@system[-1].hostname=020000000001','set ucentral.config.serial=020000000001']
  else:assert calls.read_text()==''
 assert 'set -eu' in source.read_text()
print('PASS: strict actual hostname startup with native libraries/IPKG_INSTROOT absent; valid label sets native serial/hostname; missing/invalid label refuses')
