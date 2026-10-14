#!/usr/bin/env python3
"""Execute actual stage/cleanup bodies; synthetic flash, crypto and ENV actors.
Proves partial-stage recovery control flow, not real hardware or image validity.
"""
from pathlib import Path
import tempfile, subprocess, os, json, hashlib, re
repo=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='miami-stage-retry-') as td:
 r=Path(td).resolve();kit=r/'kit';kit.mkdir();(r/'tmp').mkdir();(r/'etc').mkdir();(r/'etc/openwrt_release').write_text("DISTRIB_TIP='TIP-devel-b6d1a26f'\n")
 (r/'proc/self').mkdir(parents=True);(r/'proc/mounts').write_text('overlay / overlay rw 0 0\n');(r/'proc/self/mountinfo').write_text('')
 (r/'proc/sys/kernel/random').mkdir(parents=True);(r/'proc/sys/kernel/random/boot_id').write_text('12345678-1234-1234-1234-123456789abc')
 (r/'sys/class/ubi/ubi0').mkdir(parents=True);(r/'sys/class/ubi/ubi0/avail_eraseblocks').write_text('180');(r/'dev').mkdir()
 fit=r/'bridge.itb';fit.write_bytes(bytes.fromhex('d00dfeed')+b'\x00\x01config@mi01.6-acadia-bridge-slot0\x00')
 state=r/'env.json';log=r/'operations';tools=r/'bin';tools.mkdir()
 actor=tools/'envactor';actor.write_text('''#!/usr/bin/env python3
import os,json,sys
from pathlib import Path
p=Path(os.environ['STATE']);e=json.loads(p.read_text());a=sys.argv[1:]
if a[0]=='get':print(e.get(a[1],''))
else:
 if a[2]:e[a[1]]=a[2]
 else:e.pop(a[1],None)
 p.write_text(json.dumps(e))
''');actor.chmod(0o755)
 funcs=r/'actors.sh';funcs.write_text(r'''
readlink(){ case "$2" in */sys/class/ubi/ubi0_5) echo "$ROOT/sys/class/ubi/ubi0/ubi0_5";;*) command readlink "$@";;esac; }
stat(){ [ "${FAIL_STAT:-0}" = 0 ] || return 1;case "$4" in *ubi0_5|*charalias) echo fa:5;;*) echo 0:0;;esac; }
ab_identity(){ AB_FAMILY=miami AB_MODEL=X7-35X AB_SKU=0000002c AB_ACTIVE=$SLOT AB_TARGET=$((1-SLOT)) AB_ACTIVE_MTD=$((2+SLOT)) AB_ACTIVE_UBI=ubi0 AB_TARGET_MTD=$((3-SLOT)) AB_LEB=126976; }
ab_miami_storage_context(){ :; };ab_miami_upgrade_geometry(){ :; };ab_miami_certificate_mount(){ :; };ab_miami_readiness_identity(){ :; };ab_miami_native_connected(){ :; }
ab_miami_slot_command(){ echo legacy$1; };ab_miami_bridge_prior_pair(){ echo source-proof >> "$LOG"; }
ab_getenv(){ envactor get "$1"; };ab_setenv(){ envactor set "$1" "$2"; }
ab_ubi_volume(){ case "$2" in kernel) echo ubi0_0;;rootfs) echo ubi0_1;;*) return 1;;esac; }
ab_certificate_export(){ AB_CERTIFICATE_ARCHIVE=$ROOT/archive;AB_CERTIFICATE_DESCRIPTOR=$ROOT/descriptor;echo fixture > "$AB_CERTIFICATE_ARCHIVE";echo fixture > "$AB_CERTIFICATE_DESCRIPTOR"; }
sysupgrade(){ echo config > "$2"; };openssl(){ printf '%064d\n' 1; };get_mac_label_dt(){ echo 02:00:00:00:00:01; }
ab_lebs(){ echo $((($1+126975)/126976)); };ab_ubi_node(){ :; }
hexdump(){ echo d00dfeed; }
head(){ case "$3" in *ubi0_0) echo HASHKERNEL;;*ubi0_1) echo HASHROOT;;*) command head "$@";;esac; }
sha256sum(){
 if [ "$#" = 0 ];then read -r marker;case "$marker" in HASHKERNEL) if [ "$SLOT" = 0 ];then echo 9c22c101aad1325ca0e1cfac9c52a3d84b3c3a5bfc46a99667dc491c3765712b;else echo dcf685056218b88a8685ea2c60c8cc0fceef5a39dcc168691541f9fb90e4a255;fi;;HASHROOT) echo 1ecd75a5487c1a014d05adce627bf746b163df7b3f275deff258c77d9564dae9;;*) return 1;;esac
 else command sha256sum "$@";fi
}
ubimkvol(){ mkdir "$ROOT/sys/class/ubi/ubi0_$3";echo "$5" > "$ROOT/sys/class/ubi/ubi0_$3/name";echo "250:$3" > "$ROOT/sys/class/ubi/ubi0_$3/dev";touch "$ROOT/dev/ubi0_$3";echo create$3 >> "$LOG"; }
ubiupdatevol(){ echo failed-aux-write >> "$LOG";return 37; }
ubirmvol(){ echo remove$3 >> "$LOG";rm -rf "$ROOT/sys/class/ubi/ubi0_$3" "$ROOT/dev/ubi0_$3"; }
sync(){ :; }
''')
 for name in ('stage-bridge.sh','cleanup-bridge.sh'):
  s=(repo/'contrib/cambium/miami/ab'/name).read_text();lines=[]
  for line in s.splitlines():
   if line.startswith('. '):
    if line=='. /lib/functions/system.sh':lines.append('. "$ACTORS"')
    continue
   lines.append(line)
  s='\n'.join(lines)+'\n';s=s.replace('[ -c "$dev" ]','[ -f "$dev" ]') # Synthetic device node actor only
  s=re.sub(r'/(?:proc|sys|dev|etc|tmp)/',lambda m:str(r)+m.group(),s)
  (kit/name).write_text(s)
 n=0
 for slot in (0,1):
  (r/'sys/class/ubi/ubi0/mtd_num').write_text(str(2+slot));fit.write_bytes(bytes.fromhex('d00dfeed')+f'\0\1config@mi01.6-acadia-bridge-slot{slot}\0'.encode());sha=hashlib.sha256(fit.read_bytes()).hexdigest()
  before={'bootcmd':'run miami_persistent_restore && run miami_persistent_load || bootipq','image':str(1-slot),'changing_bootcmd':'1','miami_persistent_slot':str(slot),'miami_persistent_load':f'legacy{slot}; reset'};state.write_text(json.dumps(before))
  env={**os.environ,'LC_ALL':'C','ROOT':str(r),'STATE':str(state),'SLOT':str(slot),'LOG':str(log),'ACTORS':str(funcs),'PATH':str(tools)+':'+os.environ['PATH']}
  def run(name,*args):return subprocess.run(['sh',str(kit/name),*args],env=env,capture_output=True,text=True)
  p=run('stage-bridge.sh',str(fit),sha,'--yes','--backed-up');assert p.returncode==37,(p.returncode,p.stdout,p.stderr)
  e=json.loads(state.read_text());assert e['bootcmd']==f'run miami_boot{slot}' and e['image']==str(slot);n+=1
  # A consumed transition refuses cleanup and retains its evidence/volume.
  e.update(miami_bridge_state='started',miami_ab_state='writing');state.write_text(json.dumps(e));assert run('cleanup-bridge.sh','--yes').returncode!=0;assert (r/'sys/class/ubi/ubi0_5').exists();n+=1
  e.pop('miami_bridge_state');e.pop('miami_ab_state');state.write_text(json.dumps(e))
  # Wrong name and live mount alias each reject before removal.
  name=r/'sys/class/ubi/ubi0_5/name';name.write_text('kernel');assert run('cleanup-bridge.sh','--yes').returncode!=0;name.write_text('miami_ab_bridge');n+=1
  alias=r/'dev/alias';alias.symlink_to(r/'dev/ubi0_5');(r/'proc/self/mountinfo').write_text(f'1 0 0:1 / /mounted rw - ubifs {alias} rw\n');assert run('cleanup-bridge.sh','--yes').returncode!=0;(r/'proc/self/mountinfo').write_text('');alias.unlink();n+=1
  (r/'sys/class/block').mkdir(parents=True,exist_ok=True);block=r/'sys/class/block/ubiblock0_5';block.touch();assert run('cleanup-bridge.sh','--yes').returncode!=0;block.unlink();n+=1
  fd=r/'proc/123/fd';fd.mkdir(parents=True,exist_ok=True);opened=fd/'9';opened.symlink_to(r/'dev/ubi0_5');assert run('cleanup-bridge.sh','--yes').returncode!=0;opened.unlink();n+=1
  (r/'proc/self/mountinfo').write_text('1 0 250:5 / /mounted rw - ubifs other rw\n');assert run('cleanup-bridge.sh','--yes').returncode!=0;(r/'proc/self/mountinfo').write_text('');n+=1
  alias=r/'dev/charalias';alias.touch();(r/'proc/self/mountinfo').write_text(f'1 0 0:1 / /mounted rw - ubifs {alias} rw\n');assert run('cleanup-bridge.sh','--yes').returncode!=0;(r/'proc/self/mountinfo').write_text('');alias.unlink();n+=1
  env['FAIL_STAT']='1';assert run('cleanup-bridge.sh','--yes').returncode!=0;env['FAIL_STAT']='0';n+=1
  p=run('cleanup-bridge.sh','--yes');assert p.returncode==0,(p.stdout,p.stderr);assert not (r/'sys/class/ubi/ubi0_5').exists();n+=1
  p=run('stage-bridge.sh',str(fit),sha,'--yes','--backed-up');assert p.returncode==37,(p.returncode,p.stdout,p.stderr);n+=1
  assert run('cleanup-bridge.sh','--yes').returncode==0
 print(f'PASS: {n} actual stage→partial aux failure→cleanup→restage and consumed/wrong-name/mount-alias refusals, both slots; flash/crypto/ENV actors only')
