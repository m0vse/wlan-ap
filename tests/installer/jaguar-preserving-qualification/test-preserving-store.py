#!/usr/bin/env python3
"""Actual preserving-store preflight, private geometry/mount fixtures only."""
import hashlib,json,os,pathlib,subprocess,sys,tempfile
bundle=pathlib.Path(sys.argv[1]);work=pathlib.Path(tempfile.mkdtemp(prefix='preserving-store-tests.'));cases=[]
for name in ('valid-mounted','named-mounted','wrong-layout','wrong-mtd','missing-volume','short-volume','wrong-geometry','wrong-device','wrong-type','duplicate-mount','unmounted','symlink-store','symlink-content'):
 root=work/name;store=root/'store';store.mkdir(parents=True)
 sysfs=root/'sys';(sysfs/'ubi0').mkdir(parents=True);(sysfs/'ubi0_4').mkdir()
 (sysfs/'ubi0/mtd_num').write_text('1' if name=='wrong-mtd' else '0')
 (sysfs/'ubi0_4/reserved_ebs').write_text('19' if name=='short-volume' else '20')
 (sysfs/'ubi0_4/usable_eb_size').write_text('131072' if name=='wrong-geometry' else '126976')
 if name=='symlink-store':
  store=root/'linked';store.symlink_to(root/'store')
 if name=='symlink-content':(store/'key.pem').symlink_to('/etc/passwd')
 device='ubi0:certificates' if name=='named-mounted' else '/fixture-dev/ubi1_4' if name=='wrong-device' else '/fixture-dev/ubi0_4'
 mounts=root/'mounts';record=device+' '+str(store)+' '+('squashfs' if name=='wrong-type' else 'ubifs')+' rw 0 0\n'
 mounts.write_text('' if name=='unmounted' else record*2 if name=='duplicate-mount' else record)
 driver='''set -eu
. "$1/cambium-ab-certificates.sh"
. "$1/preservation-check.sh"
AB_LAYOUT=$TEST_LAYOUT; AB_ACTIVE_UBI=ubi0; AB_ACTIVE_MTD=0; AB_LEB=126976; AB_DEV=/fixture-dev
ab_certificate_lebs() { echo 20; }
ab_ubi_volume() { [ "$TEST_CASE" != missing-volume ] && echo ubi0_4; }
jaguar_mounted_store_check
'''
 env=dict(os.environ,AB_UBI_SYS=str(sysfs),AB_PROC_MOUNTS=str(mounts),AB_CERTIFICATE_STORE=str(store),TEST_LAYOUT='pair' if name=='wrong-layout' else 'banks',TEST_CASE=name)
 p=subprocess.run(['sh','-c',driver,'fixture',str(bundle)],env=env,capture_output=True,text=True)
 expected=name in ('valid-mounted','named-mounted')
 assert (p.returncode==0)==expected,(name,p.stderr)
 cases.append({'case':name,'passed':True,'accepted':expected})
print(json.dumps({'passed':True,'count':len(cases),'cases':cases,'helper_sha256':hashlib.sha256((bundle/'preservation-check.sh').read_bytes()).hexdigest(),
 'scope':'Actual preserving-store preflight with private sysfs/mount-table/filesystem fixtures. No AP, mount, UBI, bank or environment operations.'},indent=2))
