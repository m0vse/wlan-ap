"""Real pair/recovery flow; disposable storage/ENV and bootloader-hash boundary."""
import hashlib
import unittest
import test_cambium_sage_oem_recovery as recovery

class DeferredTests(unittest.TestCase):
    def fixture(self, slot):
        case = recovery.RecoveryTests()
        case.setUp()
        self.addCleanup(case.tearDown)
        f, root = case.f, case.r
        f.put('mtd/mtd10/flags', '0x800')
        for identifier in (0, 1, 2, 3, 4, 6, 7):
            f.put(f'ubi/ubi0_{identifier}/corrupted', '0')
        for identifier in (0, 1, 6):
            f.put(f'dev/ubi0_{identifier}', b'KEEP working source ' + str(identifier).encode())
        if slot == 1:
            f.put('ubi/ubi0_1/reserved_ebs', '372')
            f.put('ubi/ubi0_3/reserved_ebs', '285')
            f.put('ubi/ubi0_6/name', 'rootfs_data1')
            f.put('dev/ubi0_2', b'KEEP source kernel')
            f.put('dev/ubi0_3', b'KEEP source root')
        f.put('cmdline', f'ubi.mtd=fs root=/dev/ubiblock0_{2*slot+1} rootfstype=squashfs ro\n')
        case.source_boot = f'setenv image {slot}; bootm qualified-native-source'
        f.put('env-snapshot', f'image={slot}\nbootcmd=run sage_stable{slot}\nsage_ab_state=confirmed\nsage_boot{slot}={case.source_boot}\nethaddr=02:00:00:00:00:01\n')
        writer = f.bin/'ubiupdatevol'
        writer.write_text(writer.read_text().replace('("ubi0_2","ubi0_3")',
                          f'("ubi0_{2*(1-slot)}","ubi0_{2*(1-slot)+1}")').replace('dst.name=="ubi0_2"', f'dst.name=="ubi0_{2*(1-slot)}"'))
        return case, {'CSR_ACTIVE': str(slot)}

    def test_both_slots_readonly_config_preserved_writer_then_one_shot_arm(self):
        for slot in (0, 1):
            with self.subTest(slot=slot):
                case, extra = self.fixture(slot)
                protected = {p: p.read_bytes() for p in case.f.dev.iterdir()
                             if p.name not in (f'ubi0_{2*(1-slot)}', f'ubi0_{2*(1-slot)+1}')}
                result, ops = case.invoke(extra=extra, operation='csr_restore_oem_deferred')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(ops, ['ENV_BATCH', 'ROOT', 'KERNEL', 'ENV_BATCH', 'ENV_SELECTOR'])
                self.assertEqual(protected, {p: p.read_bytes() for p in protected})
                env = dict(row.split('=', 1) for row in (case.r/'env-snapshot').read_text().splitlines())
                self.assertEqual(env[f'sage_boot{slot}'], case.source_boot)
                self.assertEqual(env['image'], str(slot))
                self.assertEqual(env['sage_oem_restore_state'], 'armed')
                self.assertIn(f'saveenv && run sage_boot{1-slot}; run sage_boot{slot}', env['bootcmd'])
                self.assertIn('shared_configuration=preserved', result.stdout)

    def test_failures_never_reset_shared_data_or_claim_success(self):
        for slot in (0, 1):
            for fault in ('boundary', 'env', 'batch', 'sync', 'root', 'kernel', 'metadata_readback', 'selector'):
                with self.subTest(slot=slot, fault=fault):
                    case, extra = self.fixture(slot)
                    kept = {p: p.read_bytes() for p in case.f.dev.iterdir()
                            if p.name not in (f'ubi0_{2*(1-slot)}', f'ubi0_{2*(1-slot)+1}')}
                    result, ops = case.invoke(fault=fault, extra=extra, operation='csr_restore_oem_deferred')
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(kept, {p: p.read_bytes() for p in kept})
                    self.assertNotIn('NOR', ops)
                    self.assertNotIn('NVRAM', ops)
                    self.assertNotIn('shared_configuration=preserved', result.stdout)
                    if fault in ('boundary', 'env', 'batch', 'sync'):
                        self.assertNotIn('ROOT', ops)
                        self.assertNotIn('KERNEL', ops)
                    env = dict(row.split('=', 1) for row in (case.r/'env-snapshot').read_text().splitlines())
                    self.assertIn(env['bootcmd'], (f'run sage_stable{slot}', f'run sage_boot{slot}'))

    def test_unified_receipt_without_unmanifested_aliases(self):
        case, extra = self.fixture(0)
        directory = case.f.recovery
        for before, after in (('appsblenv', 'ENV'), ('art', 'ART'), ('manufacturing', 'MFG')):
            (directory/f'{before}.bin').rename(directory/f'{after}.bin')
        case.f.put('recovery/manifest.tsv', 'ENV\t0:APPSBLENV\t65536\tunique-env\nART\t0:ART\t65536\tcalibration\nMFG\tmfginfo\t65536\tfactory\n', 0o600)
        rows = ''.join(hashlib.sha256((directory/name).read_bytes()).hexdigest()+'  '+name+'\n'
                       for name in ('ENV.bin', 'ART.bin', 'MFG.bin', 'manifest.tsv'))
        case.f.put('recovery/SHA256SUMS', rows, 0o600)
        case.f.put('receipt', hashlib.sha256(rows.encode()).hexdigest()+'\n', 0o600)
        result, ops = case.invoke(extra=dict(extra, CSR_RECOVERY_FORMAT='unified'), operation='csr_restore_oem_deferred')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('NOR', ops)
        self.assertFalse((directory/'appsblenv.bin').exists())

    def test_concurrent_shared_store_change_does_not_block_safe_target_writer(self):
        case, extra = self.fixture(0)
        writer = case.f.bin/'ubiupdatevol'
        writer.write_text(writer.read_text()+'\nif label=="ROOT": (p/"dev/ubi0_4").write_bytes(b"simulated independent daemon write")\n')
        result, ops = case.invoke(extra=extra, operation='csr_restore_oem_deferred')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(ops, ['ENV_BATCH', 'ROOT', 'KERNEL', 'ENV_BATCH', 'ENV_SELECTOR'])
        env = dict(row.split('=', 1) for row in (case.r/'env-snapshot').read_text().splitlines())
        self.assertIn('saveenv && run sage_boot1; run sage_boot0', env['bootcmd'])
        self.assertEqual(env['sage_oem_restore_state'], 'armed')
        self.assertEqual((case.r/'dev/ubi0_4').read_bytes(), b'simulated independent daemon write')
        self.assertIn('oem_candidate_armed=', result.stdout)

    def test_source_kernel_mutation_is_still_detected_before_arm(self):
        case, extra = self.fixture(0)
        writer = case.f.bin/'ubiupdatevol'
        writer.write_text(writer.read_text()+'\nif label=="ROOT": (p/"dev/ubi0_0").write_bytes(b"wrong source write")\n')
        result, ops = case.invoke(extra=extra, operation='csr_restore_oem_deferred')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(ops, ['ENV_BATCH', 'ROOT', 'KERNEL'])
        self.assertNotIn('oem_candidate_armed=', result.stdout)

if __name__ == '__main__':
    unittest.main()
