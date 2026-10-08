from pathlib import Path
import subprocess, socket, struct, json, time, os

# This program must run only inside a new network namespace.
assert os.readlink('/proc/self/ns/net') != os.readlink('/proc/1/ns/net')
def run(*args): subprocess.run(args, check=True, stdout=subprocess.DEVNULL)
run('ip','link','set','lo','up')
run('ip','link','add','eth0','type','veth','peer','name','wire0')
run('ip','link','add','name','up','type','bridge','vlan_filtering','1','vlan_default_pvid','0')
run('ip','link','set','eth0','master','up')
run('bridge','vlan','add','dev','eth0','vid','4090','pvid','untagged')
run('bridge','vlan','add','dev','up','vid','4090','self')
run('ip','link','add','link','up','name','up0v0','type','vlan','id','4090')
for name in ('up','eth0','wire0','up0v0'): run('ip','link','set','dev',name,'up')
def mac(name):
    data=json.loads(subprocess.check_output(['ip','-j','link','show',name]))[0]
    return bytes.fromhex(data['address'].replace(':',''))
src=mac('wire0'); dst=b'\xff'*6
def checksum(data):
    total=sum(struct.unpack('!%dH'%(len(data)//2), data))
    while total>>16: total=(total&65535)+(total>>16)
    return (~total)&65535
def frame(xid,vid=None):
    bootp=struct.pack('!BBBBIHH4s4s4s4s16s64s128s',2,1,6,0,xid,0,0,b'\0'*4,socket.inet_aton('198.18.0.2'),socket.inet_aton('198.18.0.1'),b'\0'*4,src+b'\0'*10,b'\0'*64,b'\0'*128)
    bootp+=b'\x63\x82\x53\x63\x35\x01\x05\x36\x04'+socket.inet_aton('198.18.0.1')+b'\xff'
    udp=struct.pack('!HHHH',67,68,len(bootp)+8,0)+bootp
    ip=struct.pack('!BBHHHBBH4s4s',0x45,0,len(udp)+20,0,0,64,17,0,socket.inet_aton('198.18.0.1'),b'\xff'*4)
    ip=ip[:10]+struct.pack('!H',checksum(ip))+ip[12:]
    eth=dst+src+(struct.pack('!HHH',0x8100,vid,0x0800) if vid is not None else struct.pack('!H',0x0800))
    return eth+ip+udp
rx=socket.socket(socket.AF_PACKET,socket.SOCK_RAW,socket.htons(0x0800));rx.bind(('up0v0',0));rx.settimeout(0.2)
tx=socket.socket(socket.AF_PACKET,socket.SOCK_RAW);tx.bind(('wire0',0))
tx.send(frame(1))
data=rx.recv(2048);assert struct.unpack_from('!I',data,14+20+8+4)[0]==1
sent=0
for n in range(4096):
    tx.send(frame(0x80000000+n,101))
    if n%256==0: tx.send(frame(0x1000+sent));sent+=1
received=[]
while True:
    try: data=rx.recv(2048)
    except TimeoutError: break
    received.append(struct.unpack_from('!I',data,14+20+8+4)[0])
assert len(received)==sent and all(0x1000<=x<0x1000+sent for x in received),received
report={'passed':True,'scope':'isolated Linux veth/bridge/8021q namespace, same renderer internal VLAN4090 untagged/PVID topology; not AP/PPE/NSS or DHCP-client hardware acceptance','tagged_vlan101_frames_sent':4096,'tagged_frames_at_management_device':0,'untagged_dhcp_replies_received':sent+1}
print(json.dumps(report))
