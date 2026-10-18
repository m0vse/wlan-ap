#!/usr/bin/env python3
"""Persist untrusted kernel netconsole datagrams immediately; never execute them."""
import argparse, base64, datetime, hashlib, json, os, select, signal, socket, time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--bind',required=True);p.add_argument('--port',type=int,default=6666);p.add_argument('--source',required=True);p.add_argument('--directory',type=Path,required=True);p.add_argument('--stale-seconds',type=int,default=90);a=p.parse_args()
os.umask(0o077);a.directory.mkdir(parents=True,exist_ok=True);a.directory.chmod(0o700)
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,1048576);s.bind((a.bind,a.port));s.setblocking(False)
running=True

def stop(*_):
 global running;running=False
for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,stop)
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def append(name,row):
 data=(json.dumps(row,separators=(',',':'))+'\n').encode();fd=os.open(a.directory/name,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
 try:
  view=memoryview(data)
  while view:
   n=os.write(fd,view);view=view[n:]
  os.fsync(fd)
 finally:os.close(fd)
 directory_fd=os.open(a.directory,os.O_RDONLY)
 try:os.fsync(directory_fd)
 finally:os.close(directory_fd)
started=utc();last=None;last_heartbeat=None;packets=0;dropped=0;digest=None;last_payload='';last_status=0
append('lifecycle.jsonl',{'at':started,'event':'started','pid':os.getpid(),'bind':a.bind,'port':a.port,'expected_source':a.source})
try:
 while running:
  ready,_,_=select.select([s],[],[],1)
  if ready:
   for _ in range(256):
    try:data,peer=s.recvfrom(65535)
    except BlockingIOError:break
    if peer[0]!=a.source:dropped+=1;continue
    stamp=utc();text=data.decode('utf-8','replace');digest=hashlib.sha256(data).hexdigest()
    append('kernel-'+stamp[:10]+'.jsonl',{'received_utc':stamp,'source':list(peer),'bytes':len(data),'sha256':digest,'payload_b64':base64.b64encode(data).decode(),'text':text})
    # Never acknowledge before the raw datagram has reached durable storage.
    if data.startswith(b'MIAMI_CAPTURE_RECORD v=1 '):
     header,sep,body=data.partition(b'\n')
     try:
      fields=dict(part.split('=',1) for part in header.decode('ascii').split()[1:])
      valid=bool(sep) and int(fields['bytes'])==len(body) and int(fields['lines'])==len(body.splitlines())
     except (ValueError,KeyError,UnicodeError):valid=False
     if valid:
      checksum=14695981039346656037
      for byte in data:checksum=((checksum^byte)*1099511628211)&0xffffffffffffffff
      s.sendto(('MIAMI_CAPTURE_SAVED %016x\n'%checksum).encode(),peer)
    packets+=1;last=time.monotonic();last_payload=text[-512:]
    if 'MIAMI_CAPTURE_HEARTBEAT 'in text:last_heartbeat=last
  now=time.monotonic()
  if now-last_status>=1:
   status={'updated_utc':utc(),'started_utc':started,'pid':os.getpid(),'running':True,'bind':a.bind,'port':a.port,'source':a.source,'packets_fsynced':packets,'rejected_sources':dropped,'last_packet_age_seconds':None if last is None else round(now-last,1),'heartbeat_age_seconds':None if last_heartbeat is None else round(now-last_heartbeat,1),'capture_healthy':last_heartbeat is not None and now-last_heartbeat<=a.stale_seconds,'last_sha256':digest,'last_payload_tail':last_payload,'coverage':'Kernel output reaches disk while this host/interface and AP wired path operate; heartbeat absence is a gap, not proof of health.'}
   tmp=a.directory/'status.tmp';tmp.write_text(json.dumps(status,indent=2)+'\n');os.replace(tmp,a.directory/'status.json');last_status=now
finally:
 append('lifecycle.jsonl',{'at':utc(),'event':'stopped','pid':os.getpid(),'packets_fsynced':packets})
 tmp=a.directory/'status.tmp';tmp.write_text(json.dumps({'updated_utc':utc(),'pid':os.getpid(),'running':False,'capture_healthy':False,'reason':'receiver_stopped'},indent=2)+'\n');os.replace(tmp,a.directory/'status.json');s.close()
