/* Execute the complete BAM probe and DMA core registration/unregistration.
 * Hardware, allocation, sysfs channel primitives and scheduler APIs are mocked;
 * the real core's driver-owner dereference and complete control flow are not. */
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <string.h>
struct module { int id; };
struct device_driver { struct module *owner; };
struct dma_parameters { unsigned int max_segment; };
struct device {
    struct device_driver *driver;
    struct dma_parameters *dma_parms;
    struct device *parent;
    void *of_node, *drvdata;
    int refs;
    bool allocation_owner;
};
struct platform_device { struct device dev; struct dma_parameters parms; };
struct list_head { struct list_head *next, *prev; };
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define list_for_each_entry(p,h,m) \
    for (p=container_of((h)->next,__typeof__(*p),m); &p->m!=(h); \
         p=container_of(p->m.next,__typeof__(*p),m))
#define list_for_each_entry_safe(p,n,h,m) \
    for (p=container_of((h)->next,__typeof__(*p),m), \
         n=container_of(p->m.next,__typeof__(*p),m); &p->m!=(h); \
         p=n,n=container_of(n->m.next,__typeof__(*n),m))
static void INIT_LIST_HEAD(struct list_head *h) { h->next=h->prev=h; }
static void list_add_tail_rcu(struct list_head *n, struct list_head *h)
{ n->next=h; n->prev=h->prev; h->prev->next=n; h->prev=n; }
struct dma_device;
struct dma_chan;
struct channel_device { struct device device; struct dma_chan *chan; };
struct dma_chan {
    struct dma_device *device;
    struct list_head device_node;
    struct channel_device *dev;
    void *local;
};
struct dma_device {
    struct device *dev;
    struct module *owner;
    struct list_head channels, global_node;
    unsigned long cap_mask, directions;
    int chancnt, privatecnt, ref, dev_id, chan_ida;
    int residue_granularity, src_addr_widths, dst_addr_widths;
    void *device_prep_dma_memcpy, *device_prep_dma_xor;
    void *device_prep_dma_xor_val, *device_prep_dma_pq;
    void *device_prep_dma_pq_val, *device_prep_dma_memset;
    void *device_prep_dma_interrupt, *device_prep_dma_cyclic;
    void *device_prep_interleaved_dma, *device_release;
    void *device_tx_status, *device_issue_pending;
    void *device_alloc_chan_resources, *device_free_chan_resources;
    void *device_prep_slave_sg, *device_config, *device_pause;
    void *device_resume, *device_terminate_all;
};
struct qcom_qpic_lifetime { struct device *owner; bool poisoned; void (*poison_irq)(void *); void *irq_data; };
struct bam_chan { struct { struct dma_chan chan; int task; } vc; };
struct bam_device {
    struct device *dev, *dma_dev;
    struct qcom_qpic_lifetime *lifetime;
    struct dma_device common;
    void *layout, *regs, *bamclk;
    int irq, task;
    unsigned int ee, num_channels, num_ees, config_pipe_trust_reg;
    bool controlled_remotely, powered_remotely, is_bam_lite;
    struct bam_chan *channels;
};
struct of_device_id { void *data; };
static struct of_device_id match = { (void *)1 };
static struct qcom_qpic_lifetime life;
static struct device owner;
static struct dma_parameters owner_parms;
static struct device *original;
static bool qualified;
static int id_error, channel_error, channel_calls, unregister_calls;
static int clock_refs, irq_refs, list_lock, dma_list_mutex, dma_ida;
static int dmaengine_ref_count, debug_registered;
static struct list_head dma_device_list;
static void *allocations[16];
static int allocation_count;
#define GFP_KERNEL 0
#define IRQF_TRIGGER_HIGH 0
#define BAM_FIFO_SIZE 32768
#define BAM_DMA_AUTOSUSPEND_DELAY 100
#define DMA_RESIDUE_GRANULARITY_SEGMENT 1
#define DMA_SLAVE_BUSWIDTH_4_BYTES 4
#define BIT(x) (1UL<<(x))
enum { DMA_MEMCPY, DMA_XOR, DMA_XOR_VAL, DMA_PQ, DMA_PQ_VAL, DMA_MEMSET,
       DMA_INTERRUPT, DMA_CYCLIC, DMA_INTERLEAVE, DMA_PRIVATE, DMA_ASYNC_TX,
       DMA_SLAVE, DMA_DEV_TO_MEM, DMA_MEM_TO_DEV };
