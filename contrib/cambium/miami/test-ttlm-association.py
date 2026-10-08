#!/usr/bin/env python3
"""Compile the actual prepared association TTLM block against peer fixtures.

Pass the prepared SDK src/ap/ieee802_11.c. Hardware/driver mapping is the
only mocked boundary; an accidental call without an MLD is a test failure.
The old SDK block fails the zero-initialized single-link station case.
"""
import pathlib
import re
import subprocess
import sys
import tempfile

source = pathlib.Path(sys.argv[1]).read_text()
blocks = re.findall(
    r"\tif \([^;{}]+\)\n\t\thostapd_apply_ttlm_mapping_to_driver\(hapd, sta\);",
    source,
)
assert len(blocks) == 1, "association TTLM block missing or ambiguous"
program = r'''
#include <assert.h>
#define WLAN_STATUS_SUCCESS 0
struct config { int mld_ap, ttlm_enable; };
struct hostapd_data { struct config *conf; };
struct sta_info {
    struct {
        int mld_sta;
        struct {
            struct { int ttlm_resp_type; } ttlm_ongoing_negotiation_info;
        } tid_map_info;
    } mld_info;
};
static int calls;
static void hostapd_apply_ttlm_mapping_to_driver(struct hostapd_data *hapd,
                                               struct sta_info *sta) {
    assert(hapd->conf->mld_ap && sta && sta->mld_info.mld_sta);
    calls++;
}
static void association(struct hostapd_data *hapd, struct sta_info *sta) {
BLOCK
}
int main(void) {
    struct config conf = {0, 1};
    struct hostapd_data hapd = {&conf};
    struct sta_info sta = {0};
    /* Ordinary EHT/HE client: default response zero must not imply TTLM. */
    association(&hapd, &sta); assert(calls == 0);
    /* MLO-capable client associating with an independent BSS. */
    sta.mld_info.mld_sta = 1;
    association(&hapd, &sta); assert(calls == 0);
    /* Ordinary client on an explicitly configured MLD AP. */
    conf.mld_ap = 1; sta.mld_info.mld_sta = 0;
    association(&hapd, &sta); assert(calls == 0);
    /* No station, TTLM disabled, and unsuccessful TTLM response. */
    association(&hapd, 0); assert(calls == 0);
    sta.mld_info.mld_sta = 1; conf.ttlm_enable = 0;
    association(&hapd, &sta); assert(calls == 0);
    conf.ttlm_enable = 1;
    sta.mld_info.tid_map_info.ttlm_ongoing_negotiation_info.ttlm_resp_type = 1;
    association(&hapd, &sta); assert(calls == 0);
    /* Preserve a successful, enabled, explicit MLD-to-MLD mapping. */
    sta.mld_info.tid_map_info.ttlm_ongoing_negotiation_info.ttlm_resp_type = 0;
    association(&hapd, &sta); assert(calls == 1);
    return 0;
}
'''.replace("BLOCK", blocks[0])
with tempfile.TemporaryDirectory(prefix="miami-ttlm-test-") as tmp:
    path = pathlib.Path(tmp)
    (path / "test.c").write_text(program)
    subprocess.run(["cc", "-Wall", "-Werror", str(path / "test.c"), "-o", str(path / "test")], check=True)
    subprocess.run([str(path / "test")], check=True)
print("7 actual association TTLM peer cases passed")
