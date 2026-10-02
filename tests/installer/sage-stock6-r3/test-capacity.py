"""Focused actual Sage functions; synthetic UBI boundaries, no AP writes."""
import json, os, pathlib, subprocess, sys, tempfile
base=pathlib.Path(sys.argv[1]).resolve(); work=pathlib.Path(tempfile.mkdtemp(prefix='sage-capacity.'))
cases=['stock-free1','reverse-bank','floor285-free20','insufficient','same-bank','mounted-target','block-target','wrong-id','wrong-type','short-overlay','clear-fails','resize-fails']
results=[]
for case in cases:
 d=work/case; (d/'sys/ubi0').mkdir(parents=True); (d/'block').mkdir(); (d/'dev').mkdir()
 target=0 if case=='reverse-bank' else 1; active=1-target; rid=target*2+1
 if case=='wrong-id':rid=2
 r=f'ubi0_{rid}'; ov='ubi0_5'; (d/'sys'/r).mkdir(); (d/'sys'/ov).mkdir()
 roots=285 if case=='floor285-free20' else 304 if case=='insufficient' else 305
 free=20 if case=='floor285-free20' else 0 if case=='insufficient' else 1
 for p,value in {'ubi0/mtd_num':11,'ubi0/eraseblock_size':126976,'ubi0/avail_eraseblocks':free,f'{r}/reserved_ebs':roots,f'{r}/usable_eb_size':126976,f'{r}/type':'static' if case=='wrong-type' else 'dynamic',f'{ov}/reserved_ebs':66 if case=='short-overlay' else 67}.items(): (d/'sys'/p).write_text(str(value)+'\n')
 (d/'mounts').write_text(f'{d}/dev/{r} /busy ubifs rw 0 0\n' if case=='mounted-target' else '')
 if case=='block-target':(d/'block'/f'ubiblock0_{rid}').touch()
 env=dict(os.environ,CAMBIUM_SAGE_LIB=str(base/'bundle/cambium-sage.sh'),AB_UBI_SYS=str(d/'sys'),AB_PROC_MOUNTS=str(d/'mounts'),AB_BLOCK_SYS=str(d/'block'),AB_DEV=str(d/'dev'),CASE=case,ROOTVOL=r,LOG=str(d/'calls'),ACTIVE=str(active),TARGET=str(target))
 driver='''
. "$1"
AB_ACTIVE=$ACTIVE; AB_TARGET=$TARGET; AB_ACTIVE_UBI=ubi0; AB_LEB=126976
AB_FAMILY=sage; AB_LAYOUT=pair; AB_ACTIVE_MTD=11; AB_TARGET_MTD=11; SAVE_CONFIG=0
[ "$CASE" != same-bank ] || AB_TARGET=$AB_ACTIVE
ab_ubi_volume() { case "$2" in rootfs[01]) echo "$ROOTVOL";; rootfs_data[01]) echo ubi0_5;; *) return 1;; esac; }
ab_step() { shift; "$@"; }
ab_ubi_node() { :; }
ubiupdatevol() { echo "clear $*" >> "$LOG"; [ "$CASE" != clear-fails ]; }
ubirsvol() { echo "resize $*" >> "$LOG"; [ "$CASE" != resize-fails ]; }
ab_sage_certificate_capacity || exit 2
. "$2"
sage_stock_store_check || exit 4
ab_sage_prepare_overlay || exit 3
'''
 run=subprocess.run(['sh','-c',driver,'fixture',str(base/'cambium-ab-sage.sh'),str(base/'bundle/stock-store-check.sh')],env=env,capture_output=True,text=True)
 expected=case in ('stock-free1','reverse-bank','floor285-free20')
 assert (run.returncode==0)==expected,(case,run.returncode,run.stderr)
 log=(d/'calls').read_text() if (d/'calls').exists() else ''
 if case in ('stock-free1','reverse-bank'):
  assert log.splitlines()==[f'clear -t {d}/dev/{r}',f'resize {d}/dev/ubi0 -n {rid} -s {285*126976}'],log
 elif case=='clear-fails':assert len(log.splitlines())==1
 elif case=='resize-fails':assert len(log.splitlines())==2
 else:assert not log,(case,log)
 assert 'nvram' not in log and 'rootfs_data' not in log
 results.append({'case':case,'passed':True,'calls':log.splitlines()})
print(json.dumps({'passed':True,'cases':results,'scope':'Actual capacity and inactive prepare functions; synthetic UBI commands. No hardware trial.'},indent=2))
