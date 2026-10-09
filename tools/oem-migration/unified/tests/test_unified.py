"""Safe model/transaction tests; all device paths are temporary regular files.

Adapters here are orchestration fault models, not production qualification.
Actual family writer regressions are run separately by run.py.
"""
import hashlib, importlib.util, json, os, pty, select, shutil, struct, subprocess, tempfile, time, unittest
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('release_builder',BASE/'prepare-release.py')
BUILDER=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(BUILDER)
MODELS=json.loads((BASE/'tests/models.json').read_text())

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def seal(root):
    excluded={'installer.sh','oem-restore-test.sh','check-sysupgrade-ready.sh','cambium-oem-install','cambium-oem-restore-test','cambium-ab-ready','SHA256SUMS','LAUNCHER-HASHES.txt'}
    (root/'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.relative_to(root)}\n' for p in sorted(root.rglob('*')) if p.is_file() and p.name not in excluded))
    pin=digest(root/'SHA256SUMS')
    for name in ('installer.sh','oem-restore-test.sh','check-sysupgrade-ready.sh'):
        (root/name).write_text((BASE/name).read_text().replace('RELEASE_PIN_NOT_CONFIGURED',pin).replace('OEM_SYS_ROOT=\n','OEM_SYS_ROOT=$TEST_ROOT\n').replace('/tmp/cambium-unified-oem.lock','$TEST_ROOT/installer.lock'))
    return pin

