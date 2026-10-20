from pathlib import Path
import argparse, subprocess, tempfile
p = argparse.ArgumentParser()
p.add_argument('--driver', type=Path, required=True)
a = p.parse_args()
s = a.driver.read_text()
start = s.index('static int submit_descs(')
end = s.index('\nstatic void free_descs(', start)
actual = s[start:end]
assert 'try_wait_for_completion' not in actual
assert 'miami_probe_poll_deadline' not in actual
prefix = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <errno.h>
typedef int dma_cookie_t;
struct dma_chan {int unused;};
struct dma_async_tx_descriptor {struct dma_chan *chan;void (*callback)(void *);void *callback_param;};
struct desc_info {struct dma_async_tx_descriptor *dma_desc;};
struct bam_transaction {
 int rx_sgl_pos,rx_sgl_start,tx_sgl_pos,tx_sgl_start,cmd_sgl_pos,cmd_sgl_start;
 int sts_sgl_pos,sts_sgl_start,txn_done;
 struct dma_async_tx_descriptor *last_cmd_desc,*last_data_desc;
 bool wait_second_completion;
};
struct props {bool is_bam,qpic_v2;};
struct qcom_nand_controller {
 struct bam_transaction *bam_txn;struct props *props;
 struct dma_chan *rx_chan,*tx_chan,*cmd_chan,*sts_chan,*chan;
 int desc_list,miami_diag_cookie[4];bool miami_diag_enabled,miami_dma_unsafe;
};
static struct dma_async_tx_descriptor descriptor;
static struct desc_info entry = {&descriptor};
static int prepare_result,wait_result,wait_calls,issued,sync_result;
static unsigned long observed_timeout;
#define DMA_PREP_INTERRUPT 1
#define DMA_PREP_CMD 2
#define DMA_COMPLETE 0
#define QPIC_NAND_COMPLETION_TIMEOUT 2000
#define list_for_each_entry(d,l,m) for((void)(l), d=&entry;d;d=NULL)
static int prepare_bam_async_desc(struct qcom_nand_controller *n,struct dma_chan *c,int f){(void)n;(void)c;(void)f;return prepare_result;}
static int dmaengine_submit(struct dma_async_tx_descriptor *d){(void)d;return 123;}
static void qpic_bam_dma_done(void *p){(void)p;}
static void dma_async_issue_pending(struct dma_chan *c){(void)c;issued++;}
static int wait_for_completion_timeout(int *done,unsigned long timeout){(void)done;wait_calls++;observed_timeout=timeout;return wait_result;}
static int dma_sync_wait(struct dma_chan *c,int cookie){(void)c;(void)cookie;return sync_result;}
'''
suffix = r'''
int main(void){
 struct props props={.is_bam=true};struct bam_transaction bam={.cmd_sgl_pos=1,.last_cmd_desc=&descriptor};
 struct dma_chan channel;struct qcom_nand_controller n={.props=&props,.bam_txn=&bam,.cmd_chan=&channel,.miami_diag_enabled=true};
 descriptor.chan=&channel;prepare_result=0;wait_result=1;
 assert(submit_descs(&n)==0&&wait_calls==1&&observed_timeout==2000&&!n.miami_dma_unsafe);
 assert(n.miami_diag_cookie[0]==123&&issued==3);
 wait_result=0;assert(submit_descs(&n)==-ETIMEDOUT&&observed_timeout==2000&&n.miami_dma_unsafe);
 /* This is a cached safety fact, not a claim that DMA has been drained. */
 n.miami_dma_unsafe=false;prepare_result=-ENOMEM;wait_calls=issued=0;
 assert(submit_descs(&n)==-ENOMEM&&!n.miami_dma_unsafe&&wait_calls==0&&issued==0);
 prepare_result=0;props.is_bam=false;sync_result=1;
 assert(submit_descs(&n)==-ETIMEDOUT);
 puts("PASS actual submit_descs keeps normal bounded BAM/ADM completion and errors; no short-return readiness transport path; cached timeout blocks the optional probe only, not a DMA-drain claim");
}
'''
with tempfile.TemporaryDirectory() as tmp:
 c=Path(tmp)/'test.c';exe=Path(tmp)/'test';c.write_text(prefix+actual+suffix)
 subprocess.run(['cc','-Wall','-Wextra','-Werror','-o',str(exe),str(c)],check=True)
 subprocess.run([str(exe)],check=True)
