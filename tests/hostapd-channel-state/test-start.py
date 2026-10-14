#!/usr/bin/env python3
"""Execute the actual prepared C startup function with real libucode values.

Driver, beacon and interface lifecycle boundaries are mocked: no AP is used.
The package's full target compilation separately checks real structure layout.
"""
import argparse, pathlib, subprocess, tempfile, re
p=argparse.ArgumentParser();p.add_argument('--source',type=pathlib.Path,required=True)
p.add_argument('--ucode-prefix',type=pathlib.Path,required=True)
p.add_argument('--startup-source',type=pathlib.Path)
p.add_argument('--negative-control',action='store_true');a=p.parse_args()
source=(a.startup_source or a.source/'src/ap/ucode.c').read_text()
start=source.index('static void\nuc_hostapd_restore_channel(') if 'uc_hostapd_restore_channel(' in source else source.index('static uc_value_t *\nuc_hostapd_iface_start(')
end=source.index('\nstatic uc_value_t *\nuc_hostapd_iface_switch_channel(',start)
body=source[start:end]
common=(a.source/'src/common/ieee802_11_common.c').read_text()
start=common.index('enum hostapd_hw_mode\nieee80211_freq_to_channel_ext(')
end=common.index('\n}',start)+2
conversion=common[start:end]
harness=r'''
#include "utils/includes.h"
#include "utils/common.h"
#include "common/defs.h"
#include <ucode/lib.h>
#include <assert.h>
#include <limits.h>
#undef uc_fn_thisval
#undef uc_fn_arg
#define uc_fn_thisval(name) fixture_iface()
#define uc_fn_arg(n) fixture_info()
#define NL80211_REG_NUM_POWER_MODES 4
enum { HAPD_IFACE_DISABLED, HAPD_IFACE_ENABLED, HAPD_IFACE_DFS };
struct hostapd_config { int hw_mode,channel,op_class,secondary_channel,acs,punct_bitmap;
 int ieee80211n,ieee80211ac,ieee80211ax,ieee80211be,enable_edmg,edmg_channel;
 int bandwidth_device,center_freq_device,enable_best_power_mode,he_6ghz_reg_pwr_type;
 int width,seg0,seg1; };
struct hostapd_bss_config { int start_disabled; const char *iface; };
struct hostapd_data { int beacon_set_done; struct hostapd_bss_config *conf; u8 own_addr[6]; };
struct hostapd_iface { int freq,state,num_bss; struct hostapd_config *conf; struct hostapd_data **bss; };
static struct hostapd_config config;
static struct hostapd_bss_config bss_config[2];
static struct hostapd_data bss[2];
static struct hostapd_data *bss_ptr[2]={&bss[0],&bss[1]};
static struct hostapd_iface iface;
static uc_value_t *info;
static struct hostapd_iface *fixture_iface(void){return &iface;}
static uc_value_t *fixture_info(void){return info;}
static int calls,beacons,disabled,enable_ret,fail_call,fail_beacon;
static int is_6ghz_freq(int f){return f==5935||(f>=5955&&f<=7115);}
static int is_6ghz_op_class(int c){return c>=131&&c<=137;}
static enum hostapd_hw_mode ieee80211_freq_to_channel_ext(unsigned int,int,enum oper_chan_width,u8*,u8*);
static enum hostapd_hw_mode ieee80211_freq_to_chan(int f,u8*c){u8 o;return ieee80211_freq_to_channel_ext(f,0,CONF_OPER_CHWIDTH_USE_HT,&o,c);}
static int hostapd_hw_get_freq(struct hostapd_data*b,int c){return 5950+5*c;}
static void hostapd_set_oper_centr_freq_seg0_idx(struct hostapd_config*c,int v){c->seg0=v;}
static void hostapd_set_oper_centr_freq_seg1_idx(struct hostapd_config*c,int v){c->seg1=v;}
static void hostapd_set_oper_chwidth(struct hostapd_config*c,int v){c->width=v;}
static int hostapd_get_oper_chwidth(const struct hostapd_config*c){return c->width;}
static int hostapd_get_oper_centr_freq_seg0_idx(const struct hostapd_config*c){return c->seg0;}
static int hostapd_get_oper_centr_freq_seg1_idx(const struct hostapd_config*c){return c->seg1;}
static int hostapd_is_dfs_required(struct hostapd_iface*i){return 0;}
static int hostapd_is_dfs_chan_available(struct hostapd_iface*i){return 1;}
static void uc_hostapd_disable_iface(struct hostapd_iface*i){if(i->state!=HAPD_IFACE_DISABLED){disabled++;i->state=HAPD_IFACE_DISABLED;}}
static int hostapd_disable_iface(struct hostapd_iface*i){disabled++;i->state=HAPD_IFACE_DISABLED;return 0;}
static void hostapd_set_state(struct hostapd_iface*i,int state){i->state=state;}
static int hostapd_enable_iface(struct hostapd_iface*i){if(!enable_ret)i->state=HAPD_IFACE_ENABLED;return enable_ret;}
static void hostapd_apply_6ghz_dynamic_puncturing(struct hostapd_iface*i){}
static int hostapd_get_best_ap_6ghz_power_mode_for_iface(struct hostapd_iface*i){return NL80211_REG_NUM_POWER_MODES;}
static int hostapd_set_freq(struct hostapd_data*b,int mode,int freq,int channel,...){calls++;return calls==fail_call?-1:0;}
static int ieee802_11_set_beacon(struct hostapd_data*b){beacons++;return beacons==fail_beacon?-1:0;}
static void hostapd_owe_update_trans(struct hostapd_iface*i){}
#undef wpa_printf
#define wpa_printf(...) ((void)0)
static void put(const char*k,int v){ucv_object_add(info,k,ucv_int64_new(v));}
static void reset(void){
 ucv_put(info);info=ucv_object_new(NULL);calls=beacons=disabled=enable_ret=fail_call=fail_beacon=0;
 memset(&config,0,sizeof(config));config.hw_mode=HOSTAPD_MODE_IEEE80211A;config.channel=1;
 config.op_class=134;config.ieee80211ax=config.ieee80211be=1;config.width=CONF_OPER_CHWIDTH_160MHZ;config.seg0=15;
 iface=(struct hostapd_iface){.conf=&config,.freq=5955,.state=HAPD_IFACE_ENABLED,.num_bss=2,.bss=bss_ptr};
 for(int i=0;i<2;i++){bss_config[i]=(struct hostapd_bss_config){.start_disabled=1,.iface="fixture"};bss[i]=(struct hostapd_data){.conf=&bss_config[i],.beacon_set_done=1};}
 put("frequency",5955);put("channel",1);put("op_class",134);put("hw_mode",HOSTAPD_MODE_IEEE80211A);
 put("sec_channel",0);put("center_seg0_idx",15);put("center_seg1_idx",0);put("oper_chwidth",CONF_OPER_CHWIDTH_160MHZ);put("punct_bitmap",0);
}
'''
checks=r'''
static int run(void){uc_value_t*r=uc_hostapd_iface_start(NULL,1);int ok=ucv_boolean_get(r);ucv_put(r);return ok;}
int main(void){
 reset();assert(run());assert(calls==0&&beacons==0); /* identical valid tuple */
 reset();put("channel",36);assert(!run());assert(config.channel==1&&iface.freq==5955&&calls==0&&disabled==0);
 reset();ucv_object_delete(info,"channel");assert(!run());assert(config.channel==1&&calls==0);
 reset();ucv_object_delete(info,"frequency");assert(!run());assert(iface.freq==5955&&calls==0);
 reset();put("op_class",115);assert(!run());assert(config.op_class==134&&calls==0);
 reset();put("frequency",0);assert(!run());assert(iface.freq==5955&&calls==0);
 reset();put("frequency",5956);assert(!run());assert(iface.freq==5955&&calls==0);
 reset();put("oper_chwidth",CONF_OPER_CHWIDTH_80MHZ);put("center_seg0_idx",7);put("op_class",133);
 assert(run());assert(calls==2&&beacons==2&&config.width==CONF_OPER_CHWIDTH_80MHZ);
 reset();put("center_seg0_idx",47);assert(run());assert(calls==2&&beacons==2);
 reset();put("punct_bitmap",2);assert(run());assert(calls==2&&config.punct_bitmap==2);
 reset();put("op_class",133);assert(run());assert(calls==2); /* opclass-only update cannot no-op */
 reset();put("frequency",2412);put("channel",1);put("op_class",81);put("hw_mode",HOSTAPD_MODE_IEEE80211G);put("oper_chwidth",0);put("center_seg0_idx",0);
 assert(run());assert(calls==2&&iface.freq==2412); /* same channel number, different band */
 reset();put("frequency",2412);put("channel",1);put("op_class",81);put("hw_mode",HOSTAPD_MODE_IEEE80211B);put("oper_chwidth",0);put("center_seg0_idx",0);
 assert(run());assert(calls==2&&config.hw_mode==HOSTAPD_MODE_IEEE80211B); /* zero-valued legacy enum is valid */
 reset();put("frequency",5765);put("channel",153);put("op_class",125);put("oper_chwidth",0);put("center_seg0_idx",153);
 assert(run());assert(calls==2&&beacons==2&&config.channel==153); /* legacy band */
 reset();put("punct_bitmap",2);fail_call=1;assert(!run());assert(calls==1&&beacons==0&&disabled==1&&config.punct_bitmap==0);
 reset();put("punct_bitmap",2);fail_call=2;assert(!run());assert(calls==2&&beacons==0&&disabled==1);
 reset();put("punct_bitmap",2);fail_beacon=1;assert(!run());assert(calls==2&&beacons==1&&disabled==1);
 reset();iface.state=HAPD_IFACE_DISABLED;put("frequency",6115);put("channel",33);put("center_seg0_idx",47);enable_ret=-1;assert(!run());assert(beacons==0&&disabled==1&&config.channel==1&&iface.freq==5955&&iface.state==HAPD_IFACE_DISABLED);
 reset();iface.state=HAPD_IFACE_DISABLED;assert(run());assert(iface.state==HAPD_IFACE_ENABLED);
 reset();ucv_put(info);info=NULL;iface.state=HAPD_IFACE_DISABLED;enable_ret=-1;assert(!run()); /* no-info initialization */
 ucv_put(info);puts("PASS 20 actual startup-function controls with real libucode values; mocked driver/beacon/lifecycle");return 0;
}
'''
if a.negative_control:
 checks=r'''
static int run(void){uc_value_t*r=uc_hostapd_iface_start(NULL,1);int ok=ucv_boolean_get(r);ucv_put(r);return ok;}
int main(void){reset();put("punct_bitmap",2);fail_call=1;
 assert(!run());assert(calls==1&&beacons==0);return 0;}
'''
with tempfile.TemporaryDirectory(prefix='hostapd-channel-state-') as temp:
 root=pathlib.Path(temp); c=root/'test.c';binary=root/'test'
 c.write_text(harness+'\n'+conversion+'\n'+body+'\n'+checks)
 subprocess.run(['gcc','-std=gnu11','-Werror=implicit-function-declaration','-I'+str(a.source/'src'),'-I'+str(a.ucode_prefix/'include'),'-I'+str(a.ucode_prefix.parent/'host/include'),str(c),'-L'+str(a.ucode_prefix/'lib'),'-Wl,-rpath,'+str(a.ucode_prefix/'lib'),'-lucode','-o',str(binary)],check=True)
 result=subprocess.run([str(binary)],capture_output=True,text=True)
 if a.negative_control:
  assert result.returncode != 0,'Old startup unexpectedly passed the regression';print('PASS negative control: unmodified startup fails actual-function regression')
 else:
  print(result.stdout,end='');print(result.stderr,end='')
  if result.returncode:
   match=re.search(r'test.c:(\d+)',result.stderr)
   if match:print(c.read_text().splitlines()[int(match[1])-1])
  assert result.returncode==0,result.returncode
