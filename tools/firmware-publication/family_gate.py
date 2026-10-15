#!/usr/bin/env python3
"""Mandatory per-family post-publication FMS refresh and authenticated gate.

No AP commands. Credentials enter on stdin and never appear in receipts/argv.
Only the existing owfms container may be restarted; no recreation or upgrade.
"""
import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request


class GateError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise GateError(message)


FIELDS = ('deviceType', 'id', 'revision', 'image', 'imageDate', 'uri', 'firmwareHash', 'size')


def validate_manifest(manifest):
    require(manifest.get('family') in ('sage', 'jaguar', 'cheetah', 'thor', 'miami'), 'Unknown family')
    records = manifest.get('firmwares')
    require(isinstance(records, list) and records, 'Exact qualified model records required')
    models = set()
    for item in records:
        require(isinstance(item, dict) and all(key in item for key in FIELDS), 'Incomplete model receipt')
        require(all(isinstance(item[key], str) and item[key] for key in ('deviceType', 'id', 'revision', 'image', 'uri', 'firmwareHash')), 'Invalid metadata')
        require(item['deviceType'] not in models, 'Duplicate model')
        models.add(item['deviceType'])
        require(re.fullmatch(r'[a-zA-Z0-9_-]+', item['deviceType']) is not None, 'Invalid model')
        require(re.fullmatch(r'[0-9a-f]{64}', item['firmwareHash']) is not None, 'Invalid image hash')
        require(type(item['size']) is int and item['size'] > 0, 'Invalid image size')
        require(type(item['imageDate']) is int and item['imageDate'] > 0, 'Invalid image date')
        uri = urllib.parse.urlsplit(item['uri'])
        require(uri.scheme == 'https' and uri.hostname and not uri.username and not uri.password, 'Public HTTPS image URI required')
        if item.get('previousRevision'):
            require(isinstance(item['previousRevision'], str) and item['previousRevision'] != item['revision'], 'Invalid previous revision')
            if 'previousImageDate' in item:
                require(type(item['previousImageDate']) is int and 0 < item['previousImageDate'] <= item['imageDate'], 'Invalid previous image date')
    for device in manifest.get('devices', []):
        require(device.get('deviceType') in models and re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', device.get('serialNumber', '')), 'Invalid test device')
    return records


def verify_latest(expected, actual):
    require(isinstance(actual, dict), 'Invalid latest response')
    for key in FIELDS:
        require(type(actual.get(key)) is type(expected[key]) and actual[key] == expected[key], 'Live latest mismatch: ' + key)
    require(actual.get('latest') is True, 'Live latest flag not true')


def verify_age(expected, actual, current=True, serial=None):
    require(isinstance(actual, dict), 'Invalid age response')
    for key in ('revision', 'image', 'imageDate', 'uri'):
        require(actual.get(key) == expected[key], 'Live age metadata mismatch: ' + key)
    require(actual.get('latestId') == expected['id'], 'Live age latestId mismatch')
    age = actual.get('age')
    require(type(age) is int and 0 <= age <= expected['imageDate'], 'Invalid/underflowed firmware age')
    require(actual.get('latest') is current, 'Live age latest flag mismatch')
    if current:
        require(age == 0, 'Current firmware age must be zero')
    if serial:
        require(actual.get('serialNumber') == serial, 'Wrong device age result')


def public_hash(item, opener=urllib.request.urlopen):
    digest = hashlib.sha256()
    size = 0
    deadline = time.monotonic() + 180
    with opener(item['uri'], timeout=60) as response:
        require(urllib.parse.urlsplit(response.geturl()).scheme == 'https', 'Image redirected away from HTTPS')
        while True:
            require(time.monotonic() < deadline, 'Public image verification timed out')
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            require(size <= item['size'], 'Public image larger than receipt')
            digest.update(chunk)
    require(size == item['size'] and digest.hexdigest() == item['firmwareHash'], 'Public image hash/size mismatch')


# Runs inside an existing trusted Python runtime on the controller network.
# It has read-only CA access, no Docker socket and no AP-facing API methods.
PROBE = r'''
import json,ssl,sys,urllib.request,urllib.error
p=json.load(sys.stdin);context=ssl.create_default_context(cafile='/audit/ca.pem');results=[]
for path in p['paths']:
 req=urllib.request.Request(p['url']+'/api/v1/'+path,headers={'Authorization':'Bearer '+p['token']})
 try:
  with urllib.request.urlopen(req,context=context,timeout=15) as r:results.append({'status':r.status,'body':json.load(r)})
 except urllib.error.HTTPError as e:results.append({'status':e.code})
 except Exception:raise SystemExit('FMS read-only probe failed')
print(json.dumps(results))
'''


class DockerFMS:
    def __init__(self, args, token):
        self.args, self.token = args, token

    def inspect(self):
        return json.loads(subprocess.check_output(['docker', 'inspect', self.args.fms_container]))[0]

    def snapshot(self):
        ids = subprocess.check_output(['docker', 'ps', '-q'], text=True).split()
        require(ids, 'No running containers')
        return {d['Name']: {'id': d['Id'], 'started': d['State']['StartedAt'], 'image': d['Image']}
                for d in json.loads(subprocess.check_output(['docker', 'inspect', *ids]))
                if d['Config'].get('Labels', {}).get('com.docker.compose.project')}

    def probe(self, paths):
        command = ['docker', 'run', '--rm', '--pull=never', '-i', '--network', self.args.network,
                   '-v', str(pathlib.Path(self.args.ca).resolve()) + ':/audit/ca.pem:ro',
                   self.args.probe_image, 'python3', '-B', '-c', PROBE]
        result = subprocess.run(command, input=json.dumps({'token': self.token, 'url': self.args.fms_url.rstrip('/'), 'paths': paths}), text=True, capture_output=True, timeout=120)
        require(result.returncode == 0, 'FMS authenticated probe failed; credentials unchanged')
        return json.loads(result.stdout)

    def refresh(self):
        info = self.inspect()
        require(info['Config'].get('Labels', {}).get('com.docker.compose.service') == 'owfms', 'Refusing non-FMS restart target')
        require(info['State']['Running'], 'FMS is not running')
        before = self.snapshot()
        subprocess.run(['docker', 'restart', '--time', '20', self.args.fms_container], check=True, stdout=subprocess.DEVNULL, timeout=60)
        after = self.snapshot()
        target = info['Name']
        require(after.get(target, {}).get('id') == info['Id'] and after[target]['image'] == info['Image'], 'FMS identity/image changed')
        for name, data in before.items():
            if name != target:
                require(after.get(name) == data, 'Unrelated container changed: ' + name)
        return {'container': self.args.fms_container, 'image': info['Image'], 'before': before[target], 'after': after[target], 'other_containers_unchanged': len(before) - 1}


def check_live(manifest, transport):
    result = []
    for expected in manifest['firmwares']:
        model = urllib.parse.quote(expected['deviceType'], safe='')
        revision = urllib.parse.quote(expected['revision'], safe='')
        paths = ['firmwares?deviceType=' + model + '&latestOnly=true',
                 'firmwareAge?deviceType=' + model + '&revision=' + revision,
                 'firmwareAge?deviceType=' + model + '&revision=publication-gate-unknown-revision']
        responses = transport.probe(paths)
        require(len(responses) == 3, 'Incomplete live response')
        require(responses[0]['status'] == 200 and responses[1]['status'] == 200, 'Latest/age endpoint not available')
        verify_latest(expected, responses[0]['body'])
        verify_age(expected, responses[1]['body'])
        unknown = responses[2]
        require(unknown['status'] == 404 or unknown['status'] == 200 and unknown.get('body', {}).get('latest') is False, 'Unknown revision falsely current or endpoint failed')
        if expected.get('previousRevision'):
            previous = urllib.parse.quote(expected['previousRevision'], safe='')
            response = transport.probe(['firmwareAge?deviceType=' + model + '&revision=' + previous])[0]
            require(response['status'] == 200, 'Previous revision age unavailable')
            verify_age(expected, response['body'], current=False)
            if 'previousImageDate' in expected:
                require(response['body']['age'] == expected['imageDate'] - expected['previousImageDate'], 'Previous revision age mismatch')
        for device in manifest.get('devices', []):
            if device['deviceType'] != expected['deviceType']:
                continue
            serial = device['serialNumber']
            response = transport.probe(['firmwareAge?select=' + serial])[0]
            require(response['status'] == 200, 'Serial age endpoint unavailable')
            ages = response.get('body', {}).get('ages', [])
            require(len(ages) == 1, 'Serial age missing or ambiguous')
            verify_age(expected, ages[0], serial=serial)
        result.append({'deviceType': expected['deviceType'], 'id': expected['id'], 'revision': expected['revision'], 'latest': True, 'age': 0})
    return result


def publish_gate(manifest, transport, artifact_check=public_hash, publisher=None, verify_only=False, attempts=12, sleep=time.sleep):
    require(not (verify_only and publisher), 'Audit mode cannot run a publisher')
    records = validate_manifest(manifest)
    # Existing operator authentication is required BEFORE publication or restart.
    preflight = transport.probe(['firmwares?deviceType=' + urllib.parse.quote(records[0]['deviceType']) + '&latestOnly=true'])
    require(preflight[0]['status'] in (200, 404), 'Operator authentication/readiness failed; nothing changed')
    if publisher:
        publisher()  # On upload/catalogue failure: no refresh, no success receipt.
    for item in records:
        artifact_check(item)
    refresh = None if verify_only else transport.refresh()
    require(verify_only or isinstance(refresh, dict), 'Refresh receipt missing')
    for attempt in range(attempts):
        try:
            verified = check_live(manifest, transport)
            return {'family': manifest['family'], 'publication_complete': not verify_only, 'audit_only': verify_only,
                    'cache_refresh': refresh, 'verified_models': verified, 'AP_commands': False}
        except (GateError, subprocess.TimeoutExpired):
            if attempt + 1 == attempts:
                raise
            sleep(5)  # Allow normal gateway pings to repopulate serial cache; never force reconnect.
    raise GateError('Verification incomplete')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=pathlib.Path)
    parser.add_argument('--receipt', required=True, type=pathlib.Path)
    parser.add_argument('--fms-url', required=True)
    parser.add_argument('--ca', required=True)
    parser.add_argument('--probe-image', required=True, help='Existing trusted Python runtime; never pulled by this tool')
    parser.add_argument('--network', default='openwifi_openwifi')
    parser.add_argument('--fms-container', default='openwifi-owfms-1')
    parser.add_argument('--verify-only', action='store_true', help='Audit only; cannot mark publication complete')
    parser.add_argument('--publisher', nargs=argparse.REMAINDER, help='Existing qualified uploader/catalogue command; must be last option')
    args = parser.parse_args()
    require(not (args.verify_only and args.publisher), 'Audit mode cannot run a publisher')
    require(urllib.parse.urlsplit(args.fms_url).scheme == 'https', 'FMS HTTPS required')
    require(not args.receipt.exists(), 'Refusing to overwrite a receipt')
    token = sys.stdin.read().strip()
    require(token and not any(c.isspace() for c in token), 'Existing operator token required on stdin')
    manifest = json.loads(args.manifest.read_text())
    publisher = (lambda: subprocess.run(args.publisher, check=True, stdout=subprocess.DEVNULL)) if args.publisher else None
    receipt = publish_gate(manifest, DockerFMS(args, token), publisher=publisher, verify_only=args.verify_only)
    with args.receipt.open('x') as output:
        json.dump(receipt, output, indent=2)
    print(json.dumps({'family': receipt['family'], 'publication_complete': receipt['publication_complete'], 'verified_models': len(receipt['verified_models'])}))


if __name__ == '__main__':
    try:
        main()
    except (GateError, OSError, ValueError, subprocess.SubprocessError) as error:
        # Never print credential input, command environment or arbitrary response bodies.
        print('Publication gate failed: ' + (str(error) if isinstance(error, GateError) else type(error).__name__), file=sys.stderr)
        sys.exit(1)
