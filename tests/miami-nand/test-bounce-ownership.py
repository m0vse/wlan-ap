#!/usr/bin/env python3
"""Execute actual QPIC client bounce paths with scheduled DMA/cache operations.

No hardware is accessed. Channel ordering is intentionally unconstrained; this
checks software invariants, not whether this ordering occurs on physical QPIC.
This tests caller-alias isolation, not the separate resource-owner removal
contract. Provider/resource teardown must pass independent integration tests.
"""
import argparse, pathlib, re, subprocess, tempfile
p=argparse.ArgumentParser()
p.add_argument('--driver',type=pathlib.Path,required=True)
p.add_argument('--expect-unsafe',action='store_true')
p.add_argument('--require-no-caller-alias',action='store_true')
p.add_argument('--expect-bounce-failure',action='store_true')
a=p.parse_args();s=a.driver.read_text()
if a.expect_bounce_failure:
    good='sg_set_buf(&sgl[i], copy->bounce, copy->length);'
    assert s.count(good)==1
    s=s.replace(good,'sg_set_buf(&sgl[i], copy->original, copy->length);')
def function(name):
    m=re.search(r'^static\s+(?:inline\s+)?(?:int|void|bool|u32|uint8_t|ssize_t)\s*\n?'+name+r'\([^;]*?\)\s*\{',s,re.M)
    assert m,name
    b=s.index('{',m.start());e=b+1;depth=1
    while depth:depth+=(s[e]=='{')-(s[e]=='}');e+=1
    return s[m.start():e]
def structure(name):
    b=s.index('struct '+name+' {');e=s.index('\n};',b)+3
    return s[b:e]
names=['miami_io_blocked','miami_dma_reserve','miami_dma_release','miami_bounce_sg',
       'qpic_bam_dma_done','prepare_bam_async_desc','submit_descs','free_descs',
       'check_flash_errors','qcom_nandc_read_cw_raw','check_for_erased_page',
       'parse_read_errors','read_page_ecc','qcom_nandc_block_bad']
if 'static int __prepare_bam_async_desc(' in s:
    names.insert(5,'__prepare_bam_async_desc')
pre=pathlib.Path(__file__).with_name('bounce-ownership-fixture.c').read_text()
pre=pre.replace('/* ACTUAL_STRUCTURES */', structure('bam_transaction')+'\n'+structure('miami_dma_copy')+'\n'+structure('desc_info'))
pre=pre.replace('/* ACTUAL_FUNCTIONS */','\n\n'.join(function(n) for n in names))
# Compile the exact poisoned early-return prefix of public ingress callbacks.
# Code after the gate is intentionally not synthesized as an implementation:
# an abort sentinel proves none of those bodies can be entered after poison.
ingress=['qcom_nandc_read_page','qcom_nandc_read_page_raw','qcom_nandc_read_oob',
         'qcom_nandc_write_page','qcom_nandc_write_page_raw','qcom_nandc_write_oob',
         'qcom_nandc_block_bad','qcom_nandc_block_markbad','qcom_nandc_command',
         'qcom_nandc_read_byte','qcom_nandc_read_buf','qcom_nandc_write_buf',
         'qcom_serial_get_feature','qcom_serial_set_feature',
         'clear_read_regs','clear_bam_transaction','pre_command','post_command']
prefixes=[]
for name in ingress:
    text=function(name)
    gate=text.index('if (miami_io_blocked(')
    condition=text.index('(',gate);end_condition=condition+1;depth=1
    while depth:
        depth+=(text[end_condition]=='(')-(text[end_condition]==')');end_condition+=1
    if text[end_condition:].lstrip().startswith('{'):
        brace=text.index('{',end_condition);e=brace+1;depth=1
        while depth:depth+=(text[e]=='{')-(text[e]=='}');e+=1
    else:
        e=text.index(';',gate)+1
    prefix=text[:e]+'\n abort();\n}'
    prefix=re.sub(r'\b'+name+r'\(', 'entry_'+name+'(', prefix, count=1)
    prefixes.append(prefix)
pre=pre.replace('/* ACTUAL_INGRESS */','\n\n'.join(prefixes))
with tempfile.TemporaryDirectory() as d:
    c=pathlib.Path(d)/'ownership.c';exe=pathlib.Path(d)/'ownership';c.write_text(pre)
    # Host fixture only: compact mock statements trigger GCC indentation warnings.
    # Target compiler flags and runtime safety assertions remain unchanged.
    subprocess.run(['cc','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror',
                    '-Wno-unused-function','-Wno-unused-variable','-Wno-unused-parameter','-Wno-sign-compare','-Wno-misleading-indentation',
                    '-fsanitize=address,undefined','-o',str(exe),str(c)],check=True)
    command=[str(exe),str(int(a.expect_unsafe)),str(int(a.require_no_caller_alias))]
    if a.expect_bounce_failure:
        result=subprocess.run(command,capture_output=True,text=True)
        assert result.returncode!=0 and 'host.chip.data[i]==0' in result.stderr, (result.stdout,result.stderr)
        print('PASS negative control: original caller SG alias rejected before copy-back boundary')
    else:
        subprocess.run(command,check=True)
