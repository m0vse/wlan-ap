#!/usr/bin/env python3
"""Joint source-path gate, never a claim of natural-fault/hardware acceptance.

All inputs must be the actual, fully patched kernel tree. Caller isolation alone
is insufficient: owner removal, late callbacks, provider quota and mutation
controls must pass too. Nothing accesses a physical AP.
"""
import argparse
from pathlib import Path
import subprocess
import sys

parser = argparse.ArgumentParser()
for argument in ('driver', 'provider', 'driver-core', 'virt-dma'):
    parser.add_argument('--' + argument, type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).parent
def run(script, *options):
    subprocess.run([sys.executable, str(root / script), *map(str, options)], check=True)

run('test-bounce-ownership.py', '--driver', args.driver, '--require-no-caller-alias')
run('test-bounce-ownership.py', '--driver', args.driver, '--expect-bounce-failure')
run('test-provider-discard.py', '--driver', args.driver,
    '--provider', args.provider, '--virt-dma', args.virt_dma)
run('test-provider-budget.py', '--provider', args.provider)
run('test-lifetime-owner.py', '--client', args.driver,
    '--provider', args.provider, '--driver-core', args.driver_core)
run('test-lifetime-negative-controls.py', '--client', args.driver,
    '--provider', args.provider, '--driver-core', args.driver_core)
print('PASS JOINT SOURCE GATE: caller isolation + actual provider/owner removal and negative controls; hardware acceptance pending')
