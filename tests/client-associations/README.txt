Authorization-only association telemetry

Apply ucentral-schema patches including 095-authorized-station-telemetry.patch.
The package overlay installs wifi/station_authorization.uc beside station.uc.
For the pure target-runtime test, create a temporary directory containing
authorization.uc and wifi/station_authorization.uc, then run ucode authorization.uc.
The 12 cases cover authorized, unauthorized, unmasked, missing and malformed flags.

Linux nl80211 STA_FLAGS is exposed by ucode as [mask, set]. AUTHORIZED is
stable UAPI enum value 1 (bit 2). Explicit false is omitted from association
telemetry; unknown remains visible for drivers that do not expose the flag.
This avoids guessing from packet counts, which include authentication traffic.
The Clients API also excludes explicit authorized=false reports and retains
unmarked legacy reports. Old stored reports cannot be retrospectively classified.

2026-10-04: E410 ARM ucode passed all 12 cases and compilation of the actual
modified collector. A read-only kernel sample retained five authorized clients,
including Tuya 38:1f:8d:7c:f9:61 and 38:1f:8d:7c:fc:89. No firmware build or
AP restart was required. This is shared ucentral-schema code for all families;
new images must include package release 25.
