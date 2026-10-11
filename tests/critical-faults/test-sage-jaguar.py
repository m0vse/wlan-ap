#!/usr/bin/env python3
"""Execute production selector/evaluator and LED helper on isolated fixtures.

Use an existing target root with qemu, never an AP. This verifies family source
compatibility, not NAND ioctls, physical LEDs, or a firmware build/release.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[2]
SAGE = ('cambium,e410', 'cambiumnetworks,e410', 'cambiumnetworks,e410b')
JAGUAR = ('cambiumnetworks,xv2-2', 'cambiumnetworks,xv2-2t1', 'cambiumnetworks,xe3-4')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--qemu', default='/usr/bin/qemu-aarch64')
    parser.add_argument('--geometry', type=Path, default=Path(__file__).with_name('sage-jaguar-physical-geometry.json'))
    base = REPO / 'feeds/ucentral/ucentral-state/files'
    parser.add_argument('--module', type=Path, default=base / 'faults.uc')
    parser.add_argument('--profiles', type=Path, default=base / 'storage-canary.json')
    parser.add_argument('--helper', type=Path, default=REPO / 'feeds/ucentral/ucentral-client/files/usr/libexec/ucentral-led.sh')
    args = parser.parse_args()
    runtime = args.runtime_root.resolve()
    module = args.module.read_text()
    profile_bytes = args.profiles.read_bytes()
    profiles = json.loads(profile_bytes)
    geometry_bytes = args.geometry.read_bytes()
    geometry = json.loads(geometry_bytes)
    assert geometry['format'] == 1
    helper = args.helper.read_text()
    cases = []
    checks = 0

    def add(name, board, records, status, override=None):
        cases.append(dict(name=name, board=board, records=records, status=status, profiles=override or profiles))

    for board in (*SAGE, *JAGUAR):
        # Reference rows came from independent physical DTS partition-reg
        # evidence, never from the candidate profile or relative A/B table.
        reference = geometry['references'][geometry['board_references'][board]]
        assert reference['mtd_type'] == 'nand'
        expected = reference['banks']
        size = expected[0]['size']
        specs = profiles[board]
        assert len(specs) == len(expected), (board, 'physical bank count')
        for spec, exact in zip(specs, expected):
            assert all(spec.get(k) == v for k, v in exact.items()), (board, spec, exact)
            samples = spec['samples'].split(',')
            assert 1 <= len(samples) <= 8 and all(s.isdigit() and int(s) < size // 131072 for s in samples)
        records = [dict(index=29 + i * 33, type='nand', paired_ubi=True, **spec) for i, spec in enumerate(expected)]
        # Unrelated NAND and identity NOR must never become sampled banks.
        records += [dict(index=91, name='NVRAM', type='nand', size=16777216, erase=131072, write=2048, offset=201326592),
                    dict(index=92, name='0:ART', type='nor', size=65536, erase=65536, write=1, offset=1507328)]
        add(board + ':valid', board, records, 'qualified')
        for field, value in [('name', 'unknown'), ('type', 'nor'), ('size', size + 131072),
                             ('erase', 65536), ('write', 4096), ('offset', 1)]:
            changed = copy.deepcopy(records); changed[0][field] = value
            add(board + ':' + field, board, changed, 'unavailable')
        add(board + ':missing', board, records[1:], 'unavailable')
        add(board + ':ambiguous', board, records + [dict(records[0], index=93)], 'unavailable')
        absent_offset = copy.deepcopy(records); absent_offset[0]['offset'] = None
        # Offset is checked when exposed; this does not introduce a new gate.
        add(board + ':offset-unexposed', board, absent_offset, 'qualified')
        if board in SAGE:
            unproven = copy.deepcopy(records); unproven[0]['paired_ubi'] = False
            add(board + ':paired-ubi-unproven', board, unproven, 'unavailable')
        else:
            add(board + ':peer-missing', board, [records[0], *records[2:]], 'unavailable')
            # Miami's reserved prefix must not leak into these independently
            # verified zero-based Jaguar NAND partitions.
            wrong_prefix = copy.deepcopy(profiles)
            for spec in wrong_prefix[board]:
                spec['offset'] += 6 * 131072
            add(board + ':foreign-reserved-prefix', board, records, 'unavailable', wrong_prefix)
        bad = copy.deepcopy(profiles); bad[board][0]['samples'] = '0;not-a-command'
        add(board + ':bad-sample-profile', board, records, 'unavailable', bad)
    for board in ('cambiumnetworks,xv2-2t0', 'cambiumnetworks,xe3-4tn', 'cambiumnetworks,e600', 'example,board'):
        add(board + ':unqualified', board, [], 'unsupported')

    with tempfile.TemporaryDirectory(prefix='sage-jaguar-fault-compat-') as tmp:
        work = Path(tmp)
        # Only import/export/CJS bindings are replaced. Function implementations are
        # the exact production snapshot; selector/evaluator need no native I/O.
        pure = '\n'.join(line for line in module.splitlines() if not line.startswith('import '))
        pure = pure.replace('export function ', 'function ')
        epilogue = 'return { evaluate, snapshot, radio_facts, select_banks };'
        if pure.rstrip().endswith(epilogue):
            pure = pure.rstrip()[:-len(epilogue)]
        script = work / 'selector.uc'
        script.write_text("let fs = {};\n" + pure + '\nlet cases = ' + json.dumps(cases) + r''';
let results = [];
for (let c in cases) push(results, select_banks(c.profiles, c.board, c.records));
// Current critical mount failures debounce and clear when facts recover.
let bad = { mtd: [], canary: [], mounts: [{path:'/overlay',readonly:true,total_bytes:10000000,available_bytes:5000000}] };
let first = evaluate(bad, null, 1000);
let second = evaluate(bad, first, 1060);
let good = evaluate({mtd:[],canary:[],mounts:[{path:'/overlay',readonly:false,total_bytes:10000000,available_bytes:5000000}]}, second, 1120);
printf('%J\n', {results, first, second, good});
''')
        cmd = [args.qemu, '-L', str(runtime), str(runtime / 'usr/bin/ucode'), str(script)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
        output = json.loads(result.stdout)
        for case, got in zip(cases, output['results']):
            assert got['status'] == case['status'], (case['name'], got)
            if case['status'] != 'qualified':
                assert got['banks'] == [], (case['name'], got)
            else:
                wanted = case['profiles'][case['board']]
                assert len(got['banks']) == len(wanted), (case['name'], got)
                assert [b['index'] for b in got['banks']] == [29 + i * 33 for i in range(len(wanted))], (case['name'], got)
                assert all(b['name'] not in ('NVRAM', '0:ART', 'nvram') for b in got['banks'])
            checks += 1
        assert len(output['results']) == len(cases)
        assert output['first']['active'] == [] and output['good']['active'] == []
        assert any(f['code'] == 'storage_readonly' for f in output['second']['active'])
        checks += 3

        # Real helper under target ash; rewrite only filesystem bindings/stubs.
        for number, board in enumerate((*SAGE, *JAGUAR)):
            fixture = work / str(number); fixture.mkdir()
            leds = fixture / 'leds'; leds.mkdir()
            faultdir = fixture / 'faults'; faultdir.mkdir(mode=0o700)
            blue, green, amber, red = ('blue:status', 'green:status', 'amber:status', 'red:status') if board in SAGE else (
                'jaguar:status:blue', 'jaguar:status:green', 'jaguar:status:orange', 'jaguar:status:red')
            for name in (blue, green, amber, red):
                p = leds / name; p.mkdir()
                for key, value in [('brightness', '0'), ('trigger', 'none'), ('max_brightness', '255')]:
                    (p / key).write_text(value)
            stub = fixture / 'functions.sh'
            stub.write_text('board_name() { printf "%s" "$TEST_BOARD"; }\nuci() { printf "%s" "$TEST_OFF"; }\n')
            actual = fixture / 'helper.sh'
            actual.write_text(helper.replace('/lib/functions.sh', str(stub)).replace('/sys/class/leds', str(leds))
                              .replace('/tmp/ucentral-led-phase', str(fixture / 'phase')).replace('/tmp/ucentral-faults', str(faultdir)))

            def run(op, off='0'):
                env = dict(os.environ, TEST_BOARD=board, TEST_OFF=off)
                r = subprocess.run([args.qemu, '-0', 'ash', '-L', str(runtime), str(runtime / 'bin/busybox'), str(actual), op],
                                   env=env, capture_output=True, text=True, timeout=10)
                assert r.returncode == 0, (board, op, r.stderr)

            def value(name, prop='brightness'):
                return (leds / name / prop).read_text().strip()

            run('fault-supported'); run('fault-blue')
            assert value(blue) == '255' and value(amber) == value(green) == '0'; checks += 1
            run('fault-orange')
            assert value(amber) == '255' and value(blue) == value(green) == '0'; checks += 1
            run('fault-clear'); run('restore-off')
            assert value(green) == '255' and value(amber) == value(blue) == '0'; checks += 1
            run('fault-orange'); run('fault-blue', '1')
            assert all(value(n) == '0' for n in (blue, green, amber, red)); checks += 1
            run('phase-upgrade'); run('fault-blue')
            assert value(blue) == value(green) == '0'; checks += 1
            run('phase-done'); run('pattern')
            (leds / green / 'trigger').write_text('none [timer]')
            run('fault-orange')
            assert value(green, 'trigger') == 'none [timer]' and value(amber) == '0'; checks += 1
            (leds / green / 'trigger').write_text('none')
            run('fault-blue'); run('fault-clear'); run('restore-on')
            assert value(blue) == '255' and value(amber) == value(green) == '0'; checks += 1
    print(json.dumps(dict(status='PASS', checks=checks, selector_cases=len(cases), boards=6,
                          module_sha256=hashlib.sha256(module.encode()).hexdigest(),
                          profile_sha256=hashlib.sha256(profile_bytes).hexdigest(),
                          geometry_sha256=hashlib.sha256(geometry_bytes).hexdigest(),
                          helper_sha256=hashlib.sha256(helper.encode()).hexdigest(),
                          scope='Actual target ucode/ash and production functions; isolated fixtures only, no native MTD or AP qualification.')))


if __name__ == '__main__':
    main()
