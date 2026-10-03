#!/usr/bin/env python3
"""Run only inside a fresh Linux network namespace; uses no AP/network services."""
import atexit, json, os, pathlib, signal, socket, struct, subprocess, time

base = pathlib.Path('/home/phil/openwifi-cheetah-build/dhcp-wire-test')
source = pathlib.Path('/home/phil/openwifi-cheetah-build/wlan-ap')
client = base / 'busybox-1.37.0/busybox'
ucode = source / 'openwrt/staging_dir/hostpkg/bin/ucode'
run = base / ('run-' + str(os.getpid()))
run.mkdir()
def ip(*args):
    subprocess.run(['/usr/sbin/ip', *args], check=True)
ip('link', 'set', 'lo', 'up')
ip('link', 'add', 'testwan', 'type', 'veth', 'peer', 'name', 'testsrv')
holder = subprocess.Popen(['/usr/bin/unshare', '--net', '--', '/bin/sleep', '300'])
def cleanup():
    holder.terminate()
    holder.wait()
atexit.register(cleanup)
deadline = time.monotonic()+3
while os.readlink('/proc/'+str(holder.pid)+'/ns/net') == os.readlink('/proc/self/ns/net'):
    if time.monotonic()>deadline: raise TimeoutError('client namespace creation')
    time.sleep(.02)
ip('link', 'set', 'testwan', 'netns', str(holder.pid))
for device in ['testwan', 'lo']:
    subprocess.run(['/usr/bin/nsenter','-t',str(holder.pid),'--net','--','/usr/sbin/ip','link','set',device,'up'],check=True)
ip('link', 'set', 'testsrv', 'up')
ip('addr', 'add', '10.231.0.1/24', 'dev', 'testsrv')
server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
server.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, b'testsrv\0')
server.bind(('', 67))
server.settimeout(.2)

def options(data):
    result = {}
    offset = 240
    while offset < len(data):
        tag = data[offset]; offset += 1
        if tag == 255: break
        if tag == 0: continue
        size = data[offset]; offset += 1
        result[tag] = data[offset:offset+size]; offset += size
    return result

def reply(request, kind, hint, legacy):
    header = bytearray(236)
    header[:4] = bytes([2, request[1], request[2], 0])
    header[4:8] = request[4:8]
    header[10:12] = request[10:12]
    header[12:16] = request[12:16]
    header[16:20] = socket.inet_aton('10.231.0.10')
    header[20:24] = socket.inet_aton('10.231.0.1')
    header[28:44] = request[28:44]
    fields = [(53, bytes([kind])), (54, socket.inet_aton('10.231.0.1')),
              (51, struct.pack('!I', 120)), (1, socket.inet_aton('255.255.255.0'))]
    if hint is not None: fields.append((224, hint.encode()))
    if legacy: fields.append((138, socket.inet_aton('192.0.2.1')))
    payload = header + b'\x63\x82\x53\x63' + b''.join(bytes([tag, len(value)]) + value for tag,value in fields) + b'\xff'
    destination = socket.inet_ntoa(request[12:16]) if request[12:16] != b'\0'*4 else '255.255.255.255'
    server.sendto(payload, (destination, 68))

def fixture(name):
    root = run / name
    for path in ['tmp', 'etc/ucentral', 'etc/udhcpc.user.d']:
        (root/path).mkdir(parents=True)
    files = source/'feeds/tip/cloud_discovery/files'
    (root/'discovery_policy.uc').write_bytes((files/'usr/share/ucentral/discovery_policy.uc').read_bytes())
    (root/'etc/ucentral/discovery-policy.json').write_bytes((files/'etc/ucentral/discovery-policy.json').read_bytes())
    helper = (files/'usr/share/ucentral/cloud_discovery.uc').read_text()
    helper = helper.replace('/tmp/', str(root/'tmp')+'/').replace('/etc/', str(root/'etc')+'/').replace("from 'ubus'", "from './ubus.uc'")
    (root/'helper.uc').write_text(helper)
    (root/'ubus.uc').write_text("import * as fs from 'fs'; export function connect() { return { call: function() { fs.writefile('"+str(root/'tmp/renew-called')+"', 'yes'); } }; };\n")
    script = (source/'openwrt/package/network/config/netifd/files/lib/netifd/dhcp.script').read_text()
    script = script.replace('/lib/functions.sh', str(root/'stubs.sh')).replace('/lib/netifd/netifd-proto.sh', str(root/'stubs.sh'))
    script = script.replace('/tmp/', str(root/'tmp')+'/').replace('/etc/', str(root/'etc')+'/')
    (root/'event.sh').write_text(script); (root/'event.sh').chmod(0o755)
    (root/'stubs.sh').write_text('''proto_init_update() { state=$2; }
proto_add_ipv4_address() { /usr/sbin/ip addr replace "$1/24" dev testwan; }
proto_send_update() { [ "$state" != 0 ] || /usr/sbin/ip addr flush dev testwan; :; }
ipcalc() { NETWORK=10.231.0.0; }
proto_add_ipv4_route() { :; }
proto_add_dns_server() { :; }
proto_add_dns_search() { :; }
proto_add_data() { :; }
proto_close_data() { :; }
json_add_string() { :; }
json_add_int() { :; }
''')
    (root/'etc/udhcpc.user').write_text('"'+str(ucode)+'" "'+str(root/'helper.uc')+'" "$1"\nenv > "'+str(root/'tmp')+'/event-$1.env"\n')
    return root

