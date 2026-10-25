#!/usr/bin/env python3
"""Execute qualified QPIC driver functions with a scheduled DMA/cache backend.

No hardware is accessed. Channel ordering is intentionally unconstrained; this
checks software invariants, not whether this ordering occurs on physical QPIC.
Use --expect-unsafe for the released negative control. Issued timeout containment
is explicitly reported separately and remains a release-blocking limitation.
"""
import argparse, pathlib, re, subprocess, tempfile, sys
p=argparse.ArgumentParser()
p.add_argument('--driver',type=pathlib.Path,required=True)
p.add_argument('--expect-unsafe',action='store_true')
p.add_argument('--require-timeout-contained',action='store_true')
p.add_argument('--provider',type=pathlib.Path)
p.add_argument('--driver-core',type=pathlib.Path)
p.add_argument('--virt-dma',type=pathlib.Path)
a=p.parse_args();s=a.driver.read_text()
if 'static int miami_bounce_sg(' in s:
    if a.expect_unsafe:
        p.error('--expect-unsafe is for the released/scoped negative controls, not the isolated candidate')
    folder=pathlib.Path(__file__).parent
    if a.require_timeout_contained:
        if not all((a.provider,a.driver_core,a.virt_dma)):
            p.error('strict candidate gate requires --provider, --driver-core and --virt-dma; caller-only tests cannot satisfy it')
        command=[sys.executable,str(folder/'test-timeout-containment.py'),'--driver',str(a.driver),
                 '--provider',str(a.provider),'--driver-core',str(a.driver_core),'--virt-dma',str(a.virt_dma)]
    else:
        command=[sys.executable,str(folder/'test-bounce-ownership.py'),'--driver',str(a.driver)]
    subprocess.run(command,check=True)
    sys.exit(0)
def function(name):
    m=re.search(r'^static\s+(?:int|void|bool)\s*\n?'+name+r'\([^;]*?\)\s*\{',s,re.M)
    assert m,name
    b=s.index('{',m.start());e=b+1;depth=1
    while depth:depth+=(s[e]=='{')-(s[e]=='}');e+=1
    return s[m.start():e]
def structure(name):
    b=s.index('struct '+name+' {');e=s.index('\n};',b)+3
    return s[b:e]
names=['qpic_bam_dma_done','prepare_bam_async_desc','submit_descs','free_descs',
       'check_flash_errors','qcom_nandc_read_cw_raw','check_for_erased_page',
       'parse_read_errors','read_page_ecc']
if 'static int __prepare_bam_async_desc(' in s:
    names.insert(1,'__prepare_bam_async_desc')
pre=pathlib.Path(__file__).with_name('dma-ownership-fixture.c').read_text()
pre=pre.replace('/* ACTUAL_STRUCTURES */', structure('bam_transaction')+'\n'+structure('desc_info'))
pre=pre.replace('/* ACTUAL_FUNCTIONS */','\n\n'.join(function(n) for n in names))
with tempfile.TemporaryDirectory() as d:
    c=pathlib.Path(d)/'ownership.c';exe=pathlib.Path(d)/'ownership';c.write_text(pre)
    subprocess.run(['cc','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror',
                    '-Wno-unused-function','-Wno-unused-variable','-Wno-sign-compare',
                    '-fsanitize=address,undefined','-o',str(exe),str(c)],check=True)
    subprocess.run([str(exe),str(int(a.expect_unsafe)),str(int(a.require_timeout_contained))],check=True)
