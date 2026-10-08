#!/usr/bin/env python3
"""Compile actual SDK group capability selection before/after the Miami patch."""
from pathlib import Path
import re, subprocess, tempfile
repo = Path(__file__).resolve().parents[3]
sdk = repo/'feeds/qca-wifi-7/mac80211'
name = 'ath12k_core_hw_group_set_mlo_capable'
def extract(text):
    start = text.index('void '+name+'(')
    end = text.index('\nint ath12k_wsi_load_info_init', start)
    return text[start:end]
with tempfile.TemporaryDirectory(prefix='miami-phy-groups-') as directory:
    work = Path(directory)
    driver = work/'drivers/net/wireless/ath/ath12k'
    driver.mkdir(parents=True)
    original = (sdk/'src/drivers/net/wireless/ath/ath12k/core.c').read_text()
    (driver/'core.c').write_text(original)
    subprocess.run(['patch','--batch','--fuzz=0','-p1','-i',str(sdk/'patches/ath12k/0005-Cambium-X7-35X-separate-radio-PHYs.patch')], cwd=work, check=True, capture_output=True)
    patched = (driver/'core.c').read_text()
    header = r"""
#include <stdbool.h>
#include <assert.h>
#include <string.h>
#include <stdio.h>
#define lockdep_assert_held(x) ((void)0)
#define ATH12K_FW_API_V2 2
#define ATH12K_FW_FEATURE_MLO 0
struct hw {int def_num_link;};
struct ath12k_base {struct hw *hw_params; bool is_bypassed; struct {int api_version;unsigned long fw_features;} fw;};
struct ath12k_hw_group {bool mlo_capable;int num_devices;int mutex;struct ath12k_base *ab[2];};
static bool miami, ath12k_ftm_mode;
static unsigned int ath12k_mlo_capable;
static bool of_machine_is_compatible(const char *s){return miami && !strcmp(s,"cambiumnetworks,x7-35x");}
#define test_bit(n, p) (((p) >> (n)) & 1)
"""
    main = r"""
int main(void){int count=0; struct hw hw; struct ath12k_base ab[2];
for(int model=0;model<2;model++)for(int ftm=0;ftm<2;ftm++)for(int mlo=0;mlo<2;mlo++)for(int devices=1;devices<3;devices++)for(int api=1;api<3;api++)for(int feature=0;feature<2;feature++)for(int link=0;link<2;link++)for(int bypass=0;bypass<2;bypass++){
miami=model;ath12k_ftm_mode=ftm;ath12k_mlo_capable=mlo;hw.def_num_link=link;
for(int i=0;i<2;i++)ab[i]=(struct ath12k_base){.hw_params=&hw,.is_bypassed=bypass,.fw={api,feature}};
struct ath12k_hw_group group={.num_devices=devices,.ab={&ab[0],&ab[1]}},old=group;
old_select(&old);ath12k_core_hw_group_set_mlo_capable(&group);
assert(group.mlo_capable==(miami?false:old.mlo_capable));count++;
}
printf("PASS: %d actual SDK group-selection cases; Miami never merges PHYs and other boards retain original behavior\n",count);return 0;}
"""
    source = header + extract(original).replace(name,'old_select') + extract(patched) + main
    (work/'test.c').write_text(source)
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(work/'test.c'),'-o',str(work/'test')],check=True)
    subprocess.run([str(work/'test')],check=True)
