# Raw nl80211 scan SSID codec regression

`NL80211_ATTR_SCAN_SSIDS` contains binary SSIDs, not NUL-terminated strings.
Appending a terminator changes a wildcard to a one-byte SSID and makes a
maximum-length SSID exceed the kernel's 32-byte limit. The corresponding decoder
must retain all bytes and accept an empty binary attribute, while continuing to
reject empty nonbinary text attributes.

Patch 0195 adds `DF_BINARY` to the scan SSID array and permits empty binary
`DT_STRING` values during decoding. It does not change active/passive scan
selection, regulatory rules, radio firmware, board data, channel or power policy.
The package release becomes 5; the source pin and existing MLO/ACK fixes stay put.

Build both interceptors against exactly the selected module's libnl and UAPI
headers, for the same architecture and libc as the test interpreter. Sage uses
the SDK's Linux UAPI header. QCA-6/7 builds instead need `SCAN_USE_QCA_HEADER`
defined and their exact prepared `nl80211_copy.h` on the include path. Link with
`-shared -fPIC -lnl-tiny -ldl`.

Place old and fixed modules in separate directories as `nl80211.so`. Run
`test-scan-ssid-codec.py` with the matching interpreter, both module filenames,
the outgoing interceptor and `--decoder-interceptor`. `--ssh-target` explicitly
opts into an already prepared Linux target; use `--ssh-known-hosts` for a verified
host-key file. The target needs no Python installation.

The test asserts the module's actual `/proc/self/maps` pathname. Do not pass a
literal `.so` filename directly to ucode's `-L`: it treats that as a directory.
Additional default-path overrides can also shadow the candidate. The test uses
a single candidate `*.so` search pattern and fails if another module loads.

The 16 outbound controls inspect absent/passive SSIDs, the empty wildcard,
named/one-byte/32-byte/UTF-8/embedded-NUL/multiple SSIDs. Each TRIGGER_SCAN is
intercepted before transmission. Four synthetic-reply controls exercise the real
decoder with empty/nonempty binary SSIDs, another binary attribute and valid or
empty nonbinary text. GET_INTERFACE is blocked and its reply fabricated; only
normal nl80211 family discovery reaches the kernel. No interface is created and
no radio operation is performed by these regression cases.

These are codec correctness tests, not RF acceptance. A controlled hardware
comparison still reproduced deficient active 2.4 GHz discovery with the corrected
module. Do not describe this patch as a complete fix for that separate observed
fault or replace active scans with passive scans on its account.
