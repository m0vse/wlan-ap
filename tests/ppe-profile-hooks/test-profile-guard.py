from pathlib import Path
import subprocess,tempfile,json,sys,hashlib
source=Path(sys.argv[1]);text=source.read_text()
definitions=text[text.index('ifdef CONFIG_TARGET_PROFILE'):text.index('\nEXTRA_CFLAGS')]
hooks=text[text.index('ifneq ($(strip $(TARGET_PROFILE)),)'):text.index('\n$(eval $(call KernelPackage')]
cases=[]
with tempfile.TemporaryDirectory(prefix='ppe-profile-guard-review.') as t:
 path=Path(t)/'Makefile';path.write_text(definitions+'\n'+hooks+'\nall:\n\t@echo hooks=$(Hooks/Prepare/Post)\n\t@echo patch=$(PATCH_PROFILE_NAME)\n\t@echo files=$(FILES_PROFILE_NAME)\n')
 for label,value in [('absent',None),('empty',''),('quoted-empty','""'),('qualified-profile','"DEVICE_cambiumnetworks_miami"')]:
  args=['make','-s','-f',str(path)]
  if value is not None:args.append('CONFIG_TARGET_PROFILE='+value)
  out=subprocess.check_output(args,text=True)
  if label=='qualified-profile':assert 'hooks=patch_profile files_profile' in out and 'patch=patches-cambiumnetworks_miami' in out and 'files=files-cambiumnetworks_miami' in out,out
  else:assert 'hooks=\n' in out,out
  cases.append({'case':label,'passed':True})
print(json.dumps({'passed':True,'count':len(cases),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'cases':cases,'scope':'Exact GNU make profile definitions and hook guard only; no package patch execution, build or AP action.'}))
