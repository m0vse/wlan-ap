#define _GNU_SOURCE
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <fcntl.h>
#include <unistd.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <errno.h>
#include <stdarg.h>
#include <stdint.h>
#include <inttypes.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <poll.h>

static volatile sig_atomic_t running=1;
static int out=-1;
static char boot[80];
static unsigned long sequence;
static void stop(int sig){(void)sig;running=0;}
static int read_text(const char *path,char *buf,size_t size){
 int fd=open(path,O_RDONLY|O_CLOEXEC|O_NOFOLLOW);if(fd<0)return -1;
 ssize_t n=read(fd,buf,size-1);int saved=errno;close(fd);errno=saved;
 if(n<0)return -1;
 buf[n]=0;return (int)n;
}
static int emit(const char *fmt,...){
 char line[1024];va_list ap;va_start(ap,fmt);int n=vsnprintf(line,sizeof(line),fmt,ap);va_end(ap);
 if(n<0||(size_t)n>=sizeof(line)){errno=EOVERFLOW;return -1;}
 ssize_t sent=write(out,line,(size_t)n);return sent==n?0:-1;
}
/* Send a complete record atomically, outside printk's userspace limiter.
 * A receipt is returned only after the receiver fsyncs the exact datagram.
 * Retries may duplicate records; boot/nonce/sequence identify duplicates. */
static int record(const char *text,const char *test){
 char packet[8192],ack[80],expected[80];
 size_t length=strlen(text);unsigned lines=0;
 if(length>4095){errno=EOVERFLOW;return -1;}
 for(size_t i=0;i<length;i++)if(text[i]=='\n')lines++;
 if(length && text[length-1]!='\n')lines++;
 int n=snprintf(packet,sizeof(packet),"MIAMI_CAPTURE_RECORD v=1 boot=%s nonce=%s seq=%lu bytes=%zu lines=%u synthetic=%u\n%s",boot,test?test:"none",sequence,length,lines,!!test,text);
 if(n<0 || (size_t)n>=sizeof(packet)){errno=EOVERFLOW;return -1;}
 uint64_t hash=UINT64_C(14695981039346656037);
 for(int i=0;i<n;i++){hash^=(unsigned char)packet[i];hash*=UINT64_C(1099511628211);}
 snprintf(expected,sizeof(expected),"MIAMI_CAPTURE_SAVED %016" PRIx64 "\n",hash);
 for(unsigned attempt=0;attempt<3 && running;attempt++){
  if(write(out,packet,(size_t)n)!=n)continue;
  struct timespec start,now;clock_gettime(CLOCK_MONOTONIC,&start);
  for(;;){
   clock_gettime(CLOCK_MONOTONIC,&now);
   long left=1000-(now.tv_sec-start.tv_sec)*1000-(now.tv_nsec-start.tv_nsec)/1000000;
   if(left<=0)break;
   struct pollfd pfd={.fd=out,.events=POLLIN};
   if(poll(&pfd,1,(int)left)<=0)break;
   ssize_t got=recv(out,ack,sizeof(ack),0);
   if(got==(ssize_t)strlen(expected) && !memcmp(ack,expected,(size_t)got))return 0;
  }
 }
 errno=ETIMEDOUT;return -1;
}
int main(int argc,char **argv){
 const char *cache="/sys/bus/platform/devices/79b0000.nand/miami_first_failure",*remote=NULL,*port=NULL,*test=NULL;
 if(argc==6 && !strcmp(argv[1],"--self-test")){
  cache=argv[2];test=argv[3];remote=argv[4];port=argv[5];
  if(strncmp(cache,"/tmp/",5)||!test[0]||strlen(test)>64||strspn(test,"0123456789abcdef")!=strlen(test))return 2;
 }else if(argc==3){remote=argv[1];port=argv[2];}else return 2;
 if(read_text("/proc/sys/kernel/random/boot_id",boot,sizeof(boot))<0)return 1;
 boot[strcspn(boot,"\r\n")]=0;
 struct sockaddr_in peer={.sin_family=AF_INET};char *end=NULL;
 long number=strtol(port,&end,10);
 if(!end || *end || number<1 || number>65535 || inet_pton(AF_INET,remote,&peer.sin_addr)!=1)return 2;
 peer.sin_port=htons((unsigned short)number);
 out=socket(AF_INET,SOCK_DGRAM|SOCK_CLOEXEC,0);
 if(out<0 || connect(out,(struct sockaddr *)&peer,sizeof(peer))){perror("capture UDP output");return 1;}
 /* No shared libraries/external helpers or executable NAND pages after entry.
  * Failure is visible; never silently advertise a resident watcher. */
 if(mlockall(MCL_CURRENT|MCL_FUTURE)){perror("capture mlockall");close(out);return 1;}
 signal(SIGTERM,stop);signal(SIGINT,stop);
 char current[4096],previous[4096]="";
 if(test){int n=read_text(cache,current,sizeof(current));if(n<0)return 1;sequence=1;int rc=record(current,test);close(out);return rc?1:0;}
 if(emit("MIAMI_CAPTURE_HEARTBEAT boot=%s seq=0 resident=1 started=1\n",boot))return 1;
 unsigned tick=0;
 while(running){
  int n=read_text(cache,current,sizeof(current));
  if(n>=0 && strcmp(current,previous)){
   if(!strncmp(current,"state=captured ",15)){
    sequence++;if(record(current,NULL)){perror("capture record unacknowledged");sleep(1);continue;}
   }
   memcpy(previous,current,(size_t)n+1);
  }
  if(++tick%30==0 && emit("MIAMI_CAPTURE_HEARTBEAT boot=%s seq=%lu resident=1 cache=%s\n",boot,sequence,n>=0?(!strncmp(current,"state=captured ",15)?"captured":"armed"):"unavailable"))return 1;
  struct timespec pause={1,0};while(nanosleep(&pause,&pause)&&errno==EINTR&&running){}
 }
 emit("MIAMI_CAPTURE_STOP boot=%s seq=%lu\n",boot,sequence);close(out);return 0;
}
