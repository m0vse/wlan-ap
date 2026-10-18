#!/usr/bin/env python3
"""Passive UART receive only: no bytes or modem-control commands are sent."""
import argparse,base64,datetime,fcntl,json,os,select,signal,termios,time,tty
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--device',required=True);p.add_argument('--directory',required=True,type=Path);a=p.parse_args();os.umask(0o077);a.directory.mkdir(parents=True,exist_ok=True)
fd=os.open(a.device,os.O_RDONLY|os.O_NOCTTY|os.O_NONBLOCK)
# Claim an otherwise unused adapter; never share a UART reader with a terminal.
fcntl.ioctl(fd,termios.TIOCEXCL)
settings=termios.tcgetattr(fd);tty.setraw(fd,termios.TCSANOW);settings=termios.tcgetattr(fd);settings[4]=settings[5]=termios.B115200
settings[2]|=termios.CLOCAL|termios.CREAD;settings[2]&=~(termios.HUPCL|getattr(termios,'CRTSCTS',0));termios.tcsetattr(fd,termios.TCSANOW,settings)
running=True

def stop(*_):
 global running;running=False
for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,stop)
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def append(name,row):
 data=(json.dumps(row,separators=(',',':'))+'\n').encode();out=os.open(a.directory/name,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
 try:
  view=memoryview(data)
  while view:n=os.write(out,view);view=view[n:]
  os.fsync(out)
 finally:os.close(out)
started=utc();count=total=0;last=None;heartbeat=None;laststatus=0;pending=b''
append('serial-lifecycle.jsonl',{'event':'started','at':started,'pid':os.getpid(),'device':a.device,'baud':115200,'receive_only':True})
try:
 while running:
  ready,_,_=select.select([fd],[],[],1)
  if ready:
   data=os.read(fd,65536)
   if not data:raise RuntimeError('serial disconnected')
   stamp=utc();append('serial-'+stamp[:10]+'.jsonl',{'received_utc':stamp,'bytes':len(data),'payload_b64':base64.b64encode(data).decode(),'text':data.decode('utf-8','replace')});count+=1;total+=len(data);last=time.monotonic()
   pending+=data
   while b'\n'in pending:
    line,pending=pending.split(b'\n',1)
    if b'MIAMI_CAPTURE_HEARTBEAT 'in line:heartbeat=time.monotonic()
   pending=pending[-8192:]
  now=time.monotonic()
  if now-laststatus>=1:
   status={'updated_utc':utc(),'started_utc':started,'running':True,'pid':os.getpid(),'device':a.device,'receive_only':True,'chunks_fsynced':count,'bytes_fsynced':total,'last_receive_age_seconds':None if last is None else round(now-last,1),'heartbeat_age_seconds':None if heartbeat is None else round(now-heartbeat,1),'capture_healthy':heartbeat is not None and now-heartbeat<=90}
   tmp=a.directory/'serial-status.tmp';tmp.write_text(json.dumps(status,indent=2)+'\n');os.replace(tmp,a.directory/'serial-status.json');laststatus=now
finally:
 append('serial-lifecycle.jsonl',{'event':'stopped','at':utc(),'pid':os.getpid(),'bytes_fsynced':total});os.close(fd)
 tmp=a.directory/'serial-status.tmp';tmp.write_text(json.dumps({'updated_utc':utc(),'running':False,'capture_healthy':False})+'\n');os.replace(tmp,a.directory/'serial-status.json')
