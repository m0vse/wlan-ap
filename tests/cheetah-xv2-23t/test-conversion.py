from pathlib import Path
import subprocess,argparse,tempfile,os
p=argparse.ArgumentParser();p.add_argument('--sdk',required=True,type=Path);a=p.parse_args();base=a.sdk/'package/cambium';core=base/'cambium-ab/files/cambium-ab.sh';converter=base/'cambium-ab/files/cambium-ab-convert';module=base/'cambium-cheetah-support/files';count=0
with tempfile.TemporaryDirectory(prefix='23t-conversion-no-write-') as td:
 d=Path(td);system=d/'system.sh';system.write_text('board_name() { echo "$TEST_BOARD"; }; logger() { :; }\n')
 lib=d/'ab.sh';lib.write_text('. '+repr(str(core))+'''\nab_family() { ab_board "$TEST_BOARD"; }
ab_identity() { [ "${TEST_BAD_IDENTITY:-0}" = 0 ]; }
ab_converted() { return 1; }
ab_mtd_writable() { echo writable-gate >> "$TEST_TRACE"; return 1; }
''');upgrade=d/'upgrade.sh';upgrade.write_text(':\n')
 cases=[('xv2-21x',False,True,['--yes']),('xv2-23t',False,True,['--yes']),('xv2-22h',False,False,['--yes']),('unknown',False,False,['--yes']),('xv2-23t',True,False,['--yes']),('xv2-23t',False,False,[]),('xv2-23t',False,False,['--allow-untested','--yes'])]
 for i,(model,bad,admitted,args) in enumerate(cases):
  trace=d/('trace'+str(i));env={**os.environ,'CAMBIUM_SYSTEM_FUNCTIONS':str(system),'CAMBIUM_AB_LIB':str(lib),'CAMBIUM_AB_UPGRADE_LIB':str(upgrade),'CAMBIUM_AB_MODULES':str(module),'TEST_BOARD':'cambiumnetworks,'+model,'TEST_BAD_IDENTITY':str(int(bad)),'TEST_TRACE':str(trace),'AB_CONVERSION_SUPPORTED':'1'}
  r=subprocess.run(['sh',str(converter),*args],env=env,capture_output=True,text=True);assert r.returncode!=0,'Every fixture stops before write';assert trace.exists()==admitted,(model,bad,args,r.stdout,r.stderr);count+=1
 # Inspect the actual board table through the actual shared dispatch: no false qualification.
 command='. "$1"; ab_board cambiumnetworks,xv2-23t; printf "%s:%s:%s:%s" "$AB_QUALIFIED" "$AB_CONVERSION_SUPPORTED" "$AB_SKU" "$AB_FIT"; ab_board cambiumnetworks,xv2-22h; printf ":%s" "$AB_CONVERSION_SUPPORTED"'
 r=subprocess.check_output(['sh','-c',command,'sh',str(core)],env={**os.environ,'CAMBIUM_AB_MODULES':str(module)},text=True);assert r=='0:1:00000024:config@mp03.3-lynx:0',r;count+=1
 print('Actual converter/board policy: '+str(count)+' cases PASS;23T enabled, qualification pending, neighbouring model and bad identity refused; no writes')