#define dma_cap_zero(m) ((m)=0)
#define dma_cap_set(c,m) ((m)|=BIT(c))
#define dma_has_cap(c,m) (!!((m)&BIT(c)))
#define __stringify(x) #x
#define pr_err(...) ((void)0)
#define dev_err(...) ((void)0)
#define dev_dbg(...) ((void)0)
#define IS_ERR(p) ((intptr_t)(p)<0 && (intptr_t)(p)>-4096)
#define PTR_ERR(p) ((int)(intptr_t)(p))
static void mutex_lock(int *m) { (void)m; assert(!list_lock++); }
static void mutex_unlock(int *m) { (void)m; assert(--list_lock==0); }
static void kref_init(int *r) { *r=1; }
static void ida_init(int *i) { *i=0; }
static void ida_free(int *i,int n) { (void)i; (void)n; }
static bool device_has_all_tx_types(struct dma_device *d) { (void)d; return false; }
static int get_dma_id(struct dma_device *d) { d->dev_id=7; return id_error; }
static int dma_chan_get(struct dma_chan *c) { (void)c; return 0; }
static void dma_channel_rebalance(void) { }
static void dmaengine_debug_register(struct dma_device *d)
{ (void)d; debug_registered++; }
static void dmaengine_debug_unregister(struct dma_device *d)
{ (void)d; debug_registered--; }
static void dma_device_put(struct dma_device *d) { assert(d->ref==1); d->ref--; }
static int __dma_async_device_channel_register(struct dma_device *d,struct dma_chan *c)
{
    if (++channel_calls==channel_error) return -ENOMEM;
    c->dev=calloc(1,sizeof(*c->dev)); assert(c->dev);
    c->dev->device.parent=d->dev;
    c->dev->chan=c;
    d->dev->refs++;
    c->local=malloc(1); assert(c->local);
    d->chancnt++;
    return 0;
}
static void device_unregister(struct device *d)
{
    assert(d->parent==original);
    assert(d->parent->refs>1);
    d->parent->refs--;
    free(container_of(d,struct channel_device,device));
    unregister_calls++;
}
#define free_percpu(p) free(p)
static void __dma_async_device_channel_unregister(struct dma_device *d,struct dma_chan *c)
{
    device_unregister(&c->dev->device);
    free_percpu(c->local);
    c->dev=NULL; c->local=NULL; d->chancnt--;
}
/* ACTUAL_DMA_CORE */
static struct qcom_qpic_lifetime *qcom_qpic_lifetime_create(struct platform_device *p,bool provider)
{
    assert(provider);
    original=&p->dev;
    if (!qualified) return NULL;
    assert(owner.driver==NULL);
    original->refs++; /* Actual owner get_device is covered by lifetime fixture. */
    life.owner=&owner;
    return &life;
}
static struct device *qcom_qpic_lifetime_device(struct qcom_qpic_lifetime *l)
{ return l->owner; }
static bool qcom_qpic_lifetime_detach(struct qcom_qpic_lifetime *l)
{ return l && l->poisoned; }
static void *devm_kzalloc(struct device *d,size_t n,int flags)
{
    (void)flags;
    assert(d==(qualified?&owner:original));
    void *p=calloc(1,n); assert(p && allocation_count<16);
    allocations[allocation_count++]=p;
    return p;
}
static void *devm_kcalloc(struct device *d,size_t n,size_t size,int flags)
{ return devm_kzalloc(d,n*size,flags); }
static void *platform_get_resource(struct platform_device *p,int type,int i)
{ (void)p; (void)type; (void)i; return (void *)1; }
#define IORESOURCE_MEM 0
static void *devm_ioremap_resource(struct device *d,void *r)
{ assert(d==&owner); return r; }
static void *devm_platform_ioremap_resource(struct platform_device *p,int i)
{ (void)p; (void)i; return (void *)1; }
static const struct of_device_id *of_match_node(void *table,void *node)
{ (void)table; (void)node; return &match; }
static void *bam_of_match;
static int platform_get_irq(struct platform_device *p,int i)
{ (void)p; (void)i; return 3; }
static int of_property_read_u32(void *np,const char *name,unsigned int *value)
{ (void)np; (void)name; *value=0; return 0; }
static bool of_property_read_bool(void *np,const char *name)
{ (void)np; (void)name; return false; }
static void *devm_clk_get_optional(struct device *d,const char *name)
{ assert(d==(qualified?&owner:original)); (void)name; return (void *)1; }
static int clk_prepare_enable(void *clk) { (void)clk; clock_refs++; return 0; }
static void clk_disable_unprepare(void *clk) { (void)clk; clock_refs--; }
static int bam_init(struct bam_device *b) { b->num_channels=2; return 0; }
static void tasklet_setup(int *task,void (*fn)(void)) { (void)task; (void)fn; }
static void dma_tasklet(void) { }
static void tasklet_kill(int *task) { (void)task; }
static void bam_channel_init(struct bam_device *b,struct bam_chan *c,int i)
{
    (void)i; c->vc.chan.device=&b->common;
    list_add_tail_rcu(&c->vc.chan.device_node,&b->common.channels);
}
static void bam_dma_irq(void) { }
static int devm_request_irq(struct device *d,int irq,void (*fn)(void),int flags,const char *name,void *data)
{ (void)irq; (void)fn; (void)flags; (void)name; (void)data; assert(d==(qualified?&owner:original)); irq_refs++; return 0; }
static void devm_free_irq(struct device *d,int irq,void *data)
{ (void)d; (void)irq; (void)data; irq_refs--; }
static int devm_add_action_or_reset(struct device *d,void (*fn)(void *),void *data)
{ (void)fn; (void)data; assert(d==&owner); return 0; }
static void qpic_bam_unpin_clock(void *data) { (void)data; }
static void qpic_bam_disable_irq(void *data) { (void)data; }
/* Probe stores these two fields in the actual lifetime record. */
static int qpic_lifetime_lock;
static int dma_set_max_seg_size(struct device *d,unsigned int size)
{ assert(d->dma_parms); d->dma_parms->max_segment=size; return 0; }
static void platform_set_drvdata(struct platform_device *p,void *data) { p->dev.drvdata=data; }
static void fake_op(void) { }
#define bam_alloc_chan fake_op
#define bam_free_chan fake_op
#define bam_prep_slave_sg fake_op
#define bam_slave_config fake_op
#define bam_pause fake_op
#define bam_resume fake_op
#define bam_dma_terminate_all fake_op
#define bam_issue_pending fake_op
#define bam_tx_status fake_op
static int of_error;
static int of_dma_controller_register(void *np,void *xlate,struct dma_device *d)
{ (void)np; (void)xlate; assert(d->dev==original); return of_error; }
static void *bam_dma_xlate;
static void pm_runtime_irq_safe(struct device *d) { assert(d==original); }
static void pm_runtime_set_autosuspend_delay(struct device *d,int delay) { assert(d==original); (void)delay; }
static void pm_runtime_use_autosuspend(struct device *d) { assert(d==original); }
static void pm_runtime_mark_last_busy(struct device *d) { assert(d==original); }
static void pm_runtime_set_active(struct device *d) { assert(d==original); }
static void pm_runtime_enable(struct device *d) { assert(d==original); }
/* ACTUAL_PROVIDER_PROBE */
static void reset_fixture(struct platform_device *p,struct device_driver *driver)
{
    memset(p,0,sizeof(*p)); memset(&owner,0,sizeof(owner));
    memset(&owner_parms,0,sizeof(owner_parms)); memset(&life,0,sizeof(life));
    p->dev.driver=driver; p->dev.dma_parms=&p->parms; p->dev.refs=1;
    owner.dma_parms=&owner_parms; owner.allocation_owner=true; owner.refs=1;
    INIT_LIST_HEAD(&dma_device_list);
    channel_calls=unregister_calls=debug_registered=clock_refs=irq_refs=0;
    id_error=channel_error=of_error=0; allocation_count=0;
}
static void cleanup_allocations(void)
{ while(allocation_count) free(allocations[--allocation_count]); }
int main(int argc,char **argv)
{
    assert(argc==2); bool negative=atoi(argv[1]);
    struct module module={9}; struct device_driver driver={&module};
    struct platform_device p;
    qualified=true; reset_fixture(&p,&driver);
    int ret=bam_dma_probe(&p);
    if (negative) { fprintf(stderr,"UNEXPECTED_SAFE_REGISTRATION\n"); abort(); }
    assert(ret==0 && owner.driver==NULL && owner_parms.max_segment==BAM_FIFO_SIZE);
    struct bam_device *b=p.dev.drvdata;
    assert(b && b->dma_dev==&owner && b->common.dev==&p.dev);
    assert(b->common.owner==&module && p.parms.max_segment==BAM_FIFO_SIZE);
    assert(p.dev.refs==4 && debug_registered==1 && clock_refs==2);
    /* The platform object remains pinned; the core captured module identity.
     * Driver cleanup may clear driver without changing allocation ownership. */
    p.dev.driver=NULL;
    assert(dma_chan_to_owner(&b->channels[0].vc.chan)==&module);
    assert(b->dma_dev==&owner && owner.driver==NULL);
    dma_async_device_unregister(&b->common);
    assert(p.dev.refs==2 && debug_registered==0 && unregister_calls==2);
    cleanup_allocations();
    /* A built-in real driver legitimately has a NULL module owner. */
    driver.owner=NULL; reset_fixture(&p,&driver);
    assert(bam_dma_probe(&p)==0);
    b=p.dev.drvdata;
    assert(b->common.owner==NULL && owner.driver==NULL);
    p.dev.driver=NULL;
    assert(dma_chan_to_owner(&b->channels[0].vc.chan)==NULL);
    dma_async_device_unregister(&b->common);
    assert(p.dev.refs==2); cleanup_allocations(); driver.owner=&module;
    /* Ordinary unqualified provider keeps its original identity and owner. */
    qualified=false; reset_fixture(&p,&driver);
    assert(bam_dma_probe(&p)==0);
    b=p.dev.drvdata;
    assert(b->dma_dev==&p.dev && b->common.dev==&p.dev && p.dev.refs==3);
    dma_async_device_unregister(&b->common);
    assert(p.dev.refs==1); cleanup_allocations();
    /* Actual core registration failure and provider OF-registration unwind. */
    qualified=true; reset_fixture(&p,&driver); id_error=-ENOMEM;
    assert(bam_dma_probe(&p)==-ENOMEM && debug_registered==0 && irq_refs==0);
    cleanup_allocations();
    reset_fixture(&p,&driver); channel_error=2;
    assert(bam_dma_probe(&p)==-ENOMEM && debug_registered==0 && unregister_calls==1);
    assert(p.dev.refs==2); cleanup_allocations();
    reset_fixture(&p,&driver); of_error=-EINVAL;
    assert(bam_dma_probe(&p)==-EINVAL && debug_registered==0 && unregister_calls==2);
    cleanup_allocations();
    puts("PASS actual BAM probe + complete DMA core register/unregister: real driver identity, independent allocation owner, stored module owner after driver clear, channel-parent refs, ordinary-provider control and error unwind");
    return 0;
}
