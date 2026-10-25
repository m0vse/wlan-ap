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
struct qcom_nand_host {struct nand_chip chip;bool use_ecc;unsigned int status;};
struct qcom_nand_controller {void *dev,*lifetime;int miami_command_result,buf_count;bool miami_probe_active,miami_dma_unsafe;};
static struct qcom_nand_controller controller;static struct qcom_nand_host host;
static int build_error,submit_error,post_calls,free_calls,poison_on_free;
#define NAND_CMD_RESET 1
#define NAND_CMD_READID 2
#define NAND_CMD_PARAM 3
#define NAND_CMD_ERASE1 4
#define NAND_CMD_READ0 5
#define NAND_CMD_SEQIN 6
#define NAND_CMD_PAGEPROG 7
#define NAND_CMD_STATUS 8
#define NAND_CMD_NONE 9
#define NAND_STATUS_READY 0x40
#define NAND_STATUS_FAIL 1
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
static void free_descs(struct qcom_nand_controller *n){if(poison_on_free)n->miami_dma_unsafe=true;free_calls++;}
static void post_command(struct qcom_nand_host *h,unsigned int c){(void)h;(void)c;assert(!(controller.miami_probe_active&&submit_error));post_calls++;}
'''
if 'static bool miami_io_blocked(' in s:
 start=s.index('static bool miami_io_blocked(');brace=s.index('{',start);depth=1;end=brace+1
 while depth:depth+=(s[end]=='{')-(s[end]=='}');end+=1
 pre+='\nstatic bool qcom_qpic_lifetime_poisoned(void *life){return life!=NULL;}\n'+s[start:end]+'\n'
post=r'''
int main(void){
 for(unsigned int cmd=NAND_CMD_RESET;cmd<=NAND_CMD_READID;cmd++){
  build_error=-ENOMEM;submit_error=0;post_calls=free_calls=0;qcom_nandc_command(&host.chip,cmd,0,0);
  assert(controller.miami_command_result==-ENOMEM&&post_calls==0&&free_calls==1);
  build_error=0;submit_error=-ETIMEDOUT;post_calls=free_calls=0;qcom_nandc_command(&host.chip,cmd,0,0);
  assert(controller.miami_command_result==-ETIMEDOUT&&post_calls==1&&free_calls==1);
  controller.miami_probe_active=true;post_calls=free_calls=0;qcom_nandc_command(&host.chip,cmd,0,0);
  assert(controller.miami_command_result==-ETIMEDOUT&&post_calls==0&&free_calls==1);
  controller.miami_probe_active=false;
  submit_error=0;post_calls=free_calls=0;qcom_nandc_command(&host.chip,cmd,0,0);
  assert(controller.miami_command_result==0&&post_calls==1&&free_calls==1);
 }
 puts("PASS actual void READ-ID/RESET helper retains descriptor-build/submission errors and normal cleanup/post-command semantics; optional failed-submit post is poisoned");
}
'''
if 'static bool miami_io_blocked(' in s:
 post=post.replace(' puts("PASS actual void', '''
 build_error=submit_error=0;post_calls=free_calls=0;poison_on_free=1;
 qcom_nandc_command(&host.chip,NAND_CMD_READID,0,0);
 assert(controller.miami_command_result==-EIO&&free_calls==1&&post_calls==0&&(host.status&NAND_STATUS_FAIL));
 poison_on_free=0;
 for(int external=0;external<2;external++){
  controller.miami_dma_unsafe=!external;controller.lifetime=external?&controller:NULL;
  post_calls=free_calls=0;qcom_nandc_command(&host.chip,NAND_CMD_RESET,0,0);
  assert(controller.miami_command_result==-EIO&&post_calls==0&&free_calls==0&&(host.status&NAND_STATUS_FAIL));
 }
 puts("PASS actual void''')
with tempfile.TemporaryDirectory()as tmp:
 c=Path(tmp)/'test.c';out=Path(tmp)/'test';c.write_text(pre+f+post)
 subprocess.run(['cc','-Wall','-Wextra','-Werror','-o',str(out),str(c)],check=True);subprocess.run([str(out)],check=True)
