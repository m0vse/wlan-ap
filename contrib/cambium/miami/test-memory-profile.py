#!/usr/bin/env python3
"""Compile real patched SDK budget functions; mock only hardware/DT context."""
from pathlib import Path
import re, shutil, subprocess, tempfile
repo=Path(__file__).resolve().parents[3]
sdk=repo/'feeds/qca-wifi-7/mac80211'
names=['ath12k_core_get_max_station_per_radio','ath12k_core_get_max_peers_per_radio','ath12k_core_get_max_num_tids','ath12k_core_get_total_num_vdevs','ath12k_core_is_vdev_limit_reached']
def function(text,name):
 match=re.search(r'(?:bool|u8|u32) '+name+r'\([^;]+?\)\n\{',text,re.S)
 assert match,name
 start=match.start();pos=match.end();depth=1
 while depth:
  if text[pos]=='{':depth+=1
  elif text[pos]=='}':depth-=1
  pos+=1
 return text[start:pos]
with tempfile.TemporaryDirectory(prefix='miami-pci-budget-',dir='/tmp') as tmp:
 work=Path(tmp); driver=work/'drivers/net/wireless/ath/ath12k';driver.mkdir(parents=True)
 for f in ['core.c','core.h','qmi.c','mac.c','htc.c','mhi.c']:shutil.copyfile(sdk/'src/drivers/net/wireless/ath/ath12k'/f,driver/f)
 before=(driver/'core.c').read_text()
 for patch in [sdk/'patches/ath12k/0003-Cambium-X7-35X-radio-policies.patch',sdk/'patches/ath12k/0004-ath12k-module-memory-profile.patch']:
  subprocess.run(['patch','--batch','--fuzz=0','-p1','-i',str(patch)],cwd=work,check=True,capture_output=True)
 after=(driver/'core.c').read_text()
 pre='''#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <assert.h>
#include <stdio.h>
typedef uint8_t u8; typedef uint32_t u32;
#define ATH12K_BUS_PCI 1
#define ATH12K_HW_QCN9274_HW20 2
#define TARGET_NUM_STATIONS_DBS 512
#define TARGET_NUM_STATIONS_SINGLE 512
#define TARGET_NUM_PEERS_PDEV_DBS 529
#define TARGET_NUM_PEERS_PDEV_DBS_SBS 529
#define TARGET_NUM_PEERS_PDEV_SINGLE 529
#define TARGET_NUM_TIDS(x) 2000
#define TARGET_NUM_VDEVS 17
#define TARGET_NUM_BRIDGE_VDEVS 8
#define ATH12K_MAX_NUM_VDEVS_NLINK 25
#define ATH12K_MIN_NUM_DEVICES_NLINK 2
#define ATH12K_QMI_TARGET_MEM_MODE 0
#define ATH12K_QMI_TARGET_MEM_MODE_512M 1
#define ath12k_err(...) ((void)0)
#define ath12k_warn(...) ((void)0)
struct group {int num_devices;};
struct ath12k_base {struct {int bus;} hif;int hw_rev;int num_radios;struct group *ag;struct{int target_mem_mode;}qmi;};
struct ath12k{struct ath12k_base *ab;u32 num_created_vdevs;u8 num_created_bridge_vdevs;};
static char *ath12k_mem_profile;

'''
 fns='\n'.join(function(after,n) for n in ['ath12k_core_uses_low_memory_profile',*names])
 old='\n'.join(function(before,n) for n in names)
 for n in names:old=old.replace(n,'old_'+n)
 declarations='\n'.join(re.search(r'.*?\)',function(after,n),re.S).group()+';' for n in names)
 declarations+='\n'+'\n'.join(re.search(r'.*?\)',function(before,n),re.S).group().replace(n,'old_'+n)+';' for n in names)
 qmi=(driver/'qmi.c').read_text();start=qmi.index('\tab->qmi.target_mem_mode = ATH12K_QMI_TARGET_MEM_MODE;');end=qmi.index('\n\n',start)
 qmi='void set_mode(struct ath12k_base *ab){\n'+qmi[start:end]+'\n}\n'
 main='''int main(void){int count=0;struct group group;struct ath12k_base ab={0};ab.ag=&group;struct ath12k ar={.ab=&ab};
char *profiles[]={"auto","low",NULL,"invalid"};
for(int model=0;model<4;model++)for(int bus=0;bus<2;bus++)for(int hw=0;hw<3;hw++)for(int nr=1;nr<4;nr++)for(int links=1;links<3;links++){
ath12k_mem_profile=profiles[model];ab.hif.bus=bus;ab.hw_rev=hw;ab.num_radios=nr;group.num_devices=links;
bool profile=model==1;
assert(ath12k_core_uses_low_memory_profile()==profile);
set_mode(&ab);assert(ab.qmi.target_mem_mode==(profile?1:0));
if(profile){assert(ath12k_core_get_max_station_per_radio(&ab)==128);assert(ath12k_core_get_max_peers_per_radio(&ab)==137);assert(ath12k_core_get_total_num_vdevs(&ab)==9);assert(ath12k_core_get_max_num_tids(&ab)==(u32)(2*nr*137+4*9+8));}
else{assert(ath12k_core_get_max_station_per_radio(&ab)==old_ath12k_core_get_max_station_per_radio(&ab));assert(ath12k_core_get_max_peers_per_radio(&ab)==old_ath12k_core_get_max_peers_per_radio(&ab));assert(ath12k_core_get_max_num_tids(&ab)==old_ath12k_core_get_max_num_tids(&ab));assert(ath12k_core_get_total_num_vdevs(&ab)==old_ath12k_core_get_total_num_vdevs(&ab));}
for(int n=0;n<28;n++)for(int bridge=0;bridge<2;bridge++){
ar.num_created_vdevs=n;ar.num_created_bridge_vdevs=bridge;
bool got=ath12k_core_is_vdev_limit_reached(&ar,bridge);
if(profile)assert(got==(bridge || n+bridge>=9));else assert(got==old_ath12k_core_is_vdev_limit_reached(&ar,bridge));count++;
}}
printf("PASS: %d actual SDK budget/admission matrix cases; auto, null and invalid modes preserve original budgets\\n",count);return 0;}
'''
 (work/'test.c').write_text(pre+declarations+'\n'+old+'\n'+fns+'\n'+qmi+main)
 subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(work/'test.c'),'-o',str(work/'test')],check=True)
 subprocess.run([str(work/'test')],check=True)
