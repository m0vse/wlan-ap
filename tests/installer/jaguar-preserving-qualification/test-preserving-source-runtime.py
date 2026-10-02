#!/usr/bin/env python3
"""Actual installer gates on copied offline roots; no AP source execution."""
import hashlib,json,os,pathlib,re,shutil,subprocess,tempfile
bundle=pathlib.Path(os.environ['OW_PRESERVE_TEST_BUNDLE'])
source=pathlib.Path(os.environ['OW_PRESERVE_TEST_SOURCE'])
family=os.environ['OW_PRESERVE_FAMILY'];assert family in ('jaguar','sage')
source_version=os.environ.get('OW_PRESERVE_SOURCE_VERSION','2026.10.02.1').encode()
work=pathlib.Path(tempfile.mkdtemp(prefix='preserve-combined-gates.'))
root=work/'root';shutil.copytree(source,root,symlinks=True)
prepare=(bundle/'prepare-upgrader.sh').read_text()
functions=[]
for name in ('metadata_fingerprint','release_gate','runtime_gate','source_gate'):
 match=re.search(r'(?ms)^'+name+r'\(\) \{.*?^\}',prepare)
 assert match,name
 text=match.group()
 if name=='source_gate':
  text=text.replace('for path in /lib/*.sh /lib/functions/*.sh /lib/upgrade/*.sh;',
   'for path in "$BRIDGE_ROOT"/lib/*.sh "$BRIDGE_ROOT"/lib/functions/*.sh "$BRIDGE_ROOT"/lib/upgrade/*.sh;')
  text=text.replace('grep -Fxq "$path"', 'logical=${path#"$BRIDGE_ROOT"}\n  grep -Fxq "$logical"')
 functions.append(text)
checker=(bundle/'source-set-check.sh').read_text().replace('ow_source_set_matches()', 'ow_actual_source_set_matches()')
(work/'checker.sh').write_text(checker)
driver=work/'driver.sh'
driver.write_text('''#!/bin/sh
set -eu
bundle=$1
BRIDGE_ROOT=$2
. "$3/checker.sh"
. "$bundle/minimum-release-contract.sh"
. "$bundle/runtime-implementation-contract.sh"
ow_source_set_matches() { ow_actual_source_set_matches "$1" "$2" "$BRIDGE_ROOT"; }
'''+ '\n'.join(functions)+'\nsource_gate\n')
tests=[]
def run(name,expected):
 result=subprocess.run(['sh',str(driver),str(bundle),str(root),str(work)],text=True,capture_output=True)
 assert (result.returncode==0)==expected,(name,result.returncode,result.stderr)
 tests.append({'case':name,'passed':True,'accepted':expected})
def bytes_case(name,path,content,expected=False):
 p=root/path;original=p.read_bytes() if p.exists() else None
 p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(content)
 try:run(name,expected)
 finally:
  if original is None:p.unlink()
  else:p.write_bytes(original)
run('actual-frozen-source',True)
metadata=(root/'etc/openwrt_release').read_bytes()
bytes_case('newer-same-implementation','etc/openwrt_release',metadata.replace(source_version,b'2026.10.02.99'),True)
bytes_case('below-minimum','etc/openwrt_release',metadata.replace(source_version,b'2026.10.02.0'))
bytes_case('malformed-calendar','etc/openwrt_release',metadata.replace(source_version,b'2026.02.30.1'))
bytes_case('wrong-family','etc/openwrt_release',metadata.replace((family+'-2026.').encode(),b'thor-2026.'))
bytes_case('wrong-architecture','etc/openwrt_release',metadata.replace(b'DISTRIB_ARCH=',b'UNKNOWN_ARCH='))
bytes_case('mixed-stock-namespace','etc/cambium-openwrt-release',b"CAMBIUM_FAMILY='"+family.encode()+b"'\n")
bytes_case('metadata-path-injection','etc/openwrt_release',metadata+b"PATH='/tmp/unknown'\n")
bytes_case('new-wildcard-script','lib/upgrade/unreviewed-preserve-test.sh',b'#!/bin/sh\nexit 0\n')
p=root/'etc/openwrt_release';p.write_bytes(metadata.replace(source_version,b'2026.10.02.99'))
codepath='lib/functions/cambium-ab.sh'
bytes_case('newer-label-modified-updater',codepath,(root/codepath).read_bytes()+b'\n# unknown bytes\n')
p.write_bytes(metadata)
for label,path in [('busybox','bin/busybox'),('crypto-library','usr/lib/libcrypto.so.3'),('ucode-fs-import','usr/lib/ucode/fs.so')]:
 p=root/path
 if p.is_symlink():
  # Resolve only relative reviewed library aliases within the copied namespace.
  target=os.readlink(p);assert not target.startswith('/'),path
  p=p.parent/target
 bytes_case('modified-'+label,str(p.relative_to(root)),p.read_bytes()+b'unknown')
bytes_case('modified-openssl-configuration','etc/ssl/openssl.cnf',(root/'etc/ssl/openssl.cnf').read_bytes()+b'\n# unqualified\n')
bytes_case('injected-musl-search-path','etc/ld-musl-aarch64.path',b'/tmp/unqualified-libraries\n')
p=root/'bin/busybox';mode=p.stat().st_mode;p.chmod(mode & ~0o111)
try:run('runtime-executable-mode-drift',False)
finally:p.chmod(mode)
link=root/'bin/sh';assert link.is_symlink();target=os.readlink(link)
link.unlink();link.symlink_to('unknown-ash')
try:run('runtime-alias-drift',False)
finally:link.unlink();link.symlink_to(target)
run('restored-known-source',True)
print(json.dumps({'passed':True,'count':len(tests),'cases':tests,'fixture':str(work),
 'prepare_sha256':hashlib.sha256(prepare.encode()).hexdigest(),
 'scope':'Actual metadata/runtime/source gate functions with filesystem paths redirected only. No AP libraries, hardware helpers, network or upgrade executed.'},indent=2))
