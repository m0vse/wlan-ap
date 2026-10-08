#!/usr/bin/env python3
"""Actual read-only asset policy and adapter, isolated hardware boundaries."""
from pathlib import Path
import tempfile,subprocess,os,hashlib
repo=Path(__file__).resolve().parents[3]
loader=(repo/'feeds/tip/cambium-miami-radio/files/miami-board-data').read_text()
def block(name):
 start=loader.index(name+'() {');return loader[start:loader.index('\n}\n',start)+3]
functions=block('pci_bdf_suffix')+'\n'+block('validate_country_asset')
with tempfile.TemporaryDirectory(prefix='miami-deferred-test-') as td:
 r=Path(td);work=r/'work';files=work/'vault/files/lib/firmware/qcn9224/WIFI_FW';files.mkdir(parents=True)
 slot=r/'proc/device-tree/cambium-platform/storage-slot';slot.parent.mkdir(parents=True);slot.write_bytes(b'\0'*4)
 manifest=work/'vault/MANIFEST';payload=b'own-unit UK board fixture';sha=hashlib.sha256(payload).hexdigest();uk=files/'bdwlan.b1019-acadia.uk';uk.write_bytes(payload)
 row=f'file lib/firmware/qcn9224/WIFI_FW/{uk.name} {len(payload)} {sha}\n';manifest.write_text(row)
 code='WORK="$1"; PCI=lib/firmware/qcn9224/WIFI_FW; vault_locate(){ return "${FAIL_VAULT:-0}"; };\n'+functions.replace('/proc/',str(r)+'/proc/')+'\nvalidate_country_asset "$2"'
 def asset(country='GB',ok=True,extra=None):
  p=subprocess.run(['sh','-c',code,'asset',str(work),country],env=dict(os.environ,**(extra or {})),capture_output=True,text=True)
  assert (p.returncode==0)==ok,(country,p.stdout,p.stderr)
  if ok:assert p.stdout.strip()==sha
 asset();asset(extra={'FAIL_VAULT':'1'},ok=False)
 for bad in ['','gb','GB;reboot','000','GB\n']:asset(bad,False)
 uk.unlink();(files/'bdwlan.b1019-acadia').write_bytes(payload);asset(ok=False) # no ROW fallback
 uk.write_bytes(payload);manifest.write_text(row+row);asset(ok=False);manifest.write_text(row)
 uk.write_bytes(b'tampered');asset(ok=False);uk.unlink();uk.symlink_to(files/'bdwlan.b1019-acadia');asset(ok=False);uk.unlink();uk.write_bytes(payload)
 slot.unlink();asset(ok=False);slot.write_bytes(b'\0'*4)
 # Hardware guards are mocked here; their real implementations have separate
 # persistent-context fixtures and actual c319 hardware evidence.
 fns=r/'functions';fns.mkdir();(fns/'system.sh').write_text('')
 (fns/'ab.sh').write_text('''ab_identity(){ AB_FAMILY=miami; AB_MODEL=${TEST_MODEL:-X7-35X}; AB_CERTIFICATE_LEBS=64; }
ab_miami_storage_context(){ return "${FAIL_CONTEXT:-0}"; }
ab_miami_certificate_mount(){ return "${FAIL_MOUNT:-0}"; }
''')
 mock=r/'board-data';mock.write_text('#!/bin/sh\n[ "$1" = --validate-country ] || exit 9\nprintf "%s\\n" "'+sha+'"\n');mock.chmod(0o700)
 ready=r/'ready';ready.write_text('#!/bin/sh\nexit "${FAIL_READY:-0}"\n');ready.chmod(0o700)
 tmp=r/'tmp';(tmp/'miami-firmware/ath12k/QCN92XX/hw1.0').mkdir(parents=True)
 status=tmp/'cambium-board-data.status';status.write_text('vault\n');countryfile=tmp/'miami-firmware/board-country';countryfile.write_text('GB\n');bdf=tmp/'miami-firmware/ath12k/QCN92XX/hw1.0/board.bin';bdf.write_bytes(payload)
 param=r/'sys/module/cfg80211/parameters/ieee80211_regdom';param.parent.mkdir(parents=True);param.write_text('GB\n')
 phys=r/'sys/class/ieee80211';phys.mkdir(parents=True)
 for n in ['phy00','phy01','phy03']:(phys/n).mkdir()
 source=(repo/'feeds/tip/cambium-miami-persistent/files/ucentral-deferred-miami').read_text().replace('/lib/functions/system.sh',str(fns/'system.sh')).replace('/lib/functions/cambium-ab.sh',str(fns/'ab.sh')).replace('/usr/sbin/miami-board-data',str(mock)).replace('/usr/libexec/miami-radio-ready',str(ready)).replace('/tmp/',str(tmp)+'/').replace('/sys/',str(r)+'/sys/')
 script=r/'adapter';script.write_text(source)
 def run(mode='validate',ok=True,extra=None):
  before={str(p):p.read_bytes() for p in r.rglob('*') if p.is_file()}
  p=subprocess.run(['sh',str(script),mode,'GB'],env=dict(os.environ,**(extra or {})),capture_output=True,text=True)
  assert (p.returncode==0)==ok,(mode,p.stdout,p.stderr)
  assert before=={str(p):p.read_bytes() for p in r.rglob('*') if p.is_file()}
 run();run('readback')
 for extra in [{'TEST_MODEL':'wrong'},{'FAIL_CONTEXT':'1'},{'FAIL_MOUNT':'1'}]:run(ok=False,extra=extra)
 run('readback',False,{'FAIL_READY':'1'})
 countryfile.write_text('US\n');run('readback',False);countryfile.write_text('GB\n')
 bdf.write_bytes(b'wrong');run('readback',False);bdf.write_bytes(payload)
 param.write_text('US\n');run('readback',False);param.write_text('GB\n')
 (phys/'phy03').rmdir();run('readback',False)
print('PASS: actual regional policy rejects missing/hash-mismatched/duplicate/unmanifested/symlink/foreign assets; adapter checks context/BDF/kernel country/three radios and is read-only')
