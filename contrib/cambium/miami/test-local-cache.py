#!/usr/bin/env python3
"""Actual Miami provider, regular-file UBI fixtures, no network or real devices.

Run as root on Linux to exercise real root-owned private-cache validation.
Reuses the provider's existing geometry/env/storage fixture, not a fake writer.
"""
from pathlib import Path
import os
import sys

if os.geteuid() != 0 or not sys.platform.startswith('linux'):
    raise SystemExit('Requires root on Linux for the real cache ownership checks')

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
