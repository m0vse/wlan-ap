# SPDX-License-Identifier: BSD-3-Clause
from pathlib import Path
import tempfile,socket,subprocess,time,json,signal,base64,sys
receiver=Path(__file__).resolve().parents[2]/'contrib/cambium/miami/diagnostics/receiver.py'
with tempfile.TemporaryDirectory()as t:
 d=Path(t);sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
 p=subprocess.Popen([sys.executable,str(receiver),'--bind','127.0.0.1','--source','127.0.0.1','--port',str(port),'--directory',str(d),'--stale-seconds','2'])
 try:
  for _ in range(40):
   if(d/'status.json').exists():break
   time.sleep(.05)
  assert not json.loads((d/'status.json').read_text())['capture_healthy']
  s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);payload=b'<3>MIAMI_CAPTURE_HEARTBEAT boot=synthetic\n\x00\xff';s.sendto(payload,('127.0.0.1',port));time.sleep(1.3)
  status=json.loads((d/'status.json').read_text());assert status['capture_healthy'] and status['packets_fsynced']==1
  rows=[json.loads(l)for f in d.glob('kernel-*.jsonl')for l in f.read_text().splitlines()];assert len(rows)==1 and base64.b64decode(rows[0]['payload_b64'])==payload
  body=b'MIAMI_NAND_BEGIN synthetic=1\n'+b''.join(('MIAMI_NAND_REG i=%d value=00000000\n'%i).encode() for i in range(14))+b'MIAMI_NAND_END synthetic=1\n'
  packet=('MIAMI_CAPTURE_RECORD v=1 boot=test nonce=abc seq=1 bytes=%d lines=%d synthetic=1\n'%(len(body),len(body.splitlines()))).encode()+body
  checksum=14695981039346656037
  for byte in packet:checksum=((checksum^byte)*1099511628211)&0xffffffffffffffff
  s.settimeout(2)
  for attempt in range(2):
   s.sendto(packet,('127.0.0.1',port));ack,_=s.recvfrom(256)
   assert ack==('MIAMI_CAPTURE_SAVED %016x\n'%checksum).encode()
   # Receipt must imply exact bytes are already visible on disk, including duplicates.
   saved=[json.loads(l)for f in d.glob('kernel-*.jsonl')for l in f.read_text().splitlines()]
   assert sum(base64.b64decode(r['payload_b64'])==packet for r in saved)==attempt+1
  s.sendto(packet.replace(b'bytes=',b'wrong='),('127.0.0.1',port));s.settimeout(.2)
  try:s.recvfrom(256);raise AssertionError('malformed record acknowledged')
  except socket.timeout:pass
  time.sleep(2.3);assert not json.loads((d/'status.json').read_text())['capture_healthy']
 finally:p.send_signal(signal.SIGTERM);p.wait(timeout=5)
 assert not json.loads((d/'status.json').read_text())['running']
 print('PASS receiver: exact binary datagram preserved and fsynced, no healthy state before heartbeat, stale-gap detection and clean-stop status')
