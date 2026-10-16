"""Real stock13 source negative controls; no AP, ENV or flash operations."""
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('generator', BASE/'prepare-bridge.py')
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)
root, bundle = (Path(p).resolve() for p in sys.argv[1:])
ledger = generator.REPO/'tests/installer/sage-stock13-source-v1/source-sets/outgoing-stock-2026.10.13.0.set'
rows = [line.split() for line in ledger.read_text().splitlines()]
assert len(rows) == 39
wrapper = (bundle/'prepare-upgrader.sh').read_text()
assert ' cambium,e410|cambiumnetworks,e410|cambiumnetworks,e410b) ;;' in wrapper
assert (bundle/'stock-store-check.sh').is_file()
assert wrapper.index('export CAMBIUM_SAGE_LIB="$bundle/cambium-sage.sh"') < wrapper.index('. "$bundle/cambium-ab.sh"')
assert (bundle/'source-contract').read_text().splitlines()[0] == '2026.10.13.0'
assert (bundle/'source-sets'/ledger.name).is_file()
assert not (bundle/'source-sets/outgoing-stock-2026.09.29.0.set').exists()
with tempfile.TemporaryDirectory(prefix='stock13-source-denials.') as tmp:
    work = Path(tmp)
    fixture = work/'root'
    fixture.mkdir()
    for digest, name in rows:
        if digest == '-':
            continue
        src = root/name.lstrip('/')
        assert generator.digest(src) == digest, name
        dest = fixture/name.lstrip('/')
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
    for digest, name in rows:
        path = fixture/name.lstrip('/')
        original = path.read_bytes() if path.exists() else None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((original or b'')+b'\nchanged-source\n')
        try:
            generator.generate('sage', fixture, work/'must-not-exist', '2026.10.13.0')
        except ValueError as error:
            assert str(error) == 'stock source ledger mismatch: '+name, (name, error)
        else:
            raise AssertionError('changed/previously absent source admitted: '+name)
        assert not (work/'must-not-exist').exists()
        if original is None:
            path.unlink()
        else:
            path.write_bytes(original)
    path = fixture/'lib/functions/cambium-ab.sh'
    original = path.read_bytes()
    path.unlink()
    target = work/'same-bytes'
    target.write_bytes(original)
    path.symlink_to(target)
    try:
        generator.generate('sage', fixture, work/'must-not-exist', '2026.10.13.0')
    except ValueError as error:
        assert str(error) == 'stock source ledger mismatch: /lib/functions/cambium-ab.sh'
    else:
        raise AssertionError('symlink source admitted')
print('stock13: 39 changed/present-source denials + identical-byte symlink denial PASS; existing E410/E410B model gate verified')
