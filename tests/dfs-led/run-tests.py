#!/usr/bin/env python3
"""Test actual shared source at mocked LED/service boundaries; no AP operations."""
from pathlib import Path
import subprocess,sys
repo,root,runtime=map(lambda s:Path(s).resolve(),sys.argv[1:]);tests=Path(__file__).resolve().parent
for name,source in [('test-led-helper.py','feeds/ucentral/ucentral-client/files/usr/libexec/ucentral-led.sh'),('test-state.py','feeds/ucentral/ucentral-state/files/ucentral-state')]:
 subprocess.run([sys.executable,str(tests/name),str(root),str(repo/source)],check=True)
subprocess.run([sys.executable,str(tests/'test-collector.py'),str(repo/'feeds/ucentral/ucentral-state/files/ucentral-dfs-led')],check=True)
subprocess.run([sys.executable,str(tests/'test-package-closure.py'),str(repo),str(root)],check=True)
modules=root/'usr/share/ucentral'
for case in ('tests/dfs-cac/test-dfs-cac.uc','tests/mlo-health/test-mlo-health.uc'):
 subprocess.run([str(runtime),'-L',str(modules/'*.uc'),str(repo/case)],check=True)
print('PASS shared DFS LED source, arbitration, whole-collector bound, package closure and genuine CAC evidence')