class Fixture:
    def __init__(self,root,model,enabled=False):
        root=root.resolve();self.root=root;self.model=model;self.device=root/'ap';self.release=root/'release';self.log=root/'trace'
        self.device.mkdir();self.release.mkdir();self.log.write_text('')
        for name in ('ART','MFG','ENV','BOOTCODE','OEM','VAULT'):(self.device/name).write_bytes(('unique-'+name).encode())
        for name in ('proc/device-tree/cambium-platform','etc'):(self.device/name).mkdir(parents=True,exist_ok=True)
        (self.device/'proc/device-tree/cambium-platform/board-sku').write_bytes(struct.pack('>I',int(model['sku'],16)))
        self.bin=root/'bin';self.bin.mkdir();(self.bin/'id').write_text('#!/bin/sh\necho 0\n');(self.bin/'id').chmod(0o755)
        for name in ('lib','adapters'):shutil.copytree(BASE/name,self.release/name)
        shutil.copyfile(BASE/'models.tsv',self.release/'recognition.tsv')
        # Native fixture UID and macOS xattr display; production stays Root-only.
        common=self.release/'lib/common.sh';common.write_text(common.read_text().replace('$3==0',f'$3=={os.getuid()}').replace('$1=="drwx------"','$1~/^drwx------@?$/').replace('$1=="-rw-------"','$1~/^-rw-------@?$/'))
        row='\t'.join((model['sku'],model['family'],model['model'],model['family'] if enabled and model['family']!='gambit' else '-',model['fixture_oem_version']))+'\n'
        for name in ('models.tsv','restore-models.tsv','upgrade-models.tsv'):(self.release/name).write_text(row)
        (self.release/'deployment.tsv').write_text('controller\tcontroller.example.test\ndownload_url\thttps://download.example.test\nbackup_url\thttps://backup.example.test\n')
        self.env=dict(LC_ALL='C',TERM='xterm',HOME=str(root/'home'),PATH=str(self.bin)+':'+os.environ['PATH'],TEST_ROOT=str(self.device),TRACE=str(self.log),FAIL_STAGE='',FIXTURE_VERSION=model['fixture_oem_version'])
        # Explicit fake operations cannot open real devices or network.
        adapter=r'''
phase() { printf '%s\n' "$1" >> "$TRACE"; [ "${FAIL_STAGE:-}" != "$1" ]; }
protect() {
 OEM_PROTECTED_RANGES=$TEST_ROOT/ranges
 OEM_WRITE_PLAN=$TEST_ROOT/plan
 printf '1\t0\t65536\tidentity\tnor0\n2\t65536\t65536\tenvironment\tnor0\n3\t0\t100\tactive-oem\tnand0\n4\t100\t100\ttarget\tnand0\n' > "$OEM_PROTECTED_RANGES"
 printf 'ubi-update\t4\t0\tkernel\n' > "$OEM_WRITE_PLAN"
}
oem_adapter_inspect() { phase inspect || return 1; OEM_SERIAL=001122334455;OEM_SOURCE_RELEASE=$FIXTURE_VERSION;OEM_SOURCE_SLOT=0;OEM_TARGET_SLOT=1; }
oem_adapter_preflight() { phase preflight || return 1; protect; }
oem_adapter_boot_preflight() { phase boot || return 1; OEM_BOOT_PRIOR_SLOT=0;OEM_BOOT_TARGET_SLOT=1;OEM_BOOT_MODE=persist-prior-before-load;OEM_BOOT_WATCHDOG=verified; }
oem_adapter_recovery() {
 phase recovery || return 1
 OEM_RECOVERY_DIR=$TEST_ROOT/critical
 mkdir -m 700 "$OEM_RECOVERY_DIR" || return 1
 for name in ART MFG ENV;do cp "$TEST_ROOT/$name" "$OEM_RECOVERY_DIR/$name.bin";chmod 600 "$OEM_RECOVERY_DIR/$name.bin";done
 printf 'ART\tART\t10\tunique-calibration\nENV\t0:APPSBLENV\t10\tboot-environment\n' > "$OEM_RECOVERY_DIR/manifest.tsv"
 (cd "$OEM_RECOVERY_DIR";sha256sum ./*.bin manifest.tsv > SHA256SUMS) || return 1
 printf '%s\n' "$(oem_sha "$OEM_RECOVERY_DIR/SHA256SUMS")" > "$OEM_RECOVERY_DIR/OFFDEVICE_VERIFIED"
 chmod 600 "$OEM_RECOVERY_DIR/manifest.tsv" "$OEM_RECOVERY_DIR/SHA256SUMS" "$OEM_RECOVERY_DIR/OFFDEVICE_VERIFIED"
}
oem_adapter_migrate() (
 phase migrate || exit 1
 # Trace key absence from child argv/export; never print it.
 env > "$TEST_ROOT/child-env"
 printf 'writing\n' > "$TEST_ROOT/journal"
 phase write || exit 1
 printf 'new candidate\n' > "$TEST_ROOT/candidate"
 phase readback || exit 1
 phase stage || exit 1
 phase sync || exit 1
 phase unmount || exit 1
 phase arm || exit 1
 printf 'prior-before-candidate\n' > "$TEST_ROOT/armed"
 printf 'staged\n' > "$TEST_ROOT/journal"
)
oem_restore_inspect() { oem_adapter_inspect; }
oem_restore_preflight() { oem_adapter_preflight; }
oem_restore_boot_preflight() { oem_adapter_boot_preflight; }
oem_restore_recovery() { oem_adapter_recovery; }
oem_restore_migrate() { oem_adapter_migrate ''; }
'''
        if enabled:
            for prefix in ('','restore-'):(self.release/'adapters'/f'{prefix}{model["family"]}.sh').write_text(adapter)
        seal(self.release)
        self.saved={p.name:p.read_bytes() for p in self.device.iterdir() if p.is_file()}
    def unchanged(self):return all((self.device/n).read_bytes()==data for n,data in self.saved.items())
    def run(self,direction='forward',check=True):
        name='installer.sh' if direction=='forward' else 'oem-restore-test.sh'
        args=['check'] if direction=='forward' and check else ['install'] if direction=='forward' else ['--check'] if check else ['--restore']
        if direction=='reverse':(self.device/'etc/openwrt_release').write_text('DISTRIB_RELEASE=synthetic-openwifi-v1\n')
        return subprocess.run(['sh',str(self.release/name),*args],env=self.env,capture_output=True,text=True)
    def interactive(self,fail=''):
        key=os.urandom(32).hex();env=dict(self.env,FAIL_STAGE=fail)
        pid,fd=pty.fork()
        if pid==0:os.execve('/bin/sh',['sh',str(self.release/'installer.sh'),'install'],env)
        done=0;status=0;output=b'';sent_key=False;confirmed=False;declined=False;deadline=time.monotonic()+12
        try:
            while time.monotonic()<deadline:
                if select.select([fd],[],[],.1)[0]:
                    try:chunk=os.read(fd,65536)
                    except OSError:break
                    if not chunk:break
                    output+=chunk
                    if b'Onboarding key: ' in output and not sent_key:os.write(fd,(key+'\n').encode());sent_key=True
                    if b'Type INSTALL: ' in output and not confirmed:os.write(fd,b'INSTALL\n');confirmed=True
                    if b'Reboot now?' in output and not declined:os.write(fd,b'n\n');declined=True
                done,status=os.waitpid(pid,os.WNOHANG)
                if done:break
            else:os.kill(pid,9);done,status=os.waitpid(pid,0);raise AssertionError('fixture deadline exceeded')
            if not done:done,status=os.waitpid(pid,0)
            assert key.encode() not in output,'secret appeared on terminal'
            for p in (self.log,self.device/'child-env'):
                if p.exists():assert key not in p.read_text(),'secret appeared in trace or export'
            return os.waitstatus_to_exitcode(status),output.decode(errors='replace')
        finally:os.close(fd)

