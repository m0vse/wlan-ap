"""Run actual candidate fixtures with additional isolated reset fault cases."""
from pathlib import Path
import sys

fixture = Path(sys.argv[1]).resolve()
text = fixture.read_text()
# Keep synchronization isolated: record the barrier, never sync the host disk.
text = text.replace("if cmd=='wget':", "if cmd=='sync':\n if os.environ.get('FAIL_SYNC'):sys.exit(1)\n sys.exit()\nif cmd=='wget':")
text = text.replace("for cmd in ['strace',", "for cmd in ['sync','strace',")
anchor = ' # A prior image is admitted only as the exact independently pinned pair.'
extra = '''
 # Reviewer-only fresh reset rejection/fault cases, using actual installer.
 for slot in (0,1):
  for fault in ('converted','wrong-store','missing-job','bad-image','busy-mapping',
                'journal-write','sync','cert-delete','cert-create','clear-job'):
   initial(slot);run(args)
   state=json.loads((w/'env').read_text())
   state.update(miami_installer_target=str(slot),miami_installer_job='a'*64,miami_installer_image='b'*64)
   opts={};mapping=r/'sys/class/block/ubiblock9_1'
   if fault=='converted':state['miami_ab_version']='1'
   if fault=='wrong-store':(r/'sys/class/ubi/ubi9_4/reserved_ebs').write_text('63')
   if fault=='missing-job':state.pop('miami_installer_job')
   if fault=='bad-image':state['miami_installer_image']='G'*64
   if fault=='busy-mapping':mapping.touch()
   if fault=='journal-write':opts['FAIL_KEY']='miami_storage_pending'
   if fault=='sync':opts['FAIL_SYNC']='1'
   if fault=='cert-delete':opts['FAIL_COMMAND']='ubirmvol certificates'
   if fault=='cert-create':opts['FAIL_COMMAND']='ubimkvol certificates'
   if fault=='clear-job':opts['FAIL_KEY']='miami_installer_job'
   (w/'env').write_text(json.dumps(state))
   protected={n:(r/f'dev/{n}').read_bytes() for n in ('ubi9_3','mtd21ro',f'mtd{3 if slot==0 else 2}ro')}
   calls=run(fresh,False,opts)
   assert all((r/f'dev/{n}').read_bytes()==v for n,v in protected.items()),fault
   state=json.loads((w/'env').read_text())
   assert state['bootcmd']=='bootipq' and state['image']==str(1-slot),fault
   if fault in ('converted','wrong-store','missing-job','bad-image','busy-mapping','journal-write','sync'):
    assert 'ubirmvol' not in calls,fault
   if fault in ('sync','cert-delete','cert-create','clear-job'):
    assert state['miami_storage_pending'].startswith('install:'),fault
    if mapping.exists():mapping.unlink()
    run(['arm','--yes'],False)
   if mapping.exists():mapping.unlink()
   print('PASS fresh fault',slot,fault)
'''
text = text.replace(anchor, extra + '\n' + anchor)
text = text.replace("u=r/'sys/class/ubi/ubi9';free=u/'avail_eraseblocks'", "if '-N' in a and os.environ.get('FAIL_COMMAND')==cmd+' '+a[a.index('-N')+1]:sys.exit(1)\nu=r/'sys/class/ubi/ubi9';free=u/'avail_eraseblocks'")
exec(compile(text, str(fixture), 'exec'), {'__file__': str(fixture)})
