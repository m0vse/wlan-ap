import os
import pathlib,tempfile,subprocess,json
src=pathlib.Path(os.environ['NATIVE_FIRSTBOOT_SOURCE_DIR']);work=pathlib.Path(tempfile.mkdtemp(prefix='firstboot-services.'));core=work/'core';system=work/'system';system.write_text('');helper=work/'helper';log=work/'log';helper.write_text('#!/bin/sh\necho "$*" >> "'+str(log)+'"\n');helper.chmod(0o700)
boot=(src/'ucentral-installer-boot').read_text().replace('/lib/functions/cambium-ab.sh',str(core)).replace('/lib/functions/system.sh',str(system)).replace('/usr/libexec/ucentral-installer-identity',str(helper));script=work/'boot';script.write_text(boot)
cases=[]
def run(name,body,op,expected):
 if body is None:core.unlink(missing_ok=True)
 else:core.write_text(body)
 log.unlink(missing_ok=True);p=subprocess.run(['sh',str(script),op],capture_output=True);assert p.returncode==expected,(name,p.stderr);cases.append(name);return log.read_text() if log.exists() else ''
for op in ['prepare','check','pending']:assert run('non-Cambium-'+op,None,op,int(op=='pending'))==''
for op in ['prepare','check','pending']:assert run('unsupported-family-'+op,'ab_family(){ return 1; }\n',op,int(op=='pending'))==''
def fixture(target='',job='',image='',active='1'):
 return 'ab_family(){ AB_ENV=sage; }; ab_identity(){ AB_ACTIVE='+active+'; }; ab_getenv(){ case "$1" in *_target) echo "'+target+'";; *_job) echo "'+job+'";; *_image) echo "'+image+'";; esac; };\n'
for op in ['prepare','check','pending']:assert run('normal-no-pending-'+op,fixture(),op,int(op=='pending'))==''
for op in ['prepare','check','pending']:assert run('fallback-'+op,fixture('0','b'*64,'a'*64),op,int(op=='pending'))==''
assert run('pending-stages-only',fixture('1','b'*64,'a'*64),'prepare',0).startswith('prepare-settings ')
assert run('pending-check',fixture('1','b'*64,'a'*64),'check',0).startswith('check-settings ')
assert run('malformed-pending-refused',fixture('1','bad','a'*64),'prepare',1)==''
# Actual cloud init function with external service boundaries stubbed.
cloud=(src/'cloud_discover.init').read_text();cloud=cloud[cloud.index('service_triggers()'):];cloud=cloud.replace('/usr/libexec/ucentral-installer-boot','fixture_boot').replace('[ -e /tmp/ucentral-network.ready ]','true').replace('[ -f /etc/ucentral/capabilities.json ]','true')
for pending,ready,label in [(False,True,'normal-cloud-service'),(True,False,'pending-enrollment-worker'),(True,True,'enrolled-cloud-service')]:
 shim='fixture_boot(){ case "$1" in pending) return '+str(0 if pending else 1)+';; check) return '+str(0 if ready else 1)+';; esac; }; procd_open_instance(){ echo "instance:$*"; }; procd_set_param(){ echo "param:$*"; }; procd_close_instance(){ :; }; est_client(){ return 0; }; PROG=/usr/bin/cloud_discovery;\n'
 p=subprocess.run(['sh','-c',shim+cloud+'\nstart_service'],capture_output=True,text=True);assert p.returncode==0,p.stderr
 expected='/usr/libexec/ucentral-installer-firstboot' if pending and not ready else '/usr/bin/cloud_discovery';assert expected in p.stdout,(label,p.stdout);cases.append(label)
report={'passed':True,'cases':cases,'scope':'Actual boot/cloud init shell with isolated hardware/env/helper/procd boundaries; no AP/services changed.'};(src/'service-regressions.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
