#!/usr/bin/env python3
from pathlib import Path
import difflib, subprocess
parent=Path('/home/phil/openwifi-cheetah-build/wlan-ap')
root=parent/'openwrt'
raw=Path('/tmp/0127-cambium-ab-retain-bank-local-certificate-content.patch').read_text()
core=raw.split('diff --git a/target/linux/qualcommax/ipq60xx/')[0]
check=subprocess.run(['git','apply','--check','-'],cwd=root,input=core,text=True,capture_output=True)
if check.returncode == 0:
    subprocess.run(['git','apply','-'],cwd=root,input=core,text=True,check=True)
else:
    subprocess.run(['git','apply','--reverse','--check','-'],cwd=root,input=core,text=True,check=True)
rel='target/linux/qualcommax/ipq50xx/base-files/lib/upgrade/platform.sh'
p=root/rel
old=p.read_text()
assert 'ab_certificate_export' not in old
hook='''platform_pre_upgrade() {
\tif command -v ab_family >/dev/null && ab_family; then
\t\tab_certificate_export || {
\t\t\techo 'A/B upgrade: certificate snapshot failed; no bank was written' >&2
\t\t\texit 1
\t\t}
\t\treturn 0
\tfi
'''
new=old.replace('platform_pre_upgrade() {\n',hook,1)
assert old!=new
p.write_text(new)
platform=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+rel,tofile='b/'+rel))
(parent/'patches-25.12/0128-cambium-ab-retain-bank-local-certificate-content.patch').write_text(core+platform)
print('Canonical content helper installed with Cheetah pre-upgrade hook')
