#!/usr/bin/env python3
"""Verify shipped files and target module/timeout behavior; no AP access."""
import hashlib,json,os,pathlib,subprocess,tempfile,time

root=pathlib.Path(os.environ['OW_DFS_TARGET_ROOT'])
source=pathlib.Path(os.environ['OW_DFS_SOURCE'])
image=pathlib.Path(os.environ['OW_DFS_IMAGE'])
work=pathlib.Path(tempfile.mkdtemp(prefix='dfs-built-image-tests.'))
qemu=os.environ.get('OW_DFS_QEMU','/usr/bin/qemu-aarch64')
assert qemu in ('/usr/bin/qemu-aarch64','/usr/bin/qemu-arm')
interpreter='/lib/ld-musl-armhf.so.1' if qemu.endswith('qemu-arm') else '/lib/ld-musl-aarch64.so.1'
ucode=[qemu,'-L',str(root),str(root/'usr/bin/ucode'),'-L',str(root/'usr/lib/ucode')]
cases=[]
for installed,reviewed in [('usr/share/ucentral/dfs_cac.uc','system/dfs_cac.uc'),('usr/share/ucentral/health.uc','system/health.uc'),('usr/sbin/ucentral-state','ucentral-state')]:
 assert (root/installed).read_bytes()==(source/reviewed).read_bytes(),installed
 cases.append({'case':'exact-shipped-'+installed,'passed':True})
search="REQUIRE_SEARCH_PATH = [ '/usr/share/ucentral/*.uc', ...REQUIRE_SEARCH_PATH ];"
for name in ('usr/share/ucentral/health.uc','usr/sbin/ucentral-state'):
 assert search in (root/name).read_text(),name
 p=subprocess.run(ucode+['-c','-o',str(work/pathlib.Path(name).name),str(root/name)],capture_output=True,text=True)
 assert p.returncode==0,(name,p.stderr)
 cases.append({'case':'target-compile-'+name,'passed':True})
p=subprocess.run(ucode+['-p',search+" type(require('dfs_cac').collect)"],capture_output=True,text=True)
assert p.returncode==0 and p.stdout=='function',(p.returncode,p.stdout,p.stderr)
cases.append({'case':'target-dynamic-require-exact-production-search-path','passed':True})
db=(root/'lib/apk/db/installed').read_text();versions={}
for record in db.split('\n\n'):
 fields=dict(line.split(':',1) for line in record.splitlines() if ':' in line)
 if fields.get('P') in ('ucentral-schema','ucentral-state','hostapd-utils','coreutils-timeout'):
  versions[fields['P']]=fields['V']
assert versions['ucentral-schema'].endswith('-r14') and versions['ucentral-state']=='2',versions
assert versions['hostapd-utils'] and versions['coreutils-timeout'],versions
timeout=root/'usr/libexec/timeout-coreutils'
assert timeout.is_file() and timeout.stat().st_mode & 0o111
elf=subprocess.run(['readelf','-l',str(timeout)],capture_output=True,text=True,check=True).stdout
needed=subprocess.run(['readelf','-d',str(timeout)],capture_output=True,text=True,check=True).stdout
assert interpreter in elf and '[libc.so]' in needed
assert (root/interpreter.lstrip('/')).exists() and (root/'lib/libc.so').exists()
cases.append({'case':'standard-package-and-timeout-ELF-closure','passed':True})
fixture=work/'slow-child.py'
fixture.write_text("import pathlib,subprocess,time,sys\np=subprocess.Popen(['/bin/sleep','30'])\npathlib.Path(sys.argv[1]).write_text(str(p.pid))\ntime.sleep(30)\n")
started=time.monotonic()
p=subprocess.run([qemu,'-L',str(root),str(timeout),'-s','KILL','2','/usr/bin/python3',str(fixture),str(work/'pid')],capture_output=True,text=True,timeout=6)
elapsed=time.monotonic()-started
assert p.returncode in (137,-9) and 1.8<=elapsed<5,(p.returncode,elapsed,p.stderr)
pid=int((work/'pid').read_text());status=pathlib.Path('/proc')/str(pid)/'status'
for _ in range(10):
 if not status.exists() or '\nState:\tZ' in status.read_text():break
 time.sleep(.05)
assert not status.exists() or '\nState:\tZ' in status.read_text(),('live child left by timeout',pid)
cases.append({'case':'actual-shipped-target-timeout-kills-command-and-child','passed':True,'elapsed_seconds':round(elapsed,3)})
print(json.dumps({'passed':True,'count':len(cases),'cases':cases,'package_versions':versions,
 'image':str(image),'image_size':image.stat().st_size,'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),
 'tip_metadata':(root/'etc/openwrt_release').read_text(),
 'scope':'Actual extracted immutable image bytes, selected ARM target ucode compile/dynamic-require and target timeout through QEMU; private fake sleeping command only. No live AP, daemon start, ubus connection, network, flash or reboot.'},indent=2))
