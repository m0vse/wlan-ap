"""Execute shared confirmation against supplied generated main core. No hardware writes."""
import os,subprocess,sys
from pathlib import Path
repo=Path(__file__).resolve().parents[3]
core=Path(sys.argv[1]).resolve()
health=repo/'feeds/tip/certificates/files/lib/functions/cambium-installer-health.sh'
script=''' . "$CORE"
. "$HEALTH"
ab_getenv() { case "$1" in *_ab_confirmed) printf '%s' "${CONFIRMED:-}";; *_ab_state) printf '%s' "${STATE:-}";; bootcmd) printf '%s' "${BOOTCMD:-}";; *_ab_version) printf '%s' "${VERSION:-}";; esac; }
ab_installer_confirmed_context
'''
cases=[('sage','E410','sage','1','1','confirmed','run sage_stable1','1',0),('sage','E410','sage','1','1','trial','run sage_stable1','1',1),('jaguar','XV2-2','jaguar','0','0','confirmed','run jaguar_stable0','1',0),('miami','X7-35X','miami','0','','','','',1),('miami','X7-35X','miami','0','','','','0',1)]
for family,model,namespace,active,confirmed,state,bootcmd,version,want in cases:
 env={**os.environ,'CORE':str(core),'HEALTH':str(health),'AB_FAMILY':family,'AB_MODEL':model,'AB_ENV':namespace,'AB_ACTIVE':active,'CONFIRMED':confirmed,'STATE':state,'BOOTCMD':bootcmd,'VERSION':version}
 p=subprocess.run(['sh','-c',script],env=env,capture_output=True)
 assert p.returncode==want,(family,p.returncode,p.stderr)
print('PASS: main core API linkage; converted Sage/Jaguar acceptance; invalid state and absent Miami adapter fail closed')
