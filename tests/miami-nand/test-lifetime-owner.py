#!/usr/bin/env python3
"""Execute actual independent-owner, platform cleanup, remove and late IRQ paths.

The mock device/devres backend models resource ownership and reference lifetimes;
it does not claim physical stop, hardware reset, or IOMMU support.
"""
from pathlib import Path
import argparse,re,subprocess,tempfile
p=argparse.ArgumentParser();p.add_argument('--provider',type=Path,required=True);p.add_argument('--client',type=Path,required=True);p.add_argument('--cleanup','--driver-core',dest='cleanup',type=Path,required=True);a=p.parse_args()
s=a.provider.read_text();client=a.client.read_text()
def function(text,name):
 m=re.search(r'^(?:static )?(?:void|int|bool|irqreturn_t) (?:__maybe_unused )?'+name+r'\([^;]*?\)\s*\{',text,re.M);assert m,name
 b=text.index('{',m.start());d=1;e=b+1
 while d:d+=(text[e]=='{')-(text[e]=='}');e+=1
 return text[m.start():e]
start=s.index('struct qcom_qpic_lifetime {');end=s.index('struct bam_desc_hw {',start)
actual=s[start:end]
actual=re.sub(r'EXPORT_SYMBOL_GPL\([^;]+;','',actual)
fixture=Path(__file__).with_name('lifetime-owner-fixture.c').read_text()
fixture=fixture.replace('/* ACTUAL_OWNER */',actual)
fixture=fixture.replace('/* ACTUAL_REMOVAL */',function(a.cleanup.read_text(),'device_unbind_cleanup')+'\n'+function(s,'bam_alloc_chan')+'\n'+function(s,'bam_free_chan')+'\n'+function(s,'bam_dma_remove')+'\n'+function(client,'qcom_nandc_remove')+'\n'+function(s,'bam_dma_irq')+'\n'+function(s,'bam_dma_runtime_suspend')+'\n'+function(s,'bam_dma_runtime_resume')+'\n'+function(s,'qpic_bam_unpin_clock'))
with tempfile.TemporaryDirectory() as d:
 c=Path(d)/'owner.c';exe=Path(d)/'owner';c.write_text(fixture)
 subprocess.run(['cc','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-unused-parameter','-Wno-unused-variable','-Wno-misleading-indentation','-fsanitize=address,undefined','-pthread','-o',str(exe),str(c)],check=True)
 subprocess.run([str(exe)],check=True)
