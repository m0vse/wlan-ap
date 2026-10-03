#!/usr/bin/env python3
"""Opt-in external netconsole receiver. Durable raw datagrams, bounded per AP."""
import argparse,base64,ipaddress,json,os,socket,stat,time
from pathlib import Path

class Store:
    def __init__(self, directory, allowed, segment_bytes=1048576, segments=8):
        self.allowed={str(ipaddress.IPv4Address(a)) for a in allowed}
        if not 1<=len(self.allowed)<=32: raise ValueError('Require 1..32 explicit sender IPv4 addresses')
        if not 16384<=segment_bytes<=16777216 or not 2<=segments<=32: raise ValueError('Invalid retention bounds')
        self.limit,self.segments=segment_bytes,segments
        self.directory=Path(directory)
        self.directory.mkdir(mode=0o700,parents=True,exist_ok=True)
        st=self.directory.lstat()
        if not stat.S_ISDIR(st.st_mode) or st.st_uid!=os.getuid() or stat.S_IMODE(st.st_mode)!=0o700: raise ValueError('Store must be an owned private real directory, mode 700')
        expected={self.name(sender,i) for sender in self.allowed for i in range(segments)}
        for entry in self.directory.iterdir():
            st=entry.lstat()
            if entry.name not in expected or not stat.S_ISREG(st.st_mode) or st.st_uid!=os.getuid() or stat.S_IMODE(st.st_mode)!=0o600 or st.st_size>segment_bytes:
                raise ValueError('Existing store exceeds configured names, permissions or bounds; archive it separately')
        self.dirfd=os.open(self.directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    def close(self): os.close(self.dirfd)
    def name(self, sender, index): return f'{sender}.{index}.jsonl'
    def append(self, sender, data, source_port=0, truncated=False):
        if sender not in self.allowed: return False
        if len(data)>8192: data=data[:8192];truncated=True
        record=(json.dumps({'received_ns':time.time_ns(),'sender':sender,'source_port':source_port,'truncated':bool(truncated),'raw_base64':base64.b64encode(data).decode()},separators=(',',':'))+'\n').encode()
        name=self.name(sender,0)
        fd=os.open(name,os.O_RDWR|os.O_APPEND|os.O_CREAT|os.O_NOFOLLOW,0o600,dir_fd=self.dirfd)
        try:
            st=os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_uid!=os.getuid() or stat.S_IMODE(st.st_mode)!=0o600 or st.st_size>self.limit: raise ValueError('Unsafe or oversized existing capture file')
            # Recover an interrupted append without treating a partial JSON record as evidence.
            if st.st_size:
                if os.pread(fd,1,st.st_size-1)!=b'\n':
                    previous=os.pread(fd,st.st_size,0)
                    os.ftruncate(fd,previous.rfind(b'\n')+1);os.fsync(fd)
            if os.fstat(fd).st_size+len(record)>self.limit:
                os.close(fd);fd=-1
                for i in range(self.segments-1,0,-1):
                    src=self.name(sender,i-1);dest=self.name(sender,i)
                    try: os.rename(src,dest,src_dir_fd=self.dirfd,dst_dir_fd=self.dirfd)
                    except FileNotFoundError: pass
                fd=os.open(name,os.O_WRONLY|os.O_APPEND|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=self.dirfd)
            os.fsync(self.dirfd)
            view=memoryview(record)
            while view:
                n=os.write(fd,view)
                if not n: raise OSError('Short capture write')
                view=view[n:]
            os.fsync(fd)
            return True
        finally:
            if fd>=0: os.close(fd)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bind',required=True,help='Explicit collector IPv4 address')
    p.add_argument('--port',type=int,default=6666)
    p.add_argument('--allow',action='append',required=True,help='AP IPv4 sender; repeat for each AP')
    p.add_argument('--directory',required=True)
    p.add_argument('--segment-bytes',type=int,default=1048576)
    p.add_argument('--segments',type=int,default=8)
    a=p.parse_args();bind=str(ipaddress.IPv4Address(a.bind))
    if not 1<=a.port<=65535: p.error('Invalid port')
    store=Store(a.directory,a.allow,a.segment_bytes,a.segments)
    try:
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
            sock.bind((bind,a.port))
            while True:
                data,ancillary,flags,peer=sock.recvmsg(8192)
                store.append(peer[0],data,peer[1],bool(flags&socket.MSG_TRUNC))
    finally: store.close()
if __name__=='__main__': main()
