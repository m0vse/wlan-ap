#!/usr/bin/env python3
"""Actual Miami provider, regular-file UBI fixtures, no network or real devices.

Run as root on Linux to exercise real root-owned private-cache validation.
Reuses the provider's existing geometry/env/storage fixture, not a fake writer.
"""
from pathlib import Path
import os
import sys
import hashlib
import subprocess
import tempfile

if os.geteuid() != 0 or not sys.platform.startswith('linux'):
    raise SystemExit('Requires root on Linux for the real cache ownership checks')

if '--size-only' in sys.argv:
    # Exercise the actual fetch function directly; no geometry/network/UBI
    # boundary is entered for this formatting regression.
    source=Path(__file__).with_name('miami-oem-persistent.sh.in').read_text()
    fetch=source[source.index('fetch() {'):source.index('readback() {')]
    with tempfile.TemporaryDirectory(prefix='miami-cache-size-') as td:
        root=Path(td).resolve();cache=root/'cache';cache.mkdir(mode=0o700)
        (root/'tmp').mkdir();tools=root/'bin';tools.mkdir()
        data=b'complete cached object\n';member=cache/'payload';member.write_bytes(data);member.chmod(0o600)
        wc=tools/'wc';wc.write_text('''#!/usr/bin/env python3
import os,sys
count=len(sys.stdin.buffer.read())
if 'TEST_WC_COUNT' in os.environ:print(os.environ['TEST_WC_COUNT'])
else:print(f'{count:12d}')
if os.environ.get('TEST_WC_ERROR'):sys.exit(1)
''');wc.chmod(0o700)
        driver='fail(){ echo "cache refused" >&2;exit 1; };wget(){ fail; };'+fetch+'\nfetch payload "$1" "$2"'
        env={**os.environ,'PATH':str(tools)+':'+os.environ['PATH'],'R':str(root),
             'CAMBIUM_INSTALL_CACHE_DIR':str(cache),'CAMBIUM_INSTALL_LOCAL_ONLY':'1'}
        def check(size,ok,**extra):
            dest=root/'tmp/payload';dest.unlink(missing_ok=True)
            p=subprocess.run(['sh','-c',driver,'fixture',hashlib.sha256(data).hexdigest(),size],
                             env={**env,**extra},capture_output=True,text=True)
            assert (p.returncode==0)==ok,(size,p.stdout,p.stderr)
            assert member.read_bytes()==data
            if ok:assert dest.read_bytes()==data
            else:assert not dest.exists()
        check(str(len(data)),True)
        check(str(len(data)),True,TEST_WC_COUNT='\t  '+str(len(data))+'  ')
        for size in ('','0','-1','bad','1.5',' '+str(len(data)),str(len(data)+1)):
            check(size,False)
        for count in ('bad','',f'1 {len(data)}','1.5','-1'):
            check(str(len(data)),False,TEST_WC_COUNT=count)
        check(str(len(data)),False,TEST_WC_ERROR='1')
        print('PASS: 15 numeric cache-size cases; padded wc accepted, malformed/mismatching counts and wc failures refused before local copy')
    raise SystemExit(0)

fixture = Path(__file__).with_name('test-oem-persistent.py')
text = fixture.read_text()
text = text[:text.index(" initial();assert run(['check'])")]
# Synchronization remains inside the fixture, never flush the host's disks.
text = text.replace("if cmd=='wget':", "if cmd=='sync':sys.exit()\nif cmd=='wget':")
text = text.replace("for cmd in ['strace',", "for cmd in ['sync','strace',")
extra = r'''
 cache=w/'cache';cache.mkdir(mode=0o700)
 objects={}
 for slot in (0,1):
  objects[f'miami-{slot}-kernel']=kernel
  objects[f'miami-{slot}-rootfs']=rootfs
  objects[f'miami-{slot}-pair.json']=b'{"slot":'+str(slot).encode()+b'}\n'
 env.update(CAMBIUM_INSTALL_CACHE_DIR=str(cache),CAMBIUM_INSTALL_LOCAL_ONLY='1',
            CAMBIUM_INSTALL_SERVER='http://server-is-gone.invalid',ENROLMENT_READY='1')
 for slot in (0,1):
  name=f'miami-{slot}-pair.json';data=objects[name]
  env.update({f'PAIR{slot}':name,f'PAIR{slot}_SHA':hashlib.sha256(data).hexdigest(),
              f'PAIR{slot}_SIZE':str(len(data))})
 def frozen_cache():
  cache.chmod(0o700)
  for p in cache.iterdir():p.unlink()
  for name,data in objects.items():
   p=cache/name;p.write_bytes(data);p.chmod(0o600)
 for slot in (0,1):
  for role in ('kernel','rootfs','pair.json'):
   for fault in ('missing','truncated','digest','symlink','hardlink','mode','owner'):
    initial(slot);frozen_cache()
    target=cache/f'miami-{slot}-{role}'
    if fault=='missing':target.unlink()
    elif fault=='truncated':target.write_bytes(target.read_bytes()[:-1])
    elif fault=='digest':target.write_bytes(b'Z'*len(target.read_bytes()))
    elif fault=='symlink':target.unlink();target.symlink_to(r/'tmp'/f'miami-{slot}-kernel')
    elif fault=='hardlink':os.link(target,cache/'extra-link')
    elif fault=='mode':target.chmod(0o644)
    elif fault=='owner':os.chown(target,81,81)
    before={n:(r/f'dev/{n}').read_bytes() for n in ('ubi9_3','mtd21ro',f'mtd{3 if slot==0 else 2}ro')}
    calls=run(args,False)
    assert not calls,(slot,role,fault,calls)
    assert all((r/f'dev/{n}').read_bytes()==v for n,v in before.items())
  for fault in ('missing-cache','cache-mode','cache-link'):
   initial(slot);frozen_cache();opts={}
   if fault=='missing-cache':opts['CAMBIUM_INSTALL_CACHE_DIR']=''
   elif fault=='cache-mode':cache.chmod(0o755)
   else:
    alias=w/'cache-alias';alias.symlink_to(cache,target_is_directory=True)
    opts['CAMBIUM_INSTALL_CACHE_DIR']=str(alias)
   assert not run(args,False,opts)
   if fault=='cache-link':alias.unlink()
  # Server and wget are unavailable. All three exact objects are in the
  # private cache before any storage mutation, and arm is entirely local.
  initial(slot);frozen_cache()
  protected={n:(r/f'dev/{n}').read_bytes() for n in ('ubi9_3','mtd21ro',f'mtd{3 if slot==0 else 2}ro')}
  calls=run(args)
  for role in ('kernel','rootfs','pair.json'):
   name=f'miami-{slot}-{role}'
   assert (r/'tmp'/name).read_bytes()==objects[name]
  assert 'wget' not in calls
  assert all((r/f'dev/{n}').read_bytes()==v for n,v in protected.items())
  calls=run(['arm','--yes'])
  assert 'wget' not in calls
  assert json.loads((w/'env').read_text())['image']==str(1-slot)
 print('PASS: 48 pre-write cache refusals; both-slot offline install/arm; exact cached descriptors; no HTTP or protected-data mutation')
'''
exec(compile(text + extra, str(fixture), 'exec'), {'__file__': str(fixture)})
