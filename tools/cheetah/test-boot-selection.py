#!/usr/bin/env python3
"""Execute the real boot selector with isolated paths and mocked detection/render.

This checks selection/fail-closed orchestration, not the renderer or networking.
"""
from pathlib import Path
import json, os, re, subprocess, sys, tempfile

source = Path(sys.argv[1]).read_text()
with tempfile.TemporaryDirectory(prefix='cheetah-boot-selection-') as temp:
    work = Path(temp)
    for name in ('saved-tagged', 'saved-untagged', 'uuid1', 'unconfigured',
                 'fallback2', 'empty', 'dangling', 'malformed', 'missing-baseline'):
        root = work / name
        for directory in ('etc/ucentral', 'etc/config-shadow', 'tmp', 'rom/etc/ucentral',
                          'sbin', 'usr/bin', 'usr/share/ucentral', 'bin'):
            (root / directory).mkdir(parents=True)
        for item in ('network', 'system', 'dhcp', 'firewall', 'dropbear', 'ucentral'):
            (root / 'etc/config-shadow' / item).touch()
        factory = root / 'rom/etc/ucentral/ucentral.cfg.0000000001'
        factory.write_text('{"uuid":1}')
        active = root / 'etc/ucentral/ucentral.active'
        expected = active
        if name.startswith('saved') or name == 'missing-baseline':
            active.write_text(json.dumps({'uuid': 37, 'vlan': 37 if name == 'saved-tagged' else 0}))
        elif name == 'uuid1':
            active.write_text('{"uuid":1}')
            expected = factory
        elif name == 'empty': active.touch()
        elif name == 'dangling': active.symlink_to(root / 'missing')
        elif name == 'malformed': active.write_text('{invalid')
        elif name == 'fallback2':
            expected = root / 'etc/ucentral/ucentral.cfg.0000000002'
            expected.write_text('{"uuid":2}')
        else: expected = factory
        if name == 'missing-baseline': (root / 'etc/config-shadow/network').unlink()
        script = re.sub(r'/(?:etc|tmp|rom|usr|sbin)/', lambda m: str(root) + m[0], source)
        selector = root / 'selector.sh'
        selector.write_text(script)
        def executable(path, text):
            path.write_text(text); path.chmod(0o755)
        executable(root / 'bin/logger', '#!/bin/sh\nexit 0\n')
        executable(root / 'bin/jsonfilter', '#!/usr/bin/env python3\nimport json,sys\ntry: print(json.load(open(sys.argv[2]))["uuid"])\nexcept: sys.exit(1)\n')
        executable(root / 'sbin/wifi', '#!/bin/sh\nexit 0\n')
        executable(root / 'usr/share/ucentral/capabilities.uc', f'#!/bin/sh\nprintf \'{{"wifi":true}}\' > "{root}/etc/ucentral/capabilities.json"\n')
        executable(root / 'usr/bin/ucode', f'''#!/usr/bin/env python3
import json,sys
from pathlib import Path
selected=sys.argv[3]
Path("{root}/selected").write_text(selected)
try: json.loads(Path(selected).read_text())
except: sys.exit(1)
Path("{root}/tmp/ucentral-network.ready").write_text('ready')
''')
        env = dict(os.environ, PATH=str(root / 'bin') + ':' + os.environ['PATH'])
        proc = subprocess.run(['sh', str(selector)], env=env, capture_output=True)
        should_pass = name not in ('empty', 'dangling', 'malformed', 'missing-baseline')
        assert (proc.returncode == 0) == should_pass, (name, proc.stderr)
        assert (root / 'tmp/ucentral-network.ready').exists() == should_pass, name
        if should_pass:
            assert (root / 'selected').read_text() == str(expected), name
        else:
            assert (root / 'etc/ucentral/network-boot.failure').exists(), name
            assert active.exists() or active.is_symlink(), name
    print('PASS: 9 real boot-selector cases; detector/renderer mocked, no network activation')
