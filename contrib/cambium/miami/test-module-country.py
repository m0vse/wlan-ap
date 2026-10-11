#!/usr/bin/env python3
"""Run the actual country helper against saved module settings."""
from pathlib import Path
import os, shutil, subprocess, tempfile
repo = Path(__file__).resolve().parents[3]
helper = repo / 'feeds/tip/certificates/files/usr/libexec/ucentral-module-country'
with tempfile.TemporaryDirectory(prefix='miami-module-country-') as directory:
    work = Path(directory)
    # macOS has no flock; lock behavior is checked on the Linux build host.
    if not shutil.which('flock'):
        stub = work / 'flock'
        stub.write_text('#!/bin/sh\nexit 0\n')
        stub.chmod(0o755)
    conf = work / 'modules.conf'
    env = dict(os.environ, UCENTRAL_MODULE_CONF=str(conf),
               UCENTRAL_MODULE_LOCK=str(work/'lock'), PATH=str(work)+':'+os.environ['PATH'])
    cases = [
        '',
        '# preserved\noptions ath12k mem_profile=low\noptions usbcore autosuspend=-1\n',
        'options ath12k mem_profile=auto\noptions cfg80211 ieee80211_regdom=US other=1 # country\n',
        'options cfg80211 ieee80211_regdom=FR\noptions cfg80211 other=2 ieee80211_regdom=DE\n',
    ]
    for country in ['GB', '00']:
        for original in cases:
            conf.write_text(original)
            conf.chmod(0o600)
            subprocess.run(['sh', str(helper), country], env=env, check=True)
            result = conf.read_text()
            assert conf.stat().st_mode & 0o777 == 0o600
            assert result.count('ieee80211_regdom=') == 1, result
            assert 'ieee80211_regdom='+country in result
            for line in original.splitlines():
                if not line.startswith('options cfg80211'):
                    assert line in result
            if 'other=' in original:
                assert 'other=' in result
            subprocess.run(['sh', str(helper), country], env=env, check=True)
            assert conf.read_text() == result
    before = conf.read_bytes()
    for invalid in ['G', 'gb', 'GB;echo bad', 'USA', '']:
        assert subprocess.run(['sh', str(helper), invalid], env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0
        assert conf.read_bytes() == before
print('PASS: module settings survive country changes; updates are idempotent and invalid inputs preserve the file')
