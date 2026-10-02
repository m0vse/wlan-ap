"""Existing XE3 FIT/capacity extractor; immutable image, no flash boundaries."""
import hashlib,json,os,pathlib,subprocess,sys,tempfile
bundle=pathlib.Path(sys.argv[1]).resolve();work=pathlib.Path(tempfile.mkdtemp(prefix='xe34-fit-smoke.'));cases=[]
image=bundle/'cambium_xe3-4-jaguar-2026.10.02.3-sysupgrade.bin'
assert hashlib.sha256(image.read_bytes()).hexdigest()=='9237bac70039fbdaffbb013018dd9c6c9328830e0a4f8f4babe375fd4044821d'
for name,change,expected in [('XE3-FIT96MiB','',True),('wrong-FIT','AB_FIT=config@unqualified',False),('insufficient-bank','AB_BANK_LEBS=1',False)]:
 env=dict(os.environ,CAMBIUM_AB_MODULES=str(bundle/'modules'),CAMBIUM_AB_LIB=str(bundle/'cambium-ab.sh'),CAMBIUM_AB_CERTIFICATE_LIB=str(bundle/'cambium-ab-certificates.sh'),AB_WORK=str(work/name))
 script=' . "$1/cambium-ab-upgrade.sh"; AB_FAMILY=jaguar; AB_LAYOUT=banks; AB_ROOT_MAGIC=hsqs; ab_jaguar_board cambiumnetworks,xe3-4; test "$AB_QUALIFIED:$AB_SKU:$AB_BANK_SIZE:$AB_FIT" = "1:00000020:06000000:config@cp01-c3-xv3-4" || exit 99; '+change+'; ab_image_extract "$2"' if change else ' . "$1/cambium-ab-upgrade.sh"; AB_FAMILY=jaguar; AB_LAYOUT=banks; AB_ROOT_MAGIC=hsqs; ab_jaguar_board cambiumnetworks,xe3-4; test "$AB_QUALIFIED:$AB_SKU:$AB_BANK_SIZE:$AB_FIT" = "1:00000020:06000000:config@cp01-c3-xv3-4" || exit 99; ab_image_extract "$2"'
 result=subprocess.run(['sh','-c',script,'fixture',str(bundle),str(image)],env=env,capture_output=True,text=True)
 assert (result.returncode==0)==expected,(name,result.stdout,result.stderr)
 cases.append({'case':name,'accepted':expected,'passed':True})
assert hashlib.sha256(image.read_bytes()).hexdigest()=='9237bac70039fbdaffbb013018dd9c6c9328830e0a4f8f4babe375fd4044821d'
print(json.dumps({'passed':True,'count':len(cases),'cases':cases,'scope':'Actual current XE3 family selection and FIT/root/capacity extractor on immutable .3; host POSIX utilities, no bank writes/mounts/AP action.'},indent=2))
