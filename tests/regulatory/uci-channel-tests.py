#!/usr/bin/env python3
"""Run the real selected target UCI CLI on synthetic wireless configs only."""
import pathlib
import subprocess
import sys
import tempfile

qemu, root = sys.argv[1:3]
root = pathlib.Path(root)
cli = [qemu, '-L', str(root), str(root / 'sbin/uci')]
count = 0
with tempfile.TemporaryDirectory(prefix='xe34-real-uci.') as work:
    config = pathlib.Path(work) / 'config'
    save = pathlib.Path(work) / 'save'
    config.mkdir()
    save.mkdir()
    def batch(commands):
        return subprocess.run(cli + ['-c', str(config), '-t', str(save), 'batch'],
                              input=commands, text=True, capture_output=True, check=False)
    def fixture(option=''):
        (config / 'wireless').write_text("config wifi-device 'radio2'\n\toption type 'mac80211'\n" + option)
        for path in save.iterdir():
            path.unlink()
    fixture()
    broken = batch('delete wireless.radio2.channels\n')
    assert 'Entry not found' in broken.stderr, broken
    count += 1
    replacement = "set wireless.radio2.channels='__reset__'\ndelete wireless.radio2.channels\n"
    for option in ('', "\toption channels '36'\n", "\tlist channels '36'\n\tlist channels '36'\n\tlist channels '149'\n"):
        fixture(option)
        for repeat in range(2):
            result = batch(replacement + 'add_list wireless.radio2.channels=1\nadd_list wireless.radio2.channels=5\ncommit wireless\n')
            assert result.returncode == 0 and not result.stderr, (option, repeat, result)
            got = subprocess.run(cli + ['-c', str(config), '-t', str(save), 'get', 'wireless.radio2.channels'],
                                 capture_output=True, text=True, check=True)
            assert got.stdout.strip() == '1 5', got
            count += 1
    fixture()
    result = batch(replacement + 'commit wireless\n')
    assert result.returncode == 0 and not result.stderr, result
    assert 'channels' not in (config / 'wireless').read_text()
    count += 1
    bad = batch(replacement + 'delete wireless.nonexistent.channels\n')
    assert 'Entry not found' in bad.stderr, bad
    count += 1
print(f'Actual target UCI channel-reset controls: {count} PASS')
