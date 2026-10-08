#!/usr/bin/env python3
"""Compile and execute the new board-scoped record writer with synthetic ELF/SMEM."""
from pathlib import Path
import subprocess,tempfile
repo=Path(__file__).resolve().parents[3]
patch=(repo/'feeds/qca-wifi-7/ipq53xx/patches-6.6/1003-miami-root-only-userpd-bootinfo.patch').read_text()
added='\n'.join(l[1:] for l in patch.splitlines() if l.startswith('+') and not l.startswith('+++'))
start=added.index('static int copy_miami_userpd_bootargs'); brace=added.index('{',start);depth=1;end=brace+1
while depth:
 depth+=(added[end]=='{')-(added[end]=='}');end+=1
function=added[start:end]
head=r'''
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
#include <assert.h>
#include <errno.h>
#include <sys/types.h>
typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef unsigned long long u64;
#define U32_MAX UINT32_MAX
#define ELFMAG "\177ELF"
#define SELFMAG 4
#define EI_CLASS 4
#define EI_DATA 5
#define ELFCLASS32 1
#define ELFDATA2LSB 1
#define UPD_BOOTARGS_HEADER_TYPE 2
#define Q6_BOOT_ARGS_SMEM_SIZE 4096
struct elf32_hdr {u8 e_ident[16];u16 e_type,e_machine;u32 e_version,e_entry,e_phoff,e_shoff,e_flags;u16 e_ehsize,e_phentsize,e_phnum,e_shentsize,e_shnum,e_shstrndx;};
struct elf32_phdr {u32 p_type,p_offset,p_vaddr,p_paddr,p_filesz,p_memsz,p_flags,p_align;};
struct firmware {size_t size;const u8 *data;};struct device_node {int unused;};struct rproc {int unused;};struct device {struct device_node *of_node;};
struct reserved_mem {u64 base,size;};struct bootargs_header{u8 type,length;};
struct q6_userpd_bootargs{struct bootargs_header header;u8 pid;u32 bootaddr,data_size;} __attribute__((packed));
struct bootargs_smem_info{void *smem_bootargs_ptr,*smem_elem_cnt_ptr,*smem_base_ptr;};
static struct firmware firmware;static struct reserved_mem pool={0x4a900000,0x2300000};static struct rproc rproc;static int fw_error,released;
static void *dev_get_drvdata(struct device*d){(void)d;return &rproc;}
static int request_firmware(const struct firmware **f,const char*n,struct device*d){(void)d;assert(!strcmp(n,"IPQ5332/q6_fw1.mdt"));*f=&firmware;return fw_error;}
static void release_firmware(const struct firmware*f){(void)f;released++;}
static u64 rproc_get_boot_addr(struct rproc*r,const struct firmware*f){(void)r;return ((const struct elf32_hdr*)f->data)->e_entry;}
/* SDK file-extent contract: p_filesz, without the page-rounded p_memsz. */
static ssize_t qcom_mdt_get_file_size(const struct firmware*f){const struct elf32_hdr*h=(void*)f->data;const struct elf32_phdr*p=(void*)(h+1);u64 min=UINT64_MAX,max=0;for(int i=0;i<h->e_phnum;i++){if(p[i].p_type!=1||!p[i].p_memsz)continue;if(p[i].p_paddr<min)min=p[i].p_paddr;if((u64)p[i].p_paddr+p[i].p_filesz>max)max=(u64)p[i].p_paddr+p[i].p_filesz;}return min<max?(ssize_t)(max-min):-EINVAL;}
static struct device_node *of_parse_phandle(struct device_node*n,const char*s,int i){(void)s;(void)i;return n;}
static struct reserved_mem *of_reserved_mem_lookup(struct device_node*n){return n?&pool:NULL;}
static void of_node_put(struct device_node*n){(void)n;}
static u16 readw(void*p){u16 n;memcpy(&n,p,2);return n;}
#define memcpy_toio memcpy
#define dev_info(...) ((void)0)
'''
main=r'''
int main(void){
 u8 smem[4096],before[4096],elf[sizeof(struct elf32_hdr)+sizeof(struct elf32_phdr)];struct device_node node;struct device dev={&node};struct elf32_hdr*h=(void*)elf;struct elf32_phdr*p=(void*)(h+1);struct bootargs_smem_info args;int count=0;
 for(int bad=0;bad<13;bad++){
  memset(elf,0,sizeof elf);memcpy(h->e_ident,ELFMAG,4);h->e_ident[EI_CLASS]=1;h->e_ident[EI_DATA]=1;h->e_phoff=sizeof(*h);h->e_phentsize=sizeof(*p);h->e_phnum=1;h->e_entry=0x4adfc000;p->p_type=1;p->p_paddr=h->e_entry;p->p_filesz=0x503b00;p->p_memsz=0x504000;
  firmware=(struct firmware){sizeof elf,elf};fw_error=0;released=0;dev.of_node=&node;
  memset(smem,0,sizeof smem);smem[0]=2;args=(struct bootargs_smem_info){smem+4,smem+2,smem};
  switch(bad){case 1:firmware.size=10;break;case 2:h->e_ident[0]=0;break;case 3:h->e_ident[EI_CLASS]=2;break;case 4:h->e_phoff++;break;case 5:h->e_phentsize--;break;case 6:h->e_phnum=0;break;case 7:h->e_phnum=2;break;case 8:p->p_filesz=0;break;case 9:h->e_entry=0x48000000;break;case 10:h->e_entry=0x4cbfffff;break;case 11:args.smem_bootargs_ptr=smem+4090;break;case 12:fw_error=-ENOENT;break;}
  memcpy(before,smem,sizeof smem);int ret=copy_miami_userpd_bootargs(&dev,&args);
  if(bad){assert(ret<0);assert(!memcmp(before,smem,sizeof smem));}else{
   const u8 expected[]={2,0,11,0,2,9,2,0,0xc0,0xdf,0x4a,0,0x3b,0x50,0};
   assert(ret==0);assert(!memcmp(smem,expected,sizeof expected));assert(args.smem_bootargs_ptr==smem+15);
  }
  assert(released==(fw_error?0:1));count++;
 }
 printf("PASS: actual record writer, %d ELF/extent/region/SMEM/error cases; exact OEM PID2 v2 bytes, file extent, and no partial record on failure\n",count);
}
'''
with tempfile.TemporaryDirectory() as td:
 p=Path(td);(p/'test.c').write_text(head+function+main)
 subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
