#!/usr/bin/env python3
"""Exercise actual shared code with isolated env/MTD fixtures; no AP operations."""
from pathlib import Path
import os,shlex,shutil,subprocess,sys,tarfile,tempfile
root,image=map(Path,sys.argv[1:3]);w=Path(tempfile.mkdtemp(prefix='gambit-core-hooks.'));modules=w/'modules';modules.mkdir()
for p in root.glob('package/cambium/*-support/files/cambium-ab-*.sh'):shutil.copyfile(p,modules/p.name)
cores=root/'package/cambium/cambium-ab/files';testcore=w/'core.sh';testcore.write_text((cores/'cambium-ab.sh').read_text().replace('/tmp/cambium-ab-fw_env.config',str(w/'env-config')));bb=Path(sys.argv[3]) if len(sys.argv)>3 else None
cmd=['sh'];env=dict(os.environ,CAMBIUM_AB_LIB=str(testcore),CAMBIUM_AB_CERTIFICATE_LIB=str(cores/'cambium-ab-certificates.sh'),CAMBIUM_AB_MODULES=str(modules),WORK=str(w),IMAGE=str(image))
if bb:
 cmd=['/usr/bin/qemu-mips','-cpu','24Kc','-L',str(bb),str(bb/'bin/busybox'),'ash'];tools=w/'tools';tools.mkdir()
 for applet in ['hexdump','wc','tr','awk']:
  p=tools/applet;p.write_text('#!/bin/sh\nexec '+shlex.join(['/usr/bin/qemu-mips','-cpu','24Kc','-L',str(bb),str(bb/'bin/busybox'),applet])+' "$@"\n');p.chmod(0o700)
 env['PATH']=str(tools)+':'+env['PATH']
# Small FIT-format fixtures exercise the existing magic/node guard, not FIT CRC validation.
for label,kernel in [('fit-good',b'\xd0\x0d\xfe\xed\0\0\0\x01fixture-fit\0'),('fit-wrong-node',b'\xd0\x0d\xfe\xed\0\0\0\x01wrong-fit\0'),('fit-wrong-magic',b'bad!\0\0\0\x01fixture-fit\0')]:
 d=w/label/'fixture';d.mkdir(parents=True);(d/'kernel').write_bytes(kernel);(d/'root').write_bytes(b'hsqsfixture')
 with tarfile.open(w/(label+'.tar'),'w') as t:t.add(d,arcname='fixture')
source='. "$CAMBIUM_AB_LIB"; . "'+str(cores/'cambium-ab-upgrade.sh')+'"; ab_getenv() { :; }; '
def run(label,body,expected=0):
 p=subprocess.run(cmd+['-c',source+body],env=env,capture_output=True,text=True);assert p.returncode==expected,(label,p.returncode,p.stderr);print('PASS',label,flush=True)
run('Gambit declares raw-kernel hook, u-boot-env and marker0','ab_board cambiumnetworks,e400 && [ "$AB_ENV_PART" = u-boot-env ] && [ "$AB_MARKER" = 0 ] && ab_hook check_kernel')
run('Gambit actual sealed uImage extracts through actual family hook','ab_board cambiumnetworks,e400; AB_TARGET=1; AB_KERNEL_MTD1=2; AB_WORK=$WORK/extract; AB_MTD_SYS=$WORK/no-hardware; ab_image_extract "$IMAGE"')
run('Gambit uImage validation refuses FIT fixture','ab_board cambiumnetworks,e400; ab_gambit_check_kernel "$WORK/fit-good/fixture/kernel"',1)
for label in ['fit-good','fit-wrong-node','fit-wrong-magic']:
 run('nonhook FIT fallback '+label,'AB_FAMILY=fixture AB_MODEL=fixture AB_FIT=fixture-fit AB_IMAGE_DIR=fixture AB_ROOT_MAGIC=hsqs AB_VAULT=0 AB_CERTIFICATE_LEBS=0 AB_BANK_LEBS=100 AB_LEB=126976; AB_WORK=$WORK/extract-fit; ab_image_extract "$WORK/'+label+'.tar"',0 if label=='fit-good' else 1)
for label,part,idx,size,accepted in [('gambit','u-boot-env','7','00010000',True),('default','0:APPSBLENV','3','00010000',True),('duplicate','u-boot-env','7 8','00010000',False),('wrong-size','u-boot-env','7','00020000',False)]:
 body='ab_mtd_index() { [ "$1" = '+shlex.quote(part)+' ] && printf "%s\\n" '+shlex.quote(idx)+'; }; ab_mtd_geometry() { printf "%s\\n" '+shlex.quote(size+' 00010000')+'; }; AB_ENV_PART='+shlex.quote(part)+'; AB_ENV_CONFIG=; ab_env_config'
 run('environment mapping '+label,body,0 if accepted else 1)
run('family selection resets legacy defaults after Gambit','ab_board cambiumnetworks,e400; ab_board cambiumnetworks,xv2-2; [ "$AB_ENV_PART" = 0:APPSBLENV ] && [ "$AB_MARKER" = 1 ] && ! ab_hook check_kernel')
print('11 passed, 0 failed; isolated source interfaces; no hardware actions')
