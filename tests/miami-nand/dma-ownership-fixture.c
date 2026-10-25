/* Source-extraction fixture: only kernel/DMA APIs and hardware setup are mocked.
 * The driver controls descriptor preparation, callbacks, waits, cleanup,
 * ECC parsing/accounting, page-scope copy and raw erased-page fallback. */
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
typedef uint8_t u8; typedef uint32_t u32; typedef uint32_t __le32;
typedef int dma_cookie_t;
#define DMA_PREP_INTERRUPT 1
#define DMA_PREP_CMD 2
#define DMA_PREP_FENCE 4
#define DMA_PREP_LOCK 8
#define DMA_PREP_UNLOCK 16
#define DMA_COMPLETE 0
#define DMA_TO_DEVICE 1
#define DMA_FROM_DEVICE 2
#define GFP_KERNEL 0
#define QPIC_NAND_COMPLETION_TIMEOUT 2000
#define FLASH_BUF_ACC 0
#define MAX_STATUS_REG 12
#define FS_OP_ERR 16
#define FS_MPU_ERR 256
#define BS_UNCORRECTABLE_BIT 256
#define BS_CORRECTABLE_ERR_MSK 31
#define ERASED_CW 3
#define le32_to_cpu(x) (x)
#define max(a,b) ((a)>(b)?(a):(b))
#define max_t(t,a,b) max((t)(a),(t)(b))
#define BIT(i) (1UL<<(i))
#define hweight_long(x) __builtin_popcountl(x)
#define for_each_set_bit(i,p,n) for(i=0;i<(n);i++) if(*(p)&BIT(i))
#define dev_err(...) ((void)0)
struct list_head {struct list_head *next,*prev;};
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
static void init_list(struct list_head *l){l->next=l->prev=l;}
static void list_add_tail(struct list_head *n,struct list_head *h){n->prev=h->prev;n->next=h;h->prev->next=n;h->prev=n;}
static void list_del(struct list_head *n){n->prev->next=n->next;n->next->prev=n->prev;}
#define list_for_each_entry(p,h,m) for(p=container_of((h)->next,__typeof__(*p),m); &p->m!=(h);p=container_of(p->m.next,__typeof__(*p),m))
#define list_for_each_entry_safe(p,n,h,m) for(p=container_of((h)->next,__typeof__(*p),m),n=container_of(p->m.next,__typeof__(*p),m);&p->m!=(h);p=n,n=container_of(n->m.next,__typeof__(*n),m))
struct completion {int done;};
static void init_completion(struct completion *c){c->done=0;}
static void complete(struct completion *c){c->done++;}
struct dma_chan {int id;};
struct bam_cmd_element {int unused;};
struct scatterlist {void *cpu;int size,channel,mapped;};
enum dma_transfer_direction {DMA_MEM_TO_DEV=1,DMA_DEV_TO_MEM=2};
enum dma_data_direction {DUMMY_DIR=0};
struct dma_async_tx_descriptor {
 struct dma_chan *chan;void (*callback)(void *);void *callback_param;
 unsigned long flags;struct scatterlist *sg;int count,submitted,issued,finished;
};
/* ACTUAL_STRUCTURES */
struct props {bool is_bam,qpic_v2,page_scope;};
struct qcom_nand_controller {
 struct props *props;struct bam_transaction *bam_txn;void *dev;
 struct dma_chan *rx_chan,*tx_chan,*cmd_chan,*sts_chan,*chan;
 struct list_head desc_list;bool miami_diag_enabled,miami_diag_claimed;
 bool miami_dma_unsafe,miami_probe_active,miami_probe_synthetic;
 int miami_diag_cookie[4];__le32 reg_read_buf[12],status_buf[12];int sts_buf_size;
};
struct nand_ecc_ctrl {int steps,size,bytes,strength;};
struct nand_chip {struct nand_ecc_ctrl ecc;u8 data[4096],oob[128],*oob_poi;};
struct qcom_nand_host {struct nand_chip chip;bool bch_enabled,codeword_fixup,use_ecc;int cw_data,cw_size,bbm_size,ecc_bytes_hw,spare_bytes;};
struct mtd_info {int writesize;struct {u32 corrected,failed;} ecc_stats;};
struct miami_nand_diag {int result;};
struct read_stats {u32 flash,buffer,erased_cw;};
static struct qcom_nand_controller ctrl;
static struct qcom_nand_host host;
static struct bam_transaction txn;
static struct props properties;
static struct mtd_info mtd;
static struct dma_chan channels[4]={{0},{1},{2},{3}}; /* cmd/rx/tx/sts */
static struct scatterlist cmdsg[80],datasg[80],stssg[16];
static struct dma_async_tx_descriptor *descriptors[128];
static int nd,now,delay[4],missing,prep_error,submit_error,map_error;
static int prep_calls,submit_calls,maps,unmaps,violations,issues,waits,raw_reads;
static int discard_calls,cpu_owned,status_writes,raw_result,mode,diag_calls,inject_calls;
static u32 devregs[12],devstatus[12];
static unsigned long total_budget;
static void *kzalloc(size_t n,int flags){(void)flags;return calloc(1,n);}
static void kfree(void *p){free(p);}
static void sg_mark_end(struct scatterlist *s){(void)s;}
static int dma_map_sg(void *dev,struct scatterlist *s,int n,int dir){
 (void)dev;(void)dir;if(++maps==map_error)return 0;
 for(int i=0;i<n;i++){assert(!s[i].mapped);s[i].mapped=1;}return n;
}
static struct dma_async_tx_descriptor *dmaengine_prep_slave_sg(struct dma_chan *c,struct scatterlist *s,int n,int dir,unsigned long flags){
 (void)dir;if(++prep_calls==prep_error)return NULL;
 struct dma_async_tx_descriptor *d=calloc(1,sizeof(*d));assert(nd<128);
 *d=(struct dma_async_tx_descriptor){.chan=c,.flags=flags,.sg=s,.count=n};descriptors[nd++]=d;return d;
}
static int dmaengine_submit(struct dma_async_tx_descriptor *d){
 if(++submit_calls==submit_error)return -EIO;d->submitted=1;return submit_calls;
}
static bool dma_submit_error(int c){return c<0;}
static int dmaengine_terminate_sync(struct dma_chan *c){
 discard_calls++;
 for(int i=0;i<nd;i++)if(descriptors[i]->chan==c){
  assert(!descriptors[i]->issued);descriptors[i]->submitted=0;
 }
 return 0;
}
static void dma_async_issue_pending(struct dma_chan *c){
 issues++;for(int i=0;i<nd;i++)if(descriptors[i]->chan==c&&descriptors[i]->submitted)descriptors[i]->issued=1;
}
static void event(struct dma_async_tx_descriptor *d){
 d->finished=1;
 if(d->chan->id==3){memcpy(ctrl.status_buf,devstatus,sizeof(devstatus));}
 if(d->chan->id==0&&!properties.page_scope)memcpy(ctrl.reg_read_buf,devregs,sizeof(devregs));
 /* Model the provider delivering a completed descriptor callback. IRQ
  * coalescing/hardware pipe ordering is deliberately not asserted here. */
 if(d->callback)d->callback(d->callback_param);
}
static unsigned long wait_for_completion_timeout(struct completion *c,unsigned long budget){
 waits++;if(!total_budget)total_budget=budget;
 int end=now+(int)budget;
 while(!c->done){
  int k=-1;
  for(int i=0;i<nd;i++){struct dma_async_tx_descriptor *d=descriptors[i];
   if(d->issued&&!d->finished&&d->chan->id!=missing&&delay[d->chan->id]<=end&&
      (k<0||delay[d->chan->id]<delay[descriptors[k]->chan->id]))k=i;
  }
  if(k<0){now=end;return 0;}
  if(now<delay[descriptors[k]->chan->id])now=delay[descriptors[k]->chan->id];
  event(descriptors[k]);
 }
 c->done--;return end>now?(unsigned long)(end-now):1;
}
static int dma_sync_wait(struct dma_chan *c,int cookie){(void)c;(void)cookie;return DMA_COMPLETE;}
static void dma_unmap_sg(void *dev,struct scatterlist *s,int n,int dir){
 (void)dev;(void)dir;
 for(int i=0;i<nd;i++){
  struct dma_async_tx_descriptor *d=descriptors[i];
  if(d->sg==s&&d->issued&&!d->finished)violations++;
 }
 for(int i=0;i<n;i++)s[i].mapped=0;unmaps++;
}
static struct qcom_nand_controller *get_qcom_nand_controller(struct nand_chip *c){(void)c;return &ctrl;}
static struct qcom_nand_host *to_qcom_nand_host(struct nand_chip *c){return container_of(c,struct qcom_nand_host,chip);}
static struct mtd_info *nand_to_mtd(struct nand_chip *c){(void)c;return &mtd;}
static bool qcom_nandc_is_last_cw(struct nand_ecc_ctrl *e,int cw){return cw==e->steps-1;}
static void nandc_read_buffer_sync(struct qcom_nand_controller *n,bool cpu){
 if(cpu){memcpy(n->reg_read_buf,devregs,sizeof(devregs));cpu_owned=1;}
 else cpu_owned=0;
}
static void miami_probe_inject(struct qcom_nand_host *h,int p){
 (void)h;(void)p;inject_calls++;if(!cpu_owned)violations++;
}
static void miami_diag_take(struct qcom_nand_host *h,struct miami_nand_diag *d,int p,const char *r,bool valid){(void)h;(void)d;(void)p;(void)r;if(valid&&!cpu_owned)violations++;}
static void miami_diag_publish(struct qcom_nand_host *h,struct miami_nand_diag *d,bool f){(void)h;(void)d;(void)f;diag_calls++;ctrl.miami_diag_claimed=true;}
static void miami_diag_header(struct qcom_nand_host *h,u8 *d,int p,int r){(void)h;(void)d;(void)p;(void)r;}
static void miami_probe_count(struct qcom_nand_host *h,int r,u32 f,u32 c){(void)h;(void)r;(void)f;(void)c;}
static void miami_probe_run(struct qcom_nand_host *h){(void)h;}
static bool erased_chunk_check_and_fixup(u8 *b,int n){(void)b;(void)n;return false;}
static u8 *nand_get_data_buf(struct nand_chip *c){return c->data;}
static int nand_check_erased_ecc_chunk(u8 *d,int dl,u8 *o,int ol,void *e,int el,int strength){(void)d;(void)dl;(void)o;(void)ol;(void)e;(void)el;(void)strength;return raw_result;}
static void clear_bam_transaction(struct qcom_nand_controller *n){
 struct bam_transaction zero={0};*n->bam_txn=zero;
 n->bam_txn->cmd_sgl=cmdsg;n->bam_txn->data_sgl=datasg;n->bam_txn->sts_sgl=stssg;
 memset(cmdsg,0,sizeof(cmdsg));memset(datasg,0,sizeof(datasg));memset(stssg,0,sizeof(stssg));
}
static void nand_read_page_op(struct nand_chip *c,int p,int o,void *d,int n){(void)c;(void)p;(void)o;(void)d;(void)n;cpu_owned=0;memset(devregs,0,sizeof(devregs));raw_reads++;}
static void set_address(struct qcom_nand_host *h,int col,int p){(void)h;(void)col;(void)p;}
static void update_rw_regs(struct qcom_nand_host *h,int s,bool r,int cw){(void)h;(void)s;(void)r;(void)cw;}
static void config_nand_page_read(struct nand_chip *c){(void)c;}
static void nandc_set_read_loc(struct nand_chip *c,int cw,int reg,int off,int len,int last){(void)c;(void)cw;(void)reg;(void)off;(void)len;(void)last;}
static void config_nand_cw_read(struct nand_chip *c,bool ecc,int cw){
 (void)c;(void)cw;cmdsg[txn.cmd_sgl_pos++]=(struct scatterlist){.channel=0};
 if(!ecc)memset(devregs,0,sizeof(devregs));
}
static void read_data_dma(struct qcom_nand_controller *n,int off,u8 *d,int len,int f){
 (void)n;(void)off;(void)f;assert(len>=0);datasg[txn.rx_sgl_pos++]=(struct scatterlist){.cpu=d,.size=len,.channel=1};
}
static void read_status_data_dma(struct qcom_nand_controller *n,int off,void *d,int len,int f){
 (void)n;(void)off;(void)f;stssg[txn.sts_sgl_pos++]=(struct scatterlist){.cpu=d,.size=len,.channel=3};
}
/* ACTUAL_FUNCTIONS */
static void reset_case(void){
 /* Destroying a simulated test device is not a production cancellation.
  * Mark hardware gone before releasing retained contexts between cases. */
 for(int i=0;i<nd;i++)descriptors[i]->finished=1;
 if(ctrl.desc_list.next){ctrl.miami_dma_unsafe=false;free_descs(&ctrl);}
 for(int i=0;i<nd;i++)free(descriptors[i]);nd=0;
 memset(&ctrl,0,sizeof(ctrl));memset(&host,0,sizeof(host));memset(&mtd,0,sizeof(mtd));
 memset(devregs,0,sizeof(devregs));memset(devstatus,0,sizeof(devstatus));
 properties=(struct props){true,true,true};ctrl.props=&properties;ctrl.bam_txn=&txn;
 ctrl.cmd_chan=&channels[0];ctrl.rx_chan=&channels[1];ctrl.tx_chan=&channels[2];ctrl.sts_chan=&channels[3];ctrl.chan=&channels[0];
 ctrl.sts_buf_size=48;ctrl.miami_diag_enabled=true;init_list(&ctrl.desc_list);clear_bam_transaction(&ctrl);
 host.chip.ecc=(struct nand_ecc_ctrl){4,512,16,8};host.chip.oob_poi=host.chip.oob;
 host.bch_enabled=true;host.use_ecc=true;host.cw_data=516;host.cw_size=528;host.bbm_size=1;host.ecc_bytes_hw=13;host.spare_bytes=2;mtd.writesize=2048;
 now=maps=unmaps=violations=issues=waits=raw_reads=discard_calls=cpu_owned=status_writes=diag_calls=inject_calls=0;
 missing=-1;prep_error=submit_error=map_error=0;prep_calls=submit_calls=0;raw_result=-EBADMSG;mode=0;total_budget=0;
 delay[0]=10;delay[1]=20;delay[2]=15;delay[3]=30;
}
static int page(void){return read_page_ecc(&host,host.chip.data,host.chip.oob,16384);}
int main(int argc,char **argv){
 assert(argc==3);int old=atoi(argv[1]),require_timeout=atoi(argv[2]);int bugs=0;
 if(!old){for(int a=0;a<3;a++)for(int b=0;b<3;b++)for(int c=0;c<3;c++){
  if(a==b||a==c||b==c)continue;reset_case();delay[0]=(a+1)*100;delay[1]=(b+1)*100;delay[3]=(c+1)*100;
  assert(page()==0&&now==300&&!violations);
 }}
 reset_case();delay[1]=900;assert(page()==0);
 if(violations){bugs++;printf("REPRODUCED early RX unmap: %d\n",violations);}else assert(now>=900);
 reset_case();delay[3]=900;assert(page()==0);assert(now>=900&&!violations);
 reset_case();devstatus[1]=3;assert(page()==(old?0:3));
 if(mtd.ecc_stats.corrected!=3){bugs++;puts("REPRODUCED page-scope CPU status discarded by late invalidate");}else assert(cpu_owned);
 reset_case();properties.page_scope=false;devregs[1]=2;assert(page()==2&&mtd.ecc_stats.corrected==2&&!violations);
 reset_case();properties.page_scope=false;devregs[0]=FS_MPU_ERR;assert(page()==-EIO&&diag_calls==1&&!violations);
 reset_case();properties.page_scope=false;devregs[0]=FS_OP_ERR;devregs[1]=BS_UNCORRECTABLE_BIT;raw_result=2;
 assert(page()==2&&raw_reads==1&&mtd.ecc_stats.corrected==2&&mtd.ecc_stats.failed==0&&!violations);
 reset_case();properties.page_scope=false;devregs[0]=FS_OP_ERR;devregs[1]=BS_UNCORRECTABLE_BIT;
 assert(page()==0&&raw_reads==1&&mtd.ecc_stats.failed==1&&diag_calls==1&&!violations);
 reset_case();ctrl.miami_probe_active=true;properties.page_scope=false;devregs[0]=FS_OP_ERR;devregs[1]=BS_UNCORRECTABLE_BIT;
 assert(page()==-EBADMSG&&raw_reads==0&&mtd.ecc_stats.failed==1&&!violations);
 if(!old){
  for(int n=1;n<=3;n++){reset_case();prep_error=n;assert(page()==-EINVAL);assert(!issues&&!violations&&discard_calls==4);}
  for(int n=1;n<=3;n++){reset_case();map_error=n;assert(page()==-ENOMEM);assert(!issues&&!violations&&discard_calls==4);}
  for(int n=1;n<=3;n++){reset_case();submit_error=n;assert(page()==-EIO);assert(!issues&&!violations&&discard_calls==4);}
 }
 /* Shared-submit controls beyond ECC reads. */
 if(!old){
  reset_case();txn.cmd_sgl_pos=1;prep_error=1;
  assert(prepare_bam_async_desc(&ctrl,ctrl.cmd_chan,DMA_PREP_CMD)==-EINVAL);
  prep_error=0; /* caller ignores earlier queue error; submit must retain it */
  assert(submit_descs(&ctrl)==-EINVAL&&issues==0&&discard_calls==4);free_descs(&ctrl);
  reset_case();txn.cmd_sgl_pos=1;
  assert(submit_descs(&ctrl)==0&&now==10&&nd==1&&descriptors[0]->flags==DMA_PREP_CMD);
  free_descs(&ctrl);assert(!violations);
  reset_case();properties.qpic_v2=false;properties.page_scope=false;devregs[1]=1;
  assert(page()==1&&nd==2&&!violations); /* legacy BAM, no STS */
  reset_case();devstatus[1]=1;
  assert(read_page_ecc(&host,NULL,host.chip.oob,16384)==1&&!violations); /* OOB-only */
  reset_case();delay[2]=900;txn.cmd_sgl_pos=1;
  unsigned long special=DMA_PREP_CMD|DMA_PREP_FENCE|DMA_PREP_LOCK;
  assert(prepare_bam_async_desc(&ctrl,ctrl.cmd_chan,special)==0);
  txn.tx_sgl_pos=1;
  assert(prepare_bam_async_desc(&ctrl,ctrl.tx_chan,DMA_PREP_INTERRUPT)==0);
  txn.tx_sgl_pos=2;txn.cmd_sgl_pos=2;
  assert(submit_descs(&ctrl)==0&&now==900&&nd==4);
  assert(descriptors[0]->flags==special&&descriptors[1]->flags==DMA_PREP_INTERRUPT);
  assert(descriptors[2]->flags==DMA_PREP_INTERRUPT&&descriptors[3]->flags==DMA_PREP_CMD);
  free_descs(&ctrl);assert(!violations); /* write-side TX + intermediate fenced CMD */
  reset_case();properties.is_bam=false;
  struct desc_info *adm=calloc(1,sizeof(*adm));
  adm->dma_desc=calloc(1,sizeof(*adm->dma_desc));descriptors[nd++]=adm->dma_desc;
  adm->dma_desc->chan=ctrl.chan;list_add_tail(&adm->node,&ctrl.desc_list);
  assert(submit_descs(&ctrl)==0&&issues==0&&waits==0);free_descs(&ctrl);
  assert(unmaps==1&&!violations); /* unchanged ADM completion boundary */
 }
 int timeout_unsafe=0;
 for(int channel=0;channel<4;channel++){if(channel==2)continue;
  reset_case();missing=channel;int r=page();
  if(!old)assert(r==-ETIMEDOUT&&now==2000&&ctrl.miami_dma_unsafe&&diag_calls==1);
  bool outstanding=false;
  for(int i=0;i<nd;i++)if(descriptors[i]->issued&&!descriptors[i]->finished)outstanding=true;
  if(outstanding)timeout_unsafe++;
  if(!old){assert(!violations); /* retained callback contexts, still unsafe caller */
   for(int i=0;i<nd;i++)if(descriptors[i]->issued&&!descriptors[i]->finished)event(descriptors[i]);
  }
 }
 printf("UNRESOLVED issued-timeout caller-buffer ownership: %d channel cases still unsafe; no reset/cancellation claimed\n",timeout_unsafe);
 if(old)assert(bugs==2);else assert(bugs==0);
 reset_case();
 puts("PASS actual extracted prepare/submit/free/read/parser/raw-fallback paths and ECC accounting controls");
 if(require_timeout&&timeout_unsafe)return 2;
 return 0;
}
