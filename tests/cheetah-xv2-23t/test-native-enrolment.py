from pathlib import Path
import argparse,tempfile,subprocess,os,json,shutil
p=argparse.ArgumentParser();p.add_argument('--repo',required=True,type=Path);p.add_argument('--runtime',required=True,type=Path);p.add_argument('--old-identity',type=Path);a=p.parse_args();repo=a.repo.resolve();runtime=a.runtime.resolve()
with tempfile.TemporaryDirectory(prefix='cheetah-native-enrolment-') as td:
 work=Path(td);closure=work/'closure';subprocess.run(['python3',str(repo/'tests/installer/native-firstboot-format2/stage-source.py'),str(repo),str(closure)],check=True)
 wrapper=work/'ucode';wrapper.write_text('#!/bin/sh\nexec /usr/bin/qemu-aarch64 -L '+str(runtime)+' '+str(runtime/'usr/bin/ucode')+' -L '+str(runtime/'usr/lib/ucode')+' "$@"\n');wrapper.chmod(0o700)
 template=(repo/'tests/installer/native-firstboot-format2/test-native-firstboot.py').read_text().replace('/usr/bin/qemu-arm','/usr/bin/qemu-aarch64').replace('AB_ENV=sage; AB_LAYOUT=pair;','AB_ENV=cheetah; AB_LAYOUT=banks; AB_CERTIFICATE_LEBS=20;')
 env={**os.environ,'NATIVE_FIRSTBOOT_SOURCE_DIR':str(closure),'NATIVE_TEST_ROOT':str(runtime),'NATIVE_TEST_UCODE':str(wrapper),'PYTHONDONTWRITEBYTECODE':'1'}
 records=[]
 for model in ['XV2-21X','XV2-23T']:
  body=template.replace('\\tsage\\tE410\\t','\\tcheetah\\t'+model+'\\t').replace("'family':'sage','model':'E410'","'family':'cheetah','model':"+repr(model))
  script=work/(model+'.py');script.write_text(body);r=subprocess.run(['python3',str(script)],env=env,text=True,capture_output=True,timeout=180);assert r.returncode==0,(model,r.stdout[-2000:],r.stderr[-2000:]);result=json.loads(r.stdout.strip().splitlines()[-1]);assert result['passed'] and len(result['cases'])==28;records.append({'model':model,'native_est_enrollment_renewal_cases':28,'passed':True});print(model,'native FORMAT2/EST28 PASS',flush=True)
 if a.old_identity:
  shutil.copy2(a.old_identity,closure/'ucentral-installer-identity');r=subprocess.run(['python3',str(work/'XV2-23T.py')],env=env,text=True,capture_output=True,timeout=60);assert r.returncode!=0 and 'Invalid hardware identity binding' in r.stderr,(r.stdout[-500:],r.stderr[-1000:]);print('Old21X-only validator negative:23T binding refused before enrolment PASS',flush=True)
 print(json.dumps({'passed':True,'tests':records,'old_negative_control':bool(a.old_identity),'scope':'Real target ARM64 ucode/curl and native EST with isolated synthetic issuer, key, CSR, local transport and private filesystem; no AP or production CA actions'}))
