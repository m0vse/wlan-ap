/* Bounded read-only storage facts. No erase, write, feature, attach or mount ioctl. */
#define _GNU_SOURCE
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <sys/ioctl.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <mtd/mtd-user.h>

#ifndef STORAGE_ROOT
#define STORAGE_ROOT ""
#endif
#define LIMIT 128
#define MAX_BLOCKS 4096
struct cache { uint32_t version, index, size, erase, qualified; unsigned char bad[MAX_BLOCKS]; };
static int number(const char *s, unsigned long *v) {
 char *e; if (!s || !*s || *s=='-') return -1;
 errno=0; *v=strtoul(s,&e,10); return errno || *e ? -1:0;
}
static int read_text(const char *path, char *out, size_t n) {
 FILE *f=fopen(path,"r"); if (!f) return -1;
 int ok=fgets(out,n,f)!=NULL; fclose(f);
 if (ok) out[strcspn(out,"\r\n")]=0;
 return ok?0:-1;
}
static int counter(unsigned i, const char *key, unsigned long *value) {
 char path[512],out[64]; snprintf(path,sizeof(path),STORAGE_ROOT "/sys/class/mtd/mtd%u/%s",i,key);
 return read_text(path,out,sizeof(out)) || number(out,value);
}
static int bad_cache(int fd, unsigned index, struct mtd_info_user *info, struct cache *c) {
 struct stat st; char path[512];
 if (mkdir(STORAGE_ROOT "/tmp/ucentral-storage-probe",0700)<0 && errno!=EEXIST) return -1;
 if (lstat(STORAGE_ROOT "/tmp/ucentral-storage-probe",&st) || !S_ISDIR(st.st_mode) ||
     st.st_uid!=geteuid() || (st.st_mode&0777)!=0700) return -1;
 snprintf(path,sizeof(path),STORAGE_ROOT "/tmp/ucentral-storage-probe/mtd%u",index);
 int in=open(path,O_RDONLY|O_NOFOLLOW|O_CLOEXEC);
 if (in>=0) {
  int valid=!fstat(in,&st) && S_ISREG(st.st_mode) && st.st_uid==geteuid() &&
    st.st_size==sizeof(*c) && read(in,c,sizeof(*c))==sizeof(*c) &&
    c->version==2 && c->index==index && c->size==info->size && c->erase==info->erasesize;
  close(in); if (valid) return 0;
  return -1; /* Never silently refresh a changed cache within this boot. */
 }
 if (errno!=ENOENT) return -1;
 memset(c,0,sizeof(*c)); c->version=2;c->index=index;c->size=info->size;c->erase=info->erasesize;
 for (unsigned b=0;b<info->size/info->erasesize;b++) {
  loff_t offset=(loff_t)b*info->erasesize;
  int bad=ioctl(fd,MEMGETBADBLOCK,&offset); if (bad<0) return -1;
  c->bad[b]=bad!=0;
 }
 int out=open(path,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);
 if (out<0) return -1;
 int ok=write(out,c,sizeof(*c))==sizeof(*c); close(out);
 if (!ok) unlink(path);
 return ok?0:-1;
}
static void samples(unsigned index,unsigned size,unsigned erase,const char *list) {
 char path[512],type[32],name[64]; struct mtd_info_user info; struct cache c;
 snprintf(path,sizeof(path),STORAGE_ROOT "/sys/class/mtd/mtd%u/type",index);
 int qualified=!read_text(path,type,sizeof(type)) && !strcmp(type,"nand");
 snprintf(path,sizeof(path),STORAGE_ROOT "/sys/class/mtd/mtd%u/name",index);
 qualified=qualified && !read_text(path,name,sizeof(name)) &&
   (!strcmp(name,"rootfs") || !strcmp(name,"rootfs_1") || !strcmp(name,"fs") || !strcmp(name,"rootfs0") || !strcmp(name,"rootfs1"));
 snprintf(path,sizeof(path),STORAGE_ROOT "/dev/mtd%uro",index);
 int fd=open(path,O_RDONLY|O_CLOEXEC|O_NOFOLLOW);
 if (!qualified || fd<0 || ioctl(fd,MEMGETINFO,&info) || info.type!=MTD_NANDFLASH ||
     info.size!=size || info.erasesize!=erase || !erase ||
     info.size/info.erasesize>MAX_BLOCKS || info.writesize!=2048 ||
     bad_cache(fd,index,&info,&c)) {
  printf("{\"mtd\":%u,\"status\":\"unavailable\"}",index);
  if(fd>=0)close(fd);
  return;
 }
 char output[4096]="";size_t used=0;unsigned good=0;int failed=0;
 char *copy=strdup(list),*save=NULL,*s;unsigned count=0;
 if(!copy) {close(fd);printf("{\"mtd\":%u,\"status\":\"unavailable\"}",index);return;}
 for(s=strtok_r(copy,",",&save);s && count<8;s=strtok_r(NULL,",",&save)) {
  unsigned long b; if(number(s,&b) || b>=size/erase) continue;
  if(count++)used+=snprintf(output+used,sizeof(output)-used,",");
  if(c.bad[b]) {used+=snprintf(output+used,sizeof(output)-used,"{\"peb\":%lu,\"bad\":true}",b);continue;}
  unsigned char page[8192]; errno=0;
  ssize_t n=pread(fd,page,info.writesize,(off_t)b*erase);
  good++;
  if(n!=info.writesize || memcmp(page,"UBI#",4))failed=1;
  used+=snprintf(output+used,sizeof(output)-used,"{\"peb\":%lu,\"ok\":%s,\"error\":%d}",b,
    n==info.writesize && !memcmp(page,"UBI#",4)?"true":"false",n<0?errno:0);
 }
 if(!c.qualified && good && !failed) {
  c.qualified=1;
  char cachepath[512];snprintf(cachepath,sizeof(cachepath),STORAGE_ROOT "/tmp/ucentral-storage-probe/mtd%u",index);
  int out=open(cachepath,O_WRONLY|O_NOFOLLOW|O_CLOEXEC);
  if(out>=0) { if(write(out,&c,sizeof(c))!=sizeof(c))c.qualified=0;close(out); }
  else c.qualified=0;
 }
 printf("{\"mtd\":%u,\"status\":\"%s\",\"samples\":[%s]}",index,
  c.qualified && good?"checked":"unavailable",output);
 free(copy);close(fd);
}
/* Cached driver snapshot only: opening sysfs does not execute NAND commands. */
static void first_failure(void) {
 const char *path = STORAGE_ROOT "/sys/bus/platform/devices/79b0000.nand/miami_first_failure";
 char text[2048];
 int fd = open(path, O_RDONLY|O_CLOEXEC|O_NOFOLLOW);
 ssize_t n = fd < 0 ? -1 : read(fd,text,sizeof(text)-1);
 if(fd>=0)close(fd);
 const char *state = n>0 && !strncmp(text,"state=captured ",15) ? "captured" :
                     n>0 && !strncmp(text,"state=armed ",12) ? "armed" : "unavailable";
 printf("{\"state\":\"%s\"",state);
 if(strcmp(state,"unavailable")) {
  printf(",\"record\":\"");
  for(ssize_t i=0;i<n;i++) {
   unsigned char c=text[i];
   if(c=='\n')fputs("\\n",stdout);
   else if(c=='\r')fputs("\\r",stdout);
   else if(c=='\\' || c=='\"')printf("\\%c",c);
   else if(c>=32 && c<127)putchar(c);
   else printf("\\u%04x",c);
  }
  printf("\"");
 }
 printf("}");
}
int main(int argc,char **argv) {
 unsigned count=0;printf("{\"mtd\":[");
 for(unsigned i=0;i<LIMIT;i++) {
  char path[512],type[32];unsigned long failed,corrected;
  snprintf(path,sizeof(path),STORAGE_ROOT "/sys/class/mtd/mtd%u/type",i);
  if(read_text(path,type,sizeof(type)) || strcmp(type,"nand") ||
     counter(i,"ecc_failures",&failed) || counter(i,"corrected_bits",&corrected))continue;
  if(count++)printf(",");
  printf("{\"index\":%u,\"ecc_failures\":%lu,\"corrected_bits\":%lu}",i,failed,corrected);
 }
 printf("],\"mounts\":[");count=0;
 FILE *f=fopen(STORAGE_ROOT "/proc/mounts","r");char dev[256],path[256],type[64],opts[1024];
 if(f) {while(fscanf(f,"%255s %255s %63s %1023s %*d %*d\n",dev,path,type,opts)==4) {
  if(strcmp(path,"/overlay") && strcmp(path,"/certificates"))continue;
  struct statvfs v;if(statvfs(path,&v))continue;
  if(count++)printf(",");
  printf("{\"path\":\"%s\",\"readonly\":%s,\"total_bytes\":%llu,\"available_bytes\":%llu,\"available_inodes\":%llu,\"total_inodes\":%llu}",path,
   (v.f_flag&ST_RDONLY)?"true":"false",(unsigned long long)v.f_blocks*v.f_frsize,
   (unsigned long long)v.f_bavail*v.f_frsize,(unsigned long long)v.f_favail,(unsigned long long)v.f_files);
 }fclose(f);}
 printf("],\"canary\":[");
 for(int a=1;a+3<argc && a<=5;a+=4) {
  unsigned long index,size,erase;
  if(number(argv[a],&index) || index>=LIMIT || number(argv[a+1],&size) || size>UINT32_MAX ||
     number(argv[a+2],&erase) || erase>UINT32_MAX)continue;
  if(a>1)printf(",");
  samples(index,size,erase,argv[a+3]);
 }
 printf("],\"nand_first_failure\":");first_failure();
 printf("}\n");return ferror(stdout)?1:0;
}
