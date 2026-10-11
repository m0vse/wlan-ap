"""Actual reset adapter with disposable files replacing device operations."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

LIB=Path(__file__).resolve().parents[1]/'lib'

class ResetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
        self.dev=self.root/'dev';self.dev.mkdir()
        self.sys=self.root/'ubi';self.sys.mkdir()
        self.mtd=self.root/'mtd';self.mtd.mkdir()
        self.bin=self.root/'bin';self.bin.mkdir()
        self.recovery=self.root/'recovery';self.recovery.mkdir(mode=0o700)
        self.put('proc-mtd','dev: size erasesize name\nmtd5: 00010000 00010000 "0:APPSBLENV"\nmtd7: 00010000 00010000 "0:ART"\nmtd8: 00010000 00010000 "mfginfo"\nmtd10: 00010000 00010000 "config"\nmtd11: 08000000 00020000 "fs"\n')
        self.put('mtd/mtd10/name','config');self.put('mtd/mtd10/type','nor')
        self.put('mtd/mtd10/size','65536');self.put('mtd/mtd10/erasesize','65536');self.put('mtd/mtd10/flags','0x400')
        for key,value in {'mtd_num':11,'eraseblock_size':126976,'min_io_size':2048,'avail_eraseblocks':21}.items():self.put('ubi/ubi0/'+key,str(value))
        for i,name,lebs in ((0,'linux0',34),(1,'rootfs0',285),(2,'linux1',34),(3,'rootfs1',372),(4,'nvram',167),(6,'rootfs_data0',67),(7,'certificates',20)):
            for key,value in {'name':name,'reserved_ebs':lebs,'usable_eb_size':126976,'type':'dynamic','upd_marker':0}.items():self.put(f'ubi/ubi0_{i}/{key}',str(value))
        self.put('cmdline','ubi.mtd=fs root=/dev/ubiblock0_1 rootfstype=squashfs ro cambium_sage_slot=0\n')
        self.put('mounts',str(self.dev/'ubi0_6')+' /overlay ubifs rw 0 0\n')
        self.put('env-config','/dev/mtd5 0x0 0x00010000 0x00010000 1\n')
        self.put('env-snapshot','image=0\nbootcmd=run sage_stable0\nsage_ab_state=confirmed\n')
        self.put('kernel',bytes.fromhex('d00dfeed')+b'qualified FIT',0o600)
        self.put('rootfs',bytes.fromhex('31181006')+b'qualified UBIFS',0o600)
        self.put('shared-manifest','independently verified recovery set\n',0o600)
        self.put('dev/ubi0_2',(self.root/'kernel').read_bytes());self.put('dev/ubi0_3',(self.root/'rootfs').read_bytes())
        self.put('dev/ubi0_4',b'old factory configuration')
        self.put('dev/ubi0_7',b'KEEP native private identity')
        self.put('dev/mtd10',b'old NOR configuration'.ljust(65536,b'\0'));os.link(self.dev/'mtd10',self.dev/'mtd10ro')
        records=[]
        for i,name in ((5,'appsblenv'),(7,'art'),(8,'manufacturing')):
            data=(name.encode()+b' OWN AP').ljust(65536,b'\0')
            self.put(f'dev/mtd{i}ro',data);self.put('recovery/'+name+'.bin',data,0o600)
            records.append(hashlib.sha256(data).hexdigest()+'  '+name+'.bin\n')
        self.put('recovery/SHA256SUMS',''.join(records),0o600)
        self.put('receipt',hashlib.sha256((self.recovery/'SHA256SUMS').read_bytes()).hexdigest()+'\n',0o600)
        self.tool('ls', '#!/usr/bin/env python3\nimport os,stat,sys\ns=os.lstat(sys.argv[-1]);print(stat.filemode(s.st_mode),s.st_nlink,501 if os.environ.get("WRONG_OWNER") else 0,0,s.st_size,"Jan 1 00:00",sys.argv[-1])\n')
        self.tool('fw_printenv','#!/bin/sh\n[ "${FAULT:-}" != env ] || exit 1\ncat "$FIXTURE/env-snapshot"\n')
        self.tool('flash_erase','#!/usr/bin/env python3\nimport os,sys\nfrom pathlib import Path\np=Path(os.environ["FIXTURE"]);(p/"operations").open("a").write("NOR\\n")\nif os.environ.get("FAULT")=="erase":sys.exit(1)\nassert sys.argv[1:]==[str(p/"dev/mtd10"),"0","1"]\nPath(sys.argv[1]).write_bytes((b"\\0" if os.environ.get("FAULT")=="nor_readback" else b"\\xff")*65536)\n')
        self.tool('ubiupdatevol','#!/usr/bin/env python3\nimport os,sys\nfrom pathlib import Path\np=Path(os.environ["FIXTURE"]);(p/"operations").open("a").write("NVRAM\\n")\nif os.environ.get("FAULT")=="truncate":sys.exit(1)\nassert sys.argv[1:]==["-t",str(p/"dev/ubi0_4")]\nPath(sys.argv[2]).write_bytes((b"\\0" if os.environ.get("FAULT")=="nvram_readback" else b"\\xff")*(167*126976))\n')
        self.tool('sync','#!/bin/sh\n[ "${FAULT:-}" != sync ]\n')
        for name in ('fw_setenv','reboot','ubirmvol','ubimkvol'):
            self.tool(name,'#!/bin/sh\necho FORBIDDEN >> "$FIXTURE/operations"\nexit 99\n')

    def tearDown(self):self.tmp.cleanup()
    def put(self,name,data,mode=None):
        p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data.encode() if isinstance(data,str) else data)
        if mode is not None:p.chmod(mode)
    def tool(self,name,text):p=self.bin/name;p.write_text(text);p.chmod(0o700)
    def run_reset(self,fault='',extra=None):
        env={**os.environ,'PATH':str(self.bin)+':'+os.environ['PATH'],'FIXTURE':str(self.root),'LIB':str(LIB),'FAULT':fault,
             'CSR_RESET_QUALIFIED':'qualified','CSR_MODEL':'E410','CSR_ACTIVE':'0','CSR_PROC_MTD':str(self.root/'proc-mtd'),
             'CSR_DEV':str(self.dev),'CSR_MTD_SYS':str(self.mtd),'CSR_UBI_SYS':str(self.sys),'CSR_CMDLINE':str(self.root/'cmdline'),
             'CSR_MOUNTS':str(self.root/'mounts'),'CSR_ENV_CONFIG':str(self.root/'env-config'),'CSR_RECOVERY':str(self.recovery),
             'CSR_RECEIPT':str(self.root/'receipt'),'CSR_KERNEL':str(self.root/'kernel'),'CSR_ROOT':str(self.root/'rootfs'),
             'CSR_SHARED_MANIFEST':str(self.root/'shared-manifest'),'OW_SETTINGS_OWNER':'0'}
        for name,file in (('CSR_KERNEL_PIN','kernel'),('CSR_ROOT_PIN','rootfs'),('CSR_SHARED_PIN','shared-manifest')):env[name]=hashlib.sha256((self.root/file).read_bytes()).hexdigest()
        env.update(extra or {})
        script='. "$LIB/cambium-installer-settings.sh"; . "$LIB/cambium-sage-pair-write.sh"; . "$LIB/cambium-sage-oem-reset.sh"; csr_is_device() { [ -f "$1" ]; }; csr_reset_shared'
        result=subprocess.run(['sh','-c',script],env=env,capture_output=True,text=True)
        operations=(self.root/'operations').read_text().splitlines() if (self.root/'operations').exists() else []
        return result,operations

    def test_only_named_nor_and_nvram_are_reset_after_candidate_readback(self):
        protected={p:p.read_bytes() for p in self.dev.iterdir() if p.name not in ('mtd10','mtd10ro','ubi0_4')}
        result,ops=self.run_reset()
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(ops,['NOR','NVRAM'])
        self.assertIn('boot_state_changed=no',result.stdout)
        self.assertEqual(protected,{p:p.read_bytes() for p in protected})

    def test_unknown_geometry_ambiguity_pending_or_missing_recovery_never_writes(self):
        cases=[('mtd/mtd10/type','nand'),('mtd/mtd10/size','131072'),('mtd/mtd10/flags','0x0'),
               ('ubi/ubi0/mtd_num','12'),('ubi/ubi0_4/name','certificates'),('ubi/ubi0_4/reserved_ebs','168'),
               ('ubi/ubi0_4/type','static'),('mounts','ubi0:nvram /mnt/flash ubifs rw 0 0\n'),
               ('env-config','/dev/mtd7 0x0 0x10000 0x10000 1\n'),('env-snapshot','image=0\nbootcmd=run sage_stable0\nsage_ab_state=confirmed\nsage_installer_job=pending\n'),
               ('env-snapshot','image=1\nbootcmd=run sage_stable0\nsage_ab_state=confirmed\n'),('env-snapshot','image=0\nbootcmd=run sage_stable0\nsage_ab_state=armed\n'),
               ('receipt','a'*64+'\n'),('recovery/art.bin',b'DONOR'),('dev/ubi0_3',b'wrong candidate readback')]
        for name,data in cases:
            with self.subTest(name=name,data=str(data)[:30]):
                p=self.root/name;old=p.read_bytes();self.put(name,data)
                result,ops=self.run_reset();self.assertNotEqual(result.returncode,0);self.assertEqual(ops,[])
                p.write_bytes(old)
        for line in ('mtd12: 00010000 00010000 "config"\n','mtd10: 00010000 00010000 "0:ART"\n'):
            old=(self.root/'proc-mtd').read_bytes();self.put('proc-mtd',old+line.encode())
            result,ops=self.run_reset();self.assertNotEqual(result.returncode,0);self.assertEqual(ops,[]);self.put('proc-mtd',old)
        self.put('ubi/ubi0_9/name','nvram')
        result,ops=self.run_reset();self.assertNotEqual(result.returncode,0);self.assertEqual(ops,[])

    def test_missing_pin_missing_receipt_or_failed_env_read_never_writes(self):
        for extra in ({'CSR_KERNEL_PIN':''},{'CSR_RESET_QUALIFIED':'unqualified'},{'CSR_RECEIPT':str(self.root/'missing')},{'CSR_MODEL':'E600'},{'WRONG_OWNER':'1'}):
            result,ops=self.run_reset(extra=extra);self.assertNotEqual(result.returncode,0);self.assertEqual(ops,[])
        result,ops=self.run_reset(fault='env');self.assertNotEqual(result.returncode,0);self.assertEqual(ops,[])

    def test_write_and_readback_failures_never_change_boot_or_factory_identity(self):
        for fault,expected in (('erase',['NOR']),('nor_readback',['NOR']),('sync',['NOR']),('truncate',['NOR','NVRAM']),('nvram_readback',['NOR','NVRAM'])):
            with self.subTest(fault=fault):
                (self.root/'operations').unlink(missing_ok=True)
                result,ops=self.run_reset(fault=fault)
                self.assertNotEqual(result.returncode,0);self.assertEqual(ops,expected)
                self.assertNotIn('factory_configuration_reset=verified',result.stdout)

if __name__=='__main__':unittest.main()
