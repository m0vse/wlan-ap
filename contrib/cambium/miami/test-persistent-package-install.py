#!/usr/bin/env python3
"""Run the actual persistent package install recipe and verify its closure."""
from pathlib import Path
import tempfile,subprocess
r=Path(__file__).resolve().parents[3];pkg=r/'feeds/tip/cambium-miami-persistent'
s=(pkg/'Makefile').read_text().split('define Package/cambium-miami-persistent/install\n',1)[1].split('\nendef',1)[0]
with tempfile.TemporaryDirectory(prefix='miami-persistent-install-') as td:
 w=Path(td);s=s.replace('$(1)',td)
 for k,v in [('INSTALL_DIR','install -d -m0755'),('INSTALL_DATA','install -m0644'),('INSTALL_BIN','install -m0755')]:s=s.replace('$('+k+')',v)
 subprocess.run(['sh','-ec',s],cwd=pkg,check=True)
 assert (w/'lib/functions/cambium-ab-miami.sh').read_bytes()==(pkg/'files/cambium-ab-miami.sh').read_bytes()
 assert (w/'usr/libexec/miami-country-defaults').read_bytes()==(pkg/'files/miami-country-defaults').read_bytes()
 assert not (w/'usr/sbin/cambium-return-oem').exists() # owned by shared cambium-ab
print('PASS: actual persistent install recipe; family module and country helper closure; OEM return owned by shared package')
