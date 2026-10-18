from pathlib import Path
import subprocess, tempfile, argparse

root = Path(__file__).parent
parser=argparse.ArgumentParser();parser.add_argument('--driver',type=Path,default=root/'qcom_nandc.diagnostic.c');parser.add_argument('--expect-old-failure',action='store_true');args=parser.parse_args()
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
#include <stdarg.h>
#include <stdlib.h>
#include <setjmp.h>
typedef uint8_t u8; typedef uint32_t u32; typedef uint64_t u64;
#define MIAMI_DIAG_CWS 4
#define MIAMI_DIAG_REGS 14
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define BIT(i) (1u<<(i))
#define DMA_COMPLETE 0
#define spin_lock_irqsave(l,f) ((void)(l),(f)=0)
#define spin_unlock_irqrestore(l,f) ((void)(l),(void)(f))
static int raw_end_seen, emitted_regs, emitted_cws, emitted_dma;
static void diagnostic_log(const char *fmt, ...) {
 if(strstr(fmt,"MIAMI_NAND_REG "))emitted_regs++;
 if(strstr(fmt,"MIAMI_NAND_CW "))emitted_cws++;
 if(strstr(fmt,"MIAMI_NAND_DMA "))emitted_dma++;
 if(strstr(fmt,"MIAMI_NAND_END "))raw_end_seen++;
 if(getenv("MIAMI_DIAG_PRINT_FIXTURE")) {va_list ap;va_start(ap,fmt);vprintf(fmt,ap);va_end(ap);}
}
#define dev_err(dev,fmt,...) do { (void)(dev); diagnostic_log(fmt, ##__VA_ARGS__); } while (0)
''' + struct + '''
struct qcom_nand_controller {
 void *dev;
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
static int feature_calls, feature_error, take_calls, feature_block;
static jmp_buf feature_stall;
static struct qcom_nand_controller *get_qcom_nand_controller(void *p) {
 (void)p; return &controller;
}
static int qcom_serial_get_feature(struct qcom_nand_controller *n,
 struct qcom_nand_host *h, u32 address) {
 (void)h;
 assert(n->miami_diag_ready && "RAW_CACHE_BEFORE_FEATURE");
 assert(raw_end_seen==1 && emitted_regs==14 && emitted_cws==4 && emitted_dma==4 && "RAW_EXPORT_COMPLETE_BEFORE_FEATURE");
 assert(!n->miami_diag.features_complete);
 feature_calls++;
 if(feature_block)longjmp(feature_stall,1);
 return feature_error ? -ETIMEDOUT : (int)address<<8;
}
static void miami_diag_take(struct qcom_nand_host *h,
 struct miami_nand_diag *d, int page,const char *reason,bool valid) {
 (void)h;(void)valid; take_calls++;memset(d,0,sizeof(*d));
 d->page=page;d->reason=reason;
 for(int i=0;i<3;i++)d->feature[i]=-ENODATA;
}
''' + (function('miami_diag_emit')+'\n' if 'static void miami_diag_emit(' in source else '') + function('miami_diag_publish') + '\n' + function('miami_diag_header') + '\n' + function('parse_read_errors') + '''
static void reset(void) {
 memset(&controller,0,sizeof(controller)); controller.miami_diag_enabled=true;
 feature_calls=feature_error=take_calls=erased_failure=feature_block=0;raw_end_seen=emitted_regs=emitted_cws=emitted_dma=0;memset(&mtd,0,sizeof(mtd));
}
int main(void) {
 struct qcom_nand_host host={0};
 const u8 valid[]={85,66,73,35}, blank[]={255,255,255,255};
 struct miami_nand_diag d={.ns=123456789,.page=100,.reason="synthetic_offdevice_test"};
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
 reset();feature_block=1;
 if(setjmp(feature_stall)==0)miami_diag_publish(&host,&d,true);
 assert(controller.miami_diag_ready && raw_end_seen==1 && feature_calls==1);
 assert(!controller.miami_diag.features_complete);
 miami_diag_publish(&host,&d,true);assert(feature_calls==1);
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
 puts("PASS: raw cache and complete register/codeword/DMA export precede optional GET, including a non-returning feature callback");
 puts("PASS: actual parse_read_errors hooks: confirmed uncorrectable, operational error, erased-page false-positive suppression");
 puts("PASS: actual driver header observer and publisher; blank/unqualified skip, boundary, first-record retention, bounded failed GET, no GET for unfinished DMA, disabled gate");
}
'''
if 'features_complete' not in struct:
    harness=harness.replace(' assert(!n->miami_diag.features_complete);','').replace(' assert(!controller.miami_diag.features_complete);','')
with tempfile.TemporaryDirectory() as tmp:
    c=Path(tmp)/'test.c';exe=Path(tmp)/'test';c.write_text(harness)
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-o',str(exe),str(c)],check=True)
    result=subprocess.run([str(exe)],text=True,capture_output=True)
    if args.expect_old_failure:
        assert result.returncode!=0 and 'RAW_CACHE_BEFORE_FEATURE' in result.stderr,(result.stdout,result.stderr)
        print('PASS actual deployed publisher negative: optional feature runs before raw cache/export')
    else:
        assert result.returncode==0,(result.stdout,result.stderr)
        print(result.stdout,end='')
