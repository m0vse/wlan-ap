from pathlib import Path
import subprocess
import tempfile
import re
import sys

w=Path('/home/phil/openwifi-gambit-build/wlan-ap')
t=Path(tempfile.mkdtemp(prefix='gambit-component-',dir='/tmp'))
root=Path(sys.argv[1]) if len(sys.argv)>1 else None
net_path=root/'usr/libexec/ucentral-network' if root else w/'feeds/ucentral/ucentral-schema/files/usr/libexec/ucentral-network'
net=net_path.read_text()
net=re.sub(r'/rom/etc/|/etc/|/tmp/|/usr/share/|/sbin/|/usr/bin/',lambda m:str(t)+m[0],net)
for d in ['etc/ucentral','etc/config-shadow','rom/etc/ucentral','tmp','usr/share/ucentral','sbin','usr/bin','bin']:
    (t/d).mkdir(parents=True,exist_ok=True)
for name in ['network','system','dhcp','firewall','dropbear','ucentral']:
    (t/'etc/config-shadow'/name).write_text('baseline\n')
(t/'etc/ucentral/platform').write_text('ap\n')
(t/'rom/etc/ucentral/ucentral.cfg.0000000001').write_text('{"uuid":1}')
for name,body in {
    'sbin/wifi':'exit 0',
    'usr/share/ucentral/capabilities.uc':f'echo \'{{"wifi":[]}}\' > {t}/etc/ucentral/capabilities.json',
    'bin/logger':'exit 0',
    'bin/jsonfilter':'if grep -q \'"uuid":1\' "$2"; then echo 1; else echo 42; fi',
    'usr/bin/ucode':f'''printf '%s\\n' "$3" > {t}/selected
if grep -q INVALID "$3"; then exit 1; fi
printf '%s\\n' validated > {t}/tmp/ucentral-network.ready''',
}.items():
    p=t/name;p.write_text('#!/bin/sh\n'+body+'\n');p.chmod(0o755)
(t/'network.sh').write_text(net)
active=t/'etc/ucentral/ucentral.active'
def run(ok,label):
    (t/'tmp/ucentral-network.ready').unlink(missing_ok=True)
    (t/'selected').unlink(missing_ok=True)
    r=subprocess.run(['sh',str(t/'network.sh')],env={'PATH':str(t/'bin')+':/usr/bin:/bin'},capture_output=True,text=True)
    assert (r.returncode==0)==ok,(label,r.stderr)
    assert (t/'tmp/ucentral-network.ready').exists()==ok,label
    print('PASS:',label)
run(True,'genuinely unconfigured selects ROM bootstrap')
assert (t/'selected').read_text().strip()==str(t/'rom/etc/ucentral/ucentral.cfg.0000000001')
active.unlink();active.write_text('{"uuid":1}')
run(True,'UUID1 selects ROM bootstrap')
active.write_text('{"uuid":42,"management_vlan":37}')
run(True,'saved managed document precedes factory profile')
assert (t/'selected').read_text().strip()==str(active)
active.write_text('')
run(False,'empty saved document fails closed')
active.unlink();active.symlink_to('missing.json')
run(False,'dangling saved document fails closed')
active.unlink();active.write_text('INVALID managed document')
run(False,'failed saved render fails closed and retains document')
assert active.read_text()=='INVALID managed document'
assert (t/'etc/ucentral/network-boot.failure').exists()

rtty_path=root/'etc/init.d/rtty' if root else w/'feeds/ucentral/rtty/files/rtty.init'
src=rtty_path.read_text().replace('. /lib/functions/network.sh',':')
src=src.replace('/etc/ucentral/',str(t/'etc/ucentral')+'/')
(t/'rtty.sh').write_text(src)
test=f'''#!/bin/sh
. {t}/rtty.sh
procd_open_instance() {{ echo launch >> {t}/rtty.calls; }}
procd_set_param() {{ printf '%s\\n' "$*" >> {t}/rtty.calls; }}
procd_append_param() {{ printf '%s\\n' "$*" >> {t}/rtty.calls; }}
procd_close_instance() {{ :; }}
enable=0 interface= id= host= ssl=1 timeout=0
start_rtty section 0 > {t}/rtty.disabled 2>&1
test ! -e {t}/rtty.calls && test ! -s {t}/rtty.disabled || exit 1
enable=1 host=test.invalid id=fixture
start_rtty section 0
grep -q 'cert.pem -k .*key.pem' {t}/rtty.calls || exit 1
touch {t}/etc/ucentral/operational.pem
start_rtty section 0
grep -q 'operational.pem -k .*key.pem' {t}/rtty.calls || exit 1
'''
(t/'rtty-test.sh').write_text(test)
subprocess.run(['sh',str(t/'rtty-test.sh')],check=True)
print('PASS: RTTY disabled clean, cert fallback, operational preference')
print('COMPONENT_TEST_ROOT='+str(t))

identity_path=root/'etc/uci-defaults/19_cambium_openwifi_identity' if root else w/'openwrt/package/cambium/cambium-gambit-support/files/19_cambium_openwifi_identity'
identity_dir=t/'identity'; identity_dir.mkdir()
for board in ['cambiumnetworks,e400','cambiumnetworks,e500','cambiumnetworks,e501s','cambiumnetworks,e502s']:
    compatible=identity_dir/'compatible'; compatible.unlink(missing_ok=True)
    subprocess.run(['sh',str(identity_path)],env={'PATH':'/usr/bin:/bin','UCENTRAL_DIR':str(identity_dir),'CAMBIUM_BOARD_NAME':board},check=True)
    assert compatible.exists()==(board=='cambiumnetworks,e400'),board
    if compatible.exists(): assert compatible.read_text().strip()=='cambium_e400'
print('PASS: controller compatible identity applies to E400 only')

led_path=root/'usr/libexec/ucentral-led.sh' if root else w/'feeds/ucentral/ucentral-client/files/usr/libexec/ucentral-led.sh'
led_src=led_path.read_text().replace('. /lib/functions.sh','board_name() { echo "$TEST_BOARD"; }\nuci() { echo "${TEST_LEDS_OFF:-0}"; }')
led_root=t/'leds'; led_root.mkdir()
led_src=led_src.replace('/sys/class/leds/',str(led_root)+'/')
led_script=t/'led-test.sh'; led_script.write_text(led_src)
for colour in ['green','amber']:
    (led_root/(colour+':status')).mkdir()
for state,disabled,want in [('on','0',('1','0')),('off','0',('0','1')),('on','1',('0','0')),('off','1',('0','0'))]:
    for colour in ['green','amber']:
        for entry in ['brightness','trigger']: (led_root/(colour+':status')/entry).write_text('before')
    subprocess.run(['sh',str(led_script),state],env={'PATH':'/usr/bin:/bin','TEST_BOARD':'cambiumnetworks,e400','TEST_LEDS_OFF':disabled},check=True)
    actual=tuple((led_root/(colour+':status')/'brightness').read_text().strip() for colour in ['green','amber'])
    assert actual==want,(state,disabled,actual,want)
    assert all((led_root/(colour+':status')/'trigger').read_text().strip()=='none' for colour in ['green','amber'])
print('PASS: E400 connected green, disconnected amber and global LEDs-off override')
