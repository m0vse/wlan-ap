import os,subprocess,tempfile,unittest
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]

class PhysicalProfileTests(unittest.TestCase):
    def fixture(self,root,slot):
        sys=root/'sys';sys.mkdir();chips=root/'chips';chips.mkdir()
        for name in ('nand0','nor0'):(chips/name).mkdir()
        profile=BASE/'profiles/X7-35X'/f'mtd-slot{slot}.tsv'
        for index,row in enumerate(profile.read_text().splitlines()):
            name,domain,offset,size,kind,erase,write,role=row.split('\t');node=sys/f'mtd{index}';node.mkdir()
            for key,value in {'name':name,'offset':offset,'size':size,'type':kind,'erasesize':erase,'writesize':write}.items():(node/key).write_text(value)
            (node/'device').symlink_to(chips/domain)
        return sys,profile
    def run_inventory(self,root,sys,profile):
        return subprocess.run(['sh','-c',f'. "{BASE}/lib/protection.sh";oem_physical_inventory "{profile}" "{sys}" "{root}/inventory"'],capture_output=True,text=True)
    def test_both_miami_slot_profiles_and_master_write_refusal(self):
        for slot in (0,1):
            with self.subTest(slot=slot),tempfile.TemporaryDirectory() as td:
                root=Path(td).resolve();sys,profile=self.fixture(root,slot)
                p=self.run_inventory(root,sys,profile);self.assertEqual(p.returncode,0,p.stderr)
                for parent in (0,7):
                    (root/'plan').write_text(f'ubi-update\t{parent}\t0\tkernel\n')
                    p=subprocess.run(['sh','-c',f'. "{BASE}/lib/protection.sh";OEM_TARGET_SLOT={slot};oem_write_boundary "{root}/inventory" "{root}/plan"'],capture_output=True)
                    self.assertNotEqual(p.returncode,0)
    def test_type_domain_overlap_alias_missing_parent_and_wrong_offset_refuse(self):
        for fault in ('type-domain','same-chip-two-domains','alias','overlap','missing-parent','offset'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as td:
                root=Path(td).resolve();sys,profile=self.fixture(root,0);copy=root/'profile';copy.write_bytes(profile.read_bytes());profile=copy
                if fault=='type-domain':profile.write_text(profile.read_text().replace('rootfs\tnand0','rootfs\tnor0'))
                if fault=='same-chip-two-domains':(sys/'mtd7/device').unlink();(sys/'mtd7/device').symlink_to(root/'chips/nand0')
                if fault=='alias':(sys/'mtd99').mkdir();[(sys/'mtd99'/k).write_text((sys/'mtd3'/k).read_text()) for k in ('name','type','size','offset','erasesize','writesize')];(sys/'mtd99/device').symlink_to(root/'chips/nand0')
                if fault=='overlap':(sys/'mtd22/offset').write_text('786432');profile.write_text(profile.read_text().replace('0:ART\tnor0\t3145728','0:ART\tnor0\t786432'))
                if fault=='missing-parent':(sys/'mtd3/device').unlink()
                if fault=='offset':(sys/'mtd3/offset').write_text('0')
                self.assertNotEqual(self.run_inventory(root,sys,profile).returncode,0)
    def test_new_build_with_same_version_and_duplicate_version_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);actual=root/'version';expected=BASE/'profiles/X7-35X/source.tsv'
            text='\n'.join(k+'='+v for k,v in (r.split('\t',1) for r in expected.read_text().splitlines()))+'\n';actual.write_text(text)
            run=lambda:subprocess.run(['sh','-c',f'. "{BASE}/lib/common.sh";oem_source_identifiers_check "{actual}" "{expected}"'],capture_output=True)
            self.assertEqual(run().returncode,0)
            actual.write_text(text.replace('b169bb7e02ecbf1cdf31152220f63b30959ec9c2','different-build'));self.assertNotEqual(run().returncode,0)
            actual.write_text(text+'VERSION=7.2-r1\n');self.assertNotEqual(run().returncode,0)

if __name__=='__main__':unittest.main()
