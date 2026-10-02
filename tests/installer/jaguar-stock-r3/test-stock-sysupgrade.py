#!/usr/bin/env python3
"""Actual reviewed stock -T and validator sources; hardware hook isolated."""
import hashlib,json,os,pathlib,re,shutil,subprocess,tempfile
base=pathlib.Path(os.environ['OW_JAGUAR_TEST_BASE']);old=base/'outgoing-source/rootfs';payload=base/'operator-r1';work=pathlib.Path(tempfile.mkdtemp(prefix='jaguar-stock-sysupgrade.',dir='/tmp'))
ash=pathlib.Path(os.environ['OW_TEST_ASH'])
image=payload/'cambium_xv2-2t1-jaguar-2026.10.02.2-sysupgrade.bin';tests=[]
assert hashlib.sha256(image.read_bytes()).hexdigest()=='3957cab679b6a01e928d4f755ed05e733aba3659c980de66c6ec7af7befbd3ba'
paths=['sbin/sysupgrade','usr/libexec/validate_firmware_image','usr/share/libubox/jshn.sh','lib/functions.sh','lib/functions/system.sh']
paths += [str(p.relative_to(old)) for p in (old/'lib/upgrade').glob('*.sh')]
paths += [str(p.relative_to(old)) for p in (old/'lib/functions').glob('*.sh')]
for phase in ('reviewed-outgoing','installed-bridge'):
 root=work/phase;root.mkdir();(root/'bin').mkdir();(root/'tmp/sysinfo').mkdir(parents=True);(root/'etc/config').mkdir(parents=True);(root/'tmp/.uci').mkdir()
 replacements={'lib/functions/cambium-ab.sh':'cambium-ab.sh','lib/upgrade/cambium-ab.sh':'cambium-ab-upgrade.sh','lib/upgrade/cambium-ab-certificates.sh':'cambium-ab-certificates.sh','lib/functions/cambium-ab-jaguar.sh':'modules/cambium-ab-jaguar.sh'}
 actual_paths=paths+(['lib/upgrade/cambium-ab-certificates.sh'] if phase=='installed-bridge' else [])
 for name in actual_paths:
  source=(payload/replacements[name]) if phase=='installed-bridge' and name in replacements else old/name
  target=root/name;target.parent.mkdir(parents=True,exist_ok=True)
  text=source.read_text()
  # Single pass redirects filesystem literals only; no compat/-T logic changes.
  text=re.sub(r'(?<![A-Za-z0-9_])/(?:lib|usr/libexec|usr/share/libubox|usr/bin|sbin|etc|tmp|rom|overlay)(?=/|[\s"\'])',lambda m:str(root)+m.group(),text)
  text=text.replace('#!/bin/sh\n', '#!'+str(ash)+' ash\n',1)
  target.write_text(text);target.chmod(source.stat().st_mode & 0o777)
 # Hardware validation is already covered separately. The stock validator calls
 # this isolated boundary after executing its real signature/device checks.
 (root/'lib/upgrade/platform.sh').write_text('''REQUIRE_IMAGE_METADATA=1
platform_check_image() {
 printf '%s\\n' platform-hardware-boundary >> "$TEST_CALLS"
 return "${TEST_PLATFORM_RC:-0}"
}
''')
 for tool,relative in (('jshn','usr/bin/jshn'),('fwtool','usr/bin/fwtool'),('uci','sbin/uci')):
  target=root/('usr/bin/'+tool) if tool!='uci' else root/'bin/uci'
  target.parent.mkdir(parents=True,exist_ok=True)
  extra=f'-c "{root}/etc/config" -t "{root}/tmp/.uci" ' if tool=='uci' else ''
  target.write_text(f'#!/bin/sh\nexec /usr/bin/qemu-aarch64 -L "{old}" "{old/relative}" {extra}"$@"\n');target.chmod(0o755)
  if tool!='uci':shutil.copy2(target,root/'bin'/tool)
 if (old/'usr/bin/ucert').exists():
  target=root/'usr/bin/ucert';target.write_text(f'#!/bin/sh\nexec /usr/bin/qemu-aarch64 -L "{old}" "{old}/usr/bin/ucert" "$@"\n');target.chmod(0o755)
 for tool in ('ubus','upgraded','fw_setenv','ubiformat','ubiupdatevol','reboot'):
  p=root/'bin'/tool;p.write_text('#!/bin/sh\necho forbidden-$0 >> "$TEST_CALLS"\nexit 99\n');p.chmod(0o755)
 fixture_image=root/'tmp/image.bin';shutil.copy2(image,fixture_image)
 for name,board,compat,platform_rc,expected in [('matching-default','cambiumnetworks,xv2-2t1',None,0,0),('matching-explicit','cambiumnetworks,xv2-2t1','1.0',0,0),('major-fence','cambiumnetworks,xv2-2t1','2.0',0,1),('minor-fence-preserve','cambiumnetworks,xv2-2t1','1.1',0,1),('unqualified-model','cambiumnetworks,xv2-22h',None,0,1),('platform-refusal','cambiumnetworks,xv2-2t1',None,1,1),('clean-minor-reset','cambiumnetworks,xv2-2t1','1.1',0,0),('clean-major-refusal','cambiumnetworks,xv2-2t1','2.0',0,1),('clean-board-refusal','cambiumnetworks,xv2-22h',None,0,1)]:
  (root/'tmp/sysinfo/board_name').write_text(board+'\n')
  (root/'etc/config/system').write_text("config system\n"+(" option compat_version '"+compat+"'\n" if compat else ''))
  calls=root/'tmp/calls';calls.write_text('')
  env=dict(os.environ,PATH=str(root/'bin')+':'+os.environ['PATH'],TEST_CALLS=str(calls),TEST_PLATFORM_RC=str(platform_rc))
  options=['-n','-T'] if name.startswith('clean-') else ['-T']
  result=subprocess.run([str(ash),'ash',str(root/'sbin/sysupgrade'),*options,str(fixture_image)],env=env,text=True,capture_output=True)
  (root/(name+'.log')).write_text(result.stdout+result.stderr)
  assert result.returncode==expected,(phase,name,result.returncode,result.stdout,result.stderr)
  assert 'forbidden-' not in calls.read_text(),(phase,name,'mutation attempted')
  assert hashlib.sha256(fixture_image.read_bytes()).hexdigest()==hashlib.sha256(image.read_bytes()).hexdigest()
  tests.append({'phase':phase,'case':name,'result':result.returncode,'passed':True})
print(json.dumps({'passed':True,'cases':tests,'count':len(tests),'fixture':str(work),'reviewed_source_sha256':{p:hashlib.sha256((old/p).read_bytes()).hexdigest() for p in ('sbin/sysupgrade','usr/libexec/validate_firmware_image','lib/upgrade/fwtool.sh','usr/share/libubox/jshn.sh','usr/bin/fwtool','usr/bin/jshn','sbin/uci')},'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'image_compat_version':'1.0','no_qualification_config_write_required_for_default_or_1_0':True,'source_paths_and_fixture_ash_interpreter_redirected_only':True,'native_busybox_ash':str(ash),'actual_outgoing_arm64_fwtool_jshn_uci':True,'platform_hardware_boundary_stubbed':True,'full_device_sysupgrade_or_ram_pivot_acceptance':False},indent=2))
