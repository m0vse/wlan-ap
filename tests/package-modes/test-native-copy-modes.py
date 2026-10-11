#!/usr/bin/env python3
"""Exercise actual native recipe copy normalization in isolated staging roots."""
from pathlib import Path
import hashlib, json, os, re, shutil, stat, subprocess, tempfile

REPO = Path(os.environ.get('NATIVE_MODE_TEST_REPO',Path(__file__).resolve().parents[2]))
RECIPES = Path(os.environ.get('NATIVE_MODE_RECIPE_ROOT',REPO))
PACKAGES = ('feeds/tip/certificates', 'feeds/tip/cloud_discovery',
            'feeds/ucentral/ucentral-client', 'feeds/ucentral/ucentral-schema')
checks = 0
reports = []
with tempfile.TemporaryDirectory(prefix='native-copy-modes-') as temporary:
    work = Path(temporary)
    for number, package in enumerate(PACKAGES):
        base = work / str(number)
        files = base / 'files'
        files.mkdir(parents=True)
        stage = base / 'stage'
        stage.mkdir()
        manifest = subprocess.check_output(['git','ls-files','--stage',package+'/files'],
                                           cwd=REPO,text=True).splitlines()
        expected = {}
        for record in manifest:
            metadata, name = record.split('\t',1)
            mode = metadata.split()[0]
            relative = Path(name).relative_to(package+'/files')
            target = files/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            if mode == '120000':
                target.symlink_to(os.readlink(REPO/name))
                continue
            assert mode in ('100644','100755'), (package,name,mode)
            target.write_bytes((REPO/name).read_bytes())
            # Reproduce a reused group-write checkout, not just a fresh clone.
            target.chmod(0o775 if mode == '100755' else 0o664)
            expected[relative] = 0o755 if mode == '100755' else 0o644
        for path in [files,*files.rglob('*')]:
            if path.is_dir(): path.chmod(0o775)
        private = stage/'etc/ucentral/private-fixture'
        private.mkdir(parents=True,mode=0o700)
        private.chmod(0o700)
        secret = private/'key'
        secret.write_bytes(b'isolated synthetic fixture, never a real key')
        secret.chmod(0o600)
        # Use the actual BuildPackage eval/call ordering from OpenWrt's
        # include/package-pack.mk. Never emulate make's dollar escaping.
        recipe = (RECIPES/package/'Makefile').read_text()
        fragment = re.search(r'(?ms)^\tfind ./files -mindepth 1 -type d.*?^\tdone\n\tfind ./files -type f.*?^\tdone\n',recipe)
        assert fragment,package
        makefile = '''INSTALL_DIR:=install -d -m0755
INSTALL_BIN:=install -m0755
INSTALL_DATA:=install -m0644
IDIR_fixture:='''+str(stage)+'''
define Package/fixture/install
\tcp -fpR ./files/* $(1)
'''+fragment.group()+'''endef
define BuildPackage
.PHONY: $(1)
$(1):
\t$(call Package/$(1)/install,$$(IDIR_$(1)))
endef
$(eval $(call BuildPackage,fixture))
'''
        (base/'Makefile').write_text(makefile)
        copy = 'cp -fpR ./files/* "'+str(stage)+'"\n'
        subprocess.run(['sh','-ec',copy],cwd=base,check=True)
        assert any(stat.S_IMODE((stage/path).stat().st_mode)!=mode for path,mode in expected.items())
        checks += 1  # Original recursive-copy negative control.
        result = subprocess.run(['make','--no-print-directory','fixture'],cwd=base,capture_output=True,text=True)
        assert result.returncode==0,(package,result.stdout,result.stderr)
        assert '${path#./files/}' in result.stdout and '$path' in result.stdout, result.stdout
        assert not (stage/'files').exists(),package
        checks += 1
        for path, mode in expected.items():
            installed = stage/path
            assert stat.S_IMODE(installed.stat().st_mode)==mode,(package,path)
            assert installed.read_bytes()==(files/path).read_bytes(),(package,path)
            checks += 2
        for path in files.rglob('*'):
            if path.is_dir():
                assert stat.S_IMODE((stage/path.relative_to(files)).stat().st_mode)==0o755
                checks += 1
            elif path.is_symlink():
                assert (stage/path.relative_to(files)).is_symlink()
                assert os.readlink(stage/path.relative_to(files))==os.readlink(path)
                checks += 1
        assert stat.S_IMODE(private.stat().st_mode)==0o700
        assert stat.S_IMODE(secret.stat().st_mode)==0o600
        assert secret.read_bytes()==b'isolated synthetic fixture, never a real key'
        checks += 3
        (base/'Makefile').write_text(makefile.replace('INSTALL_BIN:=install -m0755','INSTALL_BIN:=false'))
        failure = subprocess.run(['make','--no-print-directory','fixture'],cwd=base,capture_output=True,text=True)
        assert failure.returncode!=0,package
        checks += 1
        reports.append(dict(package=package,tracked_files=len(expected),
                            recipe_sha256=hashlib.sha256(recipe.encode()).hexdigest()))
print(json.dumps(dict(status='PASS',checks=checks,packages=reports,
                     source_modes='0775 executables,0664 data,0775 package-owned directories',
                     outputs='0755 executables/directories,0644 data; unrelated0700/0600 private fixture untouched',
                     scope='Actual recipe fragments through GNU make eval/call and tracked file manifests; private staging only, no AP or firmware build.')))
