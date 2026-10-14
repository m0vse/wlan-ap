#!/usr/bin/env python3
"""Execute real driver getter C with injected FW boundaries; never contact an AP."""
import argparse
import pathlib
import subprocess
import tempfile

p = argparse.ArgumentParser()
p.add_argument('--source', type=pathlib.Path, required=True)
p.add_argument('--kind', choices=['ath11k', 'ath12k', 'qca-ath11k'], required=True)
p.add_argument('--negative-control', action='store_true')
a = p.parse_args()
source = a.source.read_text()
name = ('ath12k' if a.kind == 'ath12k' else 'ath11k') + '_mac_op_get_txpower'
begin = source.rfind('\n', 0, source.index('int ' + name)) + 1
brace = source.index('{', begin)
depth = 1
end = brace + 1
while depth:
    depth += (source[end] == '{') - (source[end] == '}')
    end += 1
body = source[begin:end]
prefix = r'''
#include <assert.h>
#include <stdio.h>
#include <stdbool.h>
#include <errno.h>
struct ieee80211_hw {void *priv;};
struct ieee80211_vif {struct {int txpower;} bss_conf;};
static int fw_ret,fw_calls,have_pdev,cac;
static unsigned long jiffies=10000;
#define spin_lock_bh(x) ((void)0)
#define spin_unlock_bh(x) ((void)0)
#define mutex_lock(x) ((void)0)
#define mutex_unlock(x) ((void)0)
#define lockdep_assert_wiphy(x) ((void)0)
#define test_bit(bit,flags) (cac)
#define wiphy_dereference(wiphy,val) (val)
#define list_first_entry_or_null(list,type,member) (have_pdev ? &sample : NULL)
#define msecs_to_jiffies(n) (n)
#define time_before(a,b) ((a)<(b))
#define WMI_REQUEST_PDEV_STAT 1
'''
if a.kind == 'ath12k':
    prefix += r'''
#define ATH12K_HW_STATE_ON 1
#define ATH12K_FLAG_CAC_RUNNING 0
#define ATH12K_PDEV_TX_POWER_INVALID (-999)
#define ATH12K_PDEV_TX_POWER_REFRESH_TIME_MSECS 5000
#define ath12k_dbg_level(...) ((void)0)
#define ath12k_warn(...) ((void)0)
struct ath12k_base {int unused;};
struct ath12k_fw_stats_pdev {int chan_tx_power;};
struct ath12k_fw_stats_req_params {int pdev_id,vdev_id,stats_id;};
struct pdev {int pdev_id;};
struct ath12k {struct ath12k_base *ab;struct pdev *pdev;int chan_tx_pwr;unsigned long last_tx_power_update;};
struct ath12k_link_vif {struct ath12k *ar;int vdev_id;};
struct ath12k_vif {struct ath12k_link_vif *link[16];};
struct ath12k_hw {void *hw;int state;};
static struct ath12k_fw_stats_pdev sample;
static struct ath12k_vif av;
static struct ath12k_vif *ath12k_vif_to_ahvif(struct ieee80211_vif *v){return &av;}
static int ath12k_mac_get_fw_stats(struct ath12k*a,struct ath12k_fw_stats_req_params*p){fw_calls++;return fw_ret;}
'''
    checks = r'''
int main(void){
 struct ath12k_hw ah={.state=1};struct ieee80211_hw hw={.priv=&ah};struct ieee80211_vif vif={.bss_conf.txpower=99};
 struct pdev pd={.pdev_id=3};struct ath12k ar={.pdev=&pd,.chan_tx_pwr=ATH12K_PDEV_TX_POWER_INVALID};struct ath12k_link_vif link={.ar=&ar};av.link[7]=&link;
 int dbm=777;have_pdev=1;sample.chan_tx_power=41;
 fw_ret=-ETIMEDOUT;assert(ath12k_mac_op_get_txpower(&hw,&vif,7,&dbm)==-ETIMEDOUT);assert(dbm==777&&ar.chan_tx_pwr==ATH12K_PDEV_TX_POWER_INVALID);
 fw_ret=0;have_pdev=0;assert(ath12k_mac_op_get_txpower(&hw,&vif,7,&dbm)==-ENODATA);assert(dbm==777);
 have_pdev=1;assert(!ath12k_mac_op_get_txpower(&hw,&vif,7,&dbm));assert(dbm==20);int calls=fw_calls;
 assert(!ath12k_mac_op_get_txpower(&hw,&vif,7,&dbm));assert(fw_calls==calls);
 jiffies+=5001;assert(!ath12k_mac_op_get_txpower(&hw,&vif,7,&dbm));assert(fw_calls==calls+1);
 ar.chan_tx_pwr=ATH12K_PDEV_TX_POWER_INVALID;fw_ret=-EIO;assert(ath12k_mac_op_get_txpower(&hw,&vif,7,&dbm)==-EIO);
 cac=1;assert(ath12k_mac_op_get_txpower(&hw,&vif,7,&dbm)==-EAGAIN);cac=0;
 ah.state=0;assert(ath12k_mac_op_get_txpower(&hw,&vif,7,&dbm)==-ENETDOWN);ah.state=1;
 assert(ath12k_mac_op_get_txpower(&hw,&vif,0,&dbm)==-EINVAL);
 puts("PASS 9 actual ath12k getter controls; mocked firmware/locks/RCU; no hardware I/O");
}
'''
else:
    prefix += r'''
#define ATH11K_CAC_RUNNING 0
#define ATH11K_STATE_ON 1
#define ath11k_dbg(...) ((void)0)
#define ath11k_warn(...) ((void)0)
struct ath11k_base {int unused;};
struct ath11k_fw_stats_pdev {int chan_tx_power;};
struct pdev {int pdev_id;};
struct ath11k {struct ath11k_base *ab;struct pdev *pdev;int state;};
struct stats_request_params {int pdev_id,vdev_id,stats_id;};
static struct ath11k_fw_stats_pdev sample;
static int ath11k_mac_get_fw_stats(struct ath11k*a,int p,int v,int stats){fw_calls++;return fw_ret;}
static int ath11k_fw_stats_request(struct ath11k*a,struct stats_request_params*p){fw_calls++;return fw_ret;}
'''
    checks = r'''
int main(void){
 struct pdev pd={.pdev_id=3};struct ath11k ar={.pdev=&pd,.state=1};struct ieee80211_hw hw={.priv=&ar};struct ieee80211_vif vif={.bss_conf.txpower=99};
 int dbm=777;have_pdev=1;sample.chan_tx_power=41;
 fw_ret=-ETIMEDOUT;assert(ath11k_mac_op_get_txpower(&hw,&vif,0,&dbm)==-ETIMEDOUT);assert(dbm==777);
 fw_ret=0;have_pdev=0;assert(ath11k_mac_op_get_txpower(&hw,&vif,0,&dbm)==-ENODATA);assert(dbm==777);
 have_pdev=1;assert(!ath11k_mac_op_get_txpower(&hw,&vif,0,&dbm));assert(dbm==20);
 fw_ret=-ENETDOWN;assert(ath11k_mac_op_get_txpower(&hw,&vif,0,&dbm)==-ENETDOWN);
 cac=1;assert(ath11k_mac_op_get_txpower(&hw,&vif,0,&dbm)==-EAGAIN);
 puts("PASS 5 actual ath11k getter controls; mocked firmware/locks; no hardware I/O");
}
'''
    if a.kind == 'qca-ath11k':
        checks = checks.replace(' puts("PASS 5 actual ath11k', ' cac=0;ar.state=0;assert(ath11k_mac_op_get_txpower(&hw,&vif,0,&dbm)==-ENETDOWN);\n puts("PASS 6 actual QSDK ath11k')
with tempfile.TemporaryDirectory(prefix='radio-driver-power-') as tmp:
    c = pathlib.Path(tmp) / 'power.c'
    binary = c.with_suffix('')
    c.write_text(prefix + body + checks)
    subprocess.run(['gcc', '-std=gnu11', '-Werror=implicit-function-declaration', str(c), '-o', str(binary)], check=True)
    result = subprocess.run([str(binary)], capture_output=True, text=True)
    if a.negative_control:
        assert result.returncode != 0, 'Old configured fallback unexpectedly passed'
        print('PASS negative control: original driver conceals firmware readback failure')
    else:
        print(result.stdout, end='')
        assert result.returncode == 0, result.stderr
