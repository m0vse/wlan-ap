#!/usr/bin/env python3
"""Execute actual package copy/normalization tail using actual OpenWrt macros.
No package compilation or firmware build; isolated staging directories only.
"""
import hashlib,itertools,json,os,pathlib,re,shutil,subprocess,tempfile
repo=pathlib.Path(os.environ['WLAN_AP_SOURCE_DIR'])
rules=pathlib.Path(os.environ['OW_TEST_RULES']).read_text()
cp=re.search(r'^CP:=(.+)$',rules,re.M).group(1)
install_bin=re.search(r'^INSTALL_BIN:=(.+)$',rules,re.M).group(1)
install=re.search(r'^INSTALL_DIR:=(.+)$',rules,re.M).group(1)
assert install_bin=='install -m0755'
assert cp=='cp -fpR' and install=='install -d -m0755'
work=pathlib.Path(tempfile.mkdtemp(prefix='package-runtime-mode.'))
providers=['tip/certificates','tip/cloud_discovery','tip/tip-defaults','ucentral/ucentral-schema','ucentral/ucentral-client']
packages=[];cases=[]
for provider in providers:
 source=repo/'feeds'/provider;isolated=work/provider.replace('/','-');isolated.mkdir()
 shutil.copytree(source/'files',isolated/'files')
 # Git has no directory mode tracking. Model the observed build-host checkout
 # mode rather than trusting whichever umask created this checkout.
 runtime=isolated/'files/etc/ucentral';runtime.mkdir(parents=True,exist_ok=True);runtime.chmod(0o775)
 proof=runtime/'mode-test-sentinel';proof.write_text(provider);proof.chmod(0o440)
 executable_paths=['usr/libexec/ucentral-secure-runtime','etc/init.d/early_boot'] if provider=='tip/certificates' else []
 for n in executable_paths:(isolated/'files'/n).chmod(0o775)
 staging=isolated/'package';staging.mkdir()
 block=(source/'Makefile').read_text().split('define Package/'+source.name+'/install\n',1)[1].split('endef',1)[0]
 tail=block[block.index('\t$(CP) ./files/* $(1)'):]
 assert tail.count('$(INSTALL_DIR) $(1)/etc/ucentral')==1 and tail.index('$(INSTALL_DIR)')>tail.index('$(CP)')
 # Reproduce the old package defect before executing the corrected tail.
 subprocess.run(cp.split()+['./files/etc',str(staging)],cwd=isolated,check=True)
 assert (staging/'etc/ucentral').stat().st_mode & 0o7777==0o775
 commands=tail.replace('$(CP)',cp).replace('$(INSTALL_DIR)',install).replace('$(INSTALL_BIN)',install_bin).replace('$(1)',str(staging))
 subprocess.run(['sh','-ec',commands],cwd=isolated,check=True)
 assert (staging/'etc/ucentral').stat().st_mode & 0o7777==0o755
 assert (staging/'etc/ucentral/mode-test-sentinel').read_bytes()==proof.read_bytes()
 assert (staging/'etc/ucentral/mode-test-sentinel').stat().st_mode & 0o7777==0o440
 for n in executable_paths:
  assert (staging/n).stat().st_mode & 0o7777==0o755
  assert (staging/n).read_bytes()==(isolated/'files'/n).read_bytes()
 if executable_paths:cases.append('certificate-executables-normalized-from-git-umask-0775')
 packages.append(staging);cases.append(provider+'-normalizes-observed-checkout-mode')
# Any provider may be installed last; exercise every order of the five tails.
for i,order in enumerate(itertools.permutations(packages)):
 image=work/('image-'+str(i));image.mkdir()
 for package in order:subprocess.run(cp.split()+[str(package/'etc'),str(image)],check=True)
 assert (image/'etc/ucentral').stat().st_mode & 0o7777==0o755
cases.append('all-120-package-merge-orders-produce-0755')
# A last private files/ overlay supersedes package directories. The build
# recipe must normalize its known canonical runtime directory before merge;
# otherwise its 0775 survives even when every provider package is correct.
overlay=work/'private-overlay';runtime=overlay/'etc/ucentral';runtime.mkdir(parents=True);runtime.chmod(0o775)
policy=runtime/'discovery-policy.json';policy.write_text('{"mode":"default","default":"private.example:15002"}');policy.chmod(0o600)
policy_bytes=policy.read_bytes();metadata=(runtime.stat().st_uid,runtime.stat().st_gid)
subprocess.run(cp.split()+[str(overlay/'etc'),str(image)],check=True)
assert (image/'etc/ucentral').stat().st_mode & 0o7777==0o775
subprocess.run(install.split()+[str(runtime)],check=True)
assert (runtime.stat().st_uid,runtime.stat().st_gid)==metadata
assert policy.read_bytes()==policy_bytes and policy.stat().st_mode & 0o7777==0o600
subprocess.run(cp.split()+[str(overlay/'etc'),str(image)],check=True)
assert (image/'etc/ucentral').stat().st_mode & 0o7777==0o755
assert (image/'etc/ucentral/discovery-policy.json').read_bytes()==policy_bytes
cases.append('final-private-overlay-reproduces-and-normalizes-directory-override')
print(json.dumps({'passed':True,'cases':cases,'count':len(cases),'package_orders':120,'macros':{'CP':cp,'INSTALL_DIR':install,'INSTALL_BIN':install_bin},'scope':'Actual shared package install tails and actual OpenWrt macros, synthetic checkout/executable 0775, all package orders and final private overlay normalization. No builds or AP operations.'},indent=2))
