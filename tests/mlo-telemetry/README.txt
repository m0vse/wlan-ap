Retained qualified native MLO telemetry/RSSI regressions, extended for power.

Run: python3 tests/mlo-telemetry/run-tests.py REPO SCHEMA_BEFORE_104 UCODE

The runner works only in a disposable fixture, applies the actual package
patches with zero fuzz, and executes the production peer and radio/SSID
collectors. Firmware/netlink, filesystem and transport boundaries are mocked.
It checks old-family/non-MLO output, authorization, MLD counter ownership,
radio references, missing links, native startup order, RSSI and missing/zero/
negative power. This is source regression evidence, not hardware acceptance.
