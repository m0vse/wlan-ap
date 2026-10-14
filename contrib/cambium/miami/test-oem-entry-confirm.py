from pathlib import Path
import json,os,re,shutil,struct,subprocess,tempfile,unittest
repo=Path(os.environ.get('MIAMI_OEM_FRAMEWORK_REPO',Path(__file__).resolve().parents[3]));helper=Path(__file__).with_name('ab')/'confirm-oem-entry.sh'
class ConfirmationTests(unittest.TestCase):
 def fixture(self,source):
  temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);r=Path(temp.name);kit=r/'kit';(kit/'shared').mkdir(parents=True);profiles=kit/'profiles/X7-35X';shutil.copytree(repo/'tools/oem-migration/unified/profiles/X7-35X',profiles)
  for n in ('common','protection','network'):shutil.copyfile(repo/f'tools/oem-migration/unified/lib/{n}.sh',kit/f'shared/oem-{n}.sh')
  body=helper.read_text().replace('[ "$(id -u)" = 0 ] || exit 1',': # UID actor').replace('. "$kit/shared/oem-network.sh"','. "$kit/shared/oem-network.sh"\noem_bounded_run(){ shift; "$@"; } # host network/timer actor')
  # Single pass: generated /tmp fixture prefixes must not be remapped.
  body=re.sub(r"/(etc|sys|proc|dev|tmp)/",lambda m:str(r)+m.group(0),body)
  body=body.replace('root='+str(r)+'/dev/ubiblock0_1','root=/dev/ubiblock0_1')
  # Keep inspected FW config's actual device spelling in its validation.
  body=body.replace('dev="'+str(r)+'/dev/mtd$env_mtd"','dev="/dev/mtd$env_mtd"')
  out=kit/'confirm-oem-entry.sh';out.write_text(body)
  rows=[line.split('\t') for line in (profiles/f'mtd-slot{source}.tsv').read_text().splitlines()];indices={row[0]:i for i,row in enumerate(rows)}
  for i,(name,domain,offset,size,kind,erase,write,role) in enumerate(rows):
   node=r/f'sys/class/mtd/mtd{i}';node.mkdir(parents=True);chip=r/'chips'/domain;chip.mkdir(parents=True,exist_ok=True);(node/'device').symlink_to(chip)
   for k,v in dict(name=name,type=kind,offset=offset,size=size,erasesize=erase,writesize=write,flags='0xc00' if role in ('target','environment') else '0x800').items():(node/k).write_text(v)
  (r/'proc/device-tree/cambium-platform').mkdir(parents=True);(r/'proc/device-tree/cambium-platform/board-sku').write_bytes(struct.pack('>I',44));(r/'etc').mkdir();(r/'tmp').mkdir();(r/'dev').mkdir()
  (r/'etc/version').write_text(''.join(k+'='+v+'\n' for k,v in [line.split('\t') for line in (profiles/'source.tsv').read_text().splitlines()]))
  target=1-source;bank='rootfs' if target==0 else 'rootfs_1';(r/'proc/cmdline').write_text('ubi.mtd='+bank+' root=/dev/ubiblock0_1');(r/'proc/mounts').write_text(f'{r}/dev/ubiblock0_1 / squashfs ro 0 0\n')
  u=r/'sys/class/ubi/ubi0';u.mkdir(parents=True);(u/'mtd_num').write_text(str(indices[bank]))
  for i,name,magic in ((0,'kernel',bytes.fromhex('d00dfeed')),(1,'ubi_rootfs',b'hsqs')):
   n=r/f'sys/class/ubi/ubi0_{i}';n.mkdir();(n/'name').write_text(name);(n/'upd_marker').write_text('0');(n/'corrupted').write_text('0');(r/f'dev/ubi0_{i}').write_bytes(magic+b'unchanged synthetic OEM media')
  (r/'dev/old-OW-bank').write_bytes(b'unchanged working OpenWiFi media');(r/'dev/old-cert-store').write_bytes(b'inert unchanged old certificate journal')
  (r/'etc/fw_env.config').write_text(f'/dev/mtd{indices["0:APPSBLENV"]} 0 0x10000 0x10000\n')
  part='rootfs' if source==0 else 'rootfs_1';offset='0xc0000' if source==0 else '0x60c0000';prior=f"nand device 0 && setenv mtdids nand0=nand0 && setenv mtdparts 'mtdparts=nand0:0x6000000@{offset}(fs)' && ubi part fs && ubi read 0x60000000 kernel && setenv bootargs console=ttyMSM0,115200n8 ubi.mtd={part} root=/dev/ubiblock0_1 rootfstype=squashfs rootwait && bootm 0x60000000#config@mi01.6-acadia-slot{source}"
  state={'bootcmd':f'run miami_boot{source}','bootcount':'9','image':str(source),'changing_bootcmd':'1',f'miami_boot{source}':prior,'miami_oem_once_source':str(source),'miami_oem_once_target':str(target),'miami_oem_once_state':'started','miami_oem_once_source_release':'b6d1a26f','serial#':'untouched','factory.region':'untouched'};(r/'env.json').write_text(json.dumps(state));(r/'calls').write_text('')
  tools=r/'bin';tools.mkdir();backend=r/'backend.py';backend.write_text('''import json,os,sys
from pathlib import Path
r=Path(os.environ['FIXTURE']);cmd=sys.argv[1];args=sys.argv[2:];state=json.loads((r/'env.json').read_text());fault=os.environ.get('FAULT','')
if cmd=='ip':
 if 'route' in args:print('default via 192.0.2.1 dev eth0')
 else:print('2: eth0 inet 192.0.2.2/24 scope global eth0')
 sys.exit()
if cmd=='ping':
 if fault=='probe-drift':
  state['miami_boot'+state['miami_oem_once_source']]='wrong';(r/'env.json').write_text(json.dumps(state))
 sys.exit(124 if fault=='probe-timeout' else 1 if fault=='probe' else 0)
if cmd=='wget':
 if fault=='probe-drift':
  state['miami_boot'+state['miami_oem_once_source']]='wrong';(r/'env.json').write_text(json.dumps(state))
 sys.exit(124 if fault=='probe-timeout' else 1 if fault=='probe' else 0)
if cmd=='sync':sys.exit()
if args[:1]==['-c']:args=args[2:]
if cmd=='fw_printenv':
 if fault=='counter-read' and args[:1]==['bootcount'] and (r/'calls').read_text().splitlines()[-1:]==['confirm']:print('bootcount=0');sys.exit(1)
 if not args:
  print(''.join(k+'='+v+'\\n' for k,v in state.items()),end='')
  if fault=='duplicate-env':print('serial#=duplicate')
 elif args[0] in state:print(args[0]+'='+state[args[0]])
 else:sys.exit(1)
 sys.exit()
assert cmd=='fw_setenv' and args[0]=='-s';label=Path(args[1]).name
with (r/'calls').open('a') as out:out.write(label+'\\n')
if fault==label or (fault in ('rollback','counter-rollback') and label=='rollback'):sys.exit(1)
if fault=='counter-write' and label=='confirm':sys.exit(1)
for row in Path(args[1]).read_text().splitlines():
 k,*v=row.split(' ',1)
 if v:state[k]=v[0]
 else:state.pop(k,None)
if fault in ('readback','rollback') and label=='confirm':state['bootcmd']='wrong'
if fault in ('counter-stale','counter-rollback') and label=='confirm':state['bootcount']='9'
if fault=='factory' and label=='confirm':state['serial#']='changed'
(r/'env.json').write_text(json.dumps(state))
''')
  for cmd in ('fw_printenv','fw_setenv','ip','wget','ping','sync'):
   p=tools/cmd;p.write_text('#!/bin/sh\nexec python3 "$FIXTURE/backend.py" '+cmd+' "$@"\n');p.chmod(0o755)
  return r,out,state
 def invoke(self,r,out,fault='',url=None):
  return subprocess.run(([os.environ.get('MIAMI_CONFIRM_SHELL','sh')]+([os.environ.get('MIAMI_CONFIRM_APPLET','')] if os.environ.get('MIAMI_CONFIRM_APPLET') else []))+[str(out),'--yes']+(['--network-url',url] if url else []),env={**os.environ,'FIXTURE':str(r),'FAULT':fault,'PATH':str(r/'bin')+':'+os.environ['PATH']},capture_output=True,text=True)
 def test_both_slots_confirm_only_env_preserving_media(self):
  for source in (0,1):
   r,out,before=self.fixture(source);media={p:p.read_bytes() for p in (r/'dev').iterdir()};result=self.invoke(r,out);self.assertEqual(result.returncode,0,result.stderr);state=json.loads((r/'env.json').read_text());self.assertEqual(state['bootcount'],'0');self.assertEqual(state['bootcmd'],'bootipq');self.assertEqual(state['image'],str(1-source));self.assertEqual(state['miami_oem_once_state'],'confirmed');self.assertEqual(media,{p:p.read_bytes() for p in media});self.assertEqual(state[f'miami_boot{source}'],before[f'miami_boot{source}'])
 def test_wrong_state_root_version_route_probe_refuse_without_env_write(self):
  for fault in ('state','version','root','route','probe','probe-timeout','bad-url'):
   r,out,_=self.fixture(0)
   if fault in ('state','route'):
    s=json.loads((r/'env.json').read_text());s['miami_oem_once_state' if fault=='state' else 'miami_boot0']='wrong';(r/'env.json').write_text(json.dumps(s))
   if fault=='version':(r/'etc/version').write_text('PRODUCT=miami\nVERSION=wrong\n')
   if fault=='root':(r/'proc/mounts').write_text('tmpfs / tmpfs rw 0 0\n')
   before=(r/'env.json').read_bytes();result=self.invoke(r,out,fault,'http://user@192.0.2.3/' if fault=='bad-url' else 'http://192.0.2.3/');self.assertNotEqual(result.returncode,0);self.assertEqual(before,(r/'env.json').read_bytes());self.assertEqual((r/'calls').read_text(),'')
 def test_failed_batch_readback_and_factory_drift_rollback(self):
  for fault in ('confirm','readback','factory','rollback','counter-write','counter-read','counter-stale','counter-rollback'):
   r,out,_=self.fixture(1);result=self.invoke(r,out,fault);self.assertNotEqual(result.returncode,0);self.assertNotIn('confirmed;',result.stdout)
   if fault in ('rollback','factory','counter-rollback'):self.assertIn('rollback is uncertain',result.stderr)
   else:
    s=json.loads((r/'env.json').read_text());self.assertEqual(s['bootcount'],'0');self.assertEqual(s['bootcmd'],'run miami_boot1');self.assertEqual(s['image'],'1')
 def test_post_probe_source_drift_refuses_before_env_batch(self):
  r,out,_=self.fixture(0);media={p:p.read_bytes() for p in (r/'dev').iterdir()};result=self.invoke(r,out,'probe-drift');self.assertNotEqual(result.returncode,0);self.assertEqual((r/'calls').read_text(),'');self.assertEqual(media,{p:p.read_bytes() for p in media})
 def test_gluebi_parent_proof_and_optional_health_port(self):
  for source in (0,1):
   r,out,_=self.fixture(source);view=r/'sys/class/mtd/mtd29';view.mkdir();(view/'type').write_text('ubi');(view/'name').write_text('ubi_rootfs');(view/'device').symlink_to(r/'sys/class/ubi/ubi0_1');(r/'proc/mounts').write_text(f'{r}/dev/mtdblock29 / squashfs ro,relatime 0 0\n');result=self.invoke(r,out,url='http://192.0.2.2:8080/health');self.assertEqual(result.returncode,0,result.stderr)
  for fault in ('parent','name','other-bank'):
   r,out,_=self.fixture(0);view=r/'sys/class/mtd/mtd31';view.mkdir();(view/'type').write_text('ubi');(view/'name').write_text('foreign' if fault=='name' else 'ubi_rootfs');parent=r/f'sys/class/ubi/ubi0_{0 if fault=="parent" else 1}';
   if fault=='other-bank':parent=r/'sys/class/ubi/ubi1_1';parent.mkdir()
   (view/'device').symlink_to(parent);(r/'proc/mounts').write_text(f'{r}/dev/mtdblock31 / squashfs ro 0 0\n');result=self.invoke(r,out);self.assertNotEqual(result.returncode,0);self.assertEqual((r/'calls').read_text(),'')
 def test_malformed_health_ports_refuse_before_env_write(self):
  for port in ('0','65536','bad','80:81'):
   r,out,_=self.fixture(0);result=self.invoke(r,out,url='http://192.0.2.2:'+port+'/');self.assertNotEqual(result.returncode,0);self.assertEqual((r/'calls').read_text(),'')
 def test_malformed_full_env_refuses_before_confirmation_batch(self):
  r,out,_=self.fixture(0);result=self.invoke(r,out,'duplicate-env');self.assertNotEqual(result.returncode,0);self.assertEqual((r/'calls').read_text(),'')
 def opaque_root(self,r,extent=192):
  data=bytearray(extent);data[:4]=b'hsqs';struct.pack_into('<I',data,4,1);struct.pack_into('<I',data,12,65536);struct.pack_into('<HH',data,28,4,0);struct.pack_into('<Q',data,40,extent)
  (r/'dev/ubi0_1').write_bytes(data);(r/'dev/mtd29ro').write_bytes(data);(r/'dev/mtdblock29').symlink_to(r/'dev/mtd29ro')
  node=r/'sys/class/ubi/ubi0_1'
  for k,v in [('reserved_ebs',362),('usable_eb_size',126976),('data_bytes',45965312)]:(node/k).write_text(str(v))
  (r/'sys/class/ubi/ubi0/min_io_size').write_text('2048')
  view=r/'sys/class/mtd/mtd29';view.mkdir()
  for k,v in [('type','ubi'),('name','ubi_rootfs'),('size',45965312),('erasesize',126976),('writesize',2048)]:(view/k).write_text(str(v))
  (r/'proc/mounts').write_text(f'{r}/dev/mtdblock29 / squashfs ro,relatime 0 0\n')
  return view
 def test_oem_startup_selector_and_absent_parent_content_binding_both_slots(self):
  for source in (0,1):
   r,out,_=self.fixture(source);view=self.opaque_root(r);state=json.loads((r/'env.json').read_text());state['image']=str(1-source);(r/'env.json').write_text(json.dumps(state));media={p:p.read_bytes() for p in (r/'dev').iterdir()};result=self.invoke(r,out);self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(media,{p:p.read_bytes() for p in media})
 def test_content_binding_rejects_bad_geometry_header_extent_and_short_reads(self):
  for fault in ('wrong-bank','view-short','child-short','extent','high','header','version','capacity','geometry','selector'):
   r,out,_=self.fixture(0);view=self.opaque_root(r)
   if fault in ('wrong-bank','view-short','extent','high','header','version'):
    p=r/'dev/mtd29ro';data=bytearray(p.read_bytes())
    if fault=='wrong-bank':data[100]=1
    elif fault=='view-short':data=data[:130]
    elif fault=='extent':struct.pack_into('<Q',data,40,160)
    elif fault=='high':struct.pack_into('<Q',data,40,1<<32)
    elif fault=='header':data=data[:64]
    else:struct.pack_into('<H',data,28,3)
    p.write_bytes(data)
   if fault=='child-short':(r/'dev/ubi0_1').write_bytes((r/'dev/ubi0_1').read_bytes()[:128])
   if fault=='capacity':(view/'size').write_text('96')
   if fault=='geometry':(view/'writesize').write_text('4096')
   if fault=='selector':
    state=json.loads((r/'env.json').read_text());state['image']='2';(r/'env.json').write_text(json.dumps(state))
   before=(r/'env.json').read_bytes();result=self.invoke(r,out);self.assertNotEqual(result.returncode,0,fault);self.assertEqual((r/'calls').read_text(),'');self.assertEqual(before,(r/'env.json').read_bytes())
if __name__=='__main__':unittest.main()
