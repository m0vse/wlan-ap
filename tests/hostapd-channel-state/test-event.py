#!/usr/bin/env python3
"""Execute the production channel-switch validation/commit fragment, no driver IO."""
import argparse,pathlib,subprocess,tempfile
p=argparse.ArgumentParser();p.add_argument('--source',type=pathlib.Path,required=True);p.add_argument('--negative-control',action='store_true');a=p.parse_args()
s=a.source.read_text();start=s.index('void hostapd_event_ch_switch(')
start=s.index('\t/* Check if any of configured channels require DFS */',start)
end=s.index('\n\tswitch (width)',start);body=s[start:end]
program=r'''
#include <assert.h>
#include <stdio.h>
#define HOSTAPD_MODULE_IEEE80211 0
#define HOSTAPD_LEVEL_WARNING 0
struct iface {int freq;};struct hostapd_data {struct iface *iface;};
static int lookup;
static int hostapd_is_dfs_required(struct iface*i){return 0;}
static int hostapd_hw_get_channel(struct hostapd_data*h,int f){return lookup;}
#define hostapd_logger(...) ((void)0)
static void event(struct hostapd_data*hapd,int freq){int is_dfs0,channel;
'''+body+r'''
}
int main(void){
 struct iface i={5180};struct hostapd_data h={&i};
 lookup=0;event(&h,5955);assert(i.freq==5180); /* unknown link/band cannot partially commit */
 lookup=1;event(&h,5955);assert(i.freq==5955);
 lookup=153;event(&h,5765);assert(i.freq==5765);
 lookup=0;event(&h,9999);assert(i.freq==5765);
 puts("PASS 4 actual event validation/commit controls; channel lookup/driver boundary mocked");
}
'''
with tempfile.TemporaryDirectory(prefix='hostapd-event-state-') as t:
 c=pathlib.Path(t)/'event.c';binary=c.with_suffix('');c.write_text(program)
 subprocess.run(['gcc','-std=gnu11',str(c),'-o',str(binary)],check=True)
 r=subprocess.run([str(binary)],capture_output=True,text=True)
 if a.negative_control:assert r.returncode!=0;print('PASS negative control: old channel event leaves frequency partially updated')
 else:print(r.stdout,end='');print(r.stderr,end='');assert r.returncode==0

if not a.negative_control:
 start=s.index('\t/* Check if any of configured channels require DFS */',s.index('void hostapd_event_ch_switch('))
 end=s.index('\n\tswitch (hapd->iface->current_mode->mode)',start)
 body=s[start:end]
 program=r'''
#include <assert.h>
#include <stdio.h>
enum hostapd_hw_mode {HOSTAPD_MODE_IEEE80211A,HOSTAPD_MODE_IEEE80211G};
enum {CHAN_WIDTH_80,CHAN_WIDTH_80P80,CHAN_WIDTH_160,CHAN_WIDTH_320,CHAN_WIDTH_20_NOHT,CHAN_WIDTH_20,CHAN_WIDTH_40};
enum {CONF_OPER_CHWIDTH_80MHZ,CONF_OPER_CHWIDTH_80P80MHZ,CONF_OPER_CHWIDTH_160MHZ,CONF_OPER_CHWIDTH_320MHZ,CONF_OPER_CHWIDTH_USE_HT};
struct hostapd_hw_modes {int mode;};struct conf {enum hostapd_hw_mode hw_mode;};
struct iface {int freq;struct conf *conf;struct hostapd_hw_modes *current_mode;};
struct hostapd_data {struct iface *iface;struct conf *iconf;};
static struct hostapd_hw_modes old_mode,new_mode;static int fail,lookup=1;
static int hostapd_is_dfs_required(struct iface*i){return 0;}
static int hostapd_hw_get_channel(struct hostapd_data*h,int f){return lookup;}
static int hostapd_csa_update_hwmode(struct iface*i){i->conf->hw_mode=HOSTAPD_MODE_IEEE80211G;i->current_mode=&new_mode;return fail;}
#define hostapd_logger(...) ((void)0)
static void event(struct hostapd_data*hapd,int freq,int finished){
 int channel,chwidth,is_dfs0,width=CHAN_WIDTH_160;
 int previous_freq=hapd->iface->freq;
 enum hostapd_hw_mode previous_hw_mode=hapd->iconf->hw_mode;
 struct hostapd_hw_modes *previous_mode=hapd->iface->current_mode;
'''+body+r'''
}
int main(void){
 struct conf c={HOSTAPD_MODE_IEEE80211A};struct iface i={5180,&c,&old_mode};struct hostapd_data h={&i,&c};
 fail=1;event(&h,5955,1);assert(i.freq==5180&&c.hw_mode==HOSTAPD_MODE_IEEE80211A&&i.current_mode==&old_mode);
 lookup=0;event(&h,9999,1);assert(i.freq==5180&&c.hw_mode==HOSTAPD_MODE_IEEE80211A&&i.current_mode==&old_mode);
 lookup=1;fail=0;event(&h,5955,1);assert(i.freq==5955&&c.hw_mode==HOSTAPD_MODE_IEEE80211G&&i.current_mode==&new_mode);
 i.freq=5180;c.hw_mode=HOSTAPD_MODE_IEEE80211A;i.current_mode=&old_mode;fail=1;event(&h,5955,0);assert(i.freq==5955&&i.current_mode==&old_mode);
 puts("PASS 4 actual event mode-update/rollback controls; hardware-mode boundary mocked");
}
'''
 with tempfile.TemporaryDirectory(prefix='hostapd-event-mode-') as t:
  c=pathlib.Path(t)/'event.c';binary=c.with_suffix('');c.write_text(program)
  subprocess.run(['gcc','-std=gnu11',str(c),'-o',str(binary)],check=True)
  subprocess.run([str(binary)],check=True)