class UnifiedTests(unittest.TestCase):
    def test_registry_requires_exact_fixture_for_every_model(self):
        actual={tuple(r.split('\t')) for r in (BASE/'models.tsv').read_text().splitlines() if r and not r.startswith('#')}
        fixtures={(m['sku'],m['family'],m['model']) for m in MODELS}
        self.assertEqual(actual,fixtures);self.assertEqual(len(fixtures),len(MODELS))
    def test_all_models_both_directions_unsupported_before_prompt_or_writes(self):
        for m in MODELS:
            for direction in ('forward','reverse'):
                with self.subTest(model=m['model'],direction=direction),tempfile.TemporaryDirectory() as td:
                    f=Fixture(Path(td),m);p=f.run(direction)
                    self.assertNotEqual(p.returncode,0);self.assertEqual(f.log.read_text(),'');self.assertTrue(f.unchanged());self.assertNotIn('Onboarding key:',p.stdout)
    def test_every_model_fixture_check_does_not_write_or_prompt(self):
        for m in MODELS:
            if m['family']=='gambit':continue
            with self.subTest(model=m['model']),tempfile.TemporaryDirectory() as td:
                f=Fixture(Path(td),m,True);p=f.run()
                self.assertEqual(p.returncode,0,p.stderr);self.assertTrue(f.unchanged());self.assertFalse((f.device/'journal').exists());self.assertNotIn('Onboarding key:',p.stdout)
    def test_source_version_unknown_old_and_unreviewed_new(self):
        for version in ('old-version','unknown','new-unreviewed'):
            with self.subTest(version=version),tempfile.TemporaryDirectory() as td:
                f=Fixture(Path(td),MODELS[1],True);f.env['FIXTURE_VERSION']=version;p=f.run()
                self.assertNotEqual(p.returncode,0);self.assertEqual(f.log.read_text(),'inspect\n');self.assertTrue(f.unchanged())
    def test_mutated_helper_never_executes(self):
        with tempfile.TemporaryDirectory() as td:
            f=Fixture(Path(td),MODELS[1],True);(f.release/'lib/common.sh').write_text('touch "$TEST_ROOT/compromised"\n')
            self.assertNotEqual(f.run().returncode,0);self.assertFalse((f.device/'compromised').exists());self.assertTrue(f.unchanged())
    def test_transaction_faults_preserve_critical_and_stop_arming(self):
        for stage in ('inspect','preflight','boot','recovery','migrate','write','readback','stage','sync','unmount','arm',''):
            with self.subTest(stage=stage),tempfile.TemporaryDirectory() as td:
                f=Fixture(Path(td),MODELS[1],True);code,out=f.interactive(stage)
                self.assertEqual(code==0,not stage,out);self.assertTrue(f.unchanged());self.assertEqual((f.device/'armed').exists(),not stage)
                if stage in ('write','readback','stage','sync','unmount','arm'):self.assertEqual((f.device/'journal').read_text(),'writing\n')
    def test_inherited_export_and_allexport_cannot_leak_prompt_key(self):
        with tempfile.TemporaryDirectory() as td:
            f=Fixture(Path(td),MODELS[1],True)
            for name in ('OEM_KEY','key','ENROLMENT_KEY','credential'):f.env[name]='ambient-export-canary'
            code,out=f.interactive()
            self.assertEqual(code,0,out)
            exported=(f.device/'child-env').read_text()
            for name in ('OEM_KEY','key','ENROLMENT_KEY','credential'):self.assertNotIn(name+'=',exported)
    def test_reverse_check_has_no_identity_or_env_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            f=Fixture(Path(td),MODELS[1],True);p=f.run('reverse')
            self.assertEqual(p.returncode,0,p.stderr);self.assertTrue(f.unchanged());self.assertFalse((f.device/'journal').exists())

