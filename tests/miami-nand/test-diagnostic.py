from pathlib import Path
import subprocess, tempfile, argparse

root = Path(__file__).parent
parser=argparse.ArgumentParser();parser.add_argument('--driver',type=Path,default=root/'qcom_nandc.diagnostic.c');parser.add_argument('--expect-old-failure',action='store_true');args=parser.parse_args()
source = args.driver.read_text()
def function(name):
    signature = 'static ssize_t ' if name == 'miami_first_failure_show' else 'static int ' if name == 'parse_read_errors' else 'static void '
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
#include <sys/types.h>
#include <limits.h>
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
struct dma_chan { int unused; };
struct bam_transaction { unsigned int bam_ce_pos, cmd_sgl_pos, rx_sgl_pos, tx_sgl_pos, sts_sgl_pos; };
struct qcom_nandc_props { unsigned int dev_cmd_reg_start; };
struct qcom_nand_controller {
 void *dev, *iomacro_clk;
 const struct qcom_nandc_props *props;
 struct dma_chan *cmd_chan, *rx_chan, *tx_chan, *sts_chan;
 struct bam_transaction *bam_txn;
 u32 *status_buf;
 unsigned int max_cwperpage;
 unsigned long miami_diag_clock_hz;
 int miami_diag_cookie[4];
 bool miami_diag_enabled, miami_diag_claimed, miami_diag_ready;
 unsigned int miami_diag_seen;
 int miami_diag_lock;
 struct miami_nand_diag miami_diag;
 u32 reg_read_buf[12];
};
struct nand_ecc_ctrl { int steps, size, bytes; unsigned int strength; };
struct nand_chip { struct nand_ecc_ctrl ecc; };
struct qcom_nand_host { struct nand_chip chip; int cw_data, last_command; bool bch_enabled; };
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

