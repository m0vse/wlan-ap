from pathlib import Path
import sys,re,tempfile,subprocess,shutil,hashlib
repo,root=map(lambda s:Path(s).resolve(),sys.argv[1:]);checks=0
with tempfile.TemporaryDirectory(prefix='dfs-led-package-') as temp:
 w=Path(temp);dest=w/'root';dest.mkdir();build=w/'build';build.mkdir()
 shutil.copy2(root/'usr/libexec/ucentral-storage-probe',build/'storage-probe');shutil.copy2(root/'usr/sbin/ucentral',build/'ucentral')
 for package,release in [('ucentral-state','6'),('ucentral-client','17')]:
  pkg=repo/'feeds/ucentral'/package;s=(pkg/'Makefile').read_text();assert f'PKG_RELEASE:={release}' in s
  install=re.search(r'(define Package/'+package+r'/install\n.*?\nendef)',s,re.S).group(1)
  m=w/(package+'.mk');m.write_text('INSTALL_DIR = install -d -m 0755\nINSTALL_BIN = install -m 0755\nINSTALL_DATA = install -m 0644\nCP = cp -fpR\nPKG_BUILD_DIR := '+str(build)+'\nDEST := '+str(dest)+'\n'+install+'\nall:\n\t$(call Package/'+package+'/install,$(DEST))\n')
  subprocess.run(['make','-s','-f',str(m)],cwd=pkg,check=True,stdout=subprocess.DEVNULL)
  checks+=1
 pairs={'usr/libexec/ucentral-dfs-led':'feeds/ucentral/ucentral-state/files/ucentral-dfs-led','usr/share/ucentral/dfs_led.uc':'feeds/ucentral/ucentral-state/files/dfs_led.uc','usr/sbin/ucentral-state':'feeds/ucentral/ucentral-state/files/ucentral-state','usr/libexec/ucentral-led.sh':'feeds/ucentral/ucentral-client/files/usr/libexec/ucentral-led.sh'}
 for installed,source in pairs.items():
  assert (dest/installed).read_bytes()==(repo/source).read_bytes(),installed
  mode=(dest/installed).stat().st_mode&0o777;assert mode==(0o644 if installed.endswith('.uc') else 0o755),(installed,mode)
  checks+=1
 assert '+coreutils-timeout' in (repo/'feeds/ucentral/ucentral-state/Makefile').read_text();checks+=1
 for script in ['usr/libexec/ucentral-dfs-led','usr/libexec/ucentral-led.sh']:subprocess.run(['/bin/sh','-n',str(dest/script)],check=True);checks+=1
print(f'PASS {checks} actual package-install recipe/source/mode/dependency controls; no firmware build')