results=[]
for name,hint,legacy,renew in [('approved','openwifi.shinesystems.co.uk:15002',False,True),
                             ('both','openwifi.shinesystems.co.uk:15002',True,False),
                             ('absent',None,False,False),
                             ('malformed','https://bad.example/path',False,False),
                             ('unapproved','other.example:15002',False,False)]:
    root=fixture(name)
    log=open(root/'client.log','w')
    env=dict(os.environ, INTERFACE='wire-test', IFACE6RD='0')
    proc=subprocess.Popen(['/usr/bin/nsenter','-t',str(holder.pid),'--net','--',str(client),'udhcpc','-f','-B','-i','testwan','-s',str(root/'event.sh'),'-t','3','-T','1','-n','-O','224','-O','138'],stdout=log,stderr=log,env=env)
    seen_prl=False; stage='bound'; renewed=False; deconfig_retains_cloud=None; deadline=time.monotonic()+15
    try:
        while time.monotonic()<deadline:
            event=root/'tmp'/('event-'+stage+'.env')
            if event.exists():
                cloud=json.loads((root/'tmp/cloud.json').read_text())
                assert cloud['dhcp_server']=='openwifi.shinesystems.co.uk' and cloud['dhcp_port']==15002 and cloud['no_validation'] is False, cloud
                if stage=='bound':
                    decoded=event.read_text()
                    if hint is not None: assert 'opt224='+hint+'\n' in decoded, decoded
                    else: assert not (root/'tmp/dhcp-option-224').exists()
                    if legacy: assert 'opt138=192.0.2.1\n' in decoded
                    assert seen_prl, 'option224 missing from actual DHCP request PRL'
                    if renew:
                        stage='renew'; hint=None; os.kill(proc.pid,signal.SIGUSR1); continue
                else:
                    assert not (root/'tmp/dhcp-option-224').exists(), 'stale option224 persisted'
                    assert (root/'tmp/renew-called').exists(), 'renew did not notify discovery'
                    renewed=True
                    event=root/'tmp/event-deconfig.env'
                    event.unlink(missing_ok=True)
                    (root/'tmp/renew-called').unlink(missing_ok=True)
                    os.kill(proc.pid,signal.SIGUSR2)
                    until=time.monotonic()+3
                    while not event.exists():
                        if time.monotonic()>until: raise TimeoutError('actual release/deconfig event')
                        time.sleep(.02)
                    assert not (root/'tmp/dhcp-option-224').exists()
                    retained=json.loads((root/'tmp/cloud.json').read_text())
                    deconfig_retains_cloud=retained.get('lease') is True
                    assert retained.get('lease') is False, retained
                    assert 'dhcp_server' not in retained and 'dhcp_port' not in retained, retained
                    assert (root/'tmp/renew-called').exists(), 'deconfig did not notify discovery'
                results.append({'case':name,'request_prl_224':True,'bound':True,'renew_absent_reset':renewed,'deconfig_retains_cloud_lease':deconfig_retains_cloud})
                break
            if proc.poll() is not None: raise RuntimeError((root/'client.log').read_text())
            try: packet,_=server.recvfrom(2048)
            except socket.timeout: continue
            opts=options(packet)
            if 224 in opts.get(55,b''): seen_prl=True
            kind=opts.get(53,b'\0')[0]
            if kind==1: reply(packet,2,hint,legacy)
            elif kind==3: reply(packet,5,hint,legacy)
        else: raise TimeoutError(name+' '+(root/'client.log').read_text())
    finally:
        proc.terminate()
        try: proc.wait(timeout=3)
        except subprocess.TimeoutExpired: proc.kill(); proc.wait()
        log.close()
report={'cases':results,'fixture':str(run),'actual_patched_client':True,'actual_dhcp_event_script':True,'network_namespace_only':True,'netifd_bus_stubbed':True,'gateway_tls_or_ap_hardware_test':False,'deconfig_acceptance':not any(r['deconfig_retains_cloud_lease'] for r in results)}
(run/'report.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
