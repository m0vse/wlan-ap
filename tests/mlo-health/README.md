# Shared per-link MLO health

Run `python3 tests/mlo-health/run-tests.py REPO PREPARED_SCHEMA HOST_UCODE`.
The prepared schema must precede patch104. This applies the exact package patch
without fuzz and executes actual health, MLO evidence and DFS classifier code.
Kernel, UCI, bus, filesystem and control-socket boundaries are injected fixtures.
No AP access, wireless scans, radio/configuration changes or firmware builds occur.

Legacy healthy/missing/no-channel/disabled/non-AP/fresh/expired-CAC outputs are
compared with the existing collector across Sage, Jaguar, Cheetah, Thor, Miami and
Gambit source fixtures. The existing shared DFS tests run unchanged. MLO cases
require exact configured BSS, kernel link and fresh per-link hostapd identity,
physical WIPHY, independently reported hardware-radio index, BSSID, MLD address,
SSID and band/channel agreement. Missing, disabled, stale, wrong and ambiguous
secondary links remain failures. Only a positively pending exact link is deferred
for DFS; an active primary never clears a secondary fault.

The ordinary wifi.iface dictionary and peer counter contracts are unchanged.
The helper reads only GET_INTERFACE and bounded STATUS-only control requests.
It does not infer client MLO association or repair interfaces.

The live defect was a false six-GHz missing-SSID score that triggered native
network self-healing after the usual five-minute gap. The new collector recognizes
both real links without disabling recovery for genuine failures. Runtime trials
must keep source fixtures private in RAM and bind only the health entrypoint;
no firmware, UCI, certificates, host keys or radio configuration needs changing.
