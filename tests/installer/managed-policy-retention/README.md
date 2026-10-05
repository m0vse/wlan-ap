# Discovery policy retention during managed upgrades

This concerns existing OpenWiFi managed upgrades, not OEM/OpenWrt FORMAT 2 enrollment.

The incoming certificate service restores `/certificates/discovery-policy.json` even when the saved runtime key and operational certificate are already present. An archived explicit or malformed `/etc/ucentral/discovery-policy.json` takes precedence over the older durable copy. A durable policy replaces only an absent runtime policy or a recognized `mode: default` fallback. Certificate/key files are not changed by this policy restoration.

The future `ucentral-schema` managed updater includes `/etc/ucentral/discovery-policy.json` in its explicit `/upgrade.tgz` archive independently of the two keep flags. The build validator requires that archive entry.

## Older outgoing firmware prerequisite

The published Sage 2026.10.03.2 updater omits the runtime policy; its shared-store exporter does not snapshot it. A new incoming image cannot recover an explicit runtime-only policy that the old updater never saved. Adding a line to `sysupgrade.conf` alone is insufficient: the managed command supplies its own explicit archive.

Before approving that older managed route, the source owner must establish one of these conditions:

- There is no explicit runtime policy to retain: the current file is absent or is the approved recognized fallback.
- The explicit runtime policy already matches the policy in the verified active certificate store, and the incoming restore path has been qualified.
- A qualified source-side preservation bridge updates the outgoing managed archive command to include the runtime policy before starting the upgrade. Its archive test must verify the exact policy bytes, together with the existing identities, custom gateway CA, rendered configuration and active configuration document.

If none applies, hold the managed upgrade. Do not silently replace the explicit policy with the image's fallback overlay. Source-side bridge execution or durable policy changes require the route owner's separately authorized AP operation; the source tests do not perform either.

## Source regressions

Run `tests/installer/managed-policy-retention/test-policy-restore.py` as Root with `WLAN_AP_SOURCE_DIR` and `NATIVE_TEST_UCODE` pointing to an isolated source tree and an existing target ucode wrapper. Fixtures use synthetic policy/key text only. This exercises the actual restore helper and early-boot saved/full-copy paths; mount, hardware and installer boundaries are isolated.

Run `tests/installer/managed-policy-retention/test-managed-upgrade-command.py /path/to/extracted/root` with `OW_TEST_UCODE` set to the target wrapper. It executes the actual extracted managed command with actual tar archives; network, validator, sysupgrade and reboot boundaries are blocked. It requires exact explicit policy byte retention in all four keep-flag combinations.
