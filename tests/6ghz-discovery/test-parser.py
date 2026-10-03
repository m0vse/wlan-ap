#!/usr/bin/env python3
"""Target parser controls; invalid driver ensures no radio/driver initialization."""
from pathlib import Path
import subprocess
import sys
import tempfile

emu, root = sys.argv[1:3]
wifi5 = '--wifi5' in sys.argv[3:]
root = Path(root)
with tempfile.TemporaryDirectory(prefix='6ghz-parser.') as tmp:
    config = Path(tmp) / 'hostapd.conf'
    for option in ['fils_discovery_min_interval=0', 'fils_discovery_max_interval=20',
                   'unsol_bcast_probe_resp_interval=20', 'acs_exclude_6ghz_non_psc=1']:
        config.write_text('driver=deliberately_invalid_no_radio\nssid=fixture\n'+option+'\n')
        result = subprocess.run([emu, '-L', str(root), str(root/'usr/sbin/wpad'),
                                 'hostapd', str(config)], capture_output=True, text=True, timeout=5)
        output = result.stdout + result.stderr
        assert result.returncode != 0 and 'invalid/unknown driver' in output, output
        if wifi5 and option.startswith('unsol_bcast_probe_resp_interval='):
            assert 'unknown configuration item' in output, (option,output)
        else:
            assert 'unknown configuration item' not in output, (option,output)
    config.write_text('driver=deliberately_invalid_no_radio\nunknown_discovery_control=1\n')
    result = subprocess.run([emu, '-L', str(root), str(root/'usr/sbin/wpad'),
                             'hostapd', str(config)], capture_output=True, text=True, timeout=5)
    assert 'unknown configuration item' in result.stdout+result.stderr
    print('Actual target parser discovery controls PASS; unknown-key negative control rejected; driver never initialized; wifi5='+str(wifi5))
