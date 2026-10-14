from pathlib import Path
import subprocess, tempfile, argparse

root = Path(__file__).parent
parser=argparse.ArgumentParser();parser.add_argument('--driver',type=Path,default=root/'qcom_nandc.diagnostic.c');args=parser.parse_args()
source = args.driver.read_text()
def function(name):
    signature = 'static int ' if name == 'parse_read_errors' else 'static void '
    start=source.index(signature+name+'(')
    # Skip the forward declaration.
    if source.index(';',start)<source.index('{',start):
        start=source.index(signature+name+'(',start+1)
    brace=source.index('{',start); depth=1; end=brace+1
    while depth:
        depth += (source[end]=='{')-(source[end]=='}'); end+=1
    return source[start:end]

struct=source[source.index('struct miami_nand_diag {'):source.index('struct qcom_nand_controller {')]
harness='''
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
#include <assert.h>
#include <stdio.h>
typedef uint8_t u8; typedef uint32_t u32; typedef uint64_t u64;
#define MIAMI_DIAG_CWS 4
#define MIAMI_DIAG_REGS 14
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define BIT(i) (1u<<(i))
#define DMA_COMPLETE 0
#define spin_lock_irqsave(l,f) ((void)(l),(f)=0)
#define spin_unlock_irqrestore(l,f) ((void)(l),(void)(f))
#define dev_err(...) ((void)0)
''' + struct + '''
struct qcom_nand_controller {
 bool miami_diag_enabled, miami_diag_claimed, miami_diag_ready;
 unsigned int miami_diag_seen;
 int miami_diag_lock;
 struct miami_nand_diag miami_diag;
 u32 reg_read_buf[12];
};
struct nand_ecc_ctrl { int steps, size, bytes; unsigned int strength; };
struct nand_chip { struct nand_ecc_ctrl ecc; };
struct qcom_nand_host { struct nand_chip chip; int cw_data; bool bch_enabled; };
struct mtd_info { struct { u32 failed, corrected; } ecc_stats; };
static struct mtd_info mtd;
static int erased_failure;
#define le32_to_cpu(x) (x)
#define FS_OP_ERR 16
#define FS_MPU_ERR 256
#define BS_UNCORRECTABLE_BIT 256
#define BS_CORRECTABLE_ERR_MSK 31
#define ERASED_CW 3
struct read_stats { u32 flash, buffer, erased_cw; };
static struct mtd_info *nand_to_mtd(struct nand_chip *c) { (void)c;return &mtd; }
static void nandc_read_buffer_sync(struct qcom_nand_controller *n,bool b) { (void)n;(void)b; }
static bool qcom_nandc_is_last_cw(struct nand_ecc_ctrl *e,int i) { return i==e->steps-1; }
static bool erased_chunk_check_and_fixup(u8 *d,int n) { (void)d;(void)n;return false; }
#define max(a,b) ((a)>(b)?(a):(b))
static int check_for_erased_page(struct qcom_nand_host *h,u8 *d,u8 *o,
 unsigned long c,int p,unsigned int b) {
 (void)h;(void)d;(void)o;(void)c;(void)p;(void)b;
 if(erased_failure)mtd.ecc_stats.failed++;
 return 0;
}
static struct qcom_nand_controller controller;
static int feature_calls, feature_error, take_calls;
static struct qcom_nand_controller *get_qcom_nand_controller(void *p) {
 (void)p; return &controller;
}
static int qcom_serial_get_feature(struct qcom_nand_controller *n,
 struct qcom_nand_host *h, u32 address) {
 (void)n;(void)h;feature_calls++;
 return feature_error ? -ETIMEDOUT : (int)address<<8;
}
static void miami_diag_take(struct qcom_nand_host *h,
 struct miami_nand_diag *d, int page,const char *reason,bool valid) {
 (void)h;(void)valid; take_calls++;memset(d,0,sizeof(*d));
 d->page=page;d->reason=reason;
 for(int i=0;i<3;i++)d->feature[i]=-ENODATA;
}
''' + function('miami_diag_publish') + '\n' + function('miami_diag_header') + '\n' + function('parse_read_errors') + '''
static void reset(void) {
 memset(&controller,0,sizeof(controller)); controller.miami_diag_enabled=true;
 feature_calls=feature_error=take_calls=erased_failure=0;memset(&mtd,0,sizeof(mtd));
}
int main(void) {
 struct qcom_nand_host host={0};
 const u8 valid[]={85,66,73,35}, blank[]={255,255,255,255};
 struct miami_nand_diag d={.page=100,.reason="test"};
 reset();
 miami_diag_header(&host,blank,1024*64,0);
 assert(!controller.miami_diag_ready && !feature_calls && !take_calls);
 miami_diag_header(&host,valid,1024*64,0);
 assert(controller.miami_diag_seen);
 miami_diag_header(&host,blank,1024*64+1,0);
 assert(!controller.miami_diag_ready);
 miami_diag_header(&host,blank,1024*64,0);
 assert(controller.miami_diag_ready && feature_calls==3 && take_calls==1);
 assert(controller.miami_diag.header==0xffffffff);
 assert(controller.miami_diag.feature[1]==0xb0);
 miami_diag_header(&host,blank,6*64,0);
 miami_diag_publish(&host,&d,true);
 assert(feature_calls==3 && controller.miami_diag.page==1024*64);
 reset();feature_error=1;
 miami_diag_publish(&host,&d,true);
 assert(feature_calls==1 && controller.miami_diag_ready);
 reset(); d.dma_cookie[1]=3;d.dma_state[1]=1;
 miami_diag_publish(&host,&d,true);
 assert(feature_calls==0 && controller.miami_diag_ready);
 reset();d.dma_state[1]=DMA_COMPLETE;
 miami_diag_publish(&host,&d,false);
 assert(feature_calls==0 && controller.miami_diag_ready);
 reset();controller.miami_diag_enabled=false;
 miami_diag_header(&host,valid,6*64,0);
 miami_diag_publish(&host,&d,true);
 assert(!controller.miami_diag_ready && !feature_calls);
 reset();host.chip.ecc.steps=4;host.chip.ecc.size=512;host.chip.ecc.bytes=16;
 host.cw_data=516;host.bch_enabled=true;
 controller.reg_read_buf[0]=FS_OP_ERR;controller.reg_read_buf[1]=BS_UNCORRECTABLE_BIT;
 assert(parse_read_errors(&host,NULL,NULL,500)==0);
 assert(!controller.miami_diag_ready && !feature_calls); /* recovered erased page */
 reset();controller.reg_read_buf[0]=FS_OP_ERR;controller.reg_read_buf[1]=BS_UNCORRECTABLE_BIT;
 erased_failure=1;
 assert(parse_read_errors(&host,NULL,NULL,501)==0);
 assert(controller.miami_diag_ready && controller.miami_diag.result==-EBADMSG && feature_calls==3);
 reset();controller.reg_read_buf[0]=FS_MPU_ERR;
 assert(parse_read_errors(&host,NULL,NULL,502)==-EIO);
 assert(controller.miami_diag_ready && controller.miami_diag.result==-EIO);
 reset();controller.reg_read_buf[0]=FS_OP_ERR;controller.reg_read_buf[1]=BS_UNCORRECTABLE_BIT;
 controller.reg_read_buf[2]=ERASED_CW;
 assert(parse_read_errors(&host,NULL,NULL,503)==0);
 assert(!controller.miami_diag_ready && !feature_calls);
 puts("PASS: actual parse_read_errors hooks: confirmed uncorrectable, operational error, erased-page false-positive suppression");
 puts("PASS: actual driver header observer and publisher; blank/unqualified skip, boundary, first-record retention, bounded failed GET, no GET for unfinished DMA, disabled gate");
}
'''
with tempfile.TemporaryDirectory() as tmp:
    c=Path(tmp)/'test.c';exe=Path(tmp)/'test';c.write_text(harness)
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-o',str(exe),str(c)],check=True)
    subprocess.run([str(exe)],check=True)
