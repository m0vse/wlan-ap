"""Actual staging plus isolated OverlayFS / and capability-free UID81 checks.

Run as Root on Linux. Only synthetic files in a private mount namespace are
used. This does not boot an AP or establish firmware hardware acceptance.
"""
from pathlib import Path
import importlib.util,json,os,shutil,subprocess,sys

if os.geteuid()!=0 or not sys.platform.startswith('linux'):
    raise SystemExit('Requires Root on Linux for isolated mount/UID tests')
if '--in-namespace' not in sys.argv:
    subprocess.run(['unshare','--mount','--propagation','private',sys.executable,
                    str(Path(__file__).resolve()),'--in-namespace'],check=True)
    raise SystemExit(0)
repo=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('stage_fixture',repo/'tools/oem-migration/recovery/scripts/tests/test_cambium_installer_settings.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
fixture=module.SettingsTests('test_success_only_stages_settings');fixture.setUp()
child=r'''import ctypes,json,os,subprocess
libc=ctypes.CDLL(None,use_errno=True)
assert libc.prctl(8,0,0,0,0)==0
os.setgroups([]);os.setgid(81);os.setuid(81)
class Header(ctypes.Structure):_fields_=[('version',ctypes.c_uint32),('pid',ctypes.c_int)]
class Data(ctypes.Structure):_fields_=[('effective',ctypes.c_uint32),('permitted',ctypes.c_uint32),('inheritable',ctypes.c_uint32)]
header=Header(0x20080522,0);data=(Data*2)()
assert libc.capset(ctypes.byref(header),ctypes.byref(data))==0
status=dict(line.split(':',1) for line in open('/proc/self/status') if ':' in line)
assert status['Uid'].split()==['81']*4 and status['Gid'].split()==['81']*4
assert not status['Groups'].split()
for key in ['CapEff','CapPrm','CapInh','CapAmb']:assert int(status[key].strip(),16)==0
result={}
try:
    with open('etc/public','rb') as f:result['public']=f.read()==b'public'
except PermissionError:result['public']=False
try:
    result['exec']=subprocess.run(['./bin/probe'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
except PermissionError:result['exec']=False
try:
    with open('root/.cambium-installer-settings/est-bootstrap.conf','rb'):result['private']=True
except PermissionError:result['private']=False
print(json.dumps(result))
'''
try:
    result=fixture.run_stage();assert result.returncode==0,result.stderr
    upper=fixture.mount/'upper';private=upper/'root/.cambium-installer-settings'
    assert upper.stat().st_mode&0o777==0o755
    assert (upper/'root').stat().st_mode&0o777==0o700
    assert private.stat().st_mode&0o777==0o700
    assert all(p.stat().st_mode&0o777==0o600 for p in private.iterdir())
    lower=fixture.root/'lower';work=fixture.root/'work';merged=fixture.root/'merged'
    for path in [lower,work,merged,lower/'etc',lower/'bin']:
        path.mkdir(mode=0o755);path.chmod(0o755)
        assert path.stat().st_mode&0o777==0o755
    (lower/'etc/public').write_bytes(b'public');(lower/'etc/public').chmod(0o644)
    shutil.copyfile('/bin/true',lower/'bin/probe');(lower/'bin/probe').chmod(0o755)
    for mode,want in [(0o700,False),(0o755,True)]:
        upper.chmod(mode)
        subprocess.run(['mount','-t','overlay','overlay','-o',f'lowerdir={lower},upperdir={upper},workdir={work}',str(merged)],check=True)
        try:
            assert merged.stat().st_mode&0o777==mode
            p=subprocess.run([sys.executable,'-c',child],cwd=merged,capture_output=True,text=True)
            assert p.returncode==0,p.stderr
            data=json.loads(p.stdout)
            assert data=={'public':want,'exec':want,'private':False},data
            print(f'PASS: merged root {mode:o}, capability-free UID81 public/exec={want}, private seed denied')
        finally:subprocess.run(['umount',str(merged)],check=True)
finally:
    fixture.doCleanups()
