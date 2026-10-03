#!/usr/bin/env python3
"""Execute the selected driver predicate; compile a host-only stub harness."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]).read_text()
predicate = re.search(r'(?ms)^static bool ath11k_mac_supports_tpc\(.*?^\}', source).group()
start = re.search(r'(?ms)^static int\nath11k_mac_vdev_start_restart\(.*?^\}', source).group()
fill = re.search(r'(?ms)^void ath11k_mac_fill_reg_tpc_info\(.*?^\}', source).group()
assert 'ath11k_mac_fill_reg_tpc_info(ar, arvif->vif, ctx);' in start
assert 'reg_6ghz_power_mode = bss_conf->power_type;' in fill
assert 'reg_6ghz_power_mode = IEEE80211_REG_LPI_AP;' in fill
assert 'ath11k_reg_ap_pwr_convert(reg_6ghz_power_mode)' in fill
assert 'ath11k_mac_supports_station_tpc' not in source
code = '''
#include <stdbool.h>
#include <stdio.h>
#define WMI_TLV_SERVICE_EXT_TPC_REG_SUPPORT 0
#define WMI_VDEV_TYPE_STA 1
#define WMI_VDEV_TYPE_AP 2
#define WMI_VDEV_SUBTYPE_NONE 0
#define NL80211_BAND_6GHZ 2
struct base { unsigned long svc_map; };
struct ath11k { bool ext; struct { struct base wmi_ab; } *ab; };
struct ath11k_vif { int vdev_type, vdev_subtype; };
struct channel { int band; };
struct cfg80211_chan_def { struct channel *chan; };
static bool ath11k_wmi_supports_6ghz_cc_ext(struct ath11k *ar) { return ar->ext; }
static bool test_bit(int bit, unsigned long map) { return map & (1UL << bit); }
'''+predicate+'''
int main(void) {
    unsigned count=0;
    for (int ext=0; ext<2; ext++) for(int service=0; service<2; service++)
    for (int type=0; type<4; type++) for(int subtype=0; subtype<2; subtype++)
    for (int band=0; band<3; band++) for(int present=0; present<2; present++) {
        struct { struct base wmi_ab; } base = {{service}};
        struct ath11k ar = {.ext=ext}; ar.ab=(void *)&base;
        struct ath11k_vif vif = {type, subtype};
        struct channel channel = {band};
        struct cfg80211_chan_def ctx = {present ? &channel : NULL};
        bool expected = ext && service && (type==1 || type==2) && !subtype && present && band==2;
        if(ath11k_mac_supports_tpc(&ar,&vif,&ctx)!=expected) return 1;
        count++;
    }
    printf("Actual TPC predicate: %u combinations PASS; context/LPI/STA source invariants PASS\\n",count);
}
'''
with tempfile.TemporaryDirectory(prefix='ap-tpc-harness.') as tmp:
    program = Path(tmp)/'test'
    subprocess.run(['cc','-Wall','-Wextra','-Werror','-x','c','-o',str(program),'-'], input=code, text=True, check=True)
    subprocess.run([str(program)], check=True)
