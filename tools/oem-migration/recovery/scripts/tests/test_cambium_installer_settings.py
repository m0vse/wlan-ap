"""Execute FORMAT2 staging with isolated mounts; no AP/crypto/network access."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

LIB = Path(__file__).resolve().parents[1] / 'lib/cambium-installer-settings.sh'


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.input = self.root / 'input'
        self.input.mkdir(mode=0o700)
        self.mount = self.root / 'inactive'
        self.mount.mkdir()
        self.image = self.root / 'image'
        self.image.write_bytes(b'qualified sealed candidate')
        self.values = {'format': '2', 'serial': '000456abcdef', 'family': 'sage',
                       'model': 'E410B', 'source_operation': 'production-oem-migration',
                       'source_release': '4.2.3.3-r10', 'source_contract_sha256': 'a'*64,
                       'source_slot': '0', 'target_slot': '1',
                       'image_sha256': hashlib.sha256(self.image.read_bytes()).hexdigest(),
                       'job_id': 'b'*64}
        self.put('binding.tsv', ''.join(f'{k}\t{v}\n' for k,v in self.values.items()))
        self.put('est.json', '{"server":"issuer.example.invalid","tls_ca":"/etc/ssl/certs/ca-certificates.crt"}\n')
        self.put('gateway.json', '{"DEFAULT":{"gateway":"controller.example.invalid"}}\n')
        # Synthetic fixture authorization; never a real batch credential.
        self.put('est-bootstrap.conf', 'user = "000456abcdef:' + 'X'*64 + '"\n')
        self.manifest()
        self.tools = self.root / 'bin'
        self.tools.mkdir()
        # Match BusyBox numeric ls output; macOS appends xattr annotations.
        listing = self.tools / 'ls'
        listing.write_text('#!/usr/bin/env python3\nimport os,stat,sys\np=sys.argv[-1]; s=os.lstat(p); print(stat.filemode(s.st_mode),s.st_nlink,s.st_uid,s.st_gid,s.st_size,"Jan 1 00:00",p)\n')
        listing.chmod(0o700)
        sync = self.tools / 'sync'
        sync.write_text('#!/bin/sh\n[ "${FAIL_SYNC:-0}" != 1 ]\n')
        sync.chmod(0o700)
        self.sys = self.root / 'sys'
        (self.sys / 'ubi0').mkdir(parents=True)
        (self.sys / 'ubi0/mtd_num').write_text('11')
        (self.sys / 'ubi0_5').mkdir()
        (self.sys / 'ubi0_5/name').write_text('rootfs_data1')
        self.mounts = self.root / 'mounts'
        self.mounts.write_text(f'/dev/ubi0_5 {self.mount} ubifs rw 0 0\n')
        self.source = self.root / 'source-sentinel'
        self.source.write_bytes(b'working source and existing identity')

    def put(self, name, content):
        p=self.input/name; p.write_text(content); p.chmod(0o600)

    def prepare(self, credential='X'*64):
        dest=self.root/'prepared'
        env={**os.environ, 'PATH': str(self.tools)+':'+os.environ['PATH'],
             'OW_SETTINGS_OWNER': str(os.getuid())}
        result=subprocess.run(['sh','-c',
            '. "$1"; ow_settings_prepare "$2/binding.tsv" "$2/est.json" "$2/gateway.json" "$3" "$4"',
            'fixture',str(LIB),str(self.input),credential,str(dest)],
            capture_output=True,text=True,env=env)
        self.assertNotIn('X'*64,result.stdout+result.stderr)
        return result,dest

    def test_prepare_key_for_native_worker_without_device_identity(self):
        result,dest=self.prepare()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual((dest/'est-bootstrap.conf').read_bytes(),
                         (self.input/'est-bootstrap.conf').read_bytes())
        self.assertEqual(dest.stat().st_mode & 0o777,0o700)
        self.assertEqual(set(p.name for p in dest.iterdir()),set(p.name for p in self.input.iterdir()))
        self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in dest.iterdir()))
        result2,_=self.prepare()
        self.assertNotEqual(result2.returncode,0)

    def test_invalid_key_refused_before_preparation(self):
        for credential in ('short','X'*63+';','X'*64+'\n'):
            result,dest=self.prepare(credential)
            self.assertNotEqual(result.returncode,0)
            self.assertFalse(dest.exists())
            self.assertFalse(dest.with_name('prepared.pending').exists())

    def test_prepare_rejects_symlinked_input_before_writes(self):
        target=self.root/'public-binding';target.write_bytes((self.input/'binding.tsv').read_bytes())
        (self.input/'binding.tsv').unlink();(self.input/'binding.tsv').symlink_to(target)
        result,dest=self.prepare()
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(dest.exists())

    def manifest(self):
        self.put('files.sha256', ''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n'
                 for p in sorted(self.input.iterdir()) if p.name!='files.sha256'))

    def run_stage(self, **overrides):
        env={**os.environ, 'PATH': str(self.tools)+':'+os.environ['PATH'],
             'OW_SETTINGS_OWNER': str(os.getuid()), 'OW_SETTINGS_SYS': str(self.sys),
             'OW_SETTINGS_MOUNTS': str(self.mounts), 'OW_STAGE_ADMISSION': 'qualified',
             'OW_EXPECT_TARGET_VOLUME': 'ubi0_5', 'OW_EXPECT_TARGET_MTD': '11'}
        names={'serial':'SERIAL','family':'FAMILY','model':'MODEL','source_operation':'OPERATION',
               'source_release':'RELEASE','source_contract_sha256':'CONTRACT',
               'source_slot':'SOURCE','target_slot':'TARGET','job_id':'JOB'}
        env.update({'OW_EXPECT_'+names[k]:v for k,v in self.values.items() if k in names})
        env.update(overrides)
        before=self.source.read_bytes()
        result=subprocess.run(['sh','-c','. "$1"; ow_settings_stage_overlay "$2" "$3" "$4"',
                               'fixture',str(LIB),str(self.input),str(self.image),str(self.mount)],
                              capture_output=True,text=True,env=env)
        self.assertEqual(self.source.read_bytes(),before)
        self.assertNotIn('X'*64,result.stdout+result.stderr)
        return result

    def refused_before_staging(self, **overrides):
        result=self.run_stage(**overrides)
        self.assertNotEqual(result.returncode,0,result.stdout)
        self.assertEqual(list(self.mount.iterdir()),[], 'refusal must precede directory writes')

    def test_success_only_stages_settings(self):
        result=self.run_stage(); self.assertEqual(result.returncode,0,result.stderr)
        dest=self.mount/'upper/root/.cambium-installer-settings'
        self.assertEqual({p.name:p.read_bytes() for p in dest.iterdir()},
                         {p.name:p.read_bytes() for p in self.input.iterdir()})
        self.assertEqual(dest.stat().st_mode & 0o777,0o700)
        self.assertTrue(all(p.stat().st_mode & 0o777==0o600 for p in dest.iterdir()))
        self.assertFalse((dest/'key.pem').exists())

    def test_same_job_resume_preserves_candidate_identity_and_different_job_refuses(self):
        result=self.run_stage(); self.assertEqual(result.returncode,0,result.stderr)
        identity=self.mount/'upper/root/native-identity-sentinel'
        identity.write_bytes(b'persisted unique key CSR intent')
        dest=self.mount/'upper/root/.cambium-installer-settings'
        before={p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in dest.iterdir()}
        result=self.run_stage(); self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(before,{p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in dest.iterdir()})
        self.values['job_id']='c'*64
        self.put('binding.tsv',''.join(f'{k}\t{v}\n' for k,v in self.values.items())); self.manifest()
        self.assertNotEqual(self.run_stage().returncode,0)
        self.assertEqual(identity.read_bytes(),b'persisted unique key CSR intent')

    def test_unqualified_wrong_model_source_contract_image_are_prewrite_refusals(self):
        for overrides in [{'OW_STAGE_ADMISSION':'unsupported'}, {'OW_EXPECT_MODEL':'E410'},
                          {'OW_EXPECT_SOURCE':'1'}, {'OW_EXPECT_CONTRACT':'c'*64},
                          {'OW_EXPECT_OPERATION':'production-stock-openwrt-migration'}]:
            with self.subTest(overrides=overrides): self.refused_before_staging(**overrides)
        self.image.write_bytes(b'changed'); self.refused_before_staging()

    def test_bad_permissions_links_certificates_and_manifest_refused(self):
        self.put('key.pem','forbidden old source key'); self.manifest(); self.refused_before_staging()
        (self.input/'key.pem').unlink(); self.manifest()
        (self.input/'est.json').chmod(0o644); self.refused_before_staging()
        (self.input/'est.json').chmod(0o600)
        os.link(self.input/'est.json',self.root/'linked'); self.refused_before_staging()
        (self.root/'linked').unlink()
        (self.input/'gateway.json').unlink(); (self.input/'gateway.json').symlink_to(self.input/'est.json')
        self.refused_before_staging()

    def test_manifest_tampering_and_wrong_mount_refused(self):
        self.put('est.json','changed'); self.refused_before_staging()
        self.manifest(); self.mounts.write_text(f'/dev/ubi0_6 {self.mount} ubifs rw 0 0\n')
        self.refused_before_staging()
        self.mounts.write_text(f'/dev/ubi0_5 {self.mount} ubifs ro 0 0\n'); self.refused_before_staging()

    def test_credential_requires_exact_final_newline(self):
        self.put('est-bootstrap.conf','user = "000456abcdef:'+'X'*64+'"')
        self.manifest(); self.refused_before_staging()

    def test_bad_binding_and_wrong_credential_envelope_refused(self):
        self.put('est-bootstrap.conf','user = "000456abcdef:short"\n'); self.manifest(); self.refused_before_staging()
        self.put('est-bootstrap.conf','user = "000456abcdef:'+'X'*64+'"\n')
        self.put('binding.tsv',(self.input/'binding.tsv').read_text().replace('format\t2','format\t1'))
        self.manifest(); self.refused_before_staging()

    def test_sync_failure_never_reports_success_and_preserves_prior_identity(self):
        result=self.run_stage(FAIL_SYNC='1'); self.assertNotEqual(result.returncode,0)
        self.assertNotIn('staged.',result.stdout)
        self.assertFalse((self.mount/'upper/root/.cambium-installer-settings').exists())
        self.assertTrue((self.mount/'upper/root/.cambium-installer-settings.pending').exists())

    def miami(self):
        self.values.update(family='miami',model='X7-35X')
        self.put('binding.tsv',''.join(f'{k}\t{v}\n' for k,v in self.values.items()))
        self.manifest()
        volume=self.sys/'ubi0_2';volume.mkdir()
        (volume/'name').write_text('rootfs_data')
        self.mounts.write_text(f'/dev/ubi0_2 {self.mount} ubifs rw 0 0\n')
        return {'OW_EXPECT_TARGET_VOLUME':'ubi0_2'}

    def test_miami_exact_model_and_overlay_id2(self):
        args=self.miami();result=self.run_stage(**args)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue((self.mount/'upper/root/.cambium-installer-settings/binding.tsv').is_file())

    def test_miami_wrong_model_refused(self):
        args=self.miami();self.values['model']='X7-unknown'
        self.put('binding.tsv',''.join(f'{k}\t{v}\n' for k,v in self.values.items()));self.manifest()
        self.refused_before_staging(**args)

    def test_miami_wrong_overlay_id_refused(self):
        self.miami();(self.sys/'ubi0_5/name').write_text('rootfs_data')
        self.mounts.write_text(f'/dev/ubi0_5 {self.mount} ubifs rw 0 0\n')
        self.refused_before_staging()


if __name__=='__main__': unittest.main()
