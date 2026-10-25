#!/usr/bin/env python3
"""Require native ownership tests to reject unsafe source mutations at runtime."""
import argparse,pathlib,re,subprocess,sys,tempfile
p=argparse.ArgumentParser();p.add_argument('--provider',type=pathlib.Path,required=True);p.add_argument('--client',type=pathlib.Path,required=True);p.add_argument('--driver-core',type=pathlib.Path,required=True);a=p.parse_args();s=a.provider.read_text();root=pathlib.Path(__file__).parent

def function(text,name):
 m=re.search(r'^(?:static )?(?:void|int|bool|irqreturn_t) '+name+r'\([^;]*?\)\s*\{',text,re.M);assert m,name
 b=text.index('{',m.start());d=1;e=b+1
 while d:d+=(text[e]=='{')-(text[e]=='}');e+=1
 return text[m.start():e]

def mutate(name,old,new):
 f=function(s,name);assert f.count(old)==1,(name,old)
 return s.replace(f,f.replace(old,new,1),1)
controls=[]
controls.append(('late-IRQ-MMIO',mutate('bam_dma_irq','\tif (qcom_qpic_lifetime_poisoned(bdev->lifetime))\n\t\treturn IRQ_HANDLED;',''), 'test-lifetime-owner.py'))
controls.append(('remove-live-provider',mutate('bam_dma_remove','\tif (qcom_qpic_lifetime_detach(bdev->lifetime)) {\n\t\tof_dma_controller_free(pdev->dev.of_node);\n\t\treturn 0;\n\t}', '\tqcom_qpic_lifetime_detach(bdev->lifetime);'), 'test-lifetime-owner.py'))
controls.append(('free-poisoned-callback',mutate('bam_dma_free_desc','\tif (qcom_qpic_lifetime_poisoned(to_bam_chan(vd->tx.chan)->bdev->lifetime))\n\t\treturn;',''), 'test-provider-budget.py'))
f=function(s,'qpic_lifetime_release');g=f.replace(' if (qcom_qpic_lifetime_detach(life))\n  return;',' qcom_qpic_lifetime_detach(life);')
g=g.replace(' if (qpic_poisoned || life->users) {\n  mutex_unlock(&qpic_lifetime_lock);\n  qcom_qpic_lifetime_poison(life);\n  return;\n }','')
assert f!=g;controls.append(('release-poisoned-owner',s.replace(f,g,1),'test-lifetime-owner.py'))
with tempfile.TemporaryDirectory() as d:
 for name,source,test in controls:
  path=pathlib.Path(d)/(name+'.c');path.write_text(source)
  cmd=[sys.executable,str(root/test),'--provider',str(path)]
  if test=='test-lifetime-owner.py':cmd+=['--client',str(a.client),'--driver-core',str(a.driver_core)]
  r=subprocess.run(cmd,text=True,capture_output=True)
  assert r.returncode!=0 and bool(re.search(r'Assertion.*failed|AddressSanitizer:',r.stderr)),(name,r.returncode,r.stdout,r.stderr)
  assert 'error: ' not in r.stderr,(name,'compile failure is not a runtime negative',r.stderr)
  print('PASS rejected unsafe source mutation at runtime:',name)
