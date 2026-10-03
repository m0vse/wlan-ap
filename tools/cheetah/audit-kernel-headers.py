#!/usr/bin/env python3
import json,re,sys
from pathlib import Path
root=Path(sys.argv[1]);kernel=root/'build_dir/target-aarch64_cortex-a53_musl/linux-qualcommax_ipq50xx'
objects=[kernel/'linux-6.12.85/drivers/net/mdio/.mdio-ipq4019.o.cmd',kernel/'mac80211-regular/backports-6.18.7/net/mac80211/.main.o.cmd']
objects+=list(kernel.glob('qca-ssdk-*/**/.*.o.cmd'))
objects+=list(kernel.glob('batman-adv-*/**/.*.o.cmd'))
assert len(objects)>2, 'SSDK objects missing'
report=[]
for p in objects:
 s=p.read_text(); match=re.search(r'\ndeps_[^\n]*?:=',s)
 if not match and re.search(r'aarch64-openwrt-linux-musl-ld(?:\.bfd)? ',s):
  assert '-EL' in s, 'Aggregate object link is not little endian'
  continue
 assert match, f'Missing dependency section: {p}'
 deps=s[match.end():]
 userspace=re.findall(r'\S*staging_dir/target[^\s]*?/usr/include/[^\s\\]*',deps)
 kernel_backport=[h for h in userspace if '/usr/include/mac80211/' in h or '/usr/include/mac80211-backport/' in h]
 userspace=[h for h in userspace if h not in kernel_backport]
 row={'object':str(p.relative_to(root)),'nostdinc':'-nostdinc' in s,'little_endian':'-mlittle-endian' in s,'staged_userspace_header_dependencies':userspace,'staged_kernel_backport_header_count':len(kernel_backport)}
 assert row['nostdinc'] and row['little_endian'] and not userspace, row
 report.append(row)
print(json.dumps({'objects_checked':len(report),'objects':report,'passed':True},indent=2))
