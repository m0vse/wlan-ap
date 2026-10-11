#!/usr/bin/env python3
"""Compile the actual SDK PMLO parser with lifecycle/allocation fixtures."""
import pathlib, subprocess, sys, tempfile
source = pathlib.Path(sys.argv[1]).read_text()
start = source.index('int wmi_print_ctrl_path_pmlo_stats_tlv(')
end = source.index('\nstatic int ath12k_wmi_ctrl_stats_subtlv_parser', start)
function = source[start:end]
harness = r'''
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <errno.h>
#include <assert.h>
#include <stddef.h>
#define offsetofend(T,m) (offsetof(T,m)+sizeof(((T*)0)->m))
#define min_t(t,a,b) ((t)(a)<(t)(b)?(t)(a):(t)(b))
#define WMI_AC_MAX 4
#define __packed __attribute__((packed))
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint32_t __le32;
#define GFP_ATOMIC 0
#define WMI_CTRL_PATH_PMLO_STATS 1
#define ATH12K_DBG_WMI 1
#define le32_to_cpu(v) (v)
#define GENMASK(h,l) (((1u << ((h)-(l)+1))-1) << (l))
#define u32_get_bits(v,m) (((v)&(m))/((m)&-(m)))
struct list_head { int unused; };
struct wmi_ctrl_path_pmlo_telemetry_stats {
       __le32 pdev_id;
       __le32 dl_inbss_airtime_per_ac;
       __le32 ul_inbss_airtime_per_ac;
       union {
               struct {
                       __le32 estimated_air_time_ac_be: 8,
                              estimated_air_time_ac_bk: 8,
                              estimated_air_time_ac_vi: 8,
                              estimated_air_time_ac_vo: 8;
               };
               __le32 estimated_air_time_per_ac;
       };
       __le32 avg_chan_lat_per_ac[WMI_AC_MAX];
       __le32 link_obss_airtime : 8,
              link_idle_airtime : 8,
              ul_inbss_airtime_non_ac : 8,
              dl_inbss_airtime_non_ac : 8;
       __le32 traffic_condition_used_per_ac[WMI_AC_MAX];
       __le32 payload_ratio_dl_per_ac;
       __le32 payload_ratio_ul_per_ac;
       __le32 error_margin_per_ac[WMI_AC_MAX];
       __le32 num_of_dl_asymmetric_clients_per_ac[WMI_AC_MAX];
       __le32 num_of_ul_asymmetric_clients_per_ac[WMI_AC_MAX];
} __packed;
struct wmi_ctrl_path_stats_list { void *stats_ptr; int tagid; struct list_head list; };
struct ath12k {
 int wmi_ctrl_path_stats_lock;
 struct { struct { u32 estimated_air_time_ac_be, estimated_air_time_ac_bk,
 estimated_air_time_ac_vi, estimated_air_time_ac_vo; } telemetry_stats; } stats;
 struct { int wmi_ctrl_path_stats_lock; struct list_head period_wmi_list; int wmi_ctrl_path_stats_tagid; } debug;
};
struct ath12k_pdev { u32 pdev_id; struct ath12k *ar; };
struct ath12k_base { int num_radios; struct ath12k_pdev pdevs[2]; };
struct wmi_ctrl_path_stats_ev_parse_param { struct list_head list; struct ath12k *ar; };
static struct ath12k *active;
static int warnings, calls, fail_at, live;
static void *allocated[2];
#define kzalloc(n,flags,...) test_kzalloc(n,flags)
static void *test_kzalloc(size_t n, int flags) {
 (void)flags; ++calls;
 if (calls == fail_at) return NULL;
 void *p=calloc(1,n); allocated[calls-1]=p; if(p) ++live; return p;
}
static void kfree(void *p) {
 if(!p) return;
 for(int i=0;i<2;i++) if(allocated[i]==p) allocated[i]=NULL;
 --live; free(p);
}
static struct ath12k *ath12k_mac_get_ar_by_pdev_id(struct ath12k_base *ab, u32 id) {
 for(int i=0;i<ab->num_radios;i++) if(ab->pdevs[i].pdev_id==id) return active;
 return NULL;
}
#define list_add_tail(a,b) ((void)(a),(void)(b))
#define list_del(a) ((void)(a))
#define spin_lock_bh(a) ((void)(a))
#define spin_unlock_bh(a) ((void)(a))
#define ath12k_wmi_crl_path_stats_list_free(a,b) ((void)(a),(void)(b))
#define ath12k_warn(...) (++warnings)
#define ath12k_dbg(...) ((void)0)
'''
main = r'''
int main(void) {
 struct ath12k radio={0};
 struct ath12k_base ab={.num_radios=2,.pdevs={{.pdev_id=1,.ar=&radio},{.pdev_id=2,.ar=&radio}}};
 for(int test=0;test<10;test++) {
  struct wmi_ctrl_path_stats_ev_parse_param output={0};
  struct wmi_ctrl_path_pmlo_telemetry_stats input={.pdev_id=1,.estimated_air_time_per_ac=0x04030201};
  warnings=calls=live=fail_at=0; active=NULL; memset(allocated,0,sizeof(allocated));
  u16 len=sizeof(input); int expected=0, expected_warn=0, expected_live=0;
  if(test==1) input.pdev_id=2;
  if(test==2) {input.pdev_id=0;expected=-EINVAL;expected_warn=1;}
  if(test==3) {len=15;expected=-EINVAL;expected_warn=1;}
  if(test==4) {fail_at=1;expected=-ENOMEM;}
  if(test==5) {fail_at=2;expected=-ENOMEM;}
  if(test>=6) {active=&radio;expected_live=2;}
  if(test>=7) {active=&radio;expected_live=2;len=(test==7?16:test==8?36:sizeof(input)+4);}
  unsigned char *wire=calloc(1,len);
  memcpy(wire,&input,len<sizeof(input)?len:sizeof(input));
  int ret=wmi_print_ctrl_path_pmlo_stats_tlv(&ab,len,wire,&output);
  free(wire);
  if(ret!=expected || warnings!=expected_warn || live!=expected_live) {
   fprintf(stderr,"case %d: ret %d warn %d live %d\n",test,ret,warnings,live);return 1;
  }
  if(test>=6) {
   assert(output.ar==&radio);
   assert(radio.stats.telemetry_stats.estimated_air_time_ac_be==1);
   assert(radio.stats.telemetry_stats.estimated_air_time_ac_vo==4);
  } else assert(output.ar==NULL);
  for(int i=0;i<2;i++) kfree(allocated[i]);
  assert(live==0);
 }
 puts("PASS: 10 actual PMLO parser/SDK-structure cases including bounded 16/36/108/112-byte records");
}
'''
with tempfile.TemporaryDirectory() as d:
    c = pathlib.Path(d)/'parser.c'
    c.write_text(harness + function + main)
    exe = pathlib.Path(d)/'parser'
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-fsanitize=address',str(c),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
