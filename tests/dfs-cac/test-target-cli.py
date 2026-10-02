#!/usr/bin/env python3
"""Actual archived target CLI against private fake global Unix socket."""
import json,os,pathlib,socket,subprocess,tempfile,threading
root=pathlib.Path(os.environ['OW_DFS_TARGET_ROOT'])
qemu=os.environ['OW_DFS_QEMU']
work=pathlib.Path(tempfile.mkdtemp(prefix='cac-target-global-status.'))
sock=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM);sock.bind(str(work/'global'));os.chmod(work/'global',0o600)
requests=[]
response='state=DFS\nphy=phy0\ncac_time_seconds=600\ncac_time_left_seconds=480\nbss[0]=wlan0\nssid[0]=Shine Systems\n'
def serve():
 for _ in range(2):
  data,peer=sock.recvfrom(8192);requests.append(data.decode())
  sock.sendto((response if data==b'IFNAME=wlan0 STATUS' else 'FAIL-NO-IFNAME-MATCH\n').encode(),peer)
thread=threading.Thread(target=serve,daemon=True);thread.start()
cases=[]
for name,expected in [('wlan0','state=DFS'),('nonexistent','FAIL-NO-IFNAME-MATCH')]:
 p=subprocess.run(['/usr/bin/timeout','-s','KILL','4',qemu,'-L',str(root),str(root/'usr/sbin/hostapd_cli'),'-p',str(work),'-i','global','raw','IFNAME='+name,'STATUS'],capture_output=True,text=True)
 assert p.returncode==0,(name,p.returncode,p.stderr)
 assert expected in p.stdout,(name,p.stdout,p.stderr)
 cases.append({'interface':name,'passed':True})
thread.join(timeout=2);assert not thread.is_alive();sock.close()
assert requests==['IFNAME=wlan0 STATUS','IFNAME=nonexistent STATUS'],requests
print(json.dumps({'passed':True,'count':len(cases),'cases':cases,'root':str(root),'requests':requests,
 'scope':'Actual archived target hostapd_cli/ELF loader through QEMU exchanges STATUS-only commands with a private fake Unix datagram global socket. Not a live/pre-BSS hostapd runtime acceptance test.'},indent=2))
