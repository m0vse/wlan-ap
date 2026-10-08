#!/usr/bin/env python3
"""Exercise actual SDK firmware publication and no-restage-after-bind guard."""
from pathlib import Path
import tempfile,subprocess,os
repo=Path(__file__).resolve().parents[3]
s=(repo/'feeds/tip/cambium-miami-radio/files/miami-board-data').read_text()
fn=s[s.index('publish_sdk_firmware() {'):s.index('# Stage radio files from root $1')]
with tempfile.TemporaryDirectory(prefix='miami-sdk-publication-') as td:
 r=Path(td);fw=r/'tmp/miami-firmware';ini=r/'ini';lib=r/'lib/firmware'
 for d in [ini/'internal',lib/'ath12k/QCN92XX/hw1.0',r/'sys/module/firmware_class/parameters']:
  d.mkdir(parents=True,exist_ok=True)
 originals={ini/'global.ini':b'sdk global INI',ini/'IPQ5332.ini':b'sdk IPQ5332 INI',ini/'internal/IPQ5332_i.ini':b'sdk internal INI',lib/'ath12k/QCN92XX/hw1.0/amss.bin':b'public SDK AMSS'}
 for f,data in originals.items():f.write_bytes(data)
 requests=['ath12k/IPQ5332/hw1.0/q6_fw0.mdt','ath12k/IPQ5332/hw1.0/q6_fw0.b00','ath12k/IPQ5332/hw1.0/q6_fw1.mbn','ath12k/IPQ5332/hw1.0/iu_fw.mbn','ath12k/IPQ5332/hw1.0/board.bin','ath12k/IPQ5332/hw1.0/regdb.bin','ath12k/QCN92XX/hw1.0/board.bin','ath12k/QCN92XX/hw1.0/regdb.bin','ath12k/QCN92XX/hw1.0/cal-pci-0001:01:00.0.bin']
 for name in requests:
  f=fw/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(('unit:'+name).encode())
 path=r/'sys/module/firmware_class/parameters/path';path.write_text(str(ini))
 code=fn.replace('/lib/firmware',str(lib)).replace('/ini',str(ini)).replace('/sys/module',str(r/'sys/module'))
 def run(ok=True):
  p=subprocess.run(['sh','-c','FW="$1"\n'+code+'\npublish_sdk_firmware','sh',str(fw)],capture_output=True,text=True)
  assert (p.returncode==0)==ok,(p.stdout,p.stderr)
 ini.joinpath('global.ini').unlink();run(False);assert not (lib/'IPQ5332').exists()
 ini.joinpath('global.ini').write_bytes(originals[ini/'global.ini']);run()
 for name in requests:
  assert (lib/name).is_symlink() and (lib/name).read_bytes()==(fw/name).read_bytes()
 assert (lib/'IPQ5332/q6_fw0.mdt').read_bytes()==(fw/'ath12k/IPQ5332/hw1.0/q6_fw0.mdt').read_bytes()
 assert path.read_text()==str(ini)
 for f,data in originals.items():assert f.read_bytes()==data
 # Native SDK S03 reselects exactly the same INI path; all requests still resolve.
 path.write_text(str(ini))
 for name in ['global.ini','IPQ5332.ini','internal/IPQ5332_i.ini']:assert (Path(path.read_text())/name).is_file()
 for name in requests:assert (lib/name).read_bytes()==(fw/name).read_bytes()
 # Neither a real directory at the remoteproc alias nor a firmware-directory
 # collision is accepted. No unexpected tree is erased to accommodate it.
 (lib/'IPQ5332').unlink();(lib/'IPQ5332').mkdir();sentinel=lib/'IPQ5332/keep';sentinel.write_bytes(b'keep');run(False);assert sentinel.read_bytes()==b'keep'
 start=(repo/'feeds/tip/cambium-miami-radio/files/miami-radio-start').read_text()
 start=start[:start.index('tries=0')].replace('. /lib/functions/system.sh','board_name(){ echo cambiumnetworks,x7-35x; }').replace('/sys/',str(r)+'/sys/').replace('/var/lock/miami-radio.lock',str(r/'lock'))
 for device in ['bus/platform/devices/c000000.wifi','bus/pci/devices/0001:01:00.0']:
  d=r/'sys'/device;d.mkdir(parents=True);(d/'driver').symlink_to(ini,target_is_directory=True)
  result=subprocess.run(['sh','-c',start+'\necho UNSAFE_RESTAGE'],capture_output=True,text=True)
  assert result.returncode==0 and 'UNSAFE_RESTAGE' not in result.stdout
  (d/'driver').unlink()
print('PASS: actual SDK publication; INI/public firmware bytes preserved; own root/UserPD/IU/BDF/regdb/cal requests resolve with native S03 path; missing INI/foreign directories refuse; bound AHB or PCI prevents restaging')
