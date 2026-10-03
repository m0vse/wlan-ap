from pathlib import Path
import hashlib
b=Path('/home/phil/openwifi-cheetah-build');image=b/'dfs12/cambium_xv2-21x-cheetah-2026.10.02.12-sysupgrade.bin'
sha=hashlib.sha256(image.read_bytes()).hexdigest()
p=b/'operator-preserve-minimum-r6/test-stock-sysupgrade.py';s=p.read_text().replace("payload=base/'operator-preserve-minimum-r6/payload'","payload=base/'dfs12/payload'")
s=s.replace("base/'release/cheetah-openwifi-2026.10.02.11/cambium_xv2-21x-cheetah-2026.10.02.11-sysupgrade.bin'",repr(str(image)))
s=s.replace("image="+repr(str(image)),"image=pathlib.Path("+repr(str(image))+")")
s=s.replace('b3665834e1594d401d0c07183058673d5eba1a7da008c43b98333e0a69b4015c',sha)
(b/'dfs12/test-validator.py').write_text(s)
p=b/'operator-preserve-minimum-r6/test-ram-copy.py';s=p.read_text().replace("suite=base/'operator-preserve-minimum-r6'","suite=base/'dfs12'")
s=s.replace("base/'release/cheetah-openwifi-2026.10.02.11/cambium_xv2-21x-cheetah-2026.10.02.11-sysupgrade.bin'","base/'dfs12/cambium_xv2-21x-cheetah-2026.10.02.12-sysupgrade.bin'")
(b/'dfs12/test-ram-copy.py').write_text(s)
