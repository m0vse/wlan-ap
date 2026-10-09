"""Exact byte reads work on published runtimes without od."""
from pathlib import Path
import subprocess
import tempfile
import unittest

BASE=Path(__file__).resolve().parents[1]


class HexReaderTests(unittest.TestCase):
    def test_model_detection_uses_fallback_and_refuses_short_sku(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);node=root/'proc/device-tree/cambium-platform/board-sku'
            node.parent.mkdir(parents=True)
            (root/'recognition.tsv').write_text('0000000a\tsage\tE410\n')
            script='. "$1";command(){ [ "$1:$2" = -v:hexdump ]; };OEM_SYS_ROOT=$2;OEM_BUNDLE=$2;oem_detect || exit 1;printf "%s:%s" "$OEM_SKU" "$OEM_MODEL"'
            for data,accepted in [(bytes.fromhex('0000000a'),True),(bytes.fromhex('00000a'),False)]:
                node.write_bytes(data)
                result=subprocess.run(['sh','-c',script,'detect',str(BASE/'lib/common.sh'),str(root)],capture_output=True,text=True)
                self.assertEqual(result.returncode==0,accepted,result.stderr)
                if accepted:self.assertEqual(result.stdout,'0000000a:E410')

    def test_hexdump_fallback_exact_sku_and_random_id_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'bytes'
            for data in (bytes.fromhex('0000000a'),bytes(range(16))):
                p.write_bytes(data)
                script='. "$1";command(){ [ "$1:$2" = -v:hexdump ]; };oem_read_hex "$2" "$3"'
                result=subprocess.run(['sh','-c',script,'read',str(BASE/'lib/common.sh'),str(p),str(len(data))],capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(result.stdout,data.hex()+'\n')

    def test_short_read_missing_reader_and_invalid_count_refuse(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'short';p.write_bytes(b'\x01\x02\x03')
            for shim,size in [('command(){ [ "$1:$2" = -v:hexdump ]; };','4'),
                              ('command(){ return 1; };','3'),('', '0'),('', '65')]:
                script='. "$1";'+shim+'oem_read_hex "$2" "$3"'
                result=subprocess.run(['sh','-c',script,'read',str(BASE/'lib/common.sh'),str(p),size],capture_output=True)
                self.assertNotEqual(result.returncode,0)


if __name__=='__main__':unittest.main()
