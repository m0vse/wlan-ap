"""Operator boundary tests. No AP access or production qualification changes."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/'cambium-oem-sage-install.sh'

class OperatorTests(unittest.TestCase):
    def invoke(self, code, extra=None):
        env={**os.environ,'COS_OPERATOR_SOURCE_ONLY':'1','SCRIPT':str(SCRIPT)}
        env.update(extra or {})
        return subprocess.run(['sh','-c','. "$SCRIPT" || exit; '+code,str(SCRIPT)],env=env,capture_output=True,text=True)

    def test_bootstrap_refuses_missing_pin_before_sourcing_helpers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); launcher=root/'install.sh';launcher.write_bytes(SCRIPT.read_bytes())
            libs=root/'lib';libs.mkdir();marker=root/'MUTATION'
            helper=libs/'cambium-sage-pair-write.sh';helper.write_text('touch "'+str(marker)+'"\n')
            ledger=root/'SHA256SUMS';ledger.write_text('0'*64+'  lib/cambium-sage-pair-write.sh\n')
            pin=hashlib.sha256(ledger.read_bytes()).hexdigest()
            for args in (['--check'],['--check','a'*64],['--check',pin]):
                with self.subTest(args=args):
                    env={**os.environ};env.pop('COS_OPERATOR_SOURCE_ONLY',None)
                    result=subprocess.run(['sh',str(launcher),*args],env=env,capture_output=True,text=True)
                    self.assertNotEqual(result.returncode,0);self.assertFalse(marker.exists())

    def test_missing_or_malformed_pins_never_enter_transaction(self):
        for pin in ('', 'a'*63, 'A'*64, 'g'*64, 'a'*65):
            with self.subTest(pin=pin):
                result=self.invoke('cos_install() { echo MUTATION; }; id() { echo 0; }; cos_operator_install /payload /settings /backup /receipt "$PIN" '+ 'a'*64+' '+ 'b'*64, {'PIN':pin})
                self.assertNotEqual(result.returncode,0)
                self.assertNotIn('MUTATION',result.stdout)

    def test_unqualified_unknown_or_failed_source_never_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for model,status,failed in (('E410','unqualified',False),('E410','unsupported',False),('E600','qualified',False),('E410','qualified',True)):
                with self.subTest(model=model,status=status,failed=failed):
                    reader=root/'cambium-oem-sage-prepare.sh'
                    reader.write_text('#!/bin/sh\n'+('exit 1\n' if failed else 'printf "model='+model+'\\n"\n'))
                    (root/'cambium-oem-models.tsv').write_text('0000000a\tsage\t'+model+'\tubi-pair\t08000000\tcompatible\tassets\tlayout-only\t'+status+'\n')
                    before={p.name:p.read_bytes() for p in root.iterdir()}
                    result=self.invoke('COS_READERS_DIR="$READERS"; cos_operator_context',{'READERS':str(root)})
                    self.assertNotEqual(result.returncode,0)
                    self.assertEqual(before,{p.name:p.read_bytes() for p in root.iterdir()})

    def test_payload_hash_mismatch_or_missing_file_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); files=[root/n for n in ('image','kernel','root')]
            for p in files:p.write_bytes(b'candidate');p.chmod(0o600)
            good=hashlib.sha256(b'candidate').hexdigest()
            code='ow_settings_metadata() { echo 0:600:1; }; COS_IMAGE_PIN="$PIN"; COS_KERNEL_PIN="$GOOD"; COS_ROOT_PIN="$GOOD"; cos_authenticate "$P/image" "$P/kernel" "$P/root"'
            env={'P':str(root),'GOOD':good,'PIN':'a'*64}
            self.assertNotEqual(self.invoke(code,env).returncode,0)
            env['PIN']=good
            self.assertEqual(self.invoke(code,env).returncode,0)
            files[2].unlink()
            self.assertNotEqual(self.invoke(code,env).returncode,0)

    def test_missing_recovery_parent_refuses_without_creating_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing=Path(tmp)/'absent'/'capture'
            result=self.invoke('COS_BACKUP="$BACKUP"; COS_ACK=/missing; cos_recovery',{'BACKUP':str(missing)})
            self.assertNotEqual(result.returncode,0)
            self.assertFalse(missing.parent.exists())

if __name__=='__main__':unittest.main()
