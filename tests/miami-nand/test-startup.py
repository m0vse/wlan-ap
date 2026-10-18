#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import tempfile,subprocess,os,argparse
parser=argparse.ArgumentParser();parser.add_argument('--baseline-launcher',type=Path,required=True);args=parser.parse_args()
repo=Path(__file__).resolve().parents[2];new=(repo/'feeds/tip/cambium-miami-capture/files/miami-capture-launch').read_text();old=args.baseline_launcher.read_text()
with tempfile.TemporaryDirectory(prefix='miami-startup-') as temp:
 d=Path(temp);bin=d/'bin';bin.mkdir()
 def executable(path,text):path.write_text(text);path.chmod(0o700)
 executable(bin/'ip','#!/bin/sh\necho "    inet 192.0.2.10/24 brd 192.0.2.255 scope global up0v0"\n')
 executable(bin/'cat','#!/bin/sh\ncase "$1" in /sys/class/net/up0v0/operstate) echo up;; *) /bin/cat "$@";; esac\n')
 executable(bin/'sleep','#!/bin/sh\nexit 0\n')
 executable(bin/'logger','#!/bin/sh\nprintf "%s\\n" "$*" >> "$TEST_DIR/log"\n')
 lib=d/'functions';lib.write_text('config_load() { return 0; }\nconfig_get() { case "$1" in enabled) enabled=$TEST_ENABLED;;remote_ip) remote_ip=192.0.2.20;;remote_mac) remote_mac=02:00:00:00:00:20;;remote_port) remote_port=6666;;esac; }\n')
 helper=d/'setup';executable(helper,'#!/bin/sh\nn=0; [ ! -f "$TEST_DIR/count" ] || n=$(/bin/cat "$TEST_DIR/count"); n=$((n+1)); echo "$n" > "$TEST_DIR/count"\n[ "$n" -gt "$TEST_FAILURES" ]\n')
 binary=d/'binary';executable(binary,'#!/bin/sh\necho WATCHER_STARTED\n')
 for label,source,failures,enabled,want,attempts in [('old-readiness-negative',old,2,1,1,1),('late-full-readiness',new,2,1,0,3),('bounded-unavailable',new,99,1,1,60),('disabled',new,0,0,0,0)]:
  for name in ['count','log']:
   if(d/name).exists():(d/name).unlink()
  script=source.replace('. /lib/functions.sh','. '+str(lib)).replace('/usr/libexec/miami-netconsole-setup',str(helper)).replace('/usr/libexec/miami-capture-monitor',str(binary)).replace('/tmp/miami-capture',str(d/'ram'))
  run=d/'launch';run.write_text(script);p=subprocess.run(['sh',str(run)],env={**os.environ,'PATH':str(bin)+':'+os.environ['PATH'],'TEST_DIR':str(d),'TEST_FAILURES':str(failures),'TEST_ENABLED':str(enabled)},capture_output=True,text=True)
  assert p.returncode==want,(label,p.returncode,p.stderr)
  count=int((d/'count').read_text())if(d/'count').exists()else 0;assert count==attempts,(label,count)
  assert ('WATCHER_STARTED'in p.stdout)==(label=='late-full-readiness'),(label,p.stdout)
  if label=='bounded-unavailable':assert 'ERROR:'in(d/'log').read_text()
  print('PASS',label,'setup attempts',count,'exit',p.returncode)
