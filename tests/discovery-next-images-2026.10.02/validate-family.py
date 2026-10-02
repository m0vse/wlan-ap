"""Focused actual-image checks and outgoing normal managed path fixtures."""
import json,os,pathlib,shutil,subprocess,sys,tempfile
family=sys.argv[1];revision='2026.10.02.5' if family=='sage' else '2026.10.02.4'
base=pathlib.Path('/home/phil/openwifi-'+family+'-build');release=base/('release-'+family+'-'+revision)
capture=json.loads((release/'capture.json').read_text());root=pathlib.Path(capture['root']);work=pathlib.Path(capture['work']);image=pathlib.Path(capture['image']);tools=pathlib.Path('/tmp/discovery-next-image-tools')
old=pathlib.Path('/tmp/openwifi-sage4-validation.MpnQnl/root' if family=='sage' else '/tmp/openwifi-jaguar3-validation.WcB5nJ/root')
stamp='sage-2026.10.02.5-a631587a' if family=='sage' else 'jaguar-2026.10.02.4-6dbb803b'
native='/home/phil/openwifi-sage-build/wlan-ap/openwrt/staging_dir/hostpkg/bin/ucode'
env=dict(os.environ,OW_TEST_UCODE=native,OW_TEST_ASH='/home/phil/openwifi-cheetah-build/operator-r2/busybox-ash/busybox')
def run(args,name,extra=None):
 with (release/name).open('w') as out:subprocess.run(args,check=True,env=env| (extra or {}),stdout=out)
subprocess.run(['python3',str(tools/'verify-image.py'),str(root),str(old),str(image),str(release/'image-metadata.json'),str(release/'image-contract.json'),family,stamp],check=True)
run(['python3','/tmp/test-regressions.py',capture['package']],'built-discovery-tests.json')
run(['python3',str(tools/'test-managed-upgrade-command.py'),str(old)],'outgoing-managed-archive-tests.json')
run(['python3',str(tools/'check-static-ram-closure.py'),str(root)],'incoming-static-ram-closure.json')
fixture=work/'validator-payload';fixture.mkdir()
(fixture/'IMAGE').write_text(image.name+'\n');(fixture/image.name).symlink_to(image)
helper='compatibility-check.sh' if family=='sage' else 'preservation-check.sh'
origin=pathlib.Path('/home/phil/openwifi-sage-build/preflight-from.1-r1/compatibility-check.sh' if family=='sage' else '/home/phil/openwifi-jaguar-build/operator-jaguar-openwifi-from.1-2026.10.02.3-r2/preservation-check.sh')
shutil.copy2(origin,fixture/helper)
boards=['cambiumnetworks,e410','cambiumnetworks,e410b'] if family=='sage' else ['cambiumnetworks,xv2-2','cambiumnetworks,xv2-2t1','cambiumnetworks,xe3-4']
for board in boards:
 slug=board.split(',')[1]
 run(['python3',str(tools/'test-preserving-validator.py')],'normal-outgoing-'+slug+'-validator-tests.json',{'OW_PRESERVE_TEST_SOURCE':str(old),'OW_PRESERVE_TEST_BUNDLE':str(fixture),'OW_PRESERVE_FAMILY':family,'OW_PRESERVE_TARGET_BOARD':board,'OW_PRESERVE_IMAGE_SHA256':capture['image_sha256'],'OW_PRESERVE_NORMAL_UI_ONLY':'1'})
 run(['python3',str(tools/'test-incoming-ram-copy.py'),str(old),str(image),family],'outgoing-'+slug+'-retained-ram-tests.json',{'OW_RAM_TEST_BOARD':board})
target=work/'target-runtime';target.mkdir()
qemu='/usr/bin/qemu-arm' if family=='sage' else '/usr/bin/qemu-aarch64'
run(['sudo','-n','unshare','-m','sh','/tmp/test-target-package.sh',str(root),qemu,capture['package'],'/tmp/shared-discovery-target-fixtures',str(target)],'built-target-runtime-tests.log')
print('PASS',family,stamp,capture['image_sha256'])
