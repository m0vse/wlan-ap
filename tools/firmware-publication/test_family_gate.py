import copy
import hashlib
import io
import subprocess
import unittest
from unittest.mock import Mock, patch

import family_gate as gate


def fixture(family='thor'):
    item = {'deviceType': 'cambium_' + family, 'id': 'synthetic-id', 'revision': 'OpenWrt / TIP-' + family + '-1.2.3-abcd',
            'image': family + '.bin', 'imageDate': 1000, 'uri': 'https://firmware.example/' + family + '.bin',
            'firmwareHash': hashlib.sha256(b'image').hexdigest(), 'size': 5}
    return {'family': family, 'firmwares': [item], 'devices': [{'serialNumber': '001122334455', 'deviceType': item['deviceType']}]}


def latest(item):
    return {**item, 'latest': True}


def age(item):
    return {**{k: item[k] for k in ('revision', 'image', 'imageDate', 'uri')}, 'latestId': item['id'], 'latest': True, 'age': 0}


class Transport:
    def __init__(self, manifest):
        self.manifest = manifest
        self.events = []
        self.auth = 200
        self.stale = False
        self.serial_missing = False

    def probe(self, paths):
        self.events.append('probe')
        result = []
        for path in paths:
            if self.auth != 200:
                result.append({'status': self.auth})
                continue
            item = self.manifest['firmwares'][0]
            if 'publication-gate-unknown-revision' in path:
                body = {**age(item), 'latest': False}
            elif '?select=' in path:
                body = {'ages': [{'serialNumber': '001122334455', **age(item)}] if not self.serial_missing else []}
            elif path.startswith('firmwares?'):
                body = latest(item)
                if self.stale:
                    body['id'] = 'previous-release'
            else:
                body = age(item)
            result.append({'status': 200, 'body': body})
        return result

    def refresh(self):
        self.events.append('refresh')
        return {'container': 'synthetic-owfms', 'other_containers_unchanged': 16}


