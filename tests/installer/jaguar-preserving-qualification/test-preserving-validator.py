#!/usr/bin/env python3
"""Actual reviewed stock -T and validator sources; hardware hook isolated."""
import hashlib,json,os,pathlib,re,shutil,subprocess,tempfile
old=pathlib.Path(os.environ['OW_PRESERVE_TEST_SOURCE']);payload=pathlib.Path(os.environ['OW_PRESERVE_TEST_BUNDLE']);work=pathlib.Path(tempfile.mkdtemp(prefix='preserving-validator.',dir='/tmp'))
family=os.environ['OW_PRESERVE_FAMILY'];assert family in ('sage','jaguar')
qualified_board='cambiumnetworks,e410' if family=='sage' else 'cambiumnetworks,xv2-2t1'
qualified_board=os.environ.get('OW_PRESERVE_TARGET_BOARD',qualified_board)
assert qualified_board in ('cambiumnetworks,e410','cambiumnetworks,e410b','cambiumnetworks,xv2-2','cambiumnetworks,xv2-2t1')
qemu='/usr/bin/qemu-arm' if family=='sage' else '/usr/bin/qemu-aarch64'
compat_helper='compatibility-check.sh' if family=='sage' else 'preservation-check.sh'
compat_function=family+'_configuration_preservation_check'
ash=pathlib.Path(os.environ['OW_TEST_ASH'])
image=payload/(payload/'IMAGE').read_text().strip();tests=[]
image_sha='2f86a4dd48bcc66912422fef411a4133c582c792b278b35ac5565444a92b495a' if family=='sage' else '3957cab679b6a01e928d4f755ed05e733aba3659c980de66c6ec7af7befbd3ba'
image_sha=os.environ.get('OW_PRESERVE_IMAGE_SHA256',image_sha)
assert hashlib.sha256(image.read_bytes()).hexdigest()==image_sha
paths=['sbin/sysupgrade','usr/libexec/validate_firmware_image','usr/share/libubox/jshn.sh','lib/functions.sh','lib/functions/system.sh']
paths += [str(p.relative_to(old)) for p in (old/'lib/upgrade').glob('*.sh')]
paths += [str(p.relative_to(old)) for p in (old/'lib/functions').glob('*.sh')]
phases=('reviewed-outgoing',) if os.environ.get('OW_PRESERVE_NORMAL_UI_ONLY')=='1' else ('reviewed-outgoing','installed-bridge')
for phase in phases:
 root=work/phase;root.mkdir();(root/'bin').mkdir();(root/'tmp/sysinfo').mkdir(parents=True);(root/'etc/config').mkdir(parents=True);(root/'tmp/.uci').mkdir()
 replacements={'lib/functions/cambium-ab.sh':'cambium-ab.sh','lib/upgrade/cambium-ab.sh':'cambium-ab-upgrade.sh','lib/upgrade/cambium-ab-certificates.sh':'cambium-ab-certificates.sh',f'lib/functions/cambium-ab-{family}.sh':f'modules/cambium-ab-{family}.sh'}
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
  target.write_text(f'#!/bin/sh\nexec {qemu} -L "{old}" "{old/relative}" {extra}"$@"\n');target.chmod(0o755)
  if tool!='uci':shutil.copy2(target,root/'bin'/tool)
 if (old/'usr/bin/ucert').exists():
  target=root/'usr/bin/ucert';target.write_text(f'#!/bin/sh\nexec {qemu} -L "{old}" "{old}/usr/bin/ucert" "$@"\n');target.chmod(0o755)
 # Execute the actual EST fwtool function only. Its other methods can
 # enroll/contact EST, so full daemon imports/startup are deliberately not
 # executed. Filesystem literals redirect to this private fixture only.
 est_source=(old/'usr/bin/est_client').read_text()
 est_function=est_source.split('function fwtool() {',1)[1].split('function check_cert()',1)[0]
 est_function='function fwtool() {'+est_function
 est_function=re.sub(r'(?<![A-Za-z0-9_])/(?:etc|tmp)(?=/|[\s"\'])',lambda m:str(root)+m.group(),est_function)
 est_program=root/'est-fwtool.uc'
 est_program.write_text('import * as fs from "fs"; const LOG_INFO=0; function ulog() {};\n'+est_function+'\nexit(fwtool());\n')
 # A newly generated fixture-only birth certificate exercises the metadata
 # branch; no real AP credentials, operational issuer or network are used.
 (root/'etc/ucentral').mkdir()
 subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=OpenLAN Birth Fixture','-keyout',str(root/'fixture-key.pem'),'-out',str(root/'etc/ucentral/cert.pem')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 est_tool=root/'bin/est_client'
 est_tool.write_text(f'#!/bin/sh\n[ "$1" = fwtool ] || exit 99\nexec "{os.environ["OW_TEST_UCODE"]}" "{est_program}"\n');est_tool.chmod(0o755)
 for tool in ('ubus','upgraded','fw_setenv','ubiformat','ubiupdatevol','reboot'):
  p=root/'bin'/tool;p.write_text('#!/bin/sh\necho forbidden-$0 >> "$TEST_CALLS"\nexit 99\n');p.chmod(0o755)
 fixture_image=root/'tmp/image.bin';shutil.copy2(image,fixture_image)
 for name,board,compat,platform_rc,expected in [('matching-default','cambiumnetworks,e410',None,0,0),('matching-explicit','cambiumnetworks,e410','1.0',0,0),('major-fence','cambiumnetworks,e410','2.0',0,1),('minor-mismatch-stock-reset-default','cambiumnetworks,e410','1.1',0,0),('unqualified-model','cambiumnetworks,xv2-22h',None,0,1),('platform-refusal','cambiumnetworks,e410',None,1,1)]:
  if board=='cambiumnetworks,e410': board=qualified_board
  (root/'tmp/sysinfo/board_name').write_text(board+'\n')
  (root/'etc/config/system').write_text("config system\n"+(" option compat_version '"+compat+"'\n" if compat else ''))
  calls=root/'tmp/calls';calls.write_text('')
  env=dict(os.environ,PATH=str(root/'bin')+':'+os.environ['PATH'],TEST_CALLS=str(calls),TEST_PLATFORM_RC=str(platform_rc))
  result=subprocess.run([str(ash),'ash',str(root/'sbin/sysupgrade'),'-T',str(fixture_image)],env=env,text=True,capture_output=True)
  (root/(name+'.log')).write_text(result.stdout+result.stderr)
  assert result.returncode==expected,(phase,name,result.returncode,result.stdout,result.stderr)
  assert 'forbidden-' not in calls.read_text(),(phase,name,'mutation attempted')
  assert hashlib.sha256(fixture_image.read_bytes()).hexdigest()==hashlib.sha256(image.read_bytes()).hexdigest()
  tests.append({'phase':phase,'case':name,'result':result.returncode,'passed':True})
  if compat=='1.1':
   # Actual validator must refuse preservation even though stock -T uses0.
   preserved_env=dict(env,SAVE_CONFIG='1',IGNORE_MINOR_COMPAT='0')
   preserve=subprocess.run([str(ash),'ash',str(root/'usr/libexec/validate_firmware_image'),str(fixture_image)],env=preserved_env,text=True,capture_output=True)
   assert not json.loads(preserve.stdout)['valid'], (phase,'minor preserve fence',preserve.stdout,preserve.stderr)
   tests.append({'phase':phase,'case':'actual-validator-minor-fence-SAVE_CONFIG1','passed':True})
 # Exercise the actual added compatibility function with outgoing target UCI.
 compat_driver=root/'compat-driver.sh'
 compat_driver.write_text('. "$1"; '+compat_function+'\n')
 for compat in (None,'1.0','1.1','2.0','unknown'):
  (root/'etc/config/system').write_text("config system\n"+(" option compat_version '"+compat+"'\n" if compat else ''))
  env=dict(os.environ,PATH=str(root/'bin')+':'+os.environ['PATH'])
  result=subprocess.run(['sh',str(compat_driver),str(payload/compat_helper)],env=env,capture_output=True,text=True)
  assert (result.returncode==0)==(compat in (None,'1.0')), (phase,compat,result.stderr)
  tests.append({'phase':phase,'case':'operator-preservation-compat-'+str(compat),'passed':True})
print(json.dumps({'passed':True,'cases':tests,'count':len(tests),'fixture':str(work),'reviewed_source_sha256':{p:hashlib.sha256((old/p).read_bytes()).hexdigest() for p in ('sbin/sysupgrade','usr/libexec/validate_firmware_image','lib/upgrade/fwtool.sh','usr/share/libubox/jshn.sh','usr/bin/fwtool','usr/bin/jshn','sbin/uci','usr/bin/est_client')},'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'image_compat_version':'1.0','no_qualification_config_write_required_for_default_or_1_0':True,'source_paths_and_fixture_ash_interpreter_redirected_only':True,'native_busybox_ash':str(ash),'actual_outgoing_arm_fwtool_jshn_uci':True,'actual_est_fwtool_function_native_ucode_private_birth_fixture':True,'est_enrollment_or_network_not_executed':True,'platform_hardware_boundary_stubbed':True,'full_device_sysupgrade_or_ram_pivot_acceptance':False},indent=2))
