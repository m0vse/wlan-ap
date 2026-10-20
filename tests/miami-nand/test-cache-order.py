#!/usr/bin/env python3
"""Reject actual unsafe RESET/status and synthetic-injection cache orderings."""
from pathlib import Path
import argparse
import subprocess
import sys
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--driver', type=Path, required=True)
parser.add_argument('--fixture', type=Path, default=Path(__file__).with_name('test-recovery-probe.py'))
args = parser.parse_args()
source = args.driver.read_text()
reset = ''' if (!ret) {
  nandc_read_buffer_sync(n, true);
  ret = qpic_serial_check_status(n->reg_read_buf);
 }'''
assert source.count(reset) == 1
unsafe_reset = source.replace(reset, ' if (!ret) ret = qpic_serial_check_status(n->reg_read_buf);', 1)
inject = '\n\tmiami_probe_inject(host, page);'
read = '\tret = parse_read_errors(host, data_buf_start, oob_buf_start, page);'
assert source.count(inject) == 1 and source.count(read) == 1
unsafe_inject = source.replace(inject, '', 1).replace(read, inject.strip('\n') + '\n' + read, 1)
with tempfile.TemporaryDirectory() as tmp:
    for name, text in [('RESET-without-CPU-sync', unsafe_reset), ('ECC-injection-before-CPU-sync', unsafe_inject)]:
        path = Path(tmp) / (name + '.c')
        path.write_text(text)
        subprocess.run([sys.executable, str(args.fixture), '--driver', str(path), '--expect-cache-order-failure'], check=True)
        print('PASS cache-order negative:', name)
