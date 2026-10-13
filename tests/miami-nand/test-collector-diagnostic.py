from pathlib import Path
import json, subprocess, tempfile, argparse

root=Path(__file__).parent
parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,default=root/'storage-probe.c');args=parser.parse_args()
with tempfile.TemporaryDirectory() as tmp:
    fixture=Path(tmp)/'fixture'
    attr=fixture/'sys/bus/platform/devices/79b0000.nand/miami_first_failure'
    attr.parent.mkdir(parents=True)
    exe=Path(tmp)/'probe'
    subprocess.run(['cc','-Wall','-Wextra','-Werror',f'-DSTORAGE_ROOT="{fixture}"','-o',str(exe),str(args.source)],check=True)
    def run(): return json.loads(subprocess.check_output([str(exe)]))['nand_first_failure']
    assert run()=={'state':'unavailable'}
    attr.write_text('state=armed qualified_samples=0x3ff\n')
    assert run()['state']=='armed'
    attr.write_text('state=captured reason=uncorrectable_ecc\nfeatures A0=0 B0=65 C0=0\nquote=" backslash=\\\n')
    out=run();assert out['state']=='captured' and 'B0=65' in out['record'] and 'quote="' in out['record']
    attr.write_text('state=captured '+('x'*10000))
    assert len(run()['record'])==2047
    attr.write_text('unexpected driver output')
    assert run()=={'state':'unavailable'}
print('PASS: actual storage probe old-kernel absence, armed/captured states, JSON escaping, bounded record, invalid input')
