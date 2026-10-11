from pathlib import Path
import subprocess,tempfile,os,json,hashlib
repo=Path(os.environ['WLAN_AP_SOURCE_DIR']);client=Path(os.environ['NATIVE_CLIENT_SOURCE_DIR']);version='176cab2f4e977929ce3827badeedd438767dbb88'
archive=subprocess.check_output(['git','archive',version],cwd=client)
with tempfile.TemporaryDirectory(prefix='native-patch-stack.') as temporary:
 root=Path(temporary);subprocess.run(['tar','-xf','-','-C',str(root)],input=archive,check=True)
 patches=repo/'feeds/ucentral/ucentral-client/patches';receipt={}
 assert not (patches/'020-private-activation-nonce.patch').exists(),'Obsolete activation nonce patch is still packaged'
 for p in sorted(patches.glob('*.patch')):
  subprocess.run(['patch','--fuzz=0','-p1','-d',str(root),'-i',str(p)],check=True)
  receipt[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
 assert not any(token in (root/'proto.c').read_text() for token in ['privateActivationNonce','UCENTRAL_PRIVATE_ACTIVATION_NONCE'])
 env=dict(os.environ,NATIVE_CLIENT_SOURCE_DIR=str(root));tests=repo/'tests/installer/native-firstboot-format2'
 subprocess.run(['python3',str(tests/'test-status-width.py')],env=env,check=True)
 subprocess.run(['python3',str(tests/'test-boot-transport.py')],env=env,check=True)
 print(json.dumps({'passed':True,'source_commit':version,'patches':receipt,'scope':'Whole committed native patch stack zero fuzz; actual C status and transport callbacks with isolated boundaries. No package build/AP.'}))
