#!/usr/bin/env python3
"""Actual Jaguar native boot components; ENV backend only, no devices/writers."""
from pathlib import Path
import json
import os
import subprocess
import tempfile
import unittest

HERE=Path(__file__).resolve().parents[1]
class BootTests(unittest.TestCase):
 def invoke(self,model,sku,slot,fault=''):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);state=root/'state';state.write_text(json.dumps(dict(image=str(slot),bootcmd='bootipq',factory_mac='bca993000002')))
   script=r'''
. "$HERE/lib/common.sh"; . "$HERE/adapters/jaguar.sh"
OEM_JAGUAR_ENV_CONFIG=$STATE
fw_printenv() {
 python3 -c 'import json,os,sys;s=json.load(open(os.environ["STATE"]));print("".join(k+"="+v+"\n" for k,v in s.items()),end="")'
}
fw_setenv() {
 python3 - "$@" <<'PY'
import json,os,sys
from pathlib import Path
p=Path(os.environ['STATE']);s=json.loads(p.read_text());args=sys.argv[3:];fault=os.environ['FAULT']
if args[0]=='-s':
 label='SOURCE' if 'jaguar-source.' in args[1] else 'ARM'
 with open(os.environ['LOG'],'a') as out:out.write(label+'\n')
 if fault==label:sys.exit(1)
 for row in Path(args[1]).read_text().splitlines():
  key,value=row.split(' ',1);s[key]=value
 if fault=='source-readback' and label=='SOURCE':s['jaguar_storage_pending']='bad'
 if fault=='arm-readback' and label=='ARM':s['jaguar_ab_target']='bad'
 if fault.startswith('metadata-') and label=='ARM':s['jaguar_installer_'+fault.removeprefix('metadata-')]='bad'
else:
 with open(os.environ['LOG'],'a') as out:out.write('SELECTOR\n')
 if fault=='SELECTOR':sys.exit(1)
 s[args[0]]=args[1]
p.write_text(json.dumps(s))
PY
}
sync() { [ "$FAULT" != sync ]; }
oem_jaguar_before_select() {
 [ "$FAULT" != protected ] || return 1
 case "$FAULT" in
  late-*) python3 -c 'import json,os;p=os.environ["STATE"];s=json.load(open(p));s["jaguar_installer_"+os.environ["FAULT"].removeprefix("late-")]="bad";open(p,"w").write(json.dumps(s))';;
 esac
}
OEM_JAGUAR_JOURNAL="install:$OEM_SOURCE_SLOT:$OEM_TARGET_SLOT:$(printf '%064d' 1):$(printf '%064d' 2)"
OEM_JAGUAR_IMAGE_PIN=$(printf '%064d' 1);OW_EXPECT_JOB=$(printf '%064d' 2)
oem_jaguar_persist_source "$OEM_JAGUAR_JOURNAL" || exit 1
printf 'WRITER\n' >> "$LOG"
oem_jaguar_arm
'''
   env=dict(os.environ,HERE=str(HERE),STATE=str(state),LOG=str(root/'log'),FAULT=fault,OEM_FAMILY='jaguar',OEM_MODEL=model,OEM_SKU=sku,OEM_SERIAL='bca993000002',OEM_SOURCE_RELEASE='7.2-r1',OEM_SUPPORTED_RELEASE='7.2-r1',OEM_SOURCE_SLOT=str(slot),OEM_TARGET_SLOT=str(1-slot))
   result=subprocess.run(['sh','-c',script],env=env,capture_output=True,text=True)
   return result,json.loads(state.read_text()),(root/'log').read_text().splitlines() if (root/'log').exists() else []
 def test_three_models_two_slots_source_saved_before_writer_one_shot_final(self):
  for model,sku,fit in (('XV2-2','00000014','config@cp01-c1'),('XV2-2T1','0000001f','config@cp01-c1-2'),('XE3-4','00000020','config@cp01-c3-xv3-4')):
   for slot in (0,1):
    result,state,events=self.invoke(model,sku,slot)
    self.assertEqual(result.returncode,0,result.stderr)
    self.assertEqual(events,['SOURCE','WRITER','ARM','SELECTOR'])
    self.assertEqual(state[f'jaguar_boot{slot}'],f'setenv image {slot}; bootipq')
    self.assertIn('#'+fit,state[f'jaguar_boot{1-slot}'])
    self.assertEqual(state['image'],str(slot));self.assertEqual(state['factory_mac'],'bca993000002')
    self.assertIn(f'saveenv && run jaguar_boot{1-slot}; run jaguar_boot{slot}',state['bootcmd'])
 def test_failed_persistence_or_metadata_never_activates_candidate(self):
  for slot in (0,1):
   for fault in ('SOURCE','source-readback','sync','ARM','arm-readback','metadata-target','metadata-job','metadata-image','late-target','late-job','late-image','protected','SELECTOR'):
    result,state,events=self.invoke('XV2-2T1','0000001f',slot,fault)
    self.assertNotEqual(result.returncode,0)
    self.assertIn(state['bootcmd'],('bootipq',f'run jaguar_boot{slot}'))
    if fault in ('SOURCE','source-readback','sync'):self.assertNotIn('WRITER',events)
 def test_unsupported_or_mismatched_model_never_writes_env(self):
  for model,sku in (('XV2-2T0','00000016'),('XE3-4TN','00000021'),('XV2-2','0000001f')):
   result,state,events=self.invoke(model,sku,0)
   self.assertNotEqual(result.returncode,0);self.assertEqual(events,[])

if __name__=='__main__':unittest.main()
