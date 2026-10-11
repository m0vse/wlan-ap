"""Validate actual recovery parser fences without executing vendor scripts."""
import importlib.util
import io
import lzma
from pathlib import Path
import tarfile
import unittest

PATH=Path(__file__).resolve().parents[2]/'prepare-sage-recovery.py'
SPEC=importlib.util.spec_from_file_location('sage_recovery',PATH)
RECOVERY=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(RECOVERY)


def archive(extra=()):
    buffer=io.BytesIO()
    with tarfile.open(fileobj=buffer,mode='w') as tar:
        entries=[('kernel.itb',b'\xd0\x0d\xfe\xed'+b'qualified FIT fixture'),
                 ('etc/version',b'PRODUCT=sage\nVERSION=4.2.3.3-r10\n')]
        for name,data in entries:
            info=tarfile.TarInfo(name); info.size=len(data); tar.addfile(info,io.BytesIO(data))
        for info,data in extra: tar.addfile(info,io.BytesIO(data) if data is not None else None)
    return buffer.getvalue()


class RecoveryPrepareTests(unittest.TestCase):
    def test_regular_fixture_and_absolute_symlink_without_descendants(self):
        link=tarfile.TarInfo('tmp'); link.type=tarfile.SYMTYPE; link.linkname='/run/tmp'
        records,kernel=RECOVERY.inspect_tar(archive([(link,None)]))
        self.assertEqual(len(records),3); self.assertEqual(kernel[:4],b'\xd0\x0d\xfe\xed')

    def test_traversal_duplicate_special_file_and_link_ancestor_refused(self):
        for name in ('../escape','/escape','a/../escape','kernel.itb'):
            info=tarfile.TarInfo(name); info.size=1
            with self.subTest(name=name),self.assertRaises(ValueError): RECOVERY.inspect_tar(archive([(info,b'x')]))
        link=tarfile.TarInfo('evil'); link.type=tarfile.SYMTYPE; link.linkname='/etc'
        child=tarfile.TarInfo('evil/overwrite'); child.size=1
        with self.assertRaises(ValueError): RECOVERY.inspect_tar(archive([(child,b'x'),(link,None)]))
        device=tarfile.TarInfo('dev/flash'); device.type=tarfile.CHRTYPE
        with self.assertRaises(ValueError): RECOVERY.inspect_tar(archive([(device,None)]))

    def test_unknown_owner_hardlink_target_and_release_refused(self):
        info=tarfile.TarInfo('file'); info.uid=123
        with self.assertRaises(ValueError): RECOVERY.inspect_tar(archive([(info,None)]))
        link=tarfile.TarInfo('link'); link.type=tarfile.LNKTYPE; link.linkname='missing'
        with self.assertRaises(ValueError): RECOVERY.inspect_tar(archive([(link,None)]))
        bad=archive().replace(b'VERSION=4.2.3.3-r10',b'VERSION=4.2.3.3-r11')
        with self.assertRaises(ValueError): RECOVERY.inspect_tar(bad)

    def test_signed_content_manifest_is_declarative_and_trailing_data_refused(self):
        prefix=b'------BEGIN MANIFEST\nMANIFEST_VERSION=1\nIMAGE_FORMAT=2\nSUPPORTED_PRODUCTS=E410:E600:E430:E700:E510\nIMAGE_VERSION=4.2.3.3-r10\nIMAGE_UBOOT_VERSION=1.0.13a\n# ignored vendor script, never executed\n------END MANIFEST\n------BEGIN IMAGE\n'
        payload=prefix+lzma.compress(archive())
        fields,data=RECOVERY.unpack(payload); self.assertEqual(data,archive())
        for bad in (payload+b'junk',payload.replace(b'IMAGE_FORMAT=2',b'IMAGE_FORMAT=2\nIMAGE_FORMAT=2'),payload.replace(b'IMAGE_FORMAT=2',b'UNKNOWN=2')):
            with self.assertRaises(ValueError): RECOVERY.unpack(bad)


if __name__=='__main__': unittest.main()
