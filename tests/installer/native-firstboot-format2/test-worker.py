from pathlib import Path
import tempfile,subprocess,json,os,time
base=Path(os.environ['NATIVE_FIRSTBOOT_SOURCE_DIR']);w=Path(tempfile.mkdtemp(prefix='firstboot-worker.'));bin=w/'bin';bin.mkdir();log=w/'log';pending=w/'pending';network=w/'network';clock=w/'clock';count=w/'count'
boot=bin/'boot';boot.write_text('#!/bin/sh\n[ -f '+str(pending)+' ]\n');boot.chmod(0o700)
identity=bin/'identity';identity.write_text('#!/bin/sh\necho enroll >> '+str(log)+'\nn=$(cat '+str(count)+' 2>/dev/null || echo 0); n=$((n+1)); echo $n > '+str(count)+'\n[ $n -ge 2 ]\n');identity.chmod(0o700)
sleep=bin/'sleep';sleep.write_text('#!/bin/sh\n[ "$1" != 5 ] || { echo wait >> '+str(log)+'; touch '+str(network)+' '+str(clock)+'; }\n');sleep.chmod(0o700)
for name in ['ucentral','cloud_discover']:
 p=bin/name;p.write_text('#!/bin/sh\necho '+name+' >> '+str(log)+'\n');p.chmod(0o700)
s=(base/'ucentral-installer-firstboot').read_text().replace('/usr/libexec/ucentral-installer-boot',str(boot)).replace('/usr/libexec/ucentral-installer-identity',str(identity)).replace('/tmp/ucentral-network.ready',str(network)).replace('/tmp/ntp.set',str(clock)).replace('/etc/init.d/ucentral',str(bin/'ucentral')).replace('/etc/init.d/cloud_discover',str(bin/'cloud_discover'));script=w/'script';script.write_text(s);env=dict(os.environ,PATH=str(bin)+':'+os.environ['PATH'])
subprocess.run(['sh',str(script)],env=env,check=True,timeout=3);assert not log.exists()
pending.touch();subprocess.run(['sh',str(script)],env=env,check=True,timeout=3)
for i in range(20):
 rows=log.read_text().splitlines()
 if 'cloud_discover' in rows:break
 time.sleep(.01)
assert rows[:4]==['wait','enroll','wait','enroll'],rows;assert rows.count('ucentral')==1 and rows.count('cloud_discover')==1,rows
r={'passed':True,'cases':['no-pending-no-enrollment-or-restarts','network-clock-gate','failed-enrollment-retries','services-restart-only-on-success'],'scope':'Actual worker shell; readiness/enrollment/procd boundaries isolated, no services changed.'};(base/'worker-regressions.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
