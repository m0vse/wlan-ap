import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE=Path(__file__).resolve().parents[2]/'feeds/tip/ucentral-private-pki/src/durable.c'

class DurableTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.binary=self.base/'durable'
        subprocess.run(['cc','-Wall','-Wextra','-Werror','-DPRIVATE_PKI_TEST_FAULTS',str(SOURCE),'-o',str(self.binary)],check=True)
        self.store=self.base/'store'
        self.store.mkdir(mode=0o700)
        self.write('current.json',{'generation':'old'})
        self.write('candidate.json',{'generation':'new'})
    def write(self,name,value):
        path=self.store/name
        path.write_text(json.dumps(value))
        path.chmod(0o600)
    def call(self,*args,fault=None):
        env=dict(os.environ)
        if fault: env['PRIVATE_PKI_TEST_FAULT']=fault
        return subprocess.run([str(self.binary),*args],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode
    def test_atomic_pointer_at_interrupted_boundaries(self):
        self.assertEqual(self.call('commit',str(self.store),'candidate.json','current.json',fault='before-rename'),88)
        self.assertEqual(json.loads((self.store/'current.json').read_text())['generation'],'old')
        self.assertEqual(self.call('commit',str(self.store),'candidate.json','current.json',fault='after-rename'),88)
        self.assertEqual(json.loads((self.store/'current.json').read_text())['generation'],'new')
        self.assertFalse((self.store/'candidate.json').exists())
    def test_unsafe_modes_links_traversal_and_missing_files_preserve_pointer(self):
        original=(self.store/'current.json').read_bytes()
        (self.store/'candidate.json').chmod(0o644)
        self.assertEqual(self.call('commit',str(self.store),'candidate.json','current.json'),2)
        (self.store/'candidate.json').unlink()
        (self.store/'candidate.json').symlink_to(self.store/'current.json')
        self.assertEqual(self.call('commit',str(self.store),'candidate.json','current.json'),2)
        for candidate in ('../current.json','missing','.'):
            self.assertEqual(self.call('commit',str(self.store),candidate,'current.json'),2)
        self.assertEqual((self.store/'current.json').read_bytes(),original)
    def test_seal_and_commit_with_private_real_files(self):
        self.assertEqual(self.call('seal',str(self.store),'candidate.json','current.json'),0)
        self.assertEqual(self.call('commit',str(self.store),'candidate.json','current.json'),0)
        self.assertEqual(json.loads((self.store/'current.json').read_text())['generation'],'new')
        os.link(self.store/'current.json',self.store/'hardlink')
        self.assertEqual(self.call('seal',str(self.store),'current.json'),2)

if __name__=='__main__': unittest.main(verbosity=2)
