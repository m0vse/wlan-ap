#!/usr/bin/env python3
"""Narrow admission: unrelated ELF closure is evidence, required hooks are not.
No target executables, flash, hardware or vendor tools are executed.
"""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HELPER=Path(__file__).resolve().parents[1]/'adapters/required-source.sh'

class RequiredSourceTests(unittest.TestCase):
 def fixture(self):
  directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
  root=Path(directory.name)
  (root/'etc').mkdir();(root/'lib/upgrade').mkdir(parents=True)
  version=root/'etc/version';version.write_text('PRODUCT=jaguar\nVERSION=7.2-r1\nCHANGESET=known-build\n')
  hook=root/'lib/upgrade/platform.sh';hook.write_text('platform_pre_upgrade() { ab_certificate_export; }\n')
  ledger=root/'ledger'
  ledger.write_text(''.join('F '+hashlib.sha256(p.read_bytes()).hexdigest()+' /'+str(p.relative_to(root))+'\n' for p in (version,hook))+
   'X '+'0'*64+' /bin/unrelated-elf\nF '+'0'*64+' /lib/libunrelated.so\nL ld-musl-test.so /lib/ld-test.so\n')
  return root,ledger
 def invoke(self,root,ledger,tool='sh'):
  return subprocess.run(['sh','-c','. "$HELPER"; oem_required_source_check "$LEDGER" "$ROOT" /etc/version "$TOOL"'],
   env=dict(os.environ,HELPER=str(HELPER),LEDGER=str(ledger),ROOT=str(root),TOOL=tool),capture_output=True,text=True)
 def test_missing_unrelated_elf_libc_interpreter_is_not_admission_gate(self):
  root,ledger=self.fixture();self.assertEqual(self.invoke(root,ledger).returncode,0)
 def test_changed_unrelated_library_is_not_admission_gate(self):
  root,ledger=self.fixture();(root/'lib/libunrelated.so').write_bytes(b'different libc closure')
  self.assertEqual(self.invoke(root,ledger).returncode,0)
 def test_required_hook_missing_or_changed_refuses(self):
  for mutation in ('missing','changed'):
   root,ledger=self.fixture();hook=root/'lib/upgrade/platform.sh'
   if mutation=='missing':hook.unlink()
   else:hook.write_text('platform_pre_upgrade() { :; }\n')
   self.assertNotEqual(self.invoke(root,ledger).returncode,0)
 def test_wrong_source_build_refuses(self):
  root,ledger=self.fixture();(root/'etc/version').write_text('PRODUCT=jaguar\nVERSION=7.2-r1\nCHANGESET=wrong-build\n')
  self.assertNotEqual(self.invoke(root,ledger).returncode,0)
 def test_required_command_missing_refuses(self):
  root,ledger=self.fixture();self.assertNotEqual(self.invoke(root,ledger,'nonexistent-native-command').returncode,0)
 def test_missing_or_duplicate_release_pin_refuses(self):
  for mutation in ('missing','duplicate'):
   root,ledger=self.fixture();rows=ledger.read_text().splitlines(True)
   ledger.write_text(''.join(rows[1:] if mutation=='missing' else rows+[rows[0]]))
   self.assertNotEqual(self.invoke(root,ledger).returncode,0)

if __name__=='__main__':unittest.main()
