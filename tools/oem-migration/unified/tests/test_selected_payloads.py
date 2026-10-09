"""Actual selected staging helper; disposable HTTP actor, no external network."""
from pathlib import Path
import hashlib,json,os,subprocess,tempfile,unittest

BASE=Path(__file__).resolve().parents[1]
MODELS=json.loads((BASE/'tests/models.json').read_text())
from test_unified import Fixture,seal


class SelectedPayloadTests(unittest.TestCase):
    def test_launcher_selects_before_prompt_and_rejects_source_before_fetch(self):
        for version,accepted in [('fixture-supported',True),('wrong-source',False)]:
            with tempfile.TemporaryDirectory() as td:
                root=Path(td).resolve();model=dict(MODELS[1],fixture_oem_version='fixture-supported');f=Fixture(root,model,True)
                data=b'selected firmware';source=root/'object';source.write_bytes(data)
                pin=hashlib.sha256(data).hexdigest()
                (f.release/'payload-map.tsv').write_text(f'E410\tinstall\tpayloads/E410/kernel.itb\tselected.itb\t{len(data)}\t{pin}\n')
                with (f.release/'lib/network.sh').open('a') as stream:stream.write('\noem_bounded_run(){ shift;"$@"; }\n')
                (f.bin/'wget').write_text(f'#!/bin/sh\nprintf "download\\n" >> "$TRACE"\ncp "{source}" "$3"\n');(f.bin/'wget').chmod(0o755)
                seal(f.release);f.env['FIXTURE_VERSION']=version
                result=f.run(check=True)
                self.assertEqual(result.returncode==0,accepted,result.stderr)
                trace=f.log.read_text().splitlines()
                self.assertEqual('download' in trace,accepted)
                if accepted:self.assertLess(trace.index('download'),trace.index('preflight'))
                self.assertTrue(f.unchanged());self.assertNotIn('Onboarding key:',result.stdout)

    def test_map_rejects_downloaded_code_traversal_and_duplicates(self):
        with tempfile.TemporaryDirectory() as td:
            plan=Path(td)/'map';pin='a'*64
            for name,remote in [('lib/unsafe.json','safe'),('payloads/E410/run.sh','safe'),('payloads/E410/../root.bin','safe'),('payloads/E410/root.bin','../escape')]:
                plan.write_text(f'E410\tinstall\t{name}\t{remote}\t1\t{pin}\n')
                result=subprocess.run(['sh','-c',f'. "{BASE}/lib/network.sh";oem_payload_map_check "{plan}"'],capture_output=True)
                self.assertNotEqual(result.returncode,0)
            row=f'E410\tinstall\tpayloads/E410/root.bin\troot.bin\t1\t{pin}\n';plan.write_text(row+row)
            self.assertNotEqual(subprocess.run(['sh','-c',f'. "{BASE}/lib/network.sh";oem_payload_map_check "{plan}"'],capture_output=True).returncode,0)

    def fixture(self,root):
        root=root.resolve();root.chmod(0o700)
        bundle=root/'bundle';bundle.mkdir(mode=0o700);server=root/'server';server.mkdir()
        rows=[]
        for model in MODELS:
            for op in ('install','restore','confirm'):
                data=(model['model']+op).encode();remote=f'{model["model"]}-{op}.bin'
                (server/remote).write_bytes(data)
                rows.append('\t'.join((model['model'],op,f'payloads/{model["model"]}/{op}.bin',remote,str(len(data)),hashlib.sha256(data).hexdigest()))+'\n')
        (bundle/'payload-map.tsv').write_text(''.join(rows));(bundle/'payload-map.tsv').chmod(0o600)
        (bundle/'SHA256SUMS').write_text(hashlib.sha256((bundle/'payload-map.tsv').read_bytes()).hexdigest()+'  payload-map.tsv\n')
        common=root/'common.sh';common.write_text((BASE/'lib/common.sh').read_text().replace('$3==0',f'$3=={os.getuid()}').replace('$1=="drwx------"','$1~/^drwx------@?$/').replace('$1=="-rw-------"','$1~/^-rw-------@?$/'))
        binary=root/'bin';binary.mkdir();wget=binary/'wget'
        wget.write_text('#!/bin/sh\nprintf "%s\\n" "$4" >> "$TRACE"\ncase "$FAULT" in dns) exit 1;; wrong) printf bad > "$3";; *) cp "$SERVER/${4##*/}" "$3";; esac\n');wget.chmod(0o755)
        return bundle,server,common,binary

    def run_stage(self,root,model,operation,fault='',repeat=False,tamper=False):
        bundle,server,common,binary=self.fixture(root)
        work=root/'work';work.mkdir(mode=0o700)
        script=f'. "{common}";. "{BASE}/lib/network.sh";OEM_BUNDLE="$BUNDLE";OEM_WORK="$WORK";OEM_MODEL="$MODEL";OEM_OPERATION="$OP";OEM_DOWNLOAD_URL=http://fixture.invalid;OEM_NETWORK_BUDGET_LEFT=600;'
        # Successful/failing deterministic transfers use the real fetch/hash/
        # aggregate helper; Linux process-budget faults have their own suite.
        script+='oem_bounded_run(){ shift;"$@"; };'
        if fault=='space':script+='df(){ printf "Filesystem 1024-blocks Used Available Capacity Mounted\\nfixture 1 1 0 100%% /\\n"; };'
        script+='oem_payload_stage "$OP" || exit 1;'
        if repeat:script+='rm -f "$SERVER"/*;oem_payload_stage "$OP" || exit 1;'
        if tamper:script+='printf corrupt > "$OEM_OBJECT_ROOT/payloads/$MODEL/$OP.bin";'
        script+='oem_payload_closure_check'
        trace=root/'trace';env=dict(os.environ,PATH=str(binary)+':'+os.environ['PATH'],BUNDLE=str(bundle),WORK=str(work),MODEL=model,OP=operation,SERVER=str(server),TRACE=str(trace),FAULT=fault)
        result=subprocess.run(['sh','-c',script],env=env,capture_output=True,text=True,timeout=10)
        calls=trace.read_text().splitlines() if trace.exists() else []
        return result,calls

    def test_every_exact_model_operation_fetches_only_its_objects(self):
        for model in MODELS:
            for op in ('install','restore','confirm'):
                with self.subTest(model=model['model'],op=op),tempfile.TemporaryDirectory() as td:
                    result,calls=self.run_stage(Path(td).resolve(),model['model'],op)
                    self.assertEqual(result.returncode,0,result.stderr)
                    self.assertEqual(calls,[f'http://fixture.invalid/{model["model"]}-{op}.bin'])

    def test_cached_server_loss_and_mutated_payload(self):
        for tamper in (False,True):
            with tempfile.TemporaryDirectory() as td:
                result,calls=self.run_stage(Path(td).resolve(),'E410','install',repeat=True,tamper=tamper)
                self.assertEqual(result.returncode==0,not tamper,result.stderr);self.assertEqual(len(calls),1)

    def test_self_contained_map_uses_pinned_local_objects_without_http(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td).resolve();bundle,server,common,binary=self.fixture(root)
            row=(bundle/'payload-map.tsv').read_text().splitlines()[3].split('\t')
            model,op,name,remote,size,pin=row;file=bundle/name;file.parent.mkdir(parents=True);file.write_bytes((server/remote).read_bytes());file.chmod(0o600)
            with (bundle/'SHA256SUMS').open('a') as out:out.write(pin+'  '+name+'\n')
            work=root/'work';work.mkdir(mode=0o700)
            script=f'. "{common}";. "{BASE}/lib/network.sh";OEM_BUNDLE="{bundle}";OEM_WORK="{work}";OEM_MODEL={model};OEM_OPERATION={op};OEM_NETWORK_BUDGET_LEFT=0;oem_payload_stage {op}'
            result=subprocess.run(['sh','-c',script],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);self.assertFalse((work/'cache').exists())

    def test_dns_hash_space_and_unsupported_selection_refuse(self):
        for fault,model in [('dns','E410'),('wrong','E410'),('space','E410'),('','UNKNOWN')]:
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as td:
                result,calls=self.run_stage(Path(td).resolve(),model,'install',fault=fault)
                self.assertNotEqual(result.returncode,0)
                self.assertEqual(len(calls),2 if fault in ('dns','wrong') else 0)


if __name__=='__main__':unittest.main()
