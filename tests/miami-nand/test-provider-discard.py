#!/usr/bin/env python3
"""Execute actual BAM unissued-discard path; poison any hardware pipe reset."""
import argparse,pathlib,re,subprocess,tempfile
p=argparse.ArgumentParser();p.add_argument('--provider',type=pathlib.Path,required=True);p.add_argument('--virt-dma',type=pathlib.Path,required=True);p.add_argument('--driver',type=pathlib.Path,required=True);a=p.parse_args()
def extract(s,n):
 m=re.search(r'^static(?: inline)? (?:void|int) '+n+r'\([^;]*?\)\s*\{',s,re.M);assert m,n
 b=s.index('{',m.start());d=1;e=b+1
 while d:d+=(s[e]=='{')-(s[e]=='}');e+=1
 return s[m.start():e]
s=a.provider.read_text();v=a.virt_dma.read_text();driver=a.driver.read_text()
# An interrupt is requested independently of EOT when a callback is present.
assert 'dmaengine_desc_callback_valid(&cb)' in s
assert re.search(r'dmaengine_desc_callback_valid\(&cb\).*?DESC_FLAG_EOT.*?DESC_FLAG_INT',s,re.S)
assert 'flags | DMA_PREP_INTERRUPT' not in driver
prefix=r'''
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
struct list_head {struct list_head *next,*prev;};
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define LIST_HEAD(n) struct list_head n={&n,&n}
static void init(struct list_head *l){l->next=l->prev=l;}
static int list_empty(struct list_head *l){return l->next==l;}
static void list_add(struct list_head *n,struct list_head *h){n->next=h->next;n->prev=h;h->next->prev=n;h->next=n;}
static void list_del(struct list_head *n){n->prev->next=n->next;n->next->prev=n->prev;}
static void list_splice_tail_init(struct list_head *l,struct list_head *h){
 if(list_empty(l))return;l->next->prev=h->prev;h->prev->next=l->next;l->prev->next=h;h->prev=l->prev;init(l);
}
#define list_first_entry(l,t,m) container_of((l)->next,t,m)
#define list_for_each_entry_safe(p,n,h,m) for(p=container_of((h)->next,__typeof__(*p),m),n=container_of(p->m.next,__typeof__(*p),m);&p->m!=(h);p=n,n=container_of(n->m.next,__typeof__(*n),m))
#define spin_lock_irqsave(l,f) ((void)(l),(f)=0)
#define spin_unlock_irqrestore(l,f) ((void)(l),(void)(f))
struct dma_chan {int unused;};
struct virt_dma_desc {struct list_head node;};
struct virt_dma_chan {int lock;struct list_head desc_allocated,desc_submitted,desc_issued,desc_completed,desc_terminated;};
struct bam_async_desc {struct virt_dma_desc vd;struct list_head desc_node;int dir;};
struct bam_chan {struct dma_chan chan;struct virt_dma_chan vc;struct list_head desc_list;};
static int freed,resets,allow_reset;
static struct bam_chan *to_bam_chan(struct dma_chan *c){return container_of(c,struct bam_chan,chan);}
static void bam_chan_init_hw(struct bam_chan *c,int dir){(void)c;(void)dir;resets++;assert(allow_reset);}
static void vchan_dma_desc_free_list(struct virt_dma_chan *c,struct list_head *l){
 (void)c;while(!list_empty(l)){struct list_head *n=l->next;list_del(n);freed++;}
}
'''
suffix=r'''
int main(void){
 for(int allocated=0;allocated<5;allocated++)for(int submitted=0;submitted<5;submitted++){
  struct bam_chan c={0};struct bam_async_desc entries[8]={0};
  init(&c.desc_list);init(&c.vc.desc_allocated);init(&c.vc.desc_submitted);init(&c.vc.desc_issued);init(&c.vc.desc_completed);init(&c.vc.desc_terminated);
  for(int i=0;i<allocated;i++)list_add(&entries[i].vd.node,&c.vc.desc_allocated);
  for(int i=0;i<submitted;i++)list_add(&entries[allocated+i].vd.node,&c.vc.desc_submitted);
  freed=resets=0;assert(bam_dma_terminate_all(&c.chan)==0);
  assert(freed==allocated+submitted&&resets==0&&list_empty(&c.vc.desc_allocated)&&list_empty(&c.vc.desc_submitted));
 }
 /* Positive poison control: an active pipe DOES enter the reset branch.
  * This is precisely why the client must not use discard after issue. */
 struct bam_chan c={0};struct bam_async_desc active={0};
 init(&c.desc_list);init(&c.vc.desc_allocated);init(&c.vc.desc_submitted);init(&c.vc.desc_issued);init(&c.vc.desc_completed);init(&c.vc.desc_terminated);
 list_add(&active.desc_node,&c.desc_list);freed=resets=0;allow_reset=1;
 assert(bam_dma_terminate_all(&c.chan)==0&&resets==1&&freed==1);
 puts("PASS actual BAM/virt-dma prepared+partially-submitted queues discarded with zero pipe resets; active-pipe reset positive control; callback IRQ independent of EOT");
}
'''
# Execute the provider's actual flag statements, not an IRQ/EOT surrogate.
def statement(text, needle):
 start=text.index(needle);return text[start:text.index(';',start)+1]
prep='\n'.join(statement(s,'if (flags & '+flag+')') for flag in ['DMA_PREP_FENCE','DMA_PREP_INTERRUPT'])
start=s.index('if (((avail <= async_desc->xfer_len)')
irq=s[start:s.index(';',start)+1]
prefix+='''
#define BIT(i) (1u<<(i))
#define DMA_PREP_FENCE 1
#define DMA_PREP_INTERRUPT 2
#define DESC_FLAG_NWD BIT(12)
#define DESC_FLAG_EOT BIT(14)
#define DESC_FLAG_INT BIT(15)
#define cpu_to_le16(x) (x)
struct hw {unsigned short flags;};
struct flags_async {unsigned int flags,xfer_len;};
struct cb {int valid;};
static int dmaengine_desc_callback_valid(struct cb *c){return c->valid;}
static unsigned int actual_flags(unsigned long flags,int callback){
 struct flags_async a={.xfer_len=1},*async_desc=&a;
 struct hw hardware={0},*desc=&hardware;struct cb cb={callback};
 unsigned int avail=2;void *vd=&a;
'''+prep+'\n'+irq+'''
 return async_desc->flags|desc->flags;
}
'''
suffix=suffix.replace('int main(void){','''int main(void){
 assert(actual_flags(0,0)==0);
 assert(actual_flags(0,1)==DESC_FLAG_INT);
 assert(actual_flags(DMA_PREP_FENCE,1)==(DESC_FLAG_NWD|DESC_FLAG_INT));
 assert(actual_flags(DMA_PREP_INTERRUPT,1)==DESC_FLAG_EOT);
 assert(actual_flags(DMA_PREP_FENCE|DMA_PREP_INTERRUPT,1)==(DESC_FLAG_NWD|DESC_FLAG_EOT));
 /* Universal INTERRUPT OR changes transaction protocol, not merely IRQ. */
 assert(actual_flags(DMA_PREP_INTERRUPT,1)!=actual_flags(0,1));
''')
with tempfile.TemporaryDirectory() as d:
 c=pathlib.Path(d)/'provider.c';exe=pathlib.Path(d)/'provider'
 c.write_text(prefix+extract(v,'vchan_get_all_descriptors')+'\n'+extract(s,'bam_dma_terminate_all')+suffix)
 subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-fsanitize=address,undefined','-o',str(exe),str(c)],check=True)
 subprocess.run([str(exe)],check=True)