class BoundaryTests(unittest.TestCase):
    def shell(self,script):return subprocess.run(['sh','-c',script],capture_output=True,text=True)
    def test_critical_backup_rejects_full_firmware_config_and_wrong_asset(self):
        forbidden=('rootfs','rootfs_1','fs','linux0','kernel','NVRAM','config','0:APPSBL')
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'plan'
            for name in forbidden:
                p.write_text(f'ART\t{name}\t65536\tunique-calibration\nENV\t0:APPSBLENV\t65536\tboot-environment\n')
                self.assertNotEqual(self.shell(f'. "{BASE}/lib/critical-backup.sh";oem_backup_plan_check "{p}"').returncode,0,name)
            p.write_text('ART\t0:ART\t1048576\tunique-calibration\nENV\t0:APPSBLENV\t65536\tboot-environment\n')
            self.assertEqual(self.shell(f'. "{BASE}/lib/critical-backup.sh";oem_backup_plan_check "{p}"').returncode,0)
    def test_overlap_wrong_parent_active_sage_and_alias_refused(self):
        with tempfile.TemporaryDirectory() as td:
            inv=Path(td)/'inventory';plan=Path(td)/'plan'
            inv.write_text('1\t0\t100\tidentity\tnor0\n2\t100\t100\tenvironment\tnor0\n3\t0\t100\tshared-parent\tnand0\n')
            plan.write_text('ubi-update\t3\t2\tlinux1\n')
            run=lambda:self.shell(f'. "{BASE}/lib/protection.sh";OEM_TARGET_SLOT=1;oem_write_boundary "{inv}" "{plan}"')
            self.assertEqual(run().returncode,0)
            for row in ('ubi-update\t3\t0\tlinux0\n','ubi-update\t1\t0\tkernel\n','ubi-remove\t3\t4\tcertificates\n','mtd-erase\t3\t0\tparent\n'):
                plan.write_text(row);self.assertNotEqual(run().returncode,0,row)
            plan.write_text('ubi-update\t3\t2\tlinux1\n');inv.write_text(inv.read_text().replace('2\t100','2\t50'));self.assertNotEqual(run().returncode,0)
    def test_unrelated_environment_cannot_change(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'before').write_text('bootcmd=old\nethaddr=own\ncustom=keep=exact\n');(root/'allowed').write_text('bootcmd\n');(root/'after').write_text('bootcmd=new\nethaddr=own\ncustom=keep=exact\n')
            run=lambda:self.shell(f'. "{BASE}/lib/protection.sh";oem_env_preserved "{root}/before" "{root}/after" "{root}/allowed"')
            self.assertEqual(run().returncode,0);(root/'after').write_text('bootcmd=new\nethaddr=donor\ncustom=keep=exact\n');self.assertNotEqual(run().returncode,0)
            (root/'allowed').write_text('bootcmd\nethaddr\n');self.assertNotEqual(run().returncode,0)

if __name__=='__main__':unittest.main()
