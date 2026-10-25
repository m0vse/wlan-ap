#!/usr/bin/env python3
"""Run actual BAM probe against the complete, unmodified DMA core registration.

Hardware and framework channel primitives are mocked; DMA registration's actual
owner dereference and unregister control flow execute under ASan/UBSan. The
shipped root-device identity is a runtime negative, never a compilation failure.
"""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--provider', type=Path, required=True)
parser.add_argument('--dma-core', type=Path, required=True)
parser.add_argument('--expect-unsafe', action='store_true')
args = parser.parse_args()
provider = args.provider.read_text()
core = args.dma_core.read_text()

def function(source, name):
    match = re.search(r'^(?:static )?(?:int|void|struct module \*)\s*' +
                      re.escape(name) + r'\([^;]*?\)\s*\{', source, re.M)
    assert match, name
    brace = source.index('{', match.start())
    end, depth = brace + 1, 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[match.start():end]

fixture = Path(__file__).with_name('dma-registration-fixture.c').read_text()
fixture = fixture.replace('/* ACTUAL_DMA_CORE */', '\n\n'.join(
    function(core, name) for name in (
        'dma_async_device_register', 'dma_async_device_unregister',
        'dma_chan_to_owner')))
probe = function(provider, 'bam_dma_probe')

with tempfile.TemporaryDirectory() as directory:
    directory = Path(directory)
    def execute(name, source_probe, negative):
        source = directory / (name + '.c')
        binary = directory / name
        source.write_text(fixture.replace('/* ACTUAL_PROVIDER_PROBE */', source_probe))
        subprocess.run(['cc', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra',
                        '-Werror', '-Wno-unused-function', '-Wno-unused-variable',
                        '-Wno-unused-parameter', '-Wno-sign-compare',
                        '-fsanitize=address,undefined',
                        '-o', str(binary), str(source)], check=True)
        result = subprocess.run([str(binary), str(int(negative))],
                                capture_output=True, text=True)
        if negative:
            assert result.returncode != 0, result.stdout
            assert 'dma_async_device_register' in result.stderr, result.stderr
            assert 'null pointer' in result.stderr or 'AddressSanitizer' in result.stderr, result.stderr
            assert 'UNEXPECTED_SAFE_REGISTRATION' not in result.stderr, result.stderr
            print('PASS runtime negative: actual DMA core rejects driverless root registration with null-driver fault')
        else:
            assert result.returncode == 0, (result.stdout, result.stderr)
            print(result.stdout, end='')
    execute('actual', probe, args.expect_unsafe)
    if not args.expect_unsafe:
        before = 'bdev->common.dev = &pdev->dev;'
        assert probe.count(before) == 2
        execute('released-negative', probe.replace(before,
                'bdev->common.dev = bdev->dma_dev;'), True)
