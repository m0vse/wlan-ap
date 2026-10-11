from pathlib import Path
import tempfile,os,subprocess,hashlib,json
base=Path(os.environ['CHEETAH_BUILD_ROOT']);review=base/'cheetah-format2-stock-bridge';old=base/'outgoing-source/rootfs';bb=old/'bin/busybox';parser=Path(os.environ['WLAN_AP_SOURCE_DIR'])/'tools/oem-migration/recovery/scripts/lib/cambium-installer-settings.sh'
with tempfile.TemporaryDirectory(prefix='cheetah-central-metadata.') as t:
 r=Path(t);b=r/'bin';b.mkdir();f=r/'file';f.write_text('private');d=r/'dir';d.mkdir(mode=0o700)
 for name in ['ls','awk']:
  p=b/name;p.write_text(f'#!/bin/sh\nexec /usr/bin/qemu-aarch64 -L "{old}" "{bb}" {name} "$@"\n');p.chmod(0o755)
 env=dict(os.environ,PATH=str(b)+':'+os.environ['PATH'])
 def call(p):return subprocess.run(['/usr/bin/qemu-aarch64','-L',str(old),str(bb),'ash','-c','. "$1"; ow_settings_metadata "$2"','metadata',str(parser),str(p)],env=env,capture_output=True,text=True)
 f.chmod(0o600);out=call(f);assert out.returncode==0 and out.stdout.strip()==f'{os.getuid()}:600:1'
 out=call(d);assert out.returncode==0 and out.stdout.strip()==f'{os.getuid()}:700:{d.stat().st_nlink}'
 os.link(f,r/'linked');assert call(f).stdout.strip()==f'{os.getuid()}:600:2';(r/'linked').unlink()
 for mode in [0o644,0o1600,0o4600]:
  f.chmod(mode);assert call(f).returncode!=0
 assert call(r/'absent').returncode!=0
 receipt={'passed':True,'cases':7,'central_stager_sha256':hashlib.sha256(parser.read_bytes()).hexdigest(),'stock_busybox_sha256':hashlib.sha256(bb.read_bytes()).hexdigest(),'interface':'ow_settings_metadata PATH -> uid:octalmode:nlink','scope':'Exact central parser, actual stock ARM64 ash/ls/awk; private file/directory, hardlink, unsafe modes, missing file. No AP.'}
 (review/'central-metadata-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
