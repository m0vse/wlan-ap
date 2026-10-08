#!/usr/bin/env python3
"""Execute the actual RAM-aware stock crash monitor against synthetic sysfs."""
from pathlib import Path
import tempfile,subprocess,os,shutil
repo=Path(__file__).resolve().parents[3]
src=(repo/'feeds/tip/cambium-miami-radio/files/miami-wifi-profile').read_text()
with tempfile.TemporaryDirectory(prefix='miami-profile-monitor-') as td:
 w=Path(td);(w/'bin').mkdir();(w/'lock').mkdir();(w/'pci/ieee80211').mkdir(parents=True)
 (w/'system.sh').write_text('board_name(){ echo "${MOCK_BOARD:-cambiumnetworks,x7-35x}"; }\n')
 for name,body in [('logger','exit 0'),('sync','exit 0'),('sleep','exit 0'),('dmesg','echo "0001:01:00.0 ${MOCK_CRASH:-normal boot}"')]:
  p=w/'bin'/name;p.write_text('#!/bin/sh\n'+body+'\n');p.chmod(0o755)
 if not shutil.which('flock'):
  p=w/'bin/flock';p.write_text('#!/bin/sh\nexit 0\n');p.chmod(0o755)
 script=w/'monitor';script.write_text(src.replace('/lib/functions/system.sh',str(w/'system.sh')).replace('/var/lock/',str(w/'lock')+'/').replace('/dev/kmsg',str(w/'kmsg')).replace('/tmp/miami-wifi-profile.request',str(w/'request')))
 # Retain exact PCI BDF for the dmesg selector.
 (w/'pci').rename(w/'0001:01:00.0');pci=w/'0001:01:00.0'
 env=dict(os.environ,PATH=str(w/'bin')+':'+os.environ['PATH'],MIAMI_WIFI_PCI=str(pci),MIAMI_WIFI_CONF=str(w/'modules.conf'),MIAMI_WIFI_PARAM=str(w/'param'),CAMBIUM_BDF_STATUS=str(w/'status'),MIAMI_WIFI_WAIT='1')
 cases=[('', 'auto','vault','',True,False,True),('options ath12k mem_profile=auto\n','auto','vault','',True,False,False),('', 'low','vault','',True,False,False),('', 'auto','missing','',True,False,False),('', 'auto','vault','held',True,False,False),('', 'auto','vault','',False,False,False),('', 'auto','vault','',True,True,False)]
 for conf,param,status,override,crash,phy,expected in cases:
  (w/'modules.conf').write_text(conf);(w/'param').write_text(param);(w/'status').write_text(status);(pci/'driver_override').write_text(override)
  (w/'request').unlink(missing_ok=True)
  for p in (pci/'ieee80211').iterdir():p.rmdir()
  if phy:(pci/'ieee80211/phy1').mkdir()
  r=subprocess.run(['sh',str(script)],env=dict(env,MOCK_CRASH='firmware crashed' if crash else 'normal boot'),capture_output=True,text=True)
  assert r.returncode==0,r.stderr
  assert (w/'request').exists()==expected
  assert ('mem_profile=low' in (w/'modules.conf').read_text())==expected
  if expected:
   before=(w/'modules.conf').read_text();subprocess.run(['sh',str(script)],env=env,check=True);assert (w/'modules.conf').read_text()==before
print('PASS: crash fallback in RAM, manual options, low/held/unstaged/healthy/no-crash skips, and idempotence; no reload or reboot')
