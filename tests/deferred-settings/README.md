# Deferred settings source draft

This is an unmerged source candidate based on b3fe180b550e7973083f642010c5bc2790f0b340. It does not alter published Thor firmware or the tested reboot-required UI response. No firmware was built and no AP was configured, flashed or rebooted.

The candidate shares the existing correlated reboot-required response across boot-only settings, distinguishes accepted pending configuration from applied configuration in the native client, and replaces the destructive legacy fixedconfig handler with validated pending country settings. It preserves other defaults and module options and never schedules a reboot or factory reset.

## Validation on 8 October 2026

- Native client: 8 passed, using actual callback/session/result source with real child exit and signal encoding. Queue, socket and reload boundaries are isolated.
- Shared lifecycle: 29 passed in the target aarch64 ucode runtime.
- Backend and renderer: 27 passed in the target runtime with actual root-owned fixture files. Crypto, physical radio, schema and process boundaries are explicitly mocked. The actual renderer patch applies without fuzz and executes its pre-apply block.
- Module-country shell helper: preservation of driver options, comments and permissions passed; invalid country, writable file, symlink and hardlink were refused in disposable root-owned fixtures.
- Source whitespace check passed excluding embedded unified patches, whose context lines retain upstream whitespace.

Run the native harness with `python3 test-native.py BASELINE_NATIVE REPO`. Run the target harness as root with `python3 test-target.py TARGET_ROOT REPO BASELINE_SCHEMA`. Run lifecycle.uc with the target ucode runtime and the source module directory on its library path.

## Review gates before integration

This draft is not hardware-qualified or release-ready. The Miami adapter is a separate prerequisite. The physical STORE/mount and boot-environment context helper still needs owner review and dedicated shell fixtures. Pre-driver certificate verification without clock validation, managed bank transition handling and completed-country replay need identity/upgrade-owner review. Final activation still requires normal certificate validity and a verified-clock marker.

The preinit failure marker gates the common network wrapper; returning failure from that hook does not itself prevent every later board-specific preinit callback. Miami's provisioning owner must review that ordering. Atomic individual file writes plus journal replay do not establish multi-file power-cut atomicity.

Further work is limited to these review gates and failures found by review. No additional features are intended in this draft. Test identities and domains are synthetic; generated server receipts are retained locally rather than committed.
