#!/usr/bin/env python3
"""Replay the shared board-data import and run its synthetic-data tests."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PREFIX = 'package/cambium/cambium-board-data/'
source = ROOT / 'patches-25.12/0124-qualcommax-add-Cambium-Jaguar-OpenWiFi-family.patch'
with tempfile.TemporaryDirectory(prefix='xe34-board-import.') as tmp:
    fixture = Path(tmp)
    current = None
    lines = []
    def flush():
        if current and current.startswith(PREFIX):
            dest = fixture / current
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text('\n'.join(lines) + '\n')
    for line in source.read_text().splitlines():
        if line.startswith('diff --git '):
            flush()
            current = None
            lines = []
        elif line.startswith('+++ b/'):
            current = line[6:]
        elif line.startswith('+') and not line.startswith('+++'):
            lines.append(line[1:])
    flush()
    patch = ROOT / 'patches-25.12/0158-cambium-board-data-select-own-XE34-API2.patch'
    subprocess.run(['patch', '-p1', '-F0', '--batch', '-d', tmp],
                   input=patch.read_text(), text=True, check=True)
    package = fixture / PREFIX
    subprocess.run(['sh', '-n', str(package / 'files/cambium-board-data')], check=True)
    subprocess.run(['python3', str(package / 'tests/test-xe34-api2.py')], check=True)
    assert 'PKG_RELEASE:=5\n' in (package / 'Makefile').read_text()
    print('Board-data series zero-fuzz replay, shell syntax and synthetic tests PASS')
