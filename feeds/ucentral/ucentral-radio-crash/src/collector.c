/* Potential bounded devcoredump retention backend. No sysfs writes.
 * Fixture roots are compile-time only; production integration is pending.
 * Read-only sysfs access does not release remoteproc INLINE dump recovery.
 */
#define _GNU_SOURCE
#include <sys/file.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <dirent.h>
#include <sys/statvfs.h>
#ifndef SOURCE_ROOT
#define SOURCE_ROOT "/sys/class/devcoredump"
#endif
#ifndef STORE_ROOT
#define STORE_ROOT "/etc/ucentral/radio-crash"
#endif
#ifndef BOOT_FILE
#define BOOT_FILE "/proc/sys/kernel/random/boot_id"
#endif
#define LIMIT (1024u * 1024u)
#define SLOTS 2
#define RESERVE (2u * 1024u * 1024u)
static int valid_device(const char *s) {
 if (strncmp(s,"devcd",5) || !s[5]) return 0;
 for(s+=5;*s;s++) if(!isdigit((unsigned char)*s)) return 0;
 return 1;
}
static int write_all(int fd,const void *data,size_t n) {
 const char *p=data;
 while(n) { ssize_t r=write(fd,p,n); if(r<0 && errno==EINTR)continue;
  if(r<=0)return -1;p+=r;n-=r; } return 0;
}
int main(int argc,char **argv) {
 char boot[38]={0},path[512],event[96],binary[96],meta[512],buf[4096];
 int src=-1,root=-1,lock=-1,out=-1,m=-1,rc=1,complete=0;
 unsigned count=0; size_t total=0; struct stat st;
 if(argc!=2 || !valid_device(argv[1]) || strlen(argv[1])>24 || geteuid())return 2;
 int bf=open(BOOT_FILE,O_RDONLY|O_NOFOLLOW); if(bf<0)return 3;
 ssize_t n=read(bf,boot,37);close(bf);
 if(n<36)return 3;boot[36]=0;
 for(int i=0;i<36;i++) if(!((i==8||i==13||i==18||i==23)?boot[i]=='-':isxdigit((unsigned char)boot[i])))return 3;
 if(mkdir(STORE_ROOT,0700) && errno!=EEXIST)return 4;
 root=open(STORE_ROOT,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
 if(root<0 || fstat(root,&st) || st.st_uid || (st.st_mode&0777)!=0700)goto done;
 lock=openat(root,".lock",O_RDWR|O_CREAT|O_NOFOLLOW,0600);
 if(lock<0 || fstat(lock,&st) || !S_ISREG(st.st_mode) || st.st_uid || (st.st_mode&0777)!=0600 || flock(lock,LOCK_EX|LOCK_NB))goto done;
 snprintf(event,sizeof(event),"%s-%s.json",boot,argv[1]);
 snprintf(binary,sizeof(binary),"%s-%s.bin",boot,argv[1]);
 if(!fstatat(root,event,&st,AT_SYMLINK_NOFOLLOW)) {
  if(S_ISREG(st.st_mode) && st.st_uid==0 && (st.st_mode&0777)==0600 && !fsync(root))rc=0;
  goto done;
 }
 if(errno!=ENOENT)goto done;
 DIR *entries=fdopendir(dup(root));if(!entries)goto done;
 struct dirent *entry;
 while((entry=readdir(entries))) {size_t l=strlen(entry->d_name);
  if(l>4 && !strcmp(entry->d_name+l-4,".bin"))count++;}
 closedir(entries);
 if(count>=SLOTS){rc=5;goto done;}
 struct statvfs space;
 if(fstatvfs(root,&space) || (unsigned long long)space.f_bavail*space.f_frsize < LIMIT+RESERVE+8192u){rc=6;goto done;}
 /* An orphan committed binary is retained, not overwritten automatically. */
 if(!fstatat(root,binary,&st,AT_SYMLINK_NOFOLLOW) || errno!=ENOENT)goto done;
 out=openat(root,".capture.bin",O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);if(out<0)goto done;
 snprintf(path,sizeof(path),"%s/%s/data",SOURCE_ROOT,argv[1]);
 src=open(path,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);if(src<0 || fstat(src,&st) || !S_ISREG(st.st_mode))goto cleanup;

 while(total<LIMIT){size_t want=LIMIT-total;if(want>sizeof(buf))want=sizeof(buf);
  n=read(src,buf,want);if(n<0 && errno==EINTR)continue;if(n<0)goto cleanup;
  if(!n){complete=1;break;}
  if(fstatvfs(root,&space) || (unsigned long long)space.f_bavail*space.f_frsize < RESERVE+8192u+(unsigned)n)goto cleanup;
  if(write_all(out,buf,n))goto cleanup;total+=n;}
 if(total==LIMIT){do{n=read(src,buf,1);}while(n<0 && errno==EINTR);if(n<0)goto cleanup;complete=n==0;}
 if(!total || fsync(out))goto cleanup;
 m=openat(root,".capture.json",O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);if(m<0)goto cleanup;
 n=snprintf(meta,sizeof(meta),"{\"version\":1,\"id\":\"%s-%s\",\"boot_id\":\"%s\",\"driver\":\"remoteproc-or-ath\",\"source\":\"devcoredump\",\"byte_count\":%zu,\"binaryfile\":\"%s\",\"complete\":%s,\"truncated\":%s}\n",boot,argv[1],boot,total,binary,complete?"true":"false",complete?"false":"true");
 if(n<=0 || n>=(ssize_t)sizeof(meta) || write_all(m,meta,n) || fsync(m))goto cleanup;
 if(renameat(root,".capture.bin",root,binary) || fsync(root))goto cleanup;
 /* Publish the manifest last; a power loss cannot expose it before the data. */
 if(renameat(root,".capture.json",root,event) || fsync(root))goto cleanup;
 rc=0;goto done;
cleanup:
 unlinkat(root,".capture.bin",0);if(m>=0)unlinkat(root,".capture.json",0);
done:
 if(m>=0)close(m);if(out>=0)close(out);if(src>=0)close(src);if(lock>=0)close(lock);if(root>=0)close(root);
 return rc;
}
