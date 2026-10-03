"""Offline target collector tests; all paths compiled to private fixtures."""
from pathlib import Path
import fcntl, json, os, subprocess, sys, tempfile
root, compiler, source = map(Path, sys.argv[1:])
assert os.geteuid() == 0, 'Use a root-owned private fixture, never AP paths'
work = Path(tempfile.mkdtemp(prefix='radio-capture-test.'))
dump = work/'source'; dump.mkdir()
store = work/'store'; boot = work/'boot'; boot.write_text('11111111-1111-1111-1111-111111111111\n')
text = '#define fsync fixture_fsync\n#define fstatvfs fixture_space\n'+source.read_text()+r'''
#undef fsync
#undef fstatvfs
extern int fsync(int);
extern int fstatvfs(int, struct statvfs *);
int fixture_fsync(int fd) {
 static unsigned calls;
 const char *v=getenv("TEST_FAIL_SYNC");
 if(v && ++calls==(unsigned)atoi(v)){errno=EIO;return -1;}
 return fsync(fd);
}
int fixture_space(int fd, struct statvfs *s) {
 int rc=fstatvfs(fd,s);
 if(!rc && getenv("TEST_LOW_SPACE"))s->f_bavail=0;
 return rc;
}
'''
test=work/'test.c'; test.write_text(text); binary=work/'collector'
env=dict(os.environ, STAGING_DIR=str(compiler.parents[2]))
subprocess.run([str(compiler),'-std=gnu11','-O2',
 '-DSOURCE_ROOT='+json.dumps(str(dump)), '-DSTORE_ROOT='+json.dumps(str(store)),
 '-DBOOT_FILE='+json.dumps(str(boot)), str(test),'-o',str(binary)],check=True,env=env)
checks=0
def check(ok):
 global checks
 assert ok; checks+=1
def run(name, **extra):
 return subprocess.run(['/usr/bin/qemu-aarch64','-L',str(root),str(binary),name],env=dict(env,**extra)).returncode
def add(name,data):
 p=dump/name;p.mkdir();(p/'data').write_bytes(data);return p/'data'
small=add('devcd0',b'TEST synthetic radio dump')
check(run('../devcd0')!=0 and not store.exists())
check(run('devcd0',TEST_LOW_SPACE='1')!=0 and not list(store.glob('*.bin')))
check(run('devcd0',TEST_FAIL_SYNC='1')!=0 and not list(store.glob('*.json')))
check(small.read_bytes()==b'TEST synthetic radio dump')
check(run('devcd0')==0)
p=next(store.glob('*.json')); meta=json.loads(p.read_text())
check(meta['complete'] and not meta['truncated'] and meta['source']=='devcoredump')
check((store/meta['binaryfile']).read_bytes()==small.read_bytes())
check(store.stat().st_mode&0o777==0o700 and all(p.stat().st_mode&0o777==0o600 for p in store.iterdir()))
check(run('devcd0')==0 and len(list(store.glob('*.json')))==1)
big=add('devcd1',b'TEST'+b'x'*(1024*1024+5))
check(run('devcd1')==0)
records=[json.loads(p.read_text()) for p in store.glob('*.json')]
large=next(r for r in records if r['id'].endswith('devcd1'))
check(not large['complete'] and large['truncated'] and large['byte_count']==1024*1024)
check((store/large['binaryfile']).read_bytes()==big.read_bytes()[:1024*1024])
check(big.stat().st_size==1024*1024+9)
add('devcd2',b'TEST third event')
check(run('devcd2')!=0 and len(list(store.glob('*.bin')))==2)
store.chmod(0o755);check(run('devcd0')!=0);store.chmod(0o700)
check(not list(store.glob('.capture*')))
store.rename(work/'retained-full-store')
check(run('devcd0',TEST_FAIL_SYNC='4')!=0)
check(len(list(store.glob('*.json')))==1 and small.read_bytes()==b'TEST synthetic radio dump')
check(run('devcd0')==0)
with (store/'.lock').open('r+') as locked:
 fcntl.flock(locked,fcntl.LOCK_EX|fcntl.LOCK_NB)
 check(run('devcd1')!=0 and len(list(store.glob('*.json')))==1)
store.rename(work/'retained-final-sync-store')
check(run('devcd0',TEST_FAIL_SYNC='3')!=0)
check(not list(store.glob('*.json')) and len(list(store.glob('*.bin')))==1)
check(run('devcd0')!=0 and small.read_bytes()==b'TEST synthetic radio dump')
print(f'PASS {checks} actual target collector controls; fixture {work}')
