#!/usr/bin/env python3
"""Execute the RAM bootstrap snapshot hook against isolated filesystem fixtures."""
from pathlib import Path
import tempfile,subprocess,stat,re
repo=Path(__file__).resolve().parents[3]
src=(repo/'feeds/tip/cambium-miami-radio/files/01-miami-ram-bootstrap').read_text()
with tempfile.TemporaryDirectory() as td:
 root=Path(td)
 for name in ['tmp/sysinfo','proc','etc/ucentral','rom/etc/ucentral']:(root/name).mkdir(parents=True,exist_ok=True)
 helper=root/'hook'
 paths=['/tmp/sysinfo','/proc/mounts','/rom/etc/ucentral','/etc/ucentral']
 s=re.sub('|'.join(re.escape(p) for p in paths),lambda m:str(root/m.group().lstrip('/')),src)
 helper.write_text(s);board=root/'tmp/sysinfo/board_name';mounts=root/'proc/mounts';factory=root/'etc/ucentral/ucentral.cfg.0000000001';snapshot=root/'rom/etc/ucentral/ucentral.cfg.0000000001'
 board.write_text('cambiumnetworks,x7-35x\n');mounts.write_text('tmpfs / tmpfs rw 0 0\n');factory.write_text('{"uuid":1,"interfaces":[]}\n')
 def run(ok=True):
  p=subprocess.run(['sh',str(helper)],capture_output=True,text=True);assert (p.returncode==0)==ok,(p.stdout,p.stderr)
 run();assert snapshot.read_bytes()==factory.read_bytes() and stat.S_IMODE(snapshot.stat().st_mode)==0o444
 factory.write_text('changed');run();assert snapshot.read_text().startswith('{"uuid":1')
 snapshot.unlink();mounts.write_text('/dev/root / squashfs ro 0 0\n');run();assert not snapshot.exists()
 mounts.write_text('tmpfs / tmpfs rw 0 0\n');board.write_text('other-board\n');run();assert not snapshot.exists()
 board.write_text('cambiumnetworks,x7-35x\n');factory.unlink();run(False);assert not snapshot.exists()
print('PASS: real RAM hook, immutable factory snapshot/idempotence, persistent-root and foreign-board refusal, missing factory error')
