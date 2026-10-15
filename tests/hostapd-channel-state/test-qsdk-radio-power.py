#!/usr/bin/env python3
"""Run actual QSDK setters/inheritance and iw parser in native C harnesses.

Only kernel object/firmware boundaries and netlink attribute writes are mocked.
These tests do not establish firmware power readback or RF/hardware acceptance.
"""
from pathlib import Path
import argparse
import subprocess
import tempfile
import shutil

repo = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser()
p.add_argument('--iw-source', type=Path, required=True)
p.add_argument('--negative-control', action='store_true')
a = p.parse_args()


def function(source, name):
    start = source.index(name + '(')
    start = source.rfind('\n', 0, start) + 1
    brace = source.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'


with tempfile.TemporaryDirectory(prefix='qsdk-radio-power-') as td:
    work = Path(td)
    source = repo / 'feeds/qca-wifi-7/mac80211/src'
    files = ['include/net/cfg80211.h', 'net/mac80211/ieee80211_i.h',
             'net/mac80211/cfg.c', 'net/mac80211/chan.c', 'net/mac80211/link.c']
    for name in files:
        target = work / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, target)
    if not a.negative_control:
        patch = repo / 'feeds/qca-wifi-7/mac80211/patches/ath12k/0009-mac80211-independent-radio-txpower.patch'
        subprocess.run(['patch', '--forward', '--batch', '--fuzz=0', '-p1', '-i', str(patch)],
                       cwd=work, check=True, stdout=subprocess.DEVNULL)
    cfg = (work / 'net/mac80211/cfg.c').read_text()
    header = (work / 'net/mac80211/ieee80211_i.h').read_text()
    inherit = (function(header, 'ieee80211_link_inherit_radio_power')
               if not a.negative_control else
               'void ieee80211_link_inherit_radio_power(struct ieee80211_link_data *l, const struct ieee80211_chanctx_conf *c) {}\n')
    # function() starts at the name line for a split return type.
    inherit = 'static inline void\n' + inherit if not a.negative_control else inherit
    chan = (work / 'net/mac80211/chan.c').read_text()
    if not a.negative_control:
        block = function(chan, 'ieee80211_assign_link_chanctx')
        assert block.index('rcu_assign_pointer(link->conf->chanctx_conf, conf)') < block.index('ieee80211_link_inherit_radio_power')
        assert block.index('ieee80211_link_inherit_radio_power') < block.index('ieee80211_recalc_txpower(link, false')
        assert 'ieee80211_link_inherit_radio_power(link, conf);' in block
        for marker in ['rcu_assign_pointer(link_conf->chanctx_conf, &new_ctx->conf);', 'rcu_assign_pointer(link_conf->chanctx_conf,\n\t\t\t\t\t   &ctx->conf);']:
            start = chan.index(marker)
            assert 'ieee80211_link_inherit_radio_power' in chan[start:start+len(marker)+100]
        assert 'link->user_power_level_set = false;' in (work / 'net/mac80211/link.c').read_text()
    harness = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;