class FamilyGateTests(unittest.TestCase):
    def run_gate(self, manifest=None, **kwargs):
        manifest = manifest or fixture()
        transport = kwargs.pop('transport', Transport(manifest))
        kwargs.setdefault('artifact_check', lambda _: transport.events.append('public_hash'))
        return gate.publish_gate(manifest, transport, attempts=1, **kwargs), transport

    def test_each_family_requires_own_refresh_and_live_verification(self):
        for family in ('sage', 'jaguar', 'cheetah', 'thor', 'miami'):
            with self.subTest(family=family):
                receipt, t = self.run_gate(fixture(family))
                self.assertTrue(receipt['publication_complete'])
                self.assertEqual(t.events[:3], ['probe', 'public_hash', 'refresh'])
                self.assertEqual(t.events.count('refresh'), 1)
                self.assertFalse(receipt['AP_commands'])

    def test_exact_live_metadata_fields_cannot_be_skipped(self):
        expected = fixture()['firmwares'][0]
        for field in gate.FIELDS:
            with self.subTest(field=field):
                actual = latest(expected)
                actual[field] = 'incorrect'
                with self.assertRaises(gate.GateError):gate.verify_latest(expected, actual)

    def test_latest_false_rejected_even_if_database_fields_match(self):
        e = fixture()['firmwares'][0]
        with self.assertRaises(gate.GateError):gate.verify_latest(e, {**e, 'latest': False})

    def test_unsigned_age_underflow_negative_missing_and_bool_rejected(self):
        e = fixture()['firmwares'][0]
        for value in (18446744073709273251, -1, None, True):
            with self.subTest(value=value):
                with self.assertRaises(gate.GateError):gate.verify_age(e, {**age(e), 'age': value})

    def test_current_must_have_age_zero(self):
        e = fixture()['firmwares'][0]
        with self.assertRaises(gate.GateError):gate.verify_age(e, {**age(e), 'age': 1})

    def test_wrong_serial_or_revision_never_current(self):
        e = fixture()['firmwares'][0]
        for changed in ({'serialNumber': 'other'}, {'revision': 'other'}, {'latestId': 'old'}):
            with self.subTest(changed=changed):
                with self.assertRaises(gate.GateError):gate.verify_age(e, {**age(e), 'serialNumber': '001122334455', **changed}, serial='001122334455')

    def test_missing_serial_cache_is_not_completion(self):
        m=fixture();t=Transport(m);t.serial_missing=True
        with self.assertRaises(gate.GateError):self.run_gate(m, transport=t)

    def test_stale_cache_blocks_completion_after_refresh(self):
        m=fixture();t=Transport(m);t.stale=True
        with self.assertRaises(gate.GateError):self.run_gate(m, transport=t)
        self.assertIn('refresh', t.events)

    def test_auth_failure_stops_before_publication_or_restart(self):
        m=fixture();t=Transport(m);t.auth=403;publisher=Mock()
        with self.assertRaises(gate.GateError):self.run_gate(m, transport=t, publisher=publisher)
        publisher.assert_not_called();self.assertEqual(t.events,['probe'])

    def test_publisher_failure_never_refreshes_or_succeeds(self):
        m=fixture();t=Transport(m)
        def failed():raise subprocess.CalledProcessError(1, ['synthetic-uploader'])
        with self.assertRaises(subprocess.CalledProcessError):self.run_gate(m, transport=t, publisher=failed)
        self.assertEqual(t.events,['probe'])

    def test_artifact_failure_never_refreshes(self):
        m=fixture();t=Transport(m)
        def failed(_):raise gate.GateError('hash mismatch')
        with self.assertRaises(gate.GateError):self.run_gate(m, transport=t, artifact_check=failed)
        self.assertEqual(t.events,['probe'])

    def test_refresh_failure_never_succeeds(self):
        m=fixture();t=Transport(m);t.refresh=Mock(side_effect=gate.GateError('restart failed'))
        with self.assertRaises(gate.GateError):self.run_gate(m, transport=t)

    def test_verify_only_cannot_mark_publication_complete(self):
        receipt,t=self.run_gate(verify_only=True)
        self.assertFalse(receipt['publication_complete']);self.assertNotIn('refresh',t.events)

    def test_audit_cannot_execute_uploader(self):
        publisher=Mock()
        with self.assertRaises(gate.GateError):self.run_gate(verify_only=True,publisher=publisher)
        publisher.assert_not_called()

    def test_no_refresh_receipt_cannot_succeed(self):
        m=fixture();t=Transport(m);t.refresh=lambda:None
        with self.assertRaises(gate.GateError):self.run_gate(m,transport=t)

    def test_each_model_is_checked(self):
        m=fixture();other=copy.deepcopy(m['firmwares'][0]);other['deviceType']='another_model';m['firmwares'].append(other)
        with self.assertRaises(gate.GateError):self.run_gate(m)

    def test_multiple_qualified_models_can_complete(self):
        m=fixture();m['devices']=[]
        other=copy.deepcopy(m['firmwares'][0]);other['deviceType']='qualified_alias';other['id']='alias-id';m['firmwares'].append(other)
        t=Transport(m)
        def probe(paths):
            answers=[]
            for path in paths:
                item=other if 'deviceType=qualified_alias' in path else m['firmwares'][0]
                body=latest(item) if path.startswith('firmwares?') else age(item)
                if 'publication-gate-unknown-revision' in path:body['latest']=False
                answers.append({'status':200,'body':body})
            return answers
        t.probe=probe
        receipt,_=self.run_gate(m,transport=t)
        self.assertEqual(len(receipt['verified_models']),2)
        self.assertEqual(t.events.count('refresh'),1)

    def test_uploader_hash_refresh_and_verify_are_in_order(self):
        m=fixture();t=Transport(m)
        self.run_gate(m,transport=t,publisher=lambda:t.events.append('publisher'))
        self.assertEqual(t.events[:4],['probe','publisher','public_hash','refresh'])

    def test_invalid_manifest_and_duplicate_models_stop_before_io(self):
        for field in ('family','firmwares'):
            m=fixture();m.pop(field)
            with self.assertRaises(gate.GateError):gate.validate_manifest(m)
        m=fixture();m['firmwares'].append(copy.deepcopy(m['firmwares'][0]))
        with self.assertRaises(gate.GateError):gate.validate_manifest(m)

    def test_public_hash_and_size_are_real_streamed_checks(self):
        e=fixture()['firmwares'][0]
        class Image(io.BytesIO):
            def geturl(self):return e['uri']
        gate.public_hash(e, lambda *a,**k:Image(b'image'))
        for data in (b'bad', b'image-longer', b'wrong'):
            with self.assertRaises(gate.GateError):gate.public_hash(e, lambda *a,**k:Image(data))

    def test_refresh_refuses_wrong_service_before_restart(self):
        transport=gate.DockerFMS(Mock(fms_container='openwifi-owgw-1'),'synthetic')
        transport.inspect=lambda:{'Config':{'Labels':{'com.docker.compose.service':'owgw'}}}
        with patch.object(gate.subprocess,'run') as run:
            with self.assertRaises(gate.GateError):transport.refresh()
            run.assert_not_called()

    def test_unknown_revision_not_allowed_to_claim_current(self):
        m=fixture();t=Transport(m);probe=t.probe
        def invalid(paths):
            result=probe(paths)
            if len(paths)==3:result[2]['body']['latest']=True
            return result
        t.probe=invalid
        with self.assertRaises(gate.GateError):self.run_gate(m,transport=t)

    def test_previous_revision_age_must_be_correct(self):
        m=fixture();e=m['firmwares'][0];e.update(previousRevision='old',previousImageDate=900)
        t=Transport(m);probe=t.probe
        def previous(paths):
            if len(paths)==1 and 'revision=old' in paths[0]:return [{'status':200,'body':{**age(e),'latest':False,'age':100}}]
            return probe(paths)
        t.probe=previous
        self.assertTrue(self.run_gate(m,transport=t)[0]['publication_complete'])
        e['previousImageDate']=950
        with self.assertRaises(gate.GateError):self.run_gate(m,transport=t)

    def test_actual_restart_command_is_FMS_only_and_detects_other_restart(self):
        t=gate.DockerFMS(Mock(fms_container='openwifi-owfms-1'),'synthetic')
        info={'Name':'/openwifi-owfms-1','Id':'fms-id','Image':'fms-image','State':{'Running':True},'Config':{'Labels':{'com.docker.compose.service':'owfms'}}}
        t.inspect=lambda:info
        before={'/openwifi-owfms-1':{'id':'fms-id','image':'fms-image','started':'old'},'gateway':{'id':'gw-id','image':'gw-image','started':'unchanged'}}
        after=copy.deepcopy(before);after['/openwifi-owfms-1']['started']='new'
        t.snapshot=Mock(side_effect=[before,after])
        with patch.object(gate.subprocess,'run') as run:
            t.refresh()
            self.assertEqual(run.call_args.args[0],['docker','restart','--time','20','openwifi-owfms-1'])
        after['gateway']['started']='unexpected'
        t.snapshot=Mock(side_effect=[before,after])
        with patch.object(gate.subprocess,'run'):
            with self.assertRaises(gate.GateError):t.refresh()

    def test_probe_keeps_token_off_argv_and_prevents_image_pull(self):
        args=Mock(network='synthetic-network',ca='/tmp/synthetic-ca.pem',probe_image='existing-image',fms_url='https://fms.example')
        t=gate.DockerFMS(args,'synthetic-secret-token')
        with patch.object(gate.subprocess,'run',return_value=Mock(returncode=0,stdout='[]')) as run:
            t.probe(['firmwares?deviceType=fixture'])
            self.assertNotIn('synthetic-secret-token',' '.join(run.call_args.args[0]))
            self.assertIn('--pull=never',run.call_args.args[0])
            self.assertIn('synthetic-secret-token',run.call_args.kwargs['input'])

    def test_late_serial_cache_population_retries_without_AP_command(self):
        m=fixture();t=Transport(m);t.serial_missing=True
        def settle(_):t.serial_missing=False
        receipt=gate.publish_gate(m,t,artifact_check=lambda _:None,attempts=2,sleep=settle)
        self.assertTrue(receipt['publication_complete']);self.assertEqual(t.events.count('refresh'),1)


if __name__=='__main__':unittest.main()
