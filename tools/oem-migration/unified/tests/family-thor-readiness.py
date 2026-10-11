#!/usr/bin/env python3
"""Installed .8 readiness refusal/onboarded states, no publisher-cache substitution."""
from pathlib import Path
import os,json,subprocess,tempfile
base=Path(__file__).resolve().parents[1];frozen=base/'tests/fixtures/thor-2026.10.05.8'
with tempfile.TemporaryDirectory(prefix='thor-ready-') as td:
 root=Path(td).resolve();(root/'lib/functions').mkdir(parents=True);(root/'etc').mkdir()
 (root/'etc/openwrt_release').write_text("DISTRIB_TIP_VERSION='thor-2026.10.05.8'\n")
 (root/'lib/functions/system.sh').write_text('')
 (root/'lib/functions/cambium-ab-thor.sh').write_bytes((frozen/'lib/functions/cambium-ab-thor.sh').read_bytes())
 core=(frozen/'lib/functions/cambium-ab.sh').read_text()+r'''
ab_identity(){ ab_thor_board cambiumnetworks,xv3-8;AB_FAMILY=thor;AB_ACTIVE=0;AB_TARGET=1; }
ab_getenv(){ python3 "$OEM_SYS_ROOT/env-get.py" "$1"; }
'''
 (root/'lib/functions/cambium-ab.sh').write_text(core)
 (root/'env-get.py').write_text('import json,sys,os\nfrom pathlib import Path\nd=json.loads((Path(os.environ["OEM_SYS_ROOT"])/"env.json").read_text());k=sys.argv[1]\nif k not in d:sys.exit(1)\nprint(d[k])\n')
 script='. "$ADAPTER";oem_upgrade_inspect || exit 1;printf "%s:%s\\n" "$OEM_UPGRADE_STATUS" "$OEM_UPGRADE_REASON"'
 env={**os.environ,'OEM_SYS_ROOT':str(root),'OEM_FAMILY':'thor','OEM_MODEL':'XV3-8','OEM_SKU':'00000013','OEM_SUPPORTED_RELEASE':'thor-2026.10.05.8','ADAPTER':str(base/'adapters/upgrade-thor.sh'),'CAMBIUM_AB_MODULES':str(root/'lib/functions')}
 cases=[('bare .8 confirmed mixed',{'thor_ab_confirmed':'0','thor_ab_state':'confirmed'},'onboarded:actual-native-conversion-required'),('bare .8 converted',{'thor_ab_confirmed':'0','thor_ab_state':'confirmed','thor_ab_version':'1'},'unsupported:installed-trial-command-not-prior-only'),('pending native identity',{'thor_ab_confirmed':'0','thor_ab_state':'confirmed','thor_installer_target':'0'},'unsupported:native-onboarding-pending'),('unconfirmed native',{'thor_ab_confirmed':'0','thor_ab_state':'trial-started'},'unsupported:native-trial-not-confirmed')]
 for name,d,expected in cases:
  (root/'env.json').write_text(json.dumps(d));before=(root/'env.json').read_bytes()
  p=subprocess.run(['sh','-c',script],env=env,capture_output=True,text=True)
  assert p.returncode==0 and p.stdout.strip()==expected,(name,p.stdout,p.stderr)
  assert (root/'env.json').read_bytes()==before
 print(f'PASS: {len(cases)} actual installed .8 readiness states; no false ready or ENV write')
 print('Scope: actual .8 command generator, hardware/ENV reads are actors; corrected publisher runtime is never substituted as installed support.')
