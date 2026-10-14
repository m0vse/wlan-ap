#!/usr/bin/env python3
"""Actual native MLO telemetry regressions, prepared schema must precede104/105/106."""
from pathlib import Path
import shutil,subprocess,sys,tempfile
repo,baseline,runtime=map(lambda s:Path(s).resolve(),sys.argv[1:]);tests=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='native-mlo-telemetry-') as temp:
 w=Path(temp);source=w/'source'
 for name in ('system','renderer'):shutil.copytree(baseline/name,source/name)
 shutil.copy2(source/'system/state/wifi.uc',w/'wifi.uc');shutil.copy2(source/'renderer/wifi/station.uc',w/'station.uc')
 for patch in ('104-authoritative-per-link-mlo-health.patch','105-native-mlo-radio-and-peer-telemetry.patch','106-native-mlo-average-rssi.patch','107-verify-operating-channel-width-and-power.patch'):
  subprocess.run(['patch','-p1','--fuzz=0','-i',str(repo/'feeds/ucentral/ucentral-schema/patches'/patch)],cwd=source,check=True)
 shutil.copy2(source/'system/state/wifi.uc',w/'wifi-fixed.uc');shutil.copy2(source/'renderer/wifi/station.uc',w/'station-fixed.uc')
 modules=w/'modules';modules.mkdir()
 for name in ('mlo_health.uc','mlo_telemetry.uc'):shutil.copy2(source/'system'/name,modules/name)
 owned=repo/'feeds/ucentral/ucentral-schema/files/usr/share/ucentral/wifi/station_authorization.uc'
 assert owned.is_file(),owned;shutil.copy2(owned,w/'station_authorization.uc')
 for name in ('test-native-peer.py','test-native-telemetry.py'):shutil.copy2(tests/name,w/name)
 subprocess.run([sys.executable,str(w/'test-native-peer.py'),str(runtime)],check=True)
 subprocess.run([sys.executable,str(w/'test-native-telemetry.py'),str(runtime)],check=True)
 print('PASS: exact104/105/106/107 zero-fuzz source patches; genuine peers, native init ordering, power availability and legacy reporting preserved')
