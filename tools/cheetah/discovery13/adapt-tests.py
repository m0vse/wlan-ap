from pathlib import Path
import hashlib
b=Path('/home/phil/openwifi-cheetah-build');image=b/'discovery13/cambium_xv2-21x-cheetah-2026.10.02.13-sysupgrade.bin';sha=hashlib.sha256(image.read_bytes()).hexdigest()
s=(b/'dfs12/test-validator.py').read_text().replace('/tmp/cheetah-image-check.dixkA1/rootfs','/tmp/cheetah-image-check.c1ktu4/rootfs').replace('dfs12/cambium_xv2-21x-cheetah-2026.10.02.12-sysupgrade.bin','discovery13/cambium_xv2-21x-cheetah-2026.10.02.13-sysupgrade.bin').replace('819bcef819df28c71d1a40d27c682dd2756a8386ac4c30ab4fc7f0e1ef3c5bc1',sha)
(b/'discovery13/test-validator.py').write_text(s)
s=(b/'dfs12/test-ram-copy.py').read_text().replace('/tmp/cheetah-image-check.dixkA1/rootfs','/tmp/cheetah-image-check.c1ktu4/rootfs').replace('dfs12/cambium_xv2-21x-cheetah-2026.10.02.12-sysupgrade.bin','discovery13/cambium_xv2-21x-cheetah-2026.10.02.13-sysupgrade.bin')
(b/'discovery13/test-ram-copy.py').write_text(s)
