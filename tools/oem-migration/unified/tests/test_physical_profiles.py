import os,subprocess,tempfile,unittest
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]

class PhysicalProfileTests(unittest.TestCase):
    def test_bank_transition_vault_and_identity_create_boundaries(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);inventory=root/'inventory';plan=root/'plan'
            inventory.write_text('1\t0\t65536\tidentity\tnor0\n2\t65536\t65536\tenvironment\tnor0\n3\t0\t100\tactive-oem\tnand0\n4\t100\t100\ttarget\tnand0\n5\t0\t100\tshared-parent\tnand1\n')
            run=lambda:subprocess.run(['sh','-c',f'. "{BASE}/lib/protection.sh";OEM_TARGET_SLOT=1;oem_write_boundary "{inventory}" "{plan}"'],capture_output=True).returncode
            for operation,id,name in [('ubi-remove',1,'ubi_rootfs'),('ubi-create',0,'kernel'),('ubi-create',1,'rootfs'),('ubi-create',1,'ubi_rootfs'),('ubi-create',2,'rootfs_data'),('ubi-create',3,'cambium_device_data'),('ubi-update',3,'cambium_device_data'),('ubi-resize',3,'cambium_device_data'),('ubi-create',4,'certificates')]:
                plan.write_text(f'{operation}\t4\t{id}\t{name}\n');self.assertEqual(run(),0)
                for parent in (1,3,5):
                    plan.write_text(f'{operation}\t{parent}\t{id}\t{name}\n');self.assertNotEqual(run(),0)
            for operation,id,name in [('ubi-update',4,'certificates'),('ubi-remove',4,'certificates'),('ubi-resize',4,'certificates'),('ubi-create',3,'certificates'),('ubi-remove',3,'cambium_device_data'),('ubi-create',4,'cambium_device_data'),('ubi-create',2,'ubi_rootfs')]:
                plan.write_text(f'{operation}\t4\t{id}\t{name}\n');self.assertNotEqual(run(),0)
            for name in ('linux0','linux1','rootfs0','rootfs1','rootfs_data0','rootfs_data1'):
                for id in range(7):
                    plan.write_text(f'ubi-update\t4\t{id}\t{name}\n');self.assertNotEqual(run(),0)

    def test_helpers_preserve_caller_variables_on_success_and_refusal(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);sys=root/'ubi';(sys/'ubi0').mkdir(parents=True);(sys/'ubi0_1').mkdir()
            (sys/'ubi0/mtd_num').write_text('3\n')
            for name,value in [('name','rootfs'),('upd_marker','0'),('corrupted','0')]:
                (sys/'ubi0_1'/name).write_text(value+'\n')
            variables='count sys node name parent device child expected inventory plan before after allowed offset size type found index dev proc ubi allow_root_map number path start end rows'
            calls=[f'oem_ubi_child_check "{sys}" 3 ubi0 1 rootfs',f'oem_ubi_child_check "{sys}" 3 ubi0 1 wrong']
            for call in calls:
                initialize=';'.join(f'{v}=caller_{v}' for v in variables.split())
                verify=';'.join(f'[ "${v}" = caller_{v} ] || exit 99' for v in variables.split())
                script=f'. "{BASE}/lib/protection.sh";{initialize};{call} >/dev/null 2>&1;result=$?;{verify};exit "$result"'
                p=subprocess.run(['sh','-c',script],capture_output=True)
                self.assertEqual(p.returncode,0 if call.endswith('rootfs') else 1)

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
    def test_factory_reset_cannot_run_before_confirm_or_target_identity(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);inventory=root/'inventory';plan=root/'plan'
            inventory.write_text('1\t0\t65536\tidentity\tnor0\n2\t65536\t65536\tnonunique-config\tnor0\n3\t0\t134217728\tshared-parent\tnand0\n')
            plan.write_text('nor-config-reset\t2\tsingle-partition\tconfig\nubi-config-reset\t3\t4\tnvram\n')
            run=lambda confirmed,kind:subprocess.run(['sh','-c',f'. "{BASE}/lib/protection.sh";OEM_RESTORE_CONFIRMED={confirmed};OEM_RUNNING_OS={kind};oem_confirmed_config_boundary "{inventory}" "{plan}"'],capture_output=True)
            self.assertNotEqual(run(0,'oem').returncode,0);self.assertNotEqual(run(1,'openwifi').returncode,0);self.assertEqual(run(1,'oem').returncode,0)
            plan.write_text('nor-config-reset\t1\tsingle-partition\tconfig\n');self.assertNotEqual(run(1,'oem').returncode,0)

    def test_new_build_with_same_version_and_duplicate_version_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);actual=root/'version';expected=BASE/'profiles/X7-35X/source.tsv'
            text='\n'.join(k+'='+v for k,v in (r.split('\t',1) for r in expected.read_text().splitlines()))+'\n';actual.write_text(text)
            run=lambda:subprocess.run(['sh','-c',f'. "{BASE}/lib/common.sh";oem_source_identifiers_check "{actual}" "{expected}"'],capture_output=True)
            self.assertEqual(run().returncode,0)
            actual.write_text(text.replace('b169bb7e02ecbf1cdf31152220f63b30959ec9c2','different-build'));self.assertNotEqual(run().returncode,0)
            actual.write_text(text+'VERSION=7.2-r1\n');self.assertNotEqual(run().returncode,0)

if __name__=='__main__':unittest.main()
