"""Whole recovery sequence under disposable device/ENV backends."""
import hashlib
import os
import subprocess
import unittest
import test_cambium_sage_oem_defaults as defaults

LIB=defaults.LIB
class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.d=defaults.DefaultsTests('test_compiled_defaults_and_selected_oem_bank_preserve_all_factory_keys');self.d.setUp()
        self.f=self.d.f;self.r=self.f.root
        self.f.put('cmdline','ubi.mtd=fs root=/dev/ubiblock0_1 rootfstype=squashfs ro\n')
        self.source_boot='setenv image 0; bootm qualified-native-source'
        self.f.put('env-snapshot','image=0\nbootcmd=run sage_stable0\nsage_ab_state=confirmed\nsage_boot0='+self.source_boot+'\nethaddr=02:00:00:00:00:01\n')
        self.f.tool('fw_printenv','#!/usr/bin/env python3\nimport os,sys\nfrom pathlib import Path\np=Path(os.environ["FIXTURE"]);s=dict(x.split("=",1) for x in (p/"env-snapshot").read_text().splitlines())\nif os.environ.get("FAULT")=="env":sys.exit(1)\nif "-n" in sys.argv:\n k=sys.argv[sys.argv.index("-n")+1]\n if k not in s:sys.exit(1)\n print("mismatch" if os.environ.get("FAULT")=="metadata_readback" and k=="sage_ab_target" else s[k])\nelse:print("".join(k+"="+v+"\\n" for k,v in s.items()),end="")\n')
        self.f.tool('fw_setenv','#!/usr/bin/env python3\nimport os,sys\nfrom pathlib import Path\np=Path(os.environ["FIXTURE"]);s=dict(x.split("=",1) for x in (p/"env-snapshot").read_text().splitlines());a=sys.argv[3:]\nif a[0]=="-s":\n (p/"operations").open("a").write("ENV_BATCH\\n")\n if os.environ.get("FAULT")=="batch":sys.exit(1)\n for row in Path(a[1]).read_text().splitlines():\n  k,v=row.split(" ",1);s[k]=v\nelse:\n (p/"operations").open("a").write("ENV_SELECTOR\\n")\n if os.environ.get("FAULT")=="selector":sys.exit(1)\n assert a[0]=="bootcmd";s[a[0]]=a[1]\n(p/"env-snapshot").write_text("".join(k+"="+v+"\\n" for k,v in s.items()))\n')
        self.f.tool('ubirsvol','#!/bin/sh\necho FORBIDDEN >> "$FIXTURE/operations"\nexit 99\n')
        self.f.tool('ubiupdatevol','#!/usr/bin/env python3\nimport os,sys\nfrom pathlib import Path\np=Path(os.environ["FIXTURE"]);a=sys.argv[1:]\nif a[0]=="-t":\n assert a[1]==str(p/"dev/ubi0_4");label="NVRAM"\n data=b"\\xff"*(167*126976);dst=Path(a[1])\nelse:\n dst=Path(a[0]);assert dst.name in ("ubi0_2","ubi0_3");label="KERNEL" if dst.name=="ubi0_2" else "ROOT";data=Path(a[1]).read_bytes()\n(p/"operations").open("a").write(label+"\\n")\nif os.environ.get("FAULT")==label.lower():sys.exit(1)\ndst.write_bytes(data)\n')
    def tearDown(self):self.d.tearDown()
    def invoke(self,fault='',extra=None,arm_only=False,operation=None):
        env={**os.environ,'PATH':str(self.f.bin)+':'+os.environ['PATH'],'FIXTURE':str(self.r),'LIB':str(LIB),'FAULT':fault,
            'CSR_RESET_QUALIFIED':'qualified','CSR_RECOVERY_BOOT_QUALIFIED':'qualified','CSR_OEM_DEFAULTS_QUALIFIED':'qualified',
            'CSR_MODEL':'E410','CSR_ACTIVE':'0','CSR_SOURCE_BOOT_PIN':hashlib.sha256(self.source_boot.encode()).hexdigest(),
            'CSR_PROC_MTD':str(self.r/'proc-mtd'),'CSR_DEV':str(self.f.dev),'CSR_MTD_SYS':str(self.f.mtd),'CSR_UBI_SYS':str(self.f.sys),
            'CSR_CMDLINE':str(self.r/'cmdline'),'CSR_MOUNTS':str(self.r/'mounts'),'CSR_ENV_CONFIG':str(self.r/'env-config'),
            'CSR_RECOVERY':str(self.f.recovery),'CSR_RECEIPT':str(self.r/'receipt'),'CSR_KERNEL':str(self.r/'kernel'),'CSR_ROOT':str(self.r/'rootfs'),
            'CSR_SHARED_MANIFEST':str(self.r/'shared-manifest'),'OW_SETTINGS_OWNER':'0'}
        for k,n in (('CSR_KERNEL_PIN','kernel'),('CSR_ROOT_PIN','rootfs'),('CSR_SHARED_PIN','shared-manifest')):env[k]=hashlib.sha256((self.r/n).read_bytes()).hexdigest()
        env.update(extra or {})
        code='''
. "$LIB/cambium-installer-settings.sh"; . "$LIB/cambium-sage-pair-write.sh"
. "$LIB/cambium-sage-oem-reset.sh"; . "$LIB/cambium-sage-oem-recovery.sh"
csr_is_device() { [ -f "$1" ]; }
csr_hash() {
 if [ "$1" = "$CSR_DEV/mtd6ro" ]; then echo 066bfcc317291b23e44bd42f1d10c4d08ca82ded6ca05abd15f5da280ae4dba1
 else sha256sum < "$1" | awk '{print $1}'; fi
}
csr_deferred_storage_boundary() { [ "${FAULT:-}" != boundary ]; }
'''+(operation or ('csr_arm_oem' if arm_only else 'csr_restore_oem'))
        result=subprocess.run(['sh','-c',code],env=env,capture_output=True,text=True)
        ops=(self.r/'operations').read_text().splitlines() if (self.r/'operations').exists() else []
        return result,ops
    def test_write_verify_reset_then_arm_preserves_exact_native_source(self):
        cert=(self.f.dev/'ubi0_7').read_bytes()
        result,ops=self.invoke();self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(ops,['ROOT','KERNEL','NOR','NVRAM','ENV_BATCH','ENV_SELECTOR'])
        rows=dict(x.split('=',1) for x in (self.r/'env-snapshot').read_text().splitlines())
        self.assertEqual(rows['sage_boot0'],self.source_boot);self.assertEqual(rows['sage_boot1'],'setenv image 1; bootipq')
        self.assertEqual(rows['image'],'0');self.assertEqual(rows['ethaddr'],'02:00:00:00:00:01')
        self.assertLess(rows['bootcmd'].index('saveenv'),rows['bootcmd'].index('run sage_boot1'))
        self.assertEqual(cert,(self.f.dev/'ubi0_7').read_bytes());self.assertIn('reboot_required=yes',result.stdout)
    def test_missing_boot_pin_defaults_or_readonly_nor_refuses_before_firmware(self):
        for extra in ({'CSR_SOURCE_BOOT_PIN':''},{'CSR_SOURCE_BOOT_PIN':'a'*64},{'CSR_OEM_DEFAULTS_QUALIFIED':'unqualified'},{'CSR_MODEL':'E410B'}):
            result,ops=self.invoke(extra=extra);self.assertNotEqual(result.returncode,0);self.assertEqual(ops,[])
        self.f.put('mtd/mtd10/flags','0x800')
        result,ops=self.invoke();self.assertNotEqual(result.returncode,0);self.assertEqual(ops,[])
    def test_failed_writer_never_resets_or_arms(self):
        for fault,expected in (('root',['ROOT']),('kernel',['ROOT','KERNEL'])):
            (self.r/'operations').unlink(missing_ok=True)
            result,ops=self.invoke(fault);self.assertNotEqual(result.returncode,0);self.assertEqual(ops,expected)
    def test_failed_metadata_never_changes_source_selector(self):
        self.f.put('dev/mtd10',b'\xff'*65536);self.f.put('dev/ubi0_4',b'\xff'*(167*126976))
        original=(self.r/'env-snapshot').read_bytes()
        for fault,expected in (('batch',['ENV_BATCH']),('metadata_readback',['ENV_BATCH']),('selector',['ENV_BATCH','ENV_SELECTOR'])):
            with self.subTest(fault=fault):
                (self.r/'operations').unlink(missing_ok=True);self.f.put('env-snapshot',original)
                result,ops=self.invoke(fault,arm_only=True);self.assertNotEqual(result.returncode,0);self.assertEqual(ops,expected)
                rows=dict(x.split('=',1) for x in (self.r/'env-snapshot').read_text().splitlines())
                self.assertEqual(rows['bootcmd'],'run sage_stable0')
                self.assertNotIn('oem_candidate_armed=',result.stdout)

if __name__=='__main__':unittest.main()