typedef uint64_t u64;
struct ieee80211_chan_req { struct { int width; } oper; };
#define ARRAY_SIZE(x) (sizeof(x)/sizeof((x)[0]))
#define IEEE80211_UNSET_POWER_LEVEL (-999)
#define MBM_TO_DBM(x) ((x)/100)
#define NL80211_IFTYPE_AP 1
#define NL80211_IFTYPE_MONITOR 2
#define NO_VIRTUAL_MONITOR 1
#define WANT_MONITOR_VIF 2
enum nl80211_tx_power_setting { NL80211_TX_POWER_AUTOMATIC, NL80211_TX_POWER_LIMITED, NL80211_TX_POWER_FIXED };
struct wiphy_radio_cfg { unsigned rts_threshold; bool txpower_set; int txpower_level; enum nl80211_tx_power_setting txpower_type; };
struct ieee80211_local;
struct ieee80211_sub_if_data;
struct ieee80211_chanctx_conf { int radio_idx; bool radar_enabled; };
struct ieee80211_chanctx { struct ieee80211_chanctx_conf conf; bool radar_detected; int replace_state; };
struct ieee80211_bss_conf { int txpower_type; struct ieee80211_chanctx_conf *chanctx_conf; struct ieee80211_chan_req chanreq; };
struct ieee80211_link_data { struct ieee80211_sub_if_data *sdata; unsigned link_id; struct ieee80211_bss_conf *conf; int user_power_level; bool user_power_level_set; int recalc_calls; struct ieee80211_chanctx *reserved_chanctx; struct ieee80211_chan_req reserved; bool reserved_ready, radar_required, reserved_radar_required; };
struct wireless_dev { struct ieee80211_sub_if_data *sdata; };
struct wiphy { int n_radio; struct wiphy_radio_cfg *radio_cfg; struct ieee80211_local *priv; };
struct ieee80211_hw { struct wiphy *wiphy; unsigned flags; };
struct ieee80211_sub_if_data { struct ieee80211_local *local; struct { int type; unsigned valid_links; struct ieee80211_bss_conf bss_conf; struct { bool idle; } cfg; } vif; struct { struct { unsigned int cac_time_ms; unsigned long cac_start_time; } links[16]; } wdev; struct ieee80211_link_data *link[16]; struct ieee80211_link_data deflink; bool up; };
struct list_head { struct ieee80211_sub_if_data *items[8]; int count; };
struct ieee80211_local { struct ieee80211_hw hw; struct list_head interfaces; struct ieee80211_sub_if_data *monitor_sdata; int user_power_level; bool emulate_chanctx, in_reconfig; int hw_conf_calls; };
#define wiphy_priv(w) ((w)->priv)
#define IEEE80211_WDEV_TO_SUB_IF(w) ((w)->sdata)
#define lockdep_assert_wiphy(w) ((void)(w))
#define sdata_dereference(p,s) (p)
#define wiphy_dereference(w,p) (p)
#define ieee80211_hw_check(hw,f) (!!((hw)->flags & (f)))
#define list_for_each_entry(s,h,member) for(int _i=0; _i<(h)->count && ((s)=(h)->items[_i]); _i++)
#define for_each_link_data(s,l) for(int _j=0; _j<16; _j++) if((!(s)->vif.valid_links || ((s)->vif.valid_links & (1u<<_j))) && ((l)=(s)->link[_j]))
static void ieee80211_recalc_txpower(struct ieee80211_link_data *l, bool changed, unsigned id) { assert(l->link_id==id); l->recalc_calls++; }
static void ieee80211_hw_conf_chan(struct ieee80211_local *l) { l->hw_conf_calls++; }
'''
    harness += r"""
#define NL80211_IFTYPE_NAN 8
#define NL80211_IFTYPE_P2P_DEVICE 9
#define BSS_CHANGED_IDLE 1
#define BSS_CHANGED_BANDWIDTH 2
#define IEEE80211_CHANCTX_REPLACES_OTHER 1
#define CHANCTX_SWMODE_REASSIGN_VIF 1
#define list_move(p,h) ((void)0)
#define ieee80211_link_update_chanreq(...) ((void)0)
#define _ieee80211_change_chanctx(...) ((void)0)
#define ieee80211_free_chanctx(...) ((void)0)
#define __ieee80211_link_copy_chanctx_to_vlans(...) ((void)0)
#define ieee80211_link_info_change_notify(...) ((void)0)
#define WARN_ON(x) (x)
#define WARN_ON_ONCE(x) ((void)(x))
#define jiffies 0
#define jiffies_to_msecs(x) (x)
#define rcu_dereference_protected(p,lock) (p)
#define rcu_assign_pointer(p,v) ((p)=(v))
#define rcu_access_pointer(p) (p)
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define list_del(p) ((void)0)
#define list_add(p,h) ((void)0)
#define for_each_sdata_link(local,link) for(int _s=0;_s<(local)->interfaces.count;_s++) for_each_link_data((local)->interfaces.items[_s],link)
#define ieee80211_recalc_chanctx_min_def(...) ((void)0)
#define ieee80211_recalc_chanctx_chantype(...) ((void)0)
#define ieee80211_recalc_smps_chanctx(...) ((void)0)
#define ieee80211_recalc_radar_chanctx(...) ((void)0)
#define ieee80211_vif_cfg_change_notify(...) ((void)0)
#define ieee80211_check_fast_xmit_iface(...) ((void)0)
#define drv_unassign_vif_chanctx(...) ((void)0)
static int assign_result, switch_result;
struct ieee80211_vif_chanctx_switch { void *vif; struct ieee80211_chanctx_conf *old_ctx, *new_ctx; struct ieee80211_bss_conf *link_conf; };
static struct ieee80211_chanctx *ieee80211_link_get_chanctx(struct ieee80211_link_data *l) { return l->conf->chanctx_conf ? container_of(l->conf->chanctx_conf,struct ieee80211_chanctx,conf):NULL; }
static const struct ieee80211_chan_req *ieee80211_chanctx_non_reserved_chandef(struct ieee80211_local *l, struct ieee80211_chanctx *c, const struct ieee80211_chan_req *r, struct ieee80211_chan_req *tmp) { return r; }
static int drv_switch_vif_chanctx(struct ieee80211_local *l,struct ieee80211_vif_chanctx_switch *s,int n,int mode) { return switch_result; }
static int ieee80211_chanctx_refcount(struct ieee80211_local *l,struct ieee80211_chanctx *c) { return 1; }
static void ieee80211_link_chanctx_reservation_complete(struct ieee80211_link_data *l) {}
static int drv_assign_vif_chanctx(struct ieee80211_local *l, struct ieee80211_sub_if_data *s,struct ieee80211_bss_conf *c,struct ieee80211_chanctx *n) { return assign_result; }
static int ieee80211_chanctx_num_assigned(struct ieee80211_local *l, struct ieee80211_chanctx *c) { return 1; } /* another existing peer */
static bool ieee80211_chanctx_radar_required(struct ieee80211_local *l, struct ieee80211_chanctx *c) { return false; }
"""
    harness += inherit + function(cfg, 'ieee80211_set_tx_power') + function(chan, 'ieee80211_assign_link_chanctx') + 'static int\n' + function(chan, 'ieee80211_link_use_reserved_reassign')
    harness += r'''
