/* Device/devres backend. Actual owner/removal/IRQ source is inserted below. */
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <pthread.h>
typedef uint32_t u32;
#define CONFIG_QCOM_BAM_DMA 1
#define CONFIG_MTD_NAND_QCOM 2
#define CONFIG_IOMMU_SUPPORT 3
static int builtins=1,iommu;
#define IS_BUILTIN(x) (builtins)
#define IS_ENABLED(x) (iommu)
#define DEFINE_MUTEX(n) pthread_mutex_t n=PTHREAD_MUTEX_INITIALIZER
#define mutex_lock(m) assert(pthread_mutex_lock(m)==0)
#define mutex_unlock(m) assert(pthread_mutex_unlock(m)==0)
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
#define WARN_ON(x) assert(!(x))
#define EXPORT_SYMBOL_GPL(x)
#define dev_err(...) ((void)0)
#define ERR_PTR(x) ((void *)(intptr_t)(x))
#define PTR_ERR(x) ((int)(intptr_t)(x))
#define IS_ERR(x) ((intptr_t)(x)<0 && (intptr_t)(x)>-4096)
#define __maybe_unused
#define BIT(i) (1u<<(i))
#define IORESOURCE_MEM 1
#define GFP_KERNEL 0
#define DMA_BIT_MASK(x) ((1ULL<<(x))-1)
struct device;
struct pm_domain {void (*dismiss)(struct device *);};
struct action {void (*fn)(void *);void *data;};
struct device {
 uint64_t coherent_dma_mask,*dma_mask;void *of_node,*dma_parms,*dma_range_map,*driver,*drvdata;
 struct pm_domain *pm_domain;int refs,is_owner,kobj;struct action actions[64];int na;
};
struct resource {unsigned long start;};
struct platform_device {struct device dev;struct resource resource;};
static int step,fail_at,owner_count,node_refs,freed_objects,put_count,irq_disabled;
static int mapping_count,irq_count,clock_count,hardware_calls,unregister_calls,sysfs_removed;
static int fail(void){return ++step==fail_at;}
static struct resource *platform_get_resource(struct platform_device *p,int type,int index){(void)type;(void)index;return &p->resource;}
static int of_machine_is_compatible(const char *s){return !strcmp(s,"cambiumnetworks,x7-35x");}
static struct device *root_device_register(const char *name){(void)name;if(fail())return ERR_PTR(-ENOMEM);struct device *d=calloc(1,sizeof(*d));assert(d);d->refs=1;d->is_owner=1;owner_count++;return d;}
static void *of_node_get(void *n){node_refs++;return n;}
static void of_node_put(void *n){assert(n);node_refs--;}
static struct device *get_device(struct device *d){d->refs++;return d;}
static void put_device(struct device *d){assert(d->refs>0);d->refs--;put_count++;}
static int devm_add_action_or_reset(struct device *d,void (*fn)(void *),void *data){if(fail()){fn(data);return -ENOMEM;}assert(d->na<64);d->actions[d->na++]=(struct action){fn,data};return 0;}
static void object_free(void *p){freed_objects++;free(p);}
static void *devm_kzalloc(struct device *d,size_t n,int gfp){(void)gfp;if(fail())return NULL;void *p=calloc(1,n);assert(p);assert(d->na<64);d->actions[d->na++]=(struct action){object_free,p};return p;}
static void devres_release_all(struct device *d){while(d->na){struct action a=d->actions[--d->na];a.fn(a.data);}}
static void root_device_unregister(struct device *d){assert(d->is_owner);devres_release_all(d);free(d->dma_range_map);owner_count--;free(d);}
static int of_dma_configure(struct device *d,void *np,bool force){(void)np;(void)force;if(fail())return -EINVAL;d->dma_range_map=malloc(16);assert(d->dma_range_map);memset(d->dma_range_map,0xa5,16);return 0;}
static int dma_set_mask_and_coherent(struct device *d,uint64_t mask){assert(d->dma_mask==&d->coherent_dma_mask);if(fail())return -EIO;d->coherent_dma_mask=mask;return 0;}
static void kfree(void *p){free(p);}
static void arch_teardown_dma_ops(struct device *d){assert(!d->is_owner);}
static void dev_set_drvdata(struct device *d,void *p){d->drvdata=p;}
static void pm_runtime_reinit(struct device *d){assert(!d->is_owner);}
static void dev_pm_set_driver_flags(struct device *d,int flags){(void)d;(void)flags;}
/* ACTUAL_OWNER */
struct list_head {struct list_head *next,*prev;};
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#include <stddef.h>
#define list_for_each_entry(p,h,m) for(p=container_of((h)->next,__typeof__(*p),m);&p->m!=(h);p=container_of(p->m.next,__typeof__(*p),m))
static void init_list(struct list_head *l){l->next=l->prev=l;}
static void add(struct list_head *n,struct list_head *h){n->next=h->next;n->prev=h;h->next->prev=n;h->next=n;}
struct dma_chan {int x;};
struct bam_device;
struct bam_chan {struct {struct dma_chan chan;int task,lock;}vc;struct bam_device *bdev;struct list_head desc_list;int id;void *fifo_virt;uintptr_t fifo_phys;};
struct bam_device {struct device *dev,*dma_dev;struct qcom_qpic_lifetime *lifetime;int irq,common,task;unsigned int num_channels,active_channels;bool powered_remotely;struct bam_chan *channels;void *bamclk;};
struct nand_chip {int mtd;};
struct qcom_nand_host {struct nand_chip chip;struct list_head node;};
struct props {bool switch_layout,is_serial_nand;};
struct qcom_nand_controller {struct device *dev,*dma_dev;struct qcom_qpic_lifetime *lifetime;bool miami_diag_enabled;struct list_head host_list;struct props *props;void *iomacro_clk,*aon_clk,*core_clk;uintptr_t base_dma;};
static struct bam_chan *to_bam_chan(struct dma_chan *c){return container_of(c,struct bam_chan,vc.chan);}
static void *to_virt_chan(struct dma_chan *c){return &to_bam_chan(c)->vc;}
static int list_empty(struct list_head *l){return l->next==l;}
#define spin_lock_irqsave(l,f) ((void)(l),(f)=0)
#define spin_unlock_irqrestore(l,f) ((void)(l),(void)(f))
static void vchan_free_chan_resources(void *v){(void)v;assert(!qpic_poisoned);}
static void bam_reset(struct bam_device *b){(void)b;assert(!qpic_poisoned);hardware_calls++;}
static void bam_reset_channel(struct bam_chan *b){(void)b;assert(!qpic_poisoned);hardware_calls++;}
static int mtd_busy;
struct attribute {int x;};struct device_attribute {struct attribute attr;};
static struct device_attribute dev_attr_miami_first_failure,dev_attr_miami_probe_test,dev_attr_boot_layout;
static void *platform_get_drvdata(struct platform_device *p){return p->dev.drvdata;}
static void device_remove_file(struct device *d,struct device_attribute *a){(void)d;(void)a;sysfs_removed++;}
static int mtd_device_unregister(int *m){(void)m;unregister_calls++;return mtd_busy?-EBUSY:0;}
static int *nand_to_mtd(struct nand_chip *c){return &c->mtd;}
static void nand_cleanup(struct nand_chip *c){(void)c;assert(!qpic_poisoned);freed_objects++;}
static void sysfs_remove_file(void *k,struct attribute *a){(void)k;(void)a;}
static void qcom_nandc_unalloc(struct qcom_nand_controller *n){assert(!qpic_poisoned);(void)n;mapping_count--;}
struct fake_clock {int prepare,enable;};
static void clk_disable(void *c){if(!c)return;struct fake_clock *k=c;assert(!qpic_poisoned&&k->enable>0);k->enable--;}
static int clk_enable(void *c){if(!c)return 0;struct fake_clock *k=c;assert(!qpic_poisoned&&k->prepare>0);k->enable++;return 0;}
static void clk_unprepare(void *c){if(!c)return;struct fake_clock *k=c;assert(!qpic_poisoned&&k->prepare>0);if(k->prepare==1)assert(k->enable==0);k->prepare--;}
static void clk_disable_unprepare(void *c){clk_disable(c);clk_unprepare(c);}
#define DMA_BIDIRECTIONAL 0
static void dma_unmap_resource(struct device *d,uintptr_t a,unsigned long n,int direction,int attrs){(void)d;(void)a;(void)n;(void)direction;(void)attrs;assert(!qpic_poisoned);mapping_count--;}
static unsigned long resource_size(struct resource *r){(void)r;return 0x10000;}
static void of_dma_controller_free(void *n){(void)n;}
static void dma_async_device_unregister(void *c){(void)c;assert(!qpic_poisoned);unregister_calls++;}
static void *dev_get_drvdata(struct device *d){return d->drvdata;}
static int bam_dma_runtime_suspend(struct device *d);
static void pm_runtime_force_suspend(struct device *d){assert(!qpic_poisoned);assert(bam_dma_runtime_suspend(d)==0);}
#define BAM_IRQ_SRCS_MSK_EE 0
#define BAM_IRQ_STTS 1
#define BAM_IRQ_CLR 2
#define BAM_P_IRQ_EN 3
#define BAM_CTRL 4
#define BAM_SW_RST 1
#define BAM_DESC_FIFO_SIZE 32768
static u32 register_value;
static void *bam_addr(struct bam_device *b,int p,int r){(void)b;(void)p;(void)r;return &register_value;}
static void writel_relaxed(u32 v,void *a){(void)v;(void)a;assert(!qpic_poisoned);hardware_calls++;}
static u32 readl_relaxed(void *a){(void)a;assert(!qpic_poisoned);hardware_calls++;return 0;}
static void devm_free_irq(struct device *d,int irq,void *data){(void)d;(void)irq;(void)data;assert(!qpic_poisoned);irq_count--;}
static int bam_dma_terminate_all(struct dma_chan *c){(void)c;assert(!qpic_poisoned);hardware_calls++;return 0;}
static void tasklet_kill(void *t){(void)t;assert(!qpic_poisoned);}
static void *fifo_allocations[64];static int fifo_count,fifo_fail;
static void *dma_alloc_wc(struct device *d,unsigned long size,uintptr_t *phys,int flags){(void)flags;if(fifo_fail)return NULL;assert(d->is_owner);void *p=calloc(1,size);assert(p&&fifo_count<64);fifo_allocations[fifo_count++]=p;*phys=(uintptr_t)p;return p;}
static void dma_free_wc(struct device *d,unsigned long size,void *p,uintptr_t phys){(void)d;(void)size;(void)phys;assert(!qpic_poisoned);for(int i=0;i<fifo_count;i++)if(fifo_allocations[i]==p){free(p);fifo_allocations[i]=NULL;freed_objects++;return;}assert(!p);}
static void poweroff_fifos(void){for(int i=0;i<fifo_count;i++)free(fifo_allocations[i]);fifo_count=0;}
typedef int irqreturn_t;
#define IRQ_HANDLED 1
#define IRQ_NONE 0
#define P_IRQ 1
#define BAM_IRQ 2
#define mb() ((void)0)
static u32 process_channel_irqs(struct bam_device *b){(void)b;assert(!qpic_poisoned);hardware_calls++;return 0;}
static void tasklet_schedule(void *t){(void)t;assert(!qpic_poisoned);}
static int pm_runtime_get_sync(struct device *d){(void)d;assert(!qpic_poisoned);return 0;}
static void pm_runtime_mark_last_busy(struct device *d){(void)d;assert(!qpic_poisoned);}
static void pm_runtime_put_autosuspend(struct device *d){(void)d;assert(!qpic_poisoned);}
/* ACTUAL_REMOVAL */
static void irq_disable_hook(void *data){struct bam_device *b=data;assert(b->dma_dev==qpic_lifetimes[1].owner);irq_disabled++;}
static void prepare_platform(struct platform_device *p,bool provider){memset(p,0,sizeof(*p));p->dev.refs=1;p->dev.driver=p;p->dev.of_node=p;p->dev.dma_range_map=malloc(16);p->dev.dma_mask=&p->dev.coherent_dma_mask;p->resource.start=provider?0x7984000:0x79b0000;}
static void platform_cleanup(struct platform_device *p){device_unbind_cleanup(&p->dev);assert(p->dev.driver==NULL&&p->dev.dma_range_map==NULL&&p->dev.na==0);}
/* Test-only backend power-off releases otherwise permanent poisoned roots.
 * Production exposes no reset/rearm/free operation for retained owners. */
