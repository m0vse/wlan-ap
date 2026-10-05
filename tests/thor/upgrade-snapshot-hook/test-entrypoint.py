#!/usr/bin/env python3
from pathlib import Path
import os,sys,json,subprocess,tempfile,hashlib
root=Path(sys.argv[1]).resolve();fixed=Path(sys.argv[2]).resolve();work=Path(tempfile.mkdtemp(prefix="thor-hook-regression."));bins=work/"bin";bins.mkdir()
q=["/usr/bin/qemu-aarch64","-L",str(root),str(root/"bin/busybox")]
for app in ["ls","awk","find","cp","chmod","sha256sum","tar","head","hexdump","cat","mktemp","mkdir","mv","rm","wc","sed"]:
 p=bins/app;p.write_text("#!/bin/sh\nexec "+" ".join(q)+" "+app+" \"$@\"\n");p.chmod(0o755)
ubi=work/"ubi/ubi9";ubi.mkdir(parents=True);(ubi/"mtd_num").write_text("0\n");dev=work/"dev";dev.mkdir();(dev/"ubi9_4").write_bytes(bytes.fromhex("ffffffff"));runtime=work/"runtime";runtime.mkdir();(runtime/"gateway.json").write_text("{}\n");boot=work/"bootid";boot.write_text("12345678-1234-1234-1234-123456789abc\n");core=work/"core";core.write_text("")
helper=root/"lib/upgrade/cambium-ab-certificates.sh";writer=root/"lib/upgrade/cambium-ab.sh";old=root/"lib/upgrade/platform.sh"
assert "ab_certificate_export" not in old.read_text();assert "ab_certificate_export" in fixed.read_text()
env={**os.environ,"PATH":str(bins)+":/usr/bin:/bin","CAMBIUM_AB_LIB":str(core),"CAMBIUM_AB_CERTIFICATE_LIB":str(helper),"AB_CERTIFICATE_OWNER":str(os.getuid()),"AB_ENV":"thor","AB_CERTIFICATE_LEBS":"20","AB_LEB":"126976","AB_LAYOUT":"banks","AB_FAMILY":"thor","AB_MODEL":"XV3-8","AB_SKU":"00000013","AB_ACTIVE":"0","AB_TARGET":"1","AB_ACTIVE_MTD":"0","AB_TARGET_MTD":"1","AB_ACTIVE_UBI":"ubi9","AB_UBI_SYS":str(work/"ubi"),"AB_DEV":str(dev),"AB_CERTIFICATE_STORE":str(work/"store"),"AB_CERTIFICATE_RUNTIME":str(runtime),"AB_BOOT_ID":str(boot),"AB_CERTIFICATE_ARCHIVE":str(work/"archive"),"AB_CERTIFICATE_DESCRIPTOR":str(work/"descriptor")}
functions="ab_family(){ return 0; }; board_name(){ echo cambiumnetworks,xv3-8; }; ab_identity(){ return 0; }; ab_ubi_volume(){ echo ubi9_4; }; ab_certificate_lebs(){ echo 20; }; ab_fail(){ echo FAILURE:$* >&2; return 1; };\n"
cases=[]
def run(name,platform,tail,expected,extra="",use_writer=False,override={}):
 script=". "+str(writer if use_writer else helper)+"\n. "+str(platform)+"\n"+functions+extra+"platform_pre_upgrade image\n"+tail
 p=subprocess.run(q+["ash","-c",script],env={**env,**override},capture_output=True,text=True);assert p.returncode==expected,(name,p.returncode,p.stdout,p.stderr);cases.append({"name":name,"returncode":p.returncode,"output":p.stdout.strip(),"error":p.stderr.strip()});return p
p=run("old-hook-missing-snapshot-real-guard",old,"ab_certificate_validate_snapshot\n",1);assert "missing or unsafe RAM-stage certificate snapshot" in p.stderr
run("corrected-hook-real-export-and-validation",fixed,"ab_certificate_validate_snapshot\n",0)
p=run("export-failure-exits-before-pivot",fixed,"echo PIVOT_MUST_NOT_RUN\n",1,"ab_certificate_export(){ return 1; };\n");assert "PIVOT_MUST_NOT_RUN" not in p.stdout
p=run("generic-platform-preserved",fixed,"echo GENERIC_PRESERVED\n",0,"ab_family(){ return 1; }; ab_certificate_export(){ echo FORBIDDEN_EXPORT; return 99; };\n");assert "FORBIDDEN_EXPORT" not in p.stdout
boundary="ab_upgrade_preflight(){ return 0; }; ab_image_extract(){ return 0; }; ab_setenv_batch(){ echo ENV_WRITE_BOUNDARY_STOPPED; return 99; };\n"
paths={"AB_CERTIFICATE_ARCHIVE":str(work/"writer-archive"),"AB_CERTIFICATE_DESCRIPTOR":str(work/"writer-descriptor")}
p=run("old-entrypoint-writer-refuses-before-write",old,"cambium_ab_do_upgrade image\n",1,boundary,True,paths);assert "ENV_WRITE_BOUNDARY_STOPPED" not in p.stdout
registration="case \" $RAMFS_COPY_DATA \" in *\" $AB_CERTIFICATE_ARCHIVE $AB_CERTIFICATE_DESCRIPTOR\"*) echo RAMFS_SNAPSHOT_REGISTERED;; *) exit 88;; esac\ncambium_ab_do_upgrade image\n"
p=run("fixed-entrypoint-RAM-registration-and-writer-boundary",fixed,registration,1,boundary,True,paths);assert "RAMFS_SNAPSHOT_REGISTERED" in p.stdout and "ENV_WRITE_BOUNDARY_STOPPED" in p.stdout
report={"passed":True,"count":len(cases),"cases":cases,"fixture":str(work),"input_hashes":{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [old,fixed,helper,writer,root/"bin/busybox"]},"scope":"Actual target BusyBox/platform/exporter/snapshot validation and actual writer pre-write branch; synthetic files and isolated identity/image predicates, mocked first ENV-write boundary; no AP/flash/mount/service/build actions."};(work/"receipt.json").write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