static struct wiphy_radio_cfg radios[2];
static struct wiphy w;
static struct ieee80211_local local;
static struct ieee80211_sub_if_data dev[3];
static struct ieee80211_link_data links[3][16];
static struct ieee80211_bss_conf conf[3][16];
static struct ieee80211_chanctx_conf ctx[2]={{.radio_idx=0},{.radio_idx=1}};
static void add(int d, int id, int radio) {
 struct ieee80211_link_data *l=&links[d][id];
 *l=(struct ieee80211_link_data){.sdata=&dev[d],.link_id=id,.conf=&conf[d][id],.user_power_level=IEEE80211_UNSET_POWER_LEVEL};
 conf[d][id].chanctx_conf=radio<0?NULL:&ctx[radio];
 dev[d].link[id]=l; dev[d].vif.valid_links|=1u<<id;
 if(radio>=0) ieee80211_link_inherit_radio_power(l,&ctx[radio]);
}
static void reset(void) {
 memset(radios,0,sizeof(radios)); memset(&local,0,sizeof(local)); memset(dev,0,sizeof(dev)); memset(links,0,sizeof(links)); memset(conf,0,sizeof(conf));
 w=(struct wiphy){.n_radio=2,.radio_cfg=radios,.priv=&local}; local.hw.wiphy=&w; local.user_power_level=IEEE80211_UNSET_POWER_LEVEL;
 for(int i=0;i<3;i++){dev[i].local=&local;dev[i].vif.type=NL80211_IFTYPE_AP;dev[i].up=true;local.interfaces.items[i]=&dev[i];}
 local.interfaces.count=3;
}
int main(void) {
 int cases=0;
 /* Non-MLO shared-wiphy VIFs and a third pending interface. */
 reset(); add(0,0,0);add(1,0,1);
 assert(ieee80211_set_tx_power(&w,NULL,0,NL80211_TX_POWER_FIXED,1400,0)==0);
 assert(local.user_power_level==IEEE80211_UNSET_POWER_LEVEL && links[1][0].user_power_level==IEEE80211_UNSET_POWER_LEVEL);cases++;
 assert(ieee80211_set_tx_power(&w,NULL,1,NL80211_TX_POWER_FIXED,2300,0)==0);
 assert(links[0][0].user_power_level==14 && links[1][0].user_power_level==23);cases++;
 /* MLO link IDs are deliberately not radio indices. */
 reset();add(0,0,0);add(0,7,1);add(1,4,1);add(2,9,-1);
 assert(ieee80211_set_tx_power(&w,NULL,0,NL80211_TX_POWER_FIXED,1400,0)==0);
 assert(ieee80211_set_tx_power(&w,NULL,1,NL80211_TX_POWER_FIXED,2300,0)==0);
 assert(links[0][0].user_power_level==14 && links[0][7].user_power_level==23 && links[1][4].user_power_level==23);cases++;
 /* Repeat actual live setter calls; the peer and all VIFs remain intact. */
 for(int i=0;i<200;i++) {
  int radio=i%2,peer=1-radio,power=10+i%15;
  int before=radios[peer].txpower_level,peer_level=links[0][peer?7:0].user_power_level;
  assert(ieee80211_set_tx_power(&w,NULL,radio,NL80211_TX_POWER_FIXED,power*100,0)==0);
  assert(radios[peer].txpower_level==before && links[0][peer?7:0].user_power_level==peer_level);
  assert(local.user_power_level==IEEE80211_UNSET_POWER_LEVEL);
  for(int d=0;d<3;d++)assert(dev[d].up);
  cases++;
 }
 /* Late ACS/CAC binding gets the selected radio's retained request. */
 ieee80211_link_inherit_radio_power(&links[2][9],&ctx[1]);assert(links[2][9].user_power_level==radios[1].txpower_level);cases++;
 struct ieee80211_chanctx_conf invalid={.radio_idx=-1};
 int old=links[2][9].user_power_level;ieee80211_link_inherit_radio_power(&links[2][9],&invalid);assert(links[2][9].user_power_level==old);cases++;
 /* Invalid requests are rejected before either radio is modified. */
 struct wiphy_radio_cfg snapshot[2];memcpy(snapshot,radios,sizeof(radios));
 for(int mode=0;mode<4;mode++){
  int rc=ieee80211_set_tx_power(&w,NULL,mode==0?2:0,mode==1?99:NL80211_TX_POWER_FIXED,mode==2?-100:mode==3?1450:1400,0);
  assert(rc<0 && !memcmp(snapshot,radios,sizeof(radios)));cases++;
 }
 /* Explicit per-link RRM requests remain local and survive channel rebinding. */
 struct wireless_dev wd={.sdata=&dev[0]};int peer=links[0][0].user_power_level;
 assert(ieee80211_set_tx_power(&w,&wd,255,NL80211_TX_POWER_FIXED,1200,7)==0);
 ieee80211_link_inherit_radio_power(&links[0][7],&ctx[1]);assert(links[0][7].user_power_level==12 && links[0][0].user_power_level==peer);cases++;
 assert(ieee80211_set_tx_power(&w,&wd,255,NL80211_TX_POWER_FIXED,1400,15)==-ENOLINK);cases++;
 assert(ieee80211_set_tx_power(&w,&wd,255,NL80211_TX_POWER_FIXED,1400,16)==-EINVAL);cases++;
 /* A later device default intentionally supersedes live per-link overrides. */
 assert(ieee80211_set_tx_power(&w,NULL,1,NL80211_TX_POWER_FIXED,1800,0)==0);
 assert(!links[0][7].user_power_level_set && links[0][7].user_power_level==18 && links[0][0].user_power_level==peer);cases++;
 /* Actual assign function: a peer already occupies the destination context.
  * Failed binding must not inherit that context's radio request. */
 struct ieee80211_chanctx destination={.conf={.radio_idx=1}};
 add(2,9,-1);links[2][9].user_power_level=11;assign_result=-EIO;
 assert(ieee80211_assign_link_chanctx(&links[2][9],&destination,false)==-EIO);
 assert(links[2][9].conf->chanctx_conf==NULL && links[2][9].user_power_level==11 && links[0][0].user_power_level==peer);cases++;
 assign_result=0;
 assert(ieee80211_assign_link_chanctx(&links[2][9],&destination,false)==0);
 assert(links[2][9].conf->chanctx_conf==&destination.conf && links[2][9].user_power_level==18);cases++;
 struct ieee80211_chanctx other={.conf={.radio_idx=0}};
 assert(ieee80211_assign_link_chanctx(&links[2][9],&other,false)==0);
 assert(links[2][9].user_power_level==radios[0].txpower_level);cases++;
 links[2][9].user_power_level=9;links[2][9].user_power_level_set=true;
 assert(ieee80211_assign_link_chanctx(&links[2][9],&destination,false)==0);
 assert(links[2][9].user_power_level==9);cases++;
 /* Execute actual reserved-context driver-switch error and commit paths. */
 links[2][9].user_power_level_set=false;links[2][9].user_power_level=11;
 links[2][9].reserved_ready=true;links[2][9].reserved_chanctx=&other;switch_result=-EIO;
 assert(ieee80211_link_use_reserved_reassign(&links[2][9])==-EIO);
 assert(links[2][9].conf->chanctx_conf==&destination.conf && links[2][9].user_power_level==11);cases++;
 links[2][9].reserved_chanctx=&other;switch_result=0;
 assert(ieee80211_link_use_reserved_reassign(&links[2][9])==0);
 assert(links[2][9].conf->chanctx_conf==&other.conf && links[2][9].user_power_level==radios[0].txpower_level);cases++;
 links[2][9].reserved_chanctx=&destination;
 assert(ieee80211_link_use_reserved_reassign(&links[2][9])==0);
 assert(links[2][9].user_power_level==18 && links[0][0].user_power_level==peer);cases++;
 links[2][9].user_power_level_set=true;links[2][9].user_power_level=9;links[2][9].reserved_chanctx=&other;
 assert(ieee80211_link_use_reserved_reassign(&links[2][9])==0 && links[2][9].user_power_level==9);cases++;
 /* Automatic, zero, global and legacy single-radio semantics. */
 assert(ieee80211_set_tx_power(&w,NULL,1,NL80211_TX_POWER_AUTOMATIC,0,0)==0);assert(radios[1].txpower_level==IEEE80211_UNSET_POWER_LEVEL && links[0][0].user_power_level==peer);cases++;
 assert(ieee80211_set_tx_power(&w,NULL,1,NL80211_TX_POWER_FIXED,0,0)==0);assert(links[0][7].user_power_level==0);cases++;
 assert(ieee80211_set_tx_power(&w,NULL,255,NL80211_TX_POWER_FIXED,1700,0)==0);assert(local.user_power_level==17 && radios[0].txpower_level==17 && radios[1].txpower_level==17);cases++;
 reset();w.n_radio=0;w.radio_cfg=NULL;local.emulate_chanctx=true;add(0,0,0);
 assert(ieee80211_set_tx_power(&w,NULL,255,NL80211_TX_POWER_FIXED,1500,0)==0);assert(local.user_power_level==15 && local.hw_conf_calls==1);cases++;
 printf("PASS %d actual mac80211 setter/inheritance cases; no firmware/RF claim\n",cases);
 return 0;
}
'''
    c = work / 'kernel-test.c'
    c.write_text(harness)
    binary = work / 'kernel-test'
    subprocess.run(['cc', '-std=gnu11', '-Werror', '-Wno-unused-function', str(c), '-o', str(binary)], check=True)
    result = subprocess.run([str(binary)], capture_output=True, text=True)
    if a.negative_control:
        assert result.returncode != 0, 'Old shared state unexpectedly passed independent-radio tests'
        print('PASS actual old-kernel negative control rejected independent-radio contract')
    else:
        assert result.returncode == 0, result.stderr
        print(result.stdout.strip())

with tempfile.TemporaryDirectory(prefix='iw-radio-power-') as td:
    work = Path(td)
    shutil.copy2(a.iw_source, work / 'phy.c')
    if not a.negative_control:
        subprocess.run(['patch', '--forward', '--batch', '--fuzz=0', '-p1', '-i',
                        str(repo / 'feeds/qca-wifi-7/iw/patches/634-iw-radio-scoped-txpower.patch')],
                       cwd=work, check=True, stdout=subprocess.DEVNULL)
    parser = function((work / 'phy.c').read_text(), 'handle_txpower')
    harness = r'''
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
enum id_input { II_NONE, II_NETDEV, II_PHY_NAME, II_PHY_IDX, II_WDEV };
enum nl80211_tx_power_setting { NL80211_TX_POWER_AUTOMATIC, NL80211_TX_POWER_LIMITED, NL80211_TX_POWER_FIXED };
enum { NL80211_ATTR_WIPHY_RADIO_INDEX, NL80211_ATTR_MLO_LINK_ID, NL80211_ATTR_WIPHY_TX_POWER_SETTING, NL80211_ATTR_WIPHY_TX_POWER_LEVEL };
#define MAX_MLD_LINK 15
struct nl80211_state {};
struct nl_msg { int present[4], value[4]; };
#define NLA_PUT_U8(msg, attr, val) do { if (fail_put) goto nla_put_failure; (msg)->present[attr]++; (msg)->value[attr]=(val); } while(0)
#define NLA_PUT_U32 NLA_PUT_U8
static int fail_put;
''' + parser + r'''
static struct nl_msg msg;
static int run(enum id_input id, char *input) {
 char buf[200], *args[12], *word; int n=0;
 strcpy(buf,input);memset(&msg,0,sizeof(msg));
 for(word=strtok(buf," ");word;word=strtok(NULL," "))args[n++]=word;
 return handle_txpower(NULL,&msg,n,args,id);
}
int main(void) {
 assert(run(II_PHY_NAME,"radio 1 fixed 2300")==0);
 assert(msg.present[NL80211_ATTR_WIPHY_RADIO_INDEX]==1 && msg.value[NL80211_ATTR_WIPHY_RADIO_INDEX]==1);
 assert(msg.value[NL80211_ATTR_WIPHY_TX_POWER_LEVEL]==2300 && !msg.present[NL80211_ATTR_MLO_LINK_ID]);
 assert(run(II_PHY_IDX,"radio 0 limit 1400")==0 && msg.value[NL80211_ATTR_WIPHY_RADIO_INDEX]==0);
 assert(run(II_PHY_NAME,"radio 1 auto")==0 && !msg.present[NL80211_ATTR_WIPHY_TX_POWER_LEVEL]);
 assert(run(II_PHY_NAME,"radio 1 fixed 0")==0 && msg.value[NL80211_ATTR_WIPHY_TX_POWER_LEVEL]==0);
 assert(run(II_PHY_NAME,"fixed 1700")==0 && !msg.present[NL80211_ATTR_WIPHY_RADIO_INDEX]);
 assert(run(II_NETDEV,"-l 7 fixed 1900")==0 && msg.value[NL80211_ATTR_MLO_LINK_ID]==7 && !msg.present[NL80211_ATTR_WIPHY_RADIO_INDEX]);
 assert(run(II_NETDEV,"radio 1 fixed 1700")!=0 && !msg.present[NL80211_ATTR_WIPHY_TX_POWER_SETTING]);
 assert(run(II_WDEV,"radio 1 auto")!=0);
 char *invalid[]={"radio", "radio 1", "radio bad auto", "radio -1 auto", "radio 256 auto", "radio 1 fixed", "radio 1 fixed wrong", "radio 1 auto 2300"};
 for(unsigned i=0;i<sizeof(invalid)/sizeof(*invalid);i++)assert(run(II_PHY_NAME,invalid[i])!=0);
 fail_put=1;assert(run(II_PHY_NAME,"radio 1 fixed 2300")==-ENOBUFS);
 puts("PASS 17 actual iw parser cases: radio attribute, unchanged link/global ABI, malformed inputs and netlink allocation failure");
 return 0;
}
'''
    c = work / 'iw-test.c'
    c.write_text(harness)
    binary = work / 'iw-test'
    subprocess.run(['cc', '-std=gnu11', '-Werror', str(c), '-o', str(binary)], check=True)
    result = subprocess.run([str(binary)], capture_output=True, text=True)
    if a.negative_control:
        assert result.returncode != 0, 'Old iw unexpectedly accepted radio scoping'
        print('PASS actual old-iw negative control rejected radio-scoped command')
    else:
        assert result.returncode == 0, result.stderr
        print(result.stdout.strip())
