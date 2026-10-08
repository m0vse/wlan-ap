#!/usr/bin/env python3
"""Actual read-only Miami callback/crypto, synthetic policy/device boundaries.

No real AP/issuer/ENV operations. Root Linux is needed for private ownership.
This does not establish hardware A/B readiness from mocked policy flags.
"""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,tempfile

if os.geteuid()!=0 or not sys.platform.startswith('linux'):
    raise SystemExit('Requires root on Linux for private native identity fixtures')
module=Path(__file__).resolve().parents[3]/'feeds/tip/cambium-miami-persistent/files/cambium-ab-miami.sh'
with tempfile.TemporaryDirectory(prefix='miami-readiness-') as td:
    root=Path(td);store=root/'certificates';journal=store/'.installer-import'
    journal.mkdir(parents=True,mode=0o700);store.chmod(0o700)
    tools=root/'bin';tools.mkdir();work=root/'tmp';work.mkdir()
    def crypto(*args):
        subprocess.run(['openssl',*map(str,args)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    crypto('genpkey','-algorithm','EC','-pkeyopt','ec_paramgen_curve:prime256v1','-out',root/'ca.key')
    crypto('req','-new','-x509','-key',root/'ca.key','-subj','/CN=Fixture CA','-days','2','-out',store/'operational.ca',
           '-addext','basicConstraints=critical,CA:TRUE','-addext','keyUsage=critical,keyCertSign,cRLSign')
    crypto('genpkey','-algorithm','EC','-pkeyopt','ec_paramgen_curve:prime256v1','-out',store/'key.pem')
    crypto('req','-new','-key',store/'key.pem','-subj','/CN=020000000001','-out',root/'csr')
    (root/'extensions').write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=clientAuth\n')
    crypto('x509','-req','-in',root/'csr','-CA',store/'operational.ca','-CAkey',root/'ca.key','-CAcreateserial',
           '-days','2','-out',store/'operational.pem','-extfile',root/'extensions')
    shutil.copyfile(store/'operational.pem',store/'cert.pem')
    crypto('pkey','-in',store/'key.pem','-pubout','-outform','DER','-out',root/'public.der')
    spki=hashlib.sha256((root/'public.der').read_bytes()).hexdigest()
    transaction={'accepted':True,'committed':True,'spki':spki}
    completion={'binding':{'serial':'020000000001','family':'miami','model':'X7-35X','spki_sha256':spki}}
    (journal/'transaction.json').write_text(json.dumps(transaction));(journal/'completion.json').write_text(json.dumps(completion))
    for p in store.rglob('*'):
        if p.is_file():p.chmod(0o600)
    jf=tools/'jsonfilter';jf.write_text('''#!/usr/bin/env python3
import json,sys
a=sys.argv[1:];data=json.load(open(a[a.index('-i')+1])) if '-i' in a else json.load(sys.stdin)
for field in a[a.index('-e')+1].removeprefix('@.').split('.'):data=data[field]
print(json.dumps(data) if isinstance(data,(bool,int)) else data)
''');jf.chmod(0o700)
    ubus=tools/'ubus';ubus.write_text('#!/usr/bin/env python3\nimport os\nprint(os.environ["FIXTURE_STATUS"])\n');ubus.chmod(0o700)
    status={'connected':10,'connection_generation':1,'config_received_sequence':1,'config_applied_sequence':1,
            'config_received_uuid':'same','config_applied_uuid':'same','boot_report_transport':1}
    prelude='''. "$1"
AB_FAMILY=miami AB_MODEL=X7-35X AB_ENV=miami AB_ACTIVE=${FIXTURE_SLOT:-0} AB_QUALIFIED=${FIXTURE_QUALIFIED:-0}
ab_identity(){ :; };ab_miami_label_identity(){ :; };ab_miami_certificate_mount(){ :; }
get_mac_label_dt(){ echo 02:00:00:00:00:01; }
ab_hook(){ [ "${FIXTURE_HOOK:-0}" = 1 ]; }
ab_converted(){ [ "${FIXTURE_CONVERTED:-0}" = 1 ]; }
ab_miami_upgrade_preflight(){ [ "${FIXTURE_PREFLIGHT:-1}" = 1 ]; }
ab_getenv(){
case "$1" in
miami_installer_target) echo "${FIXTURE_PENDING:-}";;
miami_ab_confirmed) echo "${FIXTURE_CONFIRMED:-$AB_ACTIVE}";;
miami_ab_state) echo "${FIXTURE_STATE:-confirmed}";;
bootcmd) echo "${FIXTURE_BOOTCMD:-run miami_stable$AB_ACTIVE}";;
esac
}
ab_setenv(){ echo UNEXPECTED_PERSISTENT_WRITE;return 1; }
ab_miami_sysupgrade_readiness
printf '%s:%s\n' "$AB_UPGRADE_READY" "$AB_UPGRADE_REASON"
'''
    env={**os.environ,'PATH':str(tools)+':'+os.environ['PATH'],'AB_MIAMI_READINESS_ROOT':str(root),
         'AB_MIAMI_READINESS_TMP':str(work),'FIXTURE_STATUS':json.dumps(status)}
    def run(want,**extra):
        before={str(p.relative_to(store)):p.read_bytes() for p in store.rglob('*') if p.is_file()}
        p=subprocess.run(['sh','-c',prelude,'fixture',str(module)],env={**env,**extra},capture_output=True,text=True)
        assert p.returncode==0 and p.stdout.strip()==want,(p.stdout,p.stderr)
        assert before=={str(p.relative_to(store)):p.read_bytes() for p in store.rglob('*') if p.is_file()}
        assert not list(work.iterdir())
    for slot in ('0','1'):
        run('onboarded:ab-profile-not-installed',FIXTURE_SLOT=slot)
        # Actual est_client publication: the operational leaf/CA are 0440.
        for name in ('operational.pem','operational.ca'):(store/name).chmod(0o440)
        run('onboarded:ab-profile-not-installed',FIXTURE_SLOT=slot)
        for name in ('operational.pem','operational.ca'):(store/name).chmod(0o600)
        run('unsupported:native-onboarding-pending',FIXTURE_SLOT=slot,FIXTURE_PENDING=slot)
        run('onboarded:ab-qualification-pending',FIXTURE_SLOT=slot,FIXTURE_HOOK='1')
        run('onboarded:ab-confirmation-pending',FIXTURE_SLOT=slot,FIXTURE_HOOK='1',FIXTURE_QUALIFIED='1')
        run('onboarded:ab-preflight-failed',FIXTURE_SLOT=slot,FIXTURE_HOOK='1',FIXTURE_QUALIFIED='1',FIXTURE_CONVERTED='1',FIXTURE_PREFLIGHT='0')
        run('ready:confirmed-native-ab',FIXTURE_SLOT=slot,FIXTURE_HOOK='1',FIXTURE_QUALIFIED='1',FIXTURE_CONVERTED='1')
        run('ready:confirmed-native-ab',FIXTURE_SLOT=slot,FIXTURE_HOOK='1',FIXTURE_QUALIFIED='1',FIXTURE_CONVERTED='1',
            FIXTURE_STATE='rolled-back',FIXTURE_BOOTCMD=f'run miami_boot{slot}')
    changed=dict(status,config_applied_uuid='different')
    run('unsupported:native-config-not-applied',FIXTURE_STATUS=json.dumps(changed))
    changed=dict(status,connected=0)
    run('unsupported:native-not-applied',FIXTURE_STATUS=json.dumps(changed))
    old=(journal/'completion.json').read_bytes();completion['binding']['serial']='020000000002'
    (journal/'completion.json').write_text(json.dumps(completion))
    run('unsupported:native-identity-invalid');(journal/'completion.json').write_bytes(old)
    old=(store/'key.pem').read_bytes();crypto('genpkey','-algorithm','EC','-pkeyopt','ec_paramgen_curve:prime256v1','-out',store/'key.pem')
    run('unsupported:native-identity-invalid');(store/'key.pem').write_bytes(old)
    journal.chmod(0o755);run('unsupported:native-identity-invalid');journal.chmod(0o700)
    for mode in (0o640,0o644,0o440):
        (store/'key.pem').chmod(mode);run('unsupported:native-identity-invalid');(store/'key.pem').chmod(0o600)
    print('PASS: 24 actual read-only callback/crypto cases; native public 0440 accepted, private key stays 0600; policy/device boundary mocks do not qualify hardware')
