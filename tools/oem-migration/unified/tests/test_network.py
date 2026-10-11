"""Linux process-budget/cache tests. No external network or device nodes."""
import hashlib,os,subprocess,sys,tempfile,time,unittest
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]

class NetworkTests(unittest.TestCase):
    def test_staging_plan_counts_verified_cache_and_all_future_copies(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td).resolve();root.chmod(0o700)
            common=root/'common.sh';common.write_text((BASE/'lib/common.sh').read_text().replace('$3==0',f'$3=={os.getuid()}').replace('$1=="drwx------"','$1~/^drwx------@?$/').replace('$1=="-rw-------"','$1~/^-rw-------@?$/'))
            out=root/'payload';data=b'verified';pin=hashlib.sha256(data).hexdigest()
            prefix=f'. "{common}";. "{BASE}/lib/network.sh";'
            run=lambda body:subprocess.run(['sh','-c',prefix+body],capture_output=True,text=True)
            p=run(f'oem_stage_missing_bytes "{out}" {pin} {len(data)}');self.assertEqual(p.stdout,str(len(data))+'\n');self.assertEqual(p.returncode,0)
            out.write_bytes(data);out.chmod(0o600)
            p=run(f'oem_stage_missing_bytes "{out}" {pin} {len(data)}');self.assertEqual(p.stdout,'0\n');self.assertEqual(p.returncode,0)
            out.write_bytes(b'corrupt');self.assertNotEqual(run(f'oem_stage_missing_bytes "{out}" {pin} {len(data)}').returncode,0)
            df='df(){ printf "Filesystem 1024-blocks Used Available Capacity Mounted\\nfixture 100 98 2 98%% /\\n"; };'
            self.assertEqual(run(df+f'oem_stage_space_check "{root}" 2048').returncode,0)
            self.assertNotEqual(run(df+f'oem_stage_space_check "{root}" 2049').returncode,0)
            self.assertNotEqual(run(df+f'oem_stage_space_check "{root}" invalid').returncode,0)

    def test_valid_local_cache_never_contacts_provider(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td).resolve();data=b'cached verified payload';out=root/'payload';out.write_bytes(data)
            sha=hashlib.sha256(data).hexdigest()
            out.chmod(0o600)
            common=root/'common.sh';common.write_text((BASE/'lib/common.sh').read_text().replace('$3==0',f'$3=={os.getuid()}').replace('$1=="drwx------"','$1~/^drwx------@?$/').replace('$1=="-rw-------"','$1~/^-rw-------@?$/'))
            script=f'. "{common}";. "{BASE}/lib/network.sh";OEM_DOWNLOAD_URL=http://provider.invalid;OEM_NETWORK_BUDGET_LEFT=0;oem_fetch_local payload {sha} {len(data)} "{out}"'
            p=subprocess.run(['sh','-c',script],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(out.read_bytes(),data)
    @unittest.skipUnless(sys.platform.startswith('linux'),'actual Linux PID-stamped timeout worker requires /proc')
    def test_all_transfer_failure_points_are_bounded_and_leave_no_payload(self):
        for fault in ('dns','connect','header','body','truncate','wrong','hang','slowloris','reset'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as td:
                root=Path(td).resolve();b=root/'bin';b.mkdir();out=root/'payload';trace=root/'network-trace'
                code='''#!/usr/bin/env python3
import os,sys,time
from pathlib import Path
Path(os.environ['TRACE']).open('a').write('request\\n')
fault=os.environ['FAULT'];p=Path(sys.argv[sys.argv.index('-O')+1])
if fault in ('dns','connect','header'):sys.exit(1)
if fault in ('body','truncate','reset'):p.write_bytes(b'partial');sys.exit(1)
if fault=='wrong':p.write_bytes(b'Y'*64);sys.exit()
if fault=='hang':
 while True:time.sleep(.1)
if fault=='slowloris':
 with p.open('wb') as f:
  while True:f.write(b'x');f.flush();time.sleep(.4)
'''
                (b/'wget').write_text(code);(b/'wget').chmod(0o755)
                # Same timeout implementation, shorter fixture duration only.
                helper=root/'network.sh';helper.write_text((BASE/'lib/network.sh').read_text().replace('oem_bounded_run 15 sh -c','oem_bounded_run 1 sh -c'))
                script=f'. "{BASE}/lib/common.sh";. "{helper}";OEM_DOWNLOAD_URL=http://fixture.invalid;OEM_NETWORK_BUDGET_LEFT=30;oem_fetch_local payload '+hashlib.sha256(b'X'*64).hexdigest()+f' 64 "{out}"'
                env={'PATH':str(b)+':'+os.environ['PATH'],'TRACE':str(trace),'FAULT':fault,'LC_ALL':'C'}
                start=time.monotonic();p=subprocess.run(['sh','-c',script],env=env,capture_output=True,text=True,timeout=8)
                self.assertNotEqual(p.returncode,0);self.assertLess(time.monotonic()-start,7);self.assertFalse(out.exists());self.assertFalse((root/'payload.part').exists());self.assertEqual(trace.read_text().count('request'),2)
    def test_nonlinux_unavailable_watchdog_never_starts_download(self):
        if sys.platform.startswith('linux'):self.skipTest('Linux worker covered separately')
        p=subprocess.run(['sh','-c',f'. "{BASE}/lib/network.sh";oem_bounded_run 1 sh -c "exit 0"'],capture_output=True)
        self.assertNotEqual(p.returncode,0)

if __name__=='__main__':unittest.main()
