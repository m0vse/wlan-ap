#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Inspect real nl80211 SSID encoding; interceptor prevents every scan send.

Build the interceptor with the selected module's headers; define
SCAN_USE_QCA_HEADER only for QCA-6/7 builds using nl80211_copy.h. Existing
nl80211 family discovery is allowed; TRIGGER_SCAN exits before transmission.
No live RF, interface creation, channel changes or hardware are used by cases.
Run on Linux with the matching ucode/module ABI and libnl-tiny development files.
"""
import argparse
import json
import shlex
import subprocess

p = argparse.ArgumentParser()
p.add_argument('--ucode', required=True)
p.add_argument('--old-module', required=True)
p.add_argument('--new-module', required=True)
p.add_argument('--interceptor', required=True)
p.add_argument('--decoder-interceptor')
p.add_argument('--ssh-target')
p.add_argument('--ssh-known-hosts')
a = p.parse_args()
cases = [None, [''], ['Example Network'], ['x'], ['x' * 32],
         ['caf\u00e9'], ['a\x00b'], ['', 'Example Network', 'a\x00b']]
count = 0
for label, module, fixed in [('old', a.old_module, False),
                             ('fixed', a.new_module, True)]:
    for ssids in cases:
        attrs = {'dev': 'lo'}
        if ssids is not None:
            attrs['scan_ssids'] = ssids
        code = ('let n=require("nl80211"); let fs=require("fs"); '
                'assert(index(fs.readfile("/proc/self/maps"),' + json.dumps(module) +
                ')>=0,"Requested module was not loaded"); n.request('
                'n.const.NL80211_CMD_TRIGGER_SCAN,0,' +
                json.dumps(attrs, ensure_ascii=True) +
                '); die("Scan interceptor failed to stop request");')
        # -L takes a directory or wildcard, not a literal .so filename.
        # Keep only the candidate override; defaults supply other modules.
        pattern = module if '*' in module else module.rsplit('/', 1)[0] + '/*.so'
        cmd = ['env', 'LD_PRELOAD=' + a.interceptor, a.ucode,
               '-L', pattern, '-e', code]
        if a.ssh_target:
            cmd = ['ssh', '-T', '-o', 'BatchMode=yes', '-o',
                   'StrictHostKeyChecking=yes', *(['-o', 'UserKnownHostsFile=' +
                   a.ssh_known_hosts] if a.ssh_known_hosts else []),
                   a.ssh_target, shlex.join(cmd)]
        r = subprocess.run(cmd,
                           capture_output=True, text=True, timeout=15)
        assert r.returncode == 0, (label, ssids, r.returncode, r.stderr)
        assert 'SCAN_SSID_INTERCEPT_ACTIVE' in r.stderr, r.stderr
        assert 'cannot be preloaded' not in r.stderr, r.stderr
        row = json.loads(r.stdout)
        wanted = [] if ssids is None else [s.encode() + (b'' if fixed else b'\0')
                                           for s in ssids]
        assert row['transmitted'] is False, row
        assert row['root_count'] == (ssids is not None), row
        assert row['ssids'] == [{'bytes': len(s), 'hex': s.hex()} for s in wanted], row
        print(json.dumps({'module': label, 'ssids': ssids, 'wire': row}))
        count += 1
print(f'PASS {count} real codec controls; old NUL regression demonstrated; no scan sent')
if a.decoder_interceptor:
    for label, module, fixed in [('old', a.old_module, False),
                                 ('fixed', a.new_module, True)]:
        for mode in ['empty', 'nonempty']:
            code = ('let n=require("nl80211"); let fs=require("fs"); '
                    'assert(index(fs.readfile("/proc/self/maps"),' + json.dumps(module) +
                    ')>=0,"Requested module was not loaded"); '
                    'printf("%J\\n",n.request(n.const.NL80211_CMD_GET_INTERFACE,'
                    'n.const.NLM_F_DUMP,{dev:"lo"}));')
            pattern = module.rsplit('/', 1)[0] + '/*.so'
            cmd = ['env', 'LD_PRELOAD=' + a.decoder_interceptor,
                   'SCAN_DECODE_CASE=' + mode, a.ucode, '-L', pattern, '-e', code]
            if a.ssh_target:
                cmd = ['ssh', '-T', '-o', 'BatchMode=yes', '-o',
                       'StrictHostKeyChecking=yes', *(['-o', 'UserKnownHostsFile=' +
                       a.ssh_known_hosts] if a.ssh_known_hosts else []),
                       a.ssh_target, shlex.join(cmd)]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            assert r.returncode == 0, (r.returncode, r.stderr)
            assert 'SCAN_SSID_DECODE_INTERCEPT_ACTIVE' in r.stderr, r.stderr
            assert 'GET_INTERFACE_BLOCKED_SYNTHETIC_REPLY' in r.stderr, r.stderr
            rows = json.loads(r.stdout)
            assert isinstance(rows, list) and len(rows) == 1, rows
            row = rows[0]
            assert row['scan_ssids'] == (['', 'abc', 'a\0b'] if fixed else ['ab', 'a\0']), row
            if mode == 'empty':
                assert row.get('ssid') == ('' if fixed else None), row
                assert row.get('frame_match') == ('' if fixed else None), row
                assert row.get('ifname') is None, row
            else:
                assert row['ssid'] == 'a\0b' and row['frame_match'] == 'a\0b', row
                assert row['ifname'] == 'wlan-test', row
            print(json.dumps({'decoder': label, 'case': mode, 'result': row}))
    print('PASS 4 actual decoder controls; empty/nonempty binary and ordinary text preserved')
