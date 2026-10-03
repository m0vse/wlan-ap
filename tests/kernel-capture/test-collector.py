"""Persistent receiver storage controls; no socket opened or AP access."""
import base64,importlib.util,json,os,sys,tempfile
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('receiver',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
d=Path(tempfile.mkdtemp(prefix='netconsole-store-'));store=m.Store(d,['192.0.2.10'],16384,2);count=0
def check(ok):
 global count
 assert ok;count+=1
try:
 check(not store.append('192.0.2.99',b'ignored') and not list(d.iterdir()))
 raw=b'Kernel panic\n\x00\xff';check(store.append('192.0.2.10',raw,6665))
 p=d/'192.0.2.10.0.jsonl';row=json.loads(p.read_text());check(base64.b64decode(row['raw_base64'])==raw and not row['truncated'])
 check((p.stat().st_mode&0o777)==0o600)
 with p.open('ab') as f:f.write(b'{partial')
 check(store.append('192.0.2.10',b'next') and len(p.read_text().splitlines())==2)
 for i in range(6):check(store.append('192.0.2.10',b'x'*9000))
 check(len(list(d.iterdir()))<=2 and sum(x.stat().st_size for x in d.iterdir())<=32768)
 rows=[json.loads(line) for x in d.iterdir() for line in x.read_text().splitlines()];check(all(r['truncated'] and len(base64.b64decode(r['raw_base64']))==8192 for r in rows))
 with patch.object(m.os,'fsync',side_effect=OSError('TEST sync failure')):
  try:store.append('192.0.2.10',b'failure');raise AssertionError('success after failed durability')
  except OSError:count+=1
finally:store.close()
bad=Path(tempfile.mkdtemp(prefix='netconsole-public-'));bad.chmod(0o755)
try:m.Store(bad,['192.0.2.10']);raise AssertionError('accepted public store')
except ValueError:count+=1
link=d.parent/(d.name+'-link');link.symlink_to(d)
try:m.Store(link,['192.0.2.10']);raise AssertionError('accepted symlink store')
except ValueError:count+=1
print(f'PASS {count} durable receiver controls; no listener deployed')
