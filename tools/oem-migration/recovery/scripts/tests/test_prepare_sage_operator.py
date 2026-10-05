import importlib.util
from pathlib import Path
import tempfile
import unittest

path = Path(__file__).resolve().parents[2] / "prepare-sage-operator.py"
spec = importlib.util.spec_from_file_location("sage_operator_generator", path)
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)

class GeneratorAdmissionTests(unittest.TestCase):
    def test_invalid_inputs_leave_output_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            archive = base / "root.tar"
            archive.write_bytes(b"untrusted source")
            out = base / "out"
            for model, pins in (("E410", ["bad"] * 3), ("unknown", ["1" * 64] * 3), ("E410", ["1" * 64] * 3)):
                with self.subTest(model=model, pins=pins), self.assertRaises(ValueError):
                    generator.generate(root, archive, out, model, pins)
                self.assertFalse(out.exists())

    def test_source_tree_and_symlink_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            archive = base / "root.tar"
            archive.write_bytes(b"untrusted source")
            with self.assertRaises(ValueError):
                generator.generate(root, archive, root / "out", "E410", ["1" * 64] * 3)
            link = base / "link.tar"
            link.symlink_to(archive)
            with self.assertRaises(ValueError):
                generator.generate(root, link, base / "out", "E410", ["1" * 64] * 3)
            self.assertEqual(list(root.iterdir()), [])
            self.assertFalse((base / "out").exists())

if __name__ == "__main__":
    unittest.main()
