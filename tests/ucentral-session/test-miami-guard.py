#!/usr/bin/env python3
"""Exact image guard/extra predicates fed real native fixture statuses.

Unrelated device IO (identity, mount, ping, journal) is controlled successful;
environment writes and reboot are captured privately in a temporary fixture.
"""
from pathlib import Path
import json, subprocess, tempfile, os, hashlib, argparse

parser=argparse.ArgumentParser()
parser.add_argument("--image-root",type=Path,required=True)
parser.add_argument("--output",type=Path,required=True)
args=parser.parse_args()
output=args.output
rows=json.loads((output/"native-status-cases.json").read_text())
guard=args.image_root/"usr/sbin/cambium-ab-guard"
miami=args.image_root/"lib/functions/cambium-ab-miami.sh"
accepted={'fresh-uuid-accepted','completed-reconnect-preserved','repeated-reconnect-no-reapply','subsequent-success-accepted','new-process-new-uuid-accepted'}
results=[]
with tempfile.TemporaryDirectory(prefix='miami-guard-receipts-') as work:
    work=Path(work)
    (work/'empty-lib').write_text('')
    jsonfilter=work/'jsonfilter'
    jsonfilter.write_text('#!/usr/bin/env python3\nimport json,sys\nd=json.load(sys.stdin); k=sys.argv[sys.argv.index("-e")+1][2:]; print(d[k])\n')
    jsonfilter.chmod(0o755)
    shell=work/'test.sh'
    shell.write_text(r'''
AB_GUARD_SOURCE_ONLY=1
CAMBIUM_SYSTEM_FUNCTIONS="$WORK/empty-lib"
CAMBIUM_AB_LIB="$WORK/empty-lib"
CAMBIUM_INSTALLER_HEALTH_LIB="$WORK/not-present"
. "$GUARD"
. "$MIAMI"
AB_GUARD_TRIES=1 PAUSE=0
AB_HEALTH_DIR="$WORK/not-present"
BOARD_DATA_STATUS="$WORK/board-status"
CAMBIUM_BDF_STATUS="$WORK/board-status"
ab_identity() { AB_ACTIVE=1;AB_ENV=miami;AB_FAMILY=miami; }
ab_getenv() {
 case "$1" in
 miami_ab_state) echo trial-started;;
 miami_ab_target) echo 1;;
 miami_ab_confirmed) echo 0;;
 esac
}
ab_hook() { return 1; }
installer_healthy() { return 0; }
ab_setenv_batch() { cat "$1" >> "$WORK/env-writes"; }
ab_setenv() { printf '%s %s\n' "$1" "$2" >> "$WORK/env-writes"; }
log() { printf '%s\n' "$*" >> "$WORK/messages"; }
do_reboot() { echo called > "$WORK/reboot"; }
ab_miami_storage_context() { return 0; }
ab_miami_certificate_mount() { return 0; }
ab_miami_readiness_identity() { return 0; }
ab_miami_ab_profile() { return 0; }
lan_interface() { echo up; }
lan_route_table() { echo main; }
ip() { echo 'default via 192.0.2.1 dev up'; }
ping() { return 0; }
ubus() { cat "$WORK/status.json"; }
healthy() {
 AB_HEALTH_FAILURE=
 ab_identity
 ab_miami_healthy_extra || { AB_HEALTH_FAILURE='miami extra health check failed';return 1; }
}
ab_guard
''')
    for row in rows:
        for name in ['env-writes','reboot','messages']:
            (work/name).unlink(missing_ok=True)
        (work/'status.json').write_text(json.dumps(row))
        (work/'board-status').write_text('vault\n')
        env={**os.environ,'PATH':str(work)+os.pathsep+os.environ['PATH'],'WORK':str(work),'GUARD':str(guard),'MIAMI':str(miami)}
        r=subprocess.run(['sh',str(shell)],env=env,capture_output=True,text=True)
        assert r.returncode==0,(row['case'],r.stdout,r.stderr)
        writes=(work/'env-writes').read_text()
        confirm='miami_ab_confirmed 1\n' in writes and 'bootcmd run miami_stable1\n' in writes
        rollback='miami_ab_state rolled-back\n' in writes and (work/'reboot').is_file()
        expect=row['case'] in accepted
        assert confirm==expect and rollback!=expect,(row['case'],writes)
        results.append({'case':row['case'],'actual_guard_confirmed':confirm,'actual_guard_rollback':rollback})
receipt={'cases':results,'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [guard,miami]},'limitations':__doc__}
(output/'miami-guard-test-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(f'PASS {len(results)} actual Miami extra-health/shared guard controls using native status outputs')
