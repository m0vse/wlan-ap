Regular wifi-scripts discovery propagation, source-only qualification

Patch0159 registers and forwards explicit FILS minimum/maximum intervals and
unsolicited probe response intervals only on 6GHz BSSes. It also forwards an
explicit non-PSC exclusion only for automatic 6GHz channels. No default is
introduced, no security/country/width/channel is changed, and independent
QCA vendor feed scripts are untouched. Native hostapd validation is retained.

Tests run the actual emission function and ACS fragment with synthetic JSON
under host sh and actual Jaguar/Sage BusyBox through QEMU: seven tests PASS.
The patch replays on regular selected scripts with zero fuzz. Tests verify
option registration, call integration, accepted parser names, absent options,
explicit zero, 6GHz gating, fixed-channel gating and shell syntax.

test-parser.py uses a deliberately invalid driver: parsing fails before driver
initialization. Actual Jaguar wpad accepts all four discovery keys; an unknown
key is rejected. Sage's Wi-Fi5 build accepts FILS keys but rejects the disabled
unsolicited 6GHz-only feature, an explicit negative control (--wifi5). Those
options are never emitted for Sage's 2G/5G configurations. No AP/driver started.

The selected regular wpad-full-openssl is a multicall build. Its hostapd
Makefile includes ../wpa_supplicant/.config when MULTICALL is set; that full
configuration already enables CONFIG_FILS=y. The commented hostapd-only base
config is not the combined binary's feature set. No redundant compile flag
or feature-policy change is added. Repeat parser checks against new images.

Runtime beacon/client discovery and reboot persistence remain separate from
these source/target-parser tests. No AP FILS changes were made during testing.
Full-caller regression: test-bss-integration.py OPENWRT_ROOT runs the entire
hostapd_set_bss_options function with the native base-files append function.
It reproduces the old FILS/ctrl_interface joining bug as a negative control.
DISCOVERY_TEST_SHELL can select the shipped BusyBox via qemu. Set
DISCOVERY_TARGET_ROOT and DISCOVERY_TARGET_EMULATOR to additionally check
complete emitted BSS text and power enums/default/invalid value against the
selected target hostapd parser, using a deliberately invalid driver (no radio
initialization). Without TARGET_ROOT the parser check explicitly skips.
