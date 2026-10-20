from pathlib import Path
import re,subprocess,tempfile,argparse
ap=argparse.ArgumentParser();ap.add_argument('--driver',type=Path,required=True);args=ap.parse_args();s=args.driver.read_text()
start=s.index('static void qcom_nandc_command(');end=s.index('\n/*',start);f=s[start:end].replace('reset(host)','test_reset(host)')
pre=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <errno.h>
struct nand_ecc_ctrl {int steps;};struct nand_chip {struct nand_ecc_ctrl ecc;};
struct qcom_nand_host {struct nand_chip chip;bool use_ecc;};
struct qcom_nand_controller {void *dev;int miami_command_result,buf_count;};
static struct qcom_nand_controller controller;static struct qcom_nand_host host;
static int build_error,submit_error,post_calls,free_calls;
#define NAND_CMD_RESET 1
#define NAND_CMD_READID 2
#define NAND_CMD_PARAM 3
#define NAND_CMD_ERASE1 4
#define NAND_CMD_READ0 5
#define NAND_CMD_SEQIN 6
#define NAND_CMD_PAGEPROG 7
#define NAND_CMD_STATUS 8
#define NAND_CMD_NONE 9
#define WARN_ON(x) assert(!(x))
#define dev_err(...) ((void)0)
static struct qcom_nand_host *to_qcom_nand_host(struct nand_chip *c){(void)c;return &host;}
static struct qcom_nand_controller *get_qcom_nand_controller(struct nand_chip *c){(void)c;return &controller;}
static void pre_command(struct qcom_nand_host *h,unsigned int c){(void)h;(void)c;}
static int test_reset(struct qcom_nand_host *h){(void)h;return build_error;}
static int read_id(struct qcom_nand_host *h,int col){(void)h;(void)col;return build_error;}
static int nandc_param(struct qcom_nand_host *h){(void)h;return build_error;}
static int erase_block(struct qcom_nand_host *h,int p){(void)h;(void)p;return build_error;}
static void set_address(struct qcom_nand_host *h,int c,int p){(void)h;(void)c;(void)p;}
static void update_rw_regs(struct qcom_nand_host *h,int s,bool e,int c){(void)h;(void)s;(void)e;(void)c;}
static int submit_descs(struct qcom_nand_controller *n){(void)n;return submit_error;}
static void free_descs(struct qcom_nand_controller *n){(void)n;free_calls++;}
static void post_command(struct qcom_nand_host *h,unsigned int c){(void)h;(void)c;post_calls++;}
'''
post=r'''
int main(void){
 for(unsigned int cmd=NAND_CMD_RESET;cmd<=NAND_CMD_READID;cmd++){
  build_error=-ENOMEM;submit_error=0;post_calls=free_calls=0;qcom_nandc_command(&host.chip,cmd,0,0);
  assert(controller.miami_command_result==-ENOMEM&&post_calls==0&&free_calls==1);
  build_error=0;submit_error=-ETIMEDOUT;post_calls=free_calls=0;qcom_nandc_command(&host.chip,cmd,0,0);
  assert(controller.miami_command_result==-ETIMEDOUT&&post_calls==1&&free_calls==1);
  submit_error=0;post_calls=free_calls=0;qcom_nandc_command(&host.chip,cmd,0,0);
  assert(controller.miami_command_result==0&&post_calls==1&&free_calls==1);
 }
 puts("PASS actual void READ-ID/RESET helper retains descriptor-build/submission errors and existing cleanup/post-command semantics");
}
'''
with tempfile.TemporaryDirectory()as tmp:
 c=Path(tmp)/'test.c';out=Path(tmp)/'test';c.write_text(pre+f+post)
 subprocess.run(['cc','-Wall','-Wextra','-Werror','-o',str(out),str(c)],check=True);subprocess.run([str(out)],check=True)