static void destroy_test_devices(struct platform_device *c,struct platform_device *p){
 for(int i=0;i<2;i++){struct device *d=qpic_lifetimes[i].owner;qpic_lifetimes[i]=(struct qcom_qpic_lifetime){0};if(d)root_device_unregister(d);}
 poweroff_fifos();qpic_poisoned=false;platform_cleanup(c);platform_cleanup(p);assert(owner_count==0&&node_refs==0&&c->dev.refs==1&&p->dev.refs==1);
}
struct get_race {struct qcom_qpic_lifetime *life;pthread_mutex_t lock;pthread_cond_t cond;int entered,release;bool acquired;};
static void *channel_alloc_race(void *arg){
 struct get_race *r=arg;r->acquired=qpic_lifetime_get(r->life);
 assert(pthread_mutex_lock(&r->lock)==0);r->entered=1;pthread_cond_signal(&r->cond);
 while(!r->release)pthread_cond_wait(&r->cond,&r->lock);
 pthread_mutex_unlock(&r->lock);if(r->acquired)qpic_lifetime_put(r->life);return NULL;
}
int main(void){
 for(int mode=0;mode<3;mode++){
  struct platform_device c,p;prepare_platform(&c,false);prepare_platform(&p,true);fail_at=0;
  struct qcom_qpic_lifetime *cl=qcom_qpic_lifetime_create(&c,false),*pl=qcom_qpic_lifetime_create(&p,true);assert(!IS_ERR(cl)&&!IS_ERR(pl));
  struct bam_device b={.dev=&p.dev,.dma_dev=pl->owner,.lifetime=pl};struct bam_chan channel={.bdev=&b};init_list(&channel.desc_list);
  if(mode==0){fifo_fail=1;assert(bam_alloc_chan(&channel.vc.chan)==-ENOMEM&&pl->users==0);fifo_fail=0;}
  assert(bam_alloc_chan(&channel.vc.chan)==0&&pl->users==1&&channel.fifo_virt&&b.active_channels==1);
  if(mode==1){qcom_qpic_lifetime_poison(cl);void *old=channel.fifo_virt;bam_free_chan(&channel.vc.chan);assert(channel.fifo_virt==old&&pl->users==1);assert(bam_alloc_chan(&channel.vc.chan)==-EIO);}
  else{bam_free_chan(&channel.vc.chan);assert(pl->users==0&&!channel.fifo_virt&&b.active_channels==0);}
  destroy_test_devices(&c,&p);
 }
 for(int mode=0;mode<2;mode++)for(int repeat=0;repeat<20;repeat++){
  struct platform_device c,p;prepare_platform(&c,false);prepare_platform(&p,true);fail_at=0;
  struct qcom_qpic_lifetime *cl=qcom_qpic_lifetime_create(&c,false),*pl=qcom_qpic_lifetime_create(&p,true);assert(!IS_ERR(cl)&&!IS_ERR(pl));
  if(mode==1)assert(!qcom_qpic_lifetime_detach(pl));
  struct get_race r={.life=pl,.lock=PTHREAD_MUTEX_INITIALIZER,.cond=PTHREAD_COND_INITIALIZER};pthread_t th;
  assert(pthread_create(&th,NULL,channel_alloc_race,&r)==0);
  pthread_mutex_lock(&r.lock);while(!r.entered)pthread_cond_wait(&r.cond,&r.lock);pthread_mutex_unlock(&r.lock);
  if(mode==0)assert(r.acquired&&qcom_qpic_lifetime_detach(pl));else assert(!r.acquired);
  pthread_mutex_lock(&r.lock);r.release=1;pthread_cond_signal(&r.cond);pthread_mutex_unlock(&r.lock);
  pthread_join(th,NULL);pthread_cond_destroy(&r.cond);pthread_mutex_destroy(&r.lock);
  if(mode==0)assert(qcom_qpic_lifetime_poisoned(cl));
  destroy_test_devices(&c,&p);
 }
 for(int failed=1;failed<=7;failed++){
  struct platform_device c,p;prepare_platform(&c,false);prepare_platform(&p,true);step=0;fail_at=failed;
  struct qcom_qpic_lifetime *l=qcom_qpic_lifetime_create(&c,false);assert(IS_ERR(l));
  fail_at=0;platform_cleanup(&c);platform_cleanup(&p);assert(owner_count==0&&node_refs==0&&c.dev.refs==1);
 }
 for(int order=0;order<4;order++){
  struct platform_device c,p;prepare_platform(&c,false);prepare_platform(&p,true);step=0;fail_at=0;
  struct qcom_qpic_lifetime *cl=qcom_qpic_lifetime_create(&c,false),*pl=qcom_qpic_lifetime_create(&p,true);assert(!IS_ERR(cl)&&!IS_ERR(pl));
  assert(cl->owner->dma_range_map!=c.dev.dma_range_map&&pl->owner->dma_range_map!=p.dev.dma_range_map);
  assert(cl->owner->dma_mask!=c.dev.dma_mask&&cl->owner->dma_mask==&cl->owner->coherent_dma_mask);
  struct bam_device b={.dev=&p.dev,.dma_dev=pl->owner,.lifetime=pl};p.dev.drvdata=&b;
  struct props props={.is_serial_nand=true};struct qcom_nand_controller n={.dev=&c.dev,.dma_dev=cl->owner,.lifetime=cl,.miami_diag_enabled=true,.props=&props};c.dev.drvdata=&n;init_list(&n.host_list);
  int *owned=devm_kzalloc(cl->owner,sizeof(int),0);assert(owned);*owned=0x1234;
  pl->poison_irq=irq_disable_hook;pl->irq_data=&b;assert(qpic_lifetime_get(pl));
  int freed=freed_objects,hw=hardware_calls,irqs=irq_disabled;
  if(order==0){qcom_qpic_lifetime_poison(cl);assert(qcom_nandc_remove(&c)==0);platform_cleanup(&c);assert(bam_dma_remove(&p)==0);platform_cleanup(&p);}
  if(order==1){qcom_qpic_lifetime_poison(cl);assert(bam_dma_remove(&p)==0);platform_cleanup(&p);assert(qcom_nandc_remove(&c)==0);platform_cleanup(&c);}
  if(order==3){struct qcom_nand_host h={0};add(&h.node,&n.host_list);mtd_busy=1;assert(qcom_nandc_remove(&c)==0);mtd_busy=0;platform_cleanup(&c);assert(bam_dma_remove(&p)==0);platform_cleanup(&p);init_list(&n.host_list);}
  if(order==2){assert(bam_dma_remove(&p)==0);platform_cleanup(&p);assert(qcom_qpic_lifetime_poisoned(cl));assert(qcom_nandc_remove(&c)==0);platform_cleanup(&c);}
  assert(*owned==0x1234&&owner_count==2&&freed_objects==freed&&hardware_calls==hw&&irq_disabled==irqs+1);
  assert(bam_dma_irq(0,&b)==IRQ_HANDLED&&hardware_calls==hw); /* late IRQ never queries MMIO */
  assert(!qpic_lifetime_get(pl));assert(IS_ERR(qcom_qpic_lifetime_create(&c,false)));assert(IS_ERR(qcom_qpic_lifetime_create(&p,true)));
  qcom_qpic_lifetime_poison(cl);assert(irq_disabled==irqs+1);qpic_lifetime_put(pl);
  destroy_test_devices(&c,&p);
 }
 /* Healthy unreferenced provider/client remove still destroys owners. */
 struct platform_device c,p;prepare_platform(&c,false);prepare_platform(&p,true);fail_at=0;
 struct qcom_qpic_lifetime *cl=qcom_qpic_lifetime_create(&c,false),*pl=qcom_qpic_lifetime_create(&p,true);
 struct fake_clock k={2,2}; /* ordinary prepare/enable plus healthy lifetime pin */
 struct bam_device b={.dev=&p.dev,.dma_dev=pl->owner,.lifetime=pl,.bamclk=&k};p.dev.drvdata=&b;
 assert(devm_add_action_or_reset(pl->owner,qpic_bam_unpin_clock,&k)==0);
 struct props props={0};struct qcom_nand_controller n={.dev=&c.dev,.dma_dev=cl->owner,.lifetime=cl,.props=&props};c.dev.drvdata=&n;init_list(&n.host_list);
 assert(qcom_nandc_remove(&c)==0&&!qpic_poisoned);platform_cleanup(&c);
 assert(bam_dma_remove(&p)==0&&!qpic_poisoned);platform_cleanup(&p);assert(owner_count==0&&node_refs==0&&k.prepare==0&&k.enable==0);
 puts("PASS actual owner+driver-core cleanup+client/provider remove: separate DMA metadata, OOM cleanup, both poison remove orders, healthy referenced-provider removal, late IRQ no MMIO, repeated requests/reprobe rejected, healthy unreferenced removal unchanged");
}
