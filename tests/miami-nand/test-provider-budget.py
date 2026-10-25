#!/usr/bin/env python3
from pathlib import Path
import argparse,re,subprocess,tempfile
p=argparse.ArgumentParser();p.add_argument('--provider',type=Path,required=True);a=p.parse_args();s=a.provider.read_text()
def structure(n):
 a=s.index('struct '+n+' {');return s[a:s.index('\n};',a)+3]
def fun(n):
 m=re.search(r'^static [^\n]*\b'+n+r'\([^;]*?\)\s*\{',s,re.M);assert m,n
 b=s.index('{',m.start());d=1;e=b+1
 while d:d+=(s[e]=='{')-(s[e]=='}');e+=1
 return s[m.start():e]
pre=r'''
#include <assert.h>
#include <stdint.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdlib.h>
#include <stddef.h>
#include <stdio.h>
typedef uint32_t u32;typedef uint16_t u16;typedef uint32_t __le32;typedef uint16_t __le16;
typedef atomic_long atomic_long_t;
#define atomic_long_add_return(n,p) (atomic_fetch_add((p),(n))+(n))
#define atomic_long_sub(n,p) atomic_fetch_sub((p),(n))
#define SZ_128K (128*1024)
#define GFP_ATOMIC 0
#define BAM_FIFO_SIZE (32768-8)
#define DMA_PREP_FENCE 1
#define DMA_PREP_INTERRUPT 2
#define DMA_PREP_CMD 4
#define DMA_PREP_LOCK 8
#define DMA_PREP_UNLOCK 16
#define DESC_FLAG_NWD (1<<12)
#define DESC_FLAG_EOT (1<<14)
#define DESC_FLAG_LOCK (1<<10)
#define DESC_FLAG_UNLOCK (1<<9)
#define DESC_FLAG_CMD (1<<11)
#define cpu_to_le16(x) (x)
#define cpu_to_le32(x) (x)
#define le16_to_cpu(x) (x)
#define DIV_ROUND_UP(n,d) (((n)+(d)-1)/(d))
#define struct_size(p,m,n) (sizeof(*(p))+sizeof((p)->m[0])*(n))
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define dev_err(...) ((void)0)
struct dma_chan {int x;};
struct dma_async_tx_descriptor {struct dma_chan *chan;};
struct virt_dma_desc {struct dma_async_tx_descriptor tx;};
struct virt_dma_chan {int x;};struct list_head {void *next,*prev;};
enum dma_transfer_direction {DMA_DEV_TO_MEM=1,DMA_MEM_TO_DEV=2};
struct scatterlist {unsigned int size;uintptr_t addr;};
#define for_each_sg(sg,s,n,i) for((i)=0,(s)=(sg);(i)<(n);(i)++,(s)++)
#define sg_dma_len(s) ((s)->size)
#define sg_dma_address(s) ((s)->addr)
struct qcom_qpic_lifetime {int x;};
static bool poisoned;static int allocation_fails,allocated,freed;
static bool qcom_qpic_lifetime_poisoned(struct qcom_qpic_lifetime *l){return l&&poisoned;}
struct bam_device {void *dev;struct qcom_qpic_lifetime *lifetime;atomic_long_t qpic_desc_bytes;};
struct bam_chan {struct dma_chan chan;struct virt_dma_chan vc;struct bam_device *bdev;};
static struct bam_chan channel;
static struct bam_chan *to_bam_chan(struct dma_chan *c){return container_of(c,struct bam_chan,chan);}
static int is_slave_direction(int d){return d==1||d==2;}
static void *kzalloc(size_t n,int flags){(void)flags;if(allocation_fails)return NULL;void *p=calloc(1,n);if(p)allocated++;return p;}
static void kfree(void *p){freed++;free(p);}
static struct dma_async_tx_descriptor *vchan_tx_prep(struct virt_dma_chan *v,struct virt_dma_desc *d,unsigned long f){(void)v;(void)f;d->tx.chan=&channel.chan;return &d->tx;}
'''
suffix=r'''
int main(void){
 struct qcom_qpic_lifetime life={0};struct bam_device b={.lifetime=&life};channel.bdev=&b;
 struct scatterlist sg[128];for(int i=0;i<128;i++)sg[i]=(struct scatterlist){512,0x40000000+i*512};
 struct dma_async_tx_descriptor *pending[4096];int count=0;
 allocation_fails=1;assert(!bam_prep_slave_sg(&channel.chan,sg,1,DMA_DEV_TO_MEM,0,NULL)&&atomic_load(&b.qpic_desc_bytes)==0);allocation_fails=0;
 while(count<4096){struct dma_async_tx_descriptor *d=bam_prep_slave_sg(&channel.chan,sg,128,DMA_DEV_TO_MEM,DMA_PREP_CMD|DMA_PREP_FENCE,NULL);if(!d)break;pending[count++]=d;assert(atomic_load(&b.qpic_desc_bytes)<=SZ_128K);}
 assert(count>0&&count<4096);long before=atomic_load(&b.qpic_desc_bytes);assert(before>0&&before<=SZ_128K);
 poisoned=true;for(int i=0;i<count;i++)bam_dma_free_desc(container_of(pending[i],struct virt_dma_desc,tx));
 assert(atomic_load(&b.qpic_desc_bytes)==before&&freed==0);
 assert(!bam_prep_slave_sg(&channel.chan,sg,1,DMA_DEV_TO_MEM,0,NULL));assert(atomic_load(&b.qpic_desc_bytes)==before);
 /* Backend destruction after simulated power off; no production unpoison API. */
 poisoned=false;for(int i=0;i<count;i++)bam_dma_free_desc(container_of(pending[i],struct virt_dma_desc,tx));assert(atomic_load(&b.qpic_desc_bytes)==0&&allocated==freed);
 b.lifetime=NULL;struct dma_async_tx_descriptor *d=bam_prep_slave_sg(&channel.chan,sg,1,DMA_MEM_TO_DEV,DMA_PREP_INTERRUPT,NULL);assert(d&&atomic_load(&b.qpic_desc_bytes)==0);bam_dma_free_desc(container_of(d,struct virt_dma_desc,tx));assert(allocated==freed);
 printf("PASS actual provider prep/free: descriptor quota %ld <=128KiB, OOM rollback, retained late-callback metadata after poison, rejected new prep, unaffected non-QPIC control\n",before);
}
'''
with tempfile.TemporaryDirectory() as d:
 c=Path(d)/'budget.c';exe=Path(d)/'budget';c.write_text(pre+structure('bam_desc_hw')+'\n'+structure('bam_async_desc')+'\n'+fun('bam_prep_slave_sg')+'\n'+fun('bam_dma_free_desc')+suffix)
 subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-fsanitize=address,undefined','-o',str(exe),str(c)],check=True);subprocess.run([str(exe)],check=True)
