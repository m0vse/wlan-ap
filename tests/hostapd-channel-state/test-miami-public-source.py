#!/usr/bin/env python3
"""Public source-only preservation receipt; no private ancestry or hardware claim."""
from pathlib import Path
import json, subprocess
repo=Path(__file__).resolve().parents[2]
ledger=json.loads((Path(__file__).with_name('protected-source.json')).read_text())
base=ledger['public_source_integration']['base']
subprocess.run(['git','merge-base','--is-ancestor',base,'HEAD'],cwd=repo,check=True)
pins={**ledger['common'],**ledger['miami_supplement']}
for name,digest in pins.items():
 p=repo/name
 assert p.is_file() and not p.is_symlink(),name
 assert subprocess.check_output(['git','hash-object','--no-filters',str(p)],text=True).strip()==digest,name
for name,digest in ledger['protected_trees'].items():
 assert subprocess.check_output(['git','rev-parse','HEAD:'+name],cwd=repo,text=True).strip()==digest,name
 subprocess.run(['git','diff','--quiet','HEAD','--',name],cwd=repo,check=True)
print(json.dumps({'passed':True,'scope':'public-source-only; private qualified-parent and hardware acceptance remain separate','protected_files':len(pins),'protected_trees':len(ledger['protected_trees'])}))
