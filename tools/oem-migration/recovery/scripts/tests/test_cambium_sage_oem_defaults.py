"""Defaults apply with actual parsers/readbacks, synthetic device/ENV backend."""
import hashlib
import os
from pathlib import Path
import subprocess
import unittest
import test_cambium_sage_oem_reset as reset
LIB=reset.LIB

class DefaultsTests(unittest.TestCase):
    def setUp(self):
        self.f=reset.ResetTests('test_only_named_nor_and_nvram_are_reset_after_candidate_readback');self.f.setUp()
        self.r=self.f.root
        self.f.put('proc-mtd',(self.r/'proc-mtd').read_text()+'mtd6: 00080000 00010000 "0:APPSBL"\n')
        self.f.put('dev/mtd6ro',b'synthetic bootloader reference')
        mfg=b'\0PL-E410XXXA-EU\0'.ljust(65536,b'\0');self.f.put('dev/mtd8ro',mfg);self.f.put('recovery/manufacturing.bin',mfg,0o600)
        rows=''.join(hashlib.sha256((self.f.recovery/(n+'.bin')).read_bytes()).hexdigest()+'  '+n+'.bin\n' for n in ('appsblenv','art','manufacturing'))
        self.f.put('recovery/SHA256SUMS',rows,0o600);self.f.put('receipt',hashlib.sha256(rows.encode()).hexdigest()+'\n',0o600)
        self.f.put('cmdline','ubi.mtd=fs root=ubi0:rootfs1 rootfstype=ubifs rw\n')
        self.f.put('version','PRODUCT=sage\nVERSION=4.2.3.3-r10\n')
        self.f.put('env-snapshot','image=0\nbootcmd=run sage_stable0\nbootdelay=4\nsage_ab_state=trial-started\nsage_installer_job='+ 'a'*64+'\nethaddr=02:00:00:00:00:01\nserial#=synthetic-device\ncustom=keep=all\n')
        self.f.tool('fw_printenv','#!/bin/sh\n[ "${FAULT:-}" != env_before ] || exit 1\nif [ "${FAULT:-}" = env_after ] && [ -e "$FIXTURE/operations" ]; then exit 1; fi\n[ "${FAULT:-}" != crc_warning ] || echo "Warning: bad CRC" >&2\ncat "$FIXTURE/env-snapshot"\n')
        self.f.tool('fw_setenv','#!/usr/bin/env python3\nimport os,sys\nfrom pathlib import Path\np=Path(os.environ["FIXTURE"]);(p/"operations").open("a").write("ENV\\n")\nif os.environ.get("FAULT")=="batch":sys.exit(1)\nassert sys.argv[1:4]==["-c",str(p/"env-config"),"-s"]\ns=dict(x.split("=",1) for x in (p/"env-snapshot").read_text().splitlines())\nfor row in Path(sys.argv[4]).read_text().splitlines():\n a=row.split(" ",1)\n if len(a)==1:s.pop(a[0],None)\n else:s[a[0]]=a[1]\nif os.environ.get("FAULT")=="defaults_readback":s["bootdelay"]="99"\nif os.environ.get("FAULT")=="identity_readback":s["ethaddr"]="changed"\n(p/"env-snapshot").write_text("".join(k+"="+v+"\\n" for k,v in s.items()))\n')
    def tearDown(self):self.f.tearDown()
    def invoke(self,fault='',extra=None):
        env={**os.environ,'PATH':str(self.f.bin)+':'+os.environ['PATH'],'FIXTURE':str(self.r),'LIB':str(LIB),'FAULT':fault,
            'CSR_MODEL':'E410','CSR_OEM_SLOT':'1','CSR_OEM_DEFAULTS_QUALIFIED':'qualified','CSR_OEM_BOOT_VERIFIED':'qualified',
            'CSR_PROC_MTD':str(self.r/'proc-mtd'),'CSR_DEV':str(self.f.dev),'CSR_CMDLINE':str(self.r/'cmdline'),
            'CSR_OEM_VERSION':str(self.r/'version'),'CSR_ENV_CONFIG':str(self.r/'env-config'),
            'CSR_RECOVERY':str(self.f.recovery),'CSR_RECEIPT':str(self.r/'receipt'),'CSR_KERNEL':str(self.r/'kernel'),
            'CSR_KERNEL_PIN':hashlib.sha256((self.r/'kernel').read_bytes()).hexdigest(),
            'CSR_SHARED_MANIFEST':str(self.r/'shared-manifest'),'CSR_SHARED_PIN':hashlib.sha256((self.r/'shared-manifest').read_bytes()).hexdigest(),'OW_SETTINGS_OWNER':'0'}
        env.update(extra or {})
        code='''
. "$LIB/cambium-installer-settings.sh"; . "$LIB/cambium-sage-pair-write.sh"
. "$LIB/cambium-sage-oem-reset.sh"; . "$LIB/cambium-sage-oem-defaults.sh"
csr_is_device() { [ -f "$1" ]; }; id() { echo 0; }
csr_hash() {
 if [ "$1" = "$CSR_DEV/mtd6ro" ] && [ "${BAD_BOOTLOADER:-0}" != 1 ]; then
  echo 066bfcc317291b23e44bd42f1d10c4d08ca82ded6ca05abd15f5da280ae4dba1
 else sha256sum < "$1" | awk '{print $1}'; fi
}
csr_apply_oem_defaults
'''
        result=subprocess.run(['sh','-c',code],env=env,capture_output=True,text=True)
        operations=(self.r/'operations').read_text().splitlines() if (self.r/'operations').exists() else []
        return result,operations
    def test_compiled_defaults_and_selected_oem_bank_preserve_all_factory_keys(self):
        result,ops=self.invoke();self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(ops,['ENV'])
        rows=dict(x.split('=',1) for x in (self.r/'env-snapshot').read_text().splitlines())
        for k,v in {'bootcmd':'bootipq','bootdelay':'2','image':'1','bootcount':'0','ipaddr':'192.168.1.11','serverip':'192.168.1.120','ethaddr':'02:00:00:00:00:01','serial#':'synthetic-device','custom':'keep=all'}.items():self.assertEqual(rows[k],v)
        self.assertNotIn('sage_ab_state',rows);self.assertNotIn('sage_installer_job',rows)
        self.assertIn('reboot_performed=no',result.stdout)
    def test_unverified_boot_model_code_or_missing_receipt_never_writes(self):
        for extra in ({'CSR_OEM_BOOT_VERIFIED':'unqualified'},{'CSR_MODEL':'E410B'},{'BAD_BOOTLOADER':'1'},{'CSR_RECEIPT':str(self.r/'missing')},{'CSR_KERNEL_PIN':''}):
            result,ops=self.invoke(extra=extra);self.assertNotEqual(result.returncode,0);self.assertEqual(ops,[])
        for fault in ('env_before','crc_warning'):
            result,ops=self.invoke(fault);self.assertNotEqual(result.returncode,0);self.assertEqual(ops,[])
    def test_failed_batch_and_readbacks_never_report_success_or_reboot(self):
        for fault in ('batch','env_after','defaults_readback','identity_readback'):
            with self.subTest(fault=fault):
                (self.r/'operations').unlink(missing_ok=True)
                result,ops=self.invoke(fault);self.assertNotEqual(result.returncode,0);self.assertEqual(ops,['ENV'])
                self.assertNotIn('oem_defaults=verified',result.stdout)

if __name__=='__main__':unittest.main()