static struct qcom_nand_controller *get_qcom_nand_controller(void *p) {
 (void)p; return &controller;
}
static void forbidden(const char *operation) {
 fprintf(stderr,"FORBIDDEN_DIAGNOSTIC_HARDWARE:%s\\n",operation);abort();
}
static unsigned long __attribute__((unused)) clk_get_rate(void *c) {
 (void)c;forbidden("clock-provider");return 0;
}
static u32 __attribute__((unused)) nandc_read(struct qcom_nand_controller *n,unsigned int r) {
 (void)n;(void)r;forbidden("controller-MMIO");return 0;
}
static int __attribute__((unused)) dma_async_is_tx_complete(struct dma_chan *c,int cookie,void *a,void *b) {
 (void)c;(void)cookie;(void)a;(void)b;forbidden("DMA-provider");return 0;
}
static int __attribute__((unused)) qcom_serial_get_feature(struct qcom_nand_controller *n,
 struct qcom_nand_host *h, u32 address) {
 (void)n;(void)h;(void)address;feature_calls++;forbidden("GET_FEATURE");return 0;
}
static u64 ktime_get_boottime_ns(void) { return 123456789; }
#define dev_cmd_reg_addr(n,reg) ((n)->props->dev_cmd_reg_start+(reg))
#define NAND_FLASH_CMD 0
#define NAND_ADDR0 4
#define NAND_ADDR1 8
#define NAND_FLASH_STATUS 0x14
#define NAND_BUFFER_STATUS 0x18
#define NAND_DEV0_CFG0 0x20
#define NAND_DEV0_CFG1 0x24
#define NAND_DEV0_ECC_CFG 0x28
#define NAND_CTRL 0xf00
#define NAND_VERSION 0xf08
#define NAND_ERASED_CW_DETECT_STATUS 0xec
#define NAND_FLASH_SPI_CFG 0xc0
#define NAND_QSPI_MSTR_CONFIG 0xf04
#define NAND_FLASH_FEATURES 0xf0
''' + function('miami_diag_take').replace('miami_diag_take(', 'miami_diag_take_actual(',1) + '''
static void miami_diag_take(struct qcom_nand_host *h,
 struct miami_nand_diag *d,int page,const char *reason,bool valid) {
 take_calls++;miami_diag_take_actual(h,d,page,reason,valid);
}
static void *dev_get_drvdata(void *dev) { (void)dev;return &controller; }
struct device { int unused; };struct device_attribute { int unused; };
#define READ_ONCE(x) (x)
static int sysfs_emit_at(char *buf,int at,const char *format,...) {
 va_list ap;va_start(ap,format);int n=vsnprintf(buf+at,4096-at,format,ap);va_end(ap);assert(n>=0 && n<4096-at);return n;
}
#define sysfs_emit(buf,...) sysfs_emit_at(buf,0,__VA_ARGS__)
''' + function('miami_first_failure_show').replace('struct device_attribute *attr,','struct device_attribute *attr __attribute__((unused)),') + '\n' + (function('miami_diag_emit')+'\n' if 'static void miami_diag_emit(' in source else '') + function('miami_diag_publish') + '\n' + function('miami_diag_header') + '\n' + function('parse_read_errors') + '''
static void reset(void) {
 memset(&controller,0,sizeof(controller)); controller.miami_diag_enabled=true;
 controller.miami_diag_clock_hz=24000000;controller.max_cwperpage=4;
 feature_calls=feature_error=take_calls=erased_failure=feature_block=0;raw_end_seen=emitted_regs=emitted_cws=emitted_dma=0;memset(&mtd,0,sizeof(mtd));
}
int main(void) {
 struct qcom_nand_host host={0};
 const u8 valid[]={85,66,73,35}, blank[]={255,255,255,255};
 struct miami_nand_diag d={.ns=123456789,.page=100,.reason="synthetic_offdevice_test"};
 reset();
 host.last_command=17;
 controller.miami_diag_cookie[0]=91;
 miami_diag_take(&host,&d,77,"read_dma_failure",false);
 assert(d.hz==24000000 && d.command==17 && d.page==77 && !d.status_valid);
 assert(d.dma_cookie[0]==91);
 for(int i=0;i<4;i++)assert(d.dma_state[i]==-ENODATA);
 for(int i=0;i<14;i++)assert(d.regs[i]==0);
 for(int i=0;i<3;i++)assert(d.feature[i]==-ENODATA);
 reset();
 miami_diag_header(&host,blank,1024*64,0);
 assert(!controller.miami_diag_ready && !feature_calls && !take_calls);
 miami_diag_header(&host,valid,1024*64,0);
 assert(controller.miami_diag_seen);
 miami_diag_header(&host,blank,1024*64+1,0);
 assert(!controller.miami_diag_ready);
 miami_diag_header(&host,blank,1024*64,0);
 assert(controller.miami_diag_ready && feature_calls==0 && take_calls==1);
 assert(controller.miami_diag.header==0xffffffff);
 assert(controller.miami_diag.feature[1]==-ENODATA);
 miami_diag_header(&host,blank,6*64,0);
 miami_diag_publish(&host,&d,true);
 assert(feature_calls==0 && controller.miami_diag.page==1024*64);
 reset();feature_block=1;
 miami_diag_publish(&host,&d,true);
 assert(controller.miami_diag_ready && raw_end_seen==1 && feature_calls==0);
 assert(!controller.miami_diag.features_complete);
 miami_diag_publish(&host,&d,true);assert(feature_calls==0);
 reset();feature_error=1;
 miami_diag_publish(&host,&d,true);
 assert(feature_calls==0 && controller.miami_diag_ready);
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
 assert(controller.miami_diag_ready && controller.miami_diag.result==-EBADMSG && feature_calls==0);
 reset();controller.reg_read_buf[0]=FS_MPU_ERR;
 assert(parse_read_errors(&host,NULL,NULL,502)==-EIO);
 assert(controller.miami_diag_ready && controller.miami_diag.result==-EIO);
 reset();controller.reg_read_buf[0]=FS_OP_ERR;controller.reg_read_buf[1]=BS_UNCORRECTABLE_BIT;
 controller.reg_read_buf[2]=ERASED_CW;
 assert(parse_read_errors(&host,NULL,NULL,503)==0);
 assert(!controller.miami_diag_ready && !feature_calls);
 reset();
 struct device dev={0};char record[4096];
 assert(miami_first_failure_show(&dev,NULL,record)>0 && strstr(record,"state=armed"));
 d.ns=~(u64)0;d.page=INT_MAX;d.result=INT_MIN;d.command=INT_MAX;
 d.reason="qualified_ec_header_changed";d.failed=d.corrected=UINT_MAX;
 d.hz=ULONG_MAX;d.header=UINT_MAX;d.status_valid=true;
 d.codewords=d.ce=d.cmd_sgl=d.rx_sgl=d.tx_sgl=d.sts_sgl=UINT_MAX;
 for(int i=0;i<12;i++)d.status[i]=d.page_scope_status[i]=UINT_MAX;
 for(int i=0;i<4;i++){d.dma_cookie[i]=INT_MAX;d.dma_state[i]=-ENODATA;}
 for(int i=0;i<3;i++)d.feature[i]=-ENODATA;
 miami_diag_publish(&host,&d,true);
 int count=miami_first_failure_show(&dev,NULL,record);
 assert(count>0 && count<2048 && "EXISTING_STORAGE_PROBE_RECORD_LIMIT");
 assert(strstr(record,"capture=ram_only") && strstr(record,"regs_available=0") && strstr(record,"features_queried=0") && strstr(record,"dma_status_queried=0"));
 assert(strstr(record,"dma[3]") && strstr(record,"not_queried"));
 if(getenv("MIAMI_DIAG_SYSFS_FIXTURE"))fputs(record,stdout);
 printf("PASS: actual sysfs formatter worst-case record %d bytes fits existing 2047-byte storage probe and 4095-byte exporter; unavailable fields explicit\\n",count);
 puts("PASS: actual miami_diag_take and publisher perform no controller MMIO, clock/DMA-provider query or feature command; raw cache/export remains complete");
 puts("PASS: actual parse_read_errors hooks: confirmed uncorrectable, operational error, erased-page false-positive suppression");
 puts("PASS: actual driver header observer and publisher; blank/unqualified skip, boundary, first-record retention, no feature calls regardless of DMA/eligibility, disabled gate");
}
'''
if 'features_complete' not in struct:
    harness=harness.replace(' assert(!n->miami_diag.features_complete);','').replace(' assert(!controller.miami_diag.features_complete);','')
if 'miami_probe_claimed' in source:
    fields=source[source.index(' bool miami_probe_claimed,'):source.index('\n};',source.index(' bool miami_probe_claimed,'))]
    harness=harness.replace(' void *dev, *iomacro_clk;', ' void *dev, *iomacro_clk;\n'+fields)
    harness=harness.replace('#include <limits.h>', '#include <limits.h>\nstruct delayed_work { int unused; };\n#define hweight_long(x) __builtin_popcountl(x)')
    harness=harness.replace(' assert(strstr(record,"dma[3]") && strstr(record,"not_queried"));',' assert(strstr(record,"dma_cookies="));')
if 'miami_probe_inject(host, page);' in function('parse_read_errors'):
    harness=harness.replace('static int parse_read_errors(', 'static void miami_probe_inject(struct qcom_nand_host *h,int p){(void)h;(void)p;}\nstatic int parse_read_errors(',1)
with tempfile.TemporaryDirectory() as tmp:
    c=Path(tmp)/'test.c';exe=Path(tmp)/'test';c.write_text(harness)
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-o',str(exe),str(c)],check=True)
    result=subprocess.run([str(exe)],text=True,capture_output=True)
    if args.expect_old_failure:
        assert result.returncode!=0 and 'FORBIDDEN_DIAGNOSTIC_HARDWARE:' in result.stderr,(result.stdout,result.stderr)
        print('PASS actual deployed snapshot negative: diagnostic calls hardware/provider before capture')
    else:
        assert result.returncode==0,(result.stdout,result.stderr)
        print(result.stdout,end='')
