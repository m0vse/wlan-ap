#!/usr/bin/env python3
"""Exercise actual mac80211 insertion guards with mocked registry/lifecycle.

Arguments: selected backports source root; optional candidate ath11k mac.c.
No firmware or AP operations.
This is a control-flow fixture, not a concurrent/hardware qualification.
"""
import pathlib
import re
import subprocess
import sys
import tempfile

root = pathlib.Path(sys.argv[1])
source = (root / 'net/mac80211/sta_info.c').read_text()
mac_path = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else root / 'drivers/net/wireless/ath/ath11k/mac.c'
mac = mac_path.read_text()
register = mac[mac.index('static int __ath11k_mac_register'):mac.index('int ath11k_mac_register')]
assert 'ieee80211_hw_set(ar->hw, NEEDS_UNIQUE_STA_ADDR);' in register

def function(name):
    start = re.search(r'^(?:static )?int ' + re.escape(name) + r'\(', source, re.M).start()
    opening = source.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]

check = function('sta_info_insert_check')
insert = function('sta_info_insert_rcu')
assert source.index('sta_info_insert_check(sta)', source.index('int sta_info_insert_rcu')) < source.index('sta_info_insert_finish(sta)', source.index('int sta_info_insert_rcu'))
harness = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#define __acquires(x)
#define unlikely(x) (x)
#define WARN_ON(x) (x)
#define NEEDS_UNIQUE_STA_ADDR 1
struct hw { void *wiphy; bool unique; };
struct ieee80211_local { struct hw hw; };
struct ieee80211_sub_if_data {
    struct ieee80211_local *local;
    struct { unsigned char addr[6]; } vif;
    bool running;
};
struct sta_info {
    struct ieee80211_sub_if_data *sdata;
    struct ieee80211_local *local;
    struct { unsigned char addr[6]; } sta;
    unsigned char addr[6];
};
static int depth, freed, driver_calls;
static struct hw *existing_hw;
static unsigned char existing_addr[6];
static bool present;
static void rcu_read_lock(void) { depth++; }
static void rcu_read_unlock(void) { assert(depth > 0); depth--; }
static void lockdep_assert_wiphy(void *p) { (void)p; }
static void might_sleep(void) {}
static bool ieee80211_sdata_running(struct ieee80211_sub_if_data *s) { return s->running; }
static bool ether_addr_equal(const unsigned char *a, const unsigned char *b) { return !memcmp(a,b,6); }
static bool is_valid_ether_addr(const unsigned char *a) { return !(a[0]&1) && memcmp(a,"\0\0\0\0\0\0",6); }
static bool ieee80211_hw_check(struct hw *hw, int f) { (void)f; return hw->unique; }
static void *ieee80211_find_sta_by_ifaddr(struct hw *hw, const unsigned char *addr, void *ifaddr) {
    assert(depth > 0); assert(!ifaddr);
    return present && hw == existing_hw && ether_addr_equal(addr,existing_addr) ? hw : NULL;
}
static void sta_info_free(struct ieee80211_local *l, struct sta_info *s) { (void)l; (void)s; freed++; }
static int sta_info_insert_finish(struct sta_info *s) { (void)s; driver_calls++; rcu_read_lock(); return 0; }
'''
harness += '\n' + check + '\n' + insert + r'''
static int attempt(struct sta_info *s) {
    assert(depth == 0);
    int rc = sta_info_insert_rcu(s);
    assert(depth == 1); rcu_read_unlock(); return rc;
}
int main(void) {
    struct ieee80211_local a = {.hw.unique=true}, b = {.hw.unique=true};
    struct ieee80211_sub_if_data s = {.local=&a,.running=true};
    struct sta_info candidate = {.sdata=&s,.local=&a,.addr={2,4,6,8,10,12},.sta.addr={2,4,6,8,10,12}};
    existing_hw=&a.hw; memcpy(existing_addr,candidate.addr,6); present=true;
    assert(attempt(&candidate)==-ENOTUNIQ && driver_calls==0 && freed==1);
    for(int i=0;i<10000;i++) assert(attempt(&candidate)==-ENOTUNIQ);
    assert(driver_calls==0 && freed==10001 && present);
    s.local=&b; candidate.local=&b;
    assert(attempt(&candidate)==0 && driver_calls==1);
    s.local=&a; candidate.local=&a; present=false;
    assert(attempt(&candidate)==0 && driver_calls==2);
    present=true; candidate.addr[5]++; candidate.sta.addr[5]++;
    assert(attempt(&candidate)==0 && driver_calls==3);
    candidate.addr[5]--; candidate.sta.addr[5]--; a.hw.unique=false;
    assert(attempt(&candidate)==0 && driver_calls==4);
    a.hw.unique=true; s.running=false;
    assert(attempt(&candidate)==-ENETDOWN && driver_calls==4 && freed==10002);
    s.running=true; memcpy(s.vif.addr,candidate.sta.addr,6);
    assert(attempt(&candidate)==-EINVAL && driver_calls==4 && freed==10003);
    puts("PASS 8 unique-STA insertion/lifecycle controls (registry mocked, actual source functions)");
}
'''
with tempfile.TemporaryDirectory(prefix='unique-sta-controls.') as temp:
    c = pathlib.Path(temp) / 'controls.c'
    binary = pathlib.Path(temp) / 'controls'
    c.write_text(harness)
    subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', str(c), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
