"""Execute exact candidate callback bodies with fixture hardware boundaries."""
from pathlib import Path
import re,subprocess,sys,tempfile
oldthor,thor,oldsyn,syn=map(Path,sys.argv[1:5]);d=Path(tempfile.mkdtemp(prefix='netpoll-callbacks-'))
t=thor.read_text();s=syn.read_text()
tguard=re.compile(r'\t/\* Netpoll requests TX-only.*?\n\t}\n\n',re.S)
rguard=re.compile(r'\t/\* Netpoll must not receive.*?\n\t\treturn 0;\n\n',re.S)
sguard=re.compile(r'\t/\* A nonzero internal bound.*?\n\t}\n\n',re.S)
assert tguard.sub('',t,count=1)==oldthor.read_text(),'Thor positive-budget source changed'
assert sguard.sub('',rguard.sub('',s,count=1),count=1)==oldsyn.read_text(),'SynGMAC positive-budget source changed'
def fn(text,name):
 match=re.search(r'^(?:static )?int '+re.escape(name)+r'\(',text,re.M);assert match;start=match.start()
 brace=text.index('{',start);level=1;i=brace+1
 while level:level+=(text[i]=='{')-(text[i]=='}');i+=1
 return text[start:i]
h=r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#define likely(x) (x)
#define unlikely(x) (x)
#define __iomem
#define container_of(ptr,type,member) ((type *)((char *)(ptr)-offsetof(type,member)))
#define EDMA_MAX_GMACS 2
#define EDMA_REG_RXDESC_INT_MASK(id) (id)
#define EDMA_REG_TX_INT_MASK(id) (id)
#define EDMA_REG_RXFILL_INT_MASK(id) (id)
#define SYN_DP_NAPI_BUDGET_TX 64
struct napi_struct { int unused; };
struct edma_txcmpl_ring { int id; };
struct edma_rxdesc_ring { int id; };
struct edma_rxfill_ring { int id; };
struct net_device { int stopped,carrier; };
struct edma_hw { struct napi_struct napi; int rxdesc_rings,txcmpl_rings,rxfill_rings; struct edma_rxdesc_ring rxdesc_ring[2]; struct edma_txcmpl_ring txcmpl_ring[2]; struct edma_rxfill_ring rxfill_ring[2]; struct net_device *netdev_arr[2]; int rxdesc_intr_mask,txcmpl_intr_mask,rxfill_intr_mask; };
struct edma_hw edma_hw;
struct syn_dp_info_rx { struct napi_struct napi; int page_mode; void *mac_base; };
struct syn_dp_info_tx { struct napi_struct napi; void *mac_base; };
static int tx,rx,refill,page_refill,complete,irq,wakes,last_budget,work=2,pending;
static void reset(void){tx=rx=refill=page_refill=complete=irq=wakes=last_budget=0;work=2;pending=0;}
static int edma_clean_rx(struct edma_hw *h,int b,struct edma_rxdesc_ring *r){rx++;return work;}
static void edma_clean_tx(struct edma_hw *h,struct edma_txcmpl_ring *r){tx++;}
static void edma_alloc_rx_buffer(struct edma_hw *h,struct edma_rxfill_ring *r){refill++;}
static int netif_queue_stopped(struct net_device *d){return d->stopped;}
static int netif_carrier_ok(struct net_device *d){return d->carrier;}
static void netif_start_queue(struct net_device *d){wakes++;d->stopped=0;}
static void napi_complete(struct napi_struct *n){complete++;}
static void edma_reg_write(int r,int v){irq++;}
static int syn_dp_rx(struct syn_dp_info_rx *r,int b){rx++;return work;}
static int syn_dp_rx_refill(struct syn_dp_info_rx *r){refill++;return pending;}
static int syn_dp_rx_refill_page_mode(struct syn_dp_info_rx *r){page_refill++;return pending;}
static void syn_enable_rx_dma_interrupt(void *m){irq++;}
static void syn_enable_tx_dma_interrupt(void *m){irq++;}
static int syn_dp_tx_complete(struct syn_dp_info_tx *t,int b){tx++;last_budget=b;assert(b>0);return work;}
'''
test=r'''
int main(void){
 struct net_device a={1,1},b={1,1};struct syn_dp_info_rx r={0};struct syn_dp_info_tx tr={0};int checks=0;
 edma_hw.rxdesc_rings=1;edma_hw.txcmpl_rings=2;edma_hw.rxfill_rings=1;edma_hw.netdev_arr[0]=&a;edma_hw.netdev_arr[1]=&b;
 reset();assert(edma_napi(&edma_hw.napi,0)==0&&tx==2&&rx==0&&refill==0&&complete==0&&irq==0&&wakes==0);checks++;
 reset();assert(edma_napi(&edma_hw.napi,64)==2&&tx==2&&rx==1&&refill==1&&complete==1&&irq==4&&wakes==2);checks++;
 reset();edma_hw.txcmpl_rings=0;assert(edma_napi(&edma_hw.napi,0)==0&&tx==0&&rx==0&&refill==0&&complete==0&&irq==0);checks++;
 reset();assert(syn_dp_napi_poll_rx(&r.napi,0)==0&&rx==0&&refill==0&&page_refill==0&&complete==0&&irq==0);checks++;
 reset();assert(syn_dp_napi_poll_rx(&r.napi,64)==2&&rx==1&&refill==1&&complete==1&&irq==1);checks++;
 reset();r.page_mode=1;assert(syn_dp_napi_poll_rx(&r.napi,64)==2&&page_refill==1&&refill==0&&complete==1&&irq==1);checks++;
 reset();pending=1;r.page_mode=0;assert(syn_dp_napi_poll_rx(&r.napi,64)==64&&rx==1&&refill==1&&complete==0&&irq==0);checks++;
 reset();assert(syn_dp_napi_poll_tx(&tr.napi,0)==0&&tx==1&&last_budget==64&&rx==0&&complete==0&&irq==0);checks++;
 reset();assert(syn_dp_napi_poll_tx(&tr.napi,64)==2&&tx==1&&last_budget==64&&complete==1&&irq==1);checks++;
 reset();work=64;assert(syn_dp_napi_poll_tx(&tr.napi,64)==64&&tx==1&&complete==0&&irq==0);checks++;
 printf("PASS %d exact callback lifecycle controls; positive-budget source byte-identical\n",checks);
}
'''
p=d/'test.c';p.write_text(h+'\n'+fn(t,'edma_napi')+'\n'+fn(s,'syn_dp_napi_poll_rx')+'\n'+fn(s,'syn_dp_napi_poll_tx')+'\n'+test)
subprocess.run(['cc','-Wall','-Werror','-Wno-unused-parameter',str(p),'-o',str(d/'test')],check=True)
subprocess.run([str(d/'test')],check=True)
