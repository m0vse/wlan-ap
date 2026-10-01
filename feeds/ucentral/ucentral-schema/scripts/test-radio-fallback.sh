#!/bin/sh
# Run against the patched source with a host ucode interpreter; no AP side effects.
set -eu
source_dir=${1:?patched schema source directory required}
ucode_bin=${2:-ucode}
{
    printf '%s\n' 'let warnings = []; function warn(fmt, ...args) { push(warnings, sprintf(fmt, ...args)); }'
    awk '/function match_htmode\(phy, radio\)/ { output = 1 } output && /let channel_list =/ { exit } output { print }' "$source_dir/renderer/templates/radio.uc"
    printf '%s\n' '
let cases = [
    [ "Sage HE20", "HE", 20, ["HT20", "HT40", "VHT20", "VHT40", "VHT80"], "2G", "VHT20", 20 ],
    [ "Sage HE40", "HE", 40, ["VHT20", "VHT40", "VHT80"], "5G", "VHT40", 40 ],
    [ "Jaguar HE80", "HE", 80, ["HE20", "HE40"], "2G", "HE40", 40 ],
    [ "exact HE40", "HE", 40, ["HE20", "HE40", "HE80"], "5G", "HE40", 40 ],
    [ "PHY rank", "EHT", 320, ["HE320", "EHT20"], "5G", "EHT20", 20 ],
    [ "no 80+80 widening", "HE", 80, ["VHT80+80", "VHT80", "VHT40"], "5G", "VHT80", 80 ],
    [ "80+80 exact", "VHT", 8080, ["VHT80+80", "VHT80"], "5G", "VHT80+80", 8080 ],
    [ "80+80 fallback", "HE", 8080, ["VHT160", "VHT80"], "5G", "VHT160", 160 ],
    [ "HT fallback", "HE", 80, ["HT20", "HT40"], "5G", "HT40", 40 ]
];
for (let c in cases) {
    let radio = { channel_mode: c[1], channel_width: c[2], band: c[4], allow_dfs: true, channel: 36 };
    let got = match_htmode({ htmode: c[3], band: [c[4]] }, radio);
    assert(got == c[5], c[0] + ": wrong mode " + got);
    assert(radio.channel_width == c[6], c[0] + ": wrong effective width");
    assert((c[2] == c[6]) == exists(radio, "channel"), c[0] + ": channel preservation");
}
let radio = { channel_mode: "HE", channel_width: 320, band: "5G", allow_dfs: false };
assert(match_htmode({ htmode: ["VHT160", "VHT80"], band: ["5G"] }, radio) == "VHT80", "no-DFS fallback");
let failed = false;
try { match_htmode({ htmode: ["VHT40"], band: ["5G"] }, {channel_mode: "HE", channel_width: 20}); }
catch (e) { failed = true; }
assert(failed, "must fail rather than widen when no compatible width exists");
print("11 radio fallback cases passed\n");
'
} | "$ucode_bin" -

# Exercise the actual post-apply classification, not a duplicate implementation.
{
    printf '%s\n' 'for (let c in [[true, "batch", ["[W] warning"], 0], [false, "batch", ["strict reject"], 2], [true, "", [], 2], [true, "batch", ["[E] actual error"], 1]]) { let state = c[0]; let batch = c[1]; let logs = c[2]; let error = 0;'
    awk '/if \(!length\(batch\) \|\| !state\)/ { output = 1 } output && /^}/ { exit } output { print }' "$source_dir/renderer/ucentral.uc"
    printf '%s\n' 'assert(error == c[3], "wrong configure result"); } print("4 configure status cases passed\n");'
} | "$ucode_bin" -
grep -Fq 'if (state?.strict && length(logs))' "$source_dir/renderer/ucentral.uc"
grep -Fq 'status.warnings = logs;' "$source_dir/renderer/ucentral.uc"
