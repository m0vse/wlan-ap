# SPDX-License-Identifier: BSD-3-Clause
import socket,subprocess,threading,tempfile,pathlib,time,os,sys
binary=sys.argv[1]
with tempfile.TemporaryDirectory() as temp:
 fixture=pathlib.Path(temp)/'fixture';body=b'MIAMI_NAND_BEGIN synthetic=1\n'+b''.join(('MIAMI_NAND_REG i=%d\n'%i).encode() for i in range(14))+b'MIAMI_NAND_END\n';fixture.write_bytes(body)
 for mode in ('drop-first-datagram','drop-first-receipt','no-receipts'):
  sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.bind(('127.0.0.1',0));sock.settimeout(.2);saved=[];packets=[];done=threading.Event()
  def receive():
   while not done.is_set():
    try:data,peer=sock.recvfrom(8192)
    except socket.timeout:continue
    packets.append(data)
    if mode=='drop-first-datagram' and len(packets)==1:continue
    with open(pathlib.Path(temp)/mode,'ab',buffering=0) as f:f.write(data);os.fsync(f.fileno())
    saved.append(data)
    if mode=='no-receipts' or (mode=='drop-first-receipt' and len(saved)==1):continue
    checksum=14695981039346656037
    for byte in data:checksum=((checksum^byte)*1099511628211)&0xffffffffffffffff
    sock.sendto(('MIAMI_CAPTURE_SAVED %016x\n'%checksum).encode(),peer)
  thread=threading.Thread(target=receive);thread.start()
  p=subprocess.run([binary,'--self-test',str(fixture),'abc','127.0.0.1',str(sock.getsockname()[1])],capture_output=True,timeout=6)
  done.set();thread.join();sock.close()
  assert p.returncode==(1 if mode=='no-receipts' else 0),(mode,p.returncode,p.stderr)
  assert len(packets)==(3 if mode=='no-receipts' else 2),(mode,len(packets))
  assert all(x.split(b'\n',1)[1]==body for x in saved)
  print('PASS',mode,'packets',len(packets),'exact saved copies',len(saved),'exit',p.returncode)
