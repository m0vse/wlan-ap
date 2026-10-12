#!/usr/bin/env python3
"""Run actual health/DFS code; prepared schema must precede patch104; no AP access."""
from pathlib import Path
import shutil,subprocess,sys,tempfile
repo,baseline,runtime=map(lambda s:Path(s).resolve(),sys.argv[1:]);tests=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='native-mlo-health-') as temp:
 w=Path(temp);source=w/'source';shutil.copytree(baseline/'system',source/'system')
 assert 'mlo_health.collect' not in (source/'system/health.uc').read_text(),'baseline must precede104'
 shutil.copy2(source/'system/health.uc',w/'health.uc');shutil.copy2(source/'system/dfs_cac.uc',w/'dfs_cac.uc')
 subprocess.run(['patch','-p1','--fuzz=0','-i',str(repo/'feeds/ucentral/ucentral-schema/patches/104-authoritative-per-link-mlo-health.patch')],cwd=source,check=True)
 fixture=w/'mlo-health-fixture';fixture.mkdir()
 for name in ('dfs_cac.uc','mlo_health.uc'):shutil.copy2(source/'system'/name,fixture/name)
 shutil.copy2(w/'dfs_cac.uc',fixture/'dfs_base.uc');shutil.copy2(source/'system/health.uc',w/'health-fixed.uc')
 for name in ('test-mlo-health.uc','test-health-golden.py'):shutil.copy2(tests/name,w/name)
 subprocess.run([str(runtime),'-L',str(fixture/'*.uc'),str(w/'test-mlo-health.uc')],check=True)
 subprocess.run([str(runtime),'-L',str(fixture/'*.uc'),str(tests/'test-generated-config.uc'),str(tests/'generated-miami-config.json')],check=True)
 subprocess.run([str(runtime),'-L',str(fixture/'*.uc'),str(repo/'tests/dfs-cac/test-dfs-cac.uc')],check=True)
 subprocess.run([sys.executable,str(w/'test-health-golden.py'),str(runtime)],check=True)
 print('PASS: exact package patch104 applied without fuzz; ordinary reporting and genuine failures preserved')
