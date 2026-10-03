# Shared controller LED policy source tests

Run `test-state-policy.py ROOT STATE_SOURCE` and `test-helper-policy.py ROOT
HELPER_SOURCE` on a host with qemu-aarch64 and an extracted qualified Thor or
Jaguar root. Tests use the actual ARM ucode/ash runtimes and disposable fixtures,
not AP sysfs, controllers, wireless devices or hardware reset interfaces.

The state fixture executes the full production source with module/service and
filesystem boundaries mocked. The helper fixture executes the real shell helper
against private files. Age-zero connections, invalid status values, repeated
status updates during identify/factory-reset, timeout restoration, phase priority,
reversible global off, mapped channel absence, and excluded models are covered.
Generated test outputs must stay outside source commits.

Run `test-diag-lifecycle.py ROOT HELPER_SOURCE PATCH_0143` to apply the
diagnostic hook to a disposable copy of the extracted `/etc/diag.sh` and execute
its real `set_state` entrypoint under target ash with fixture LED functions.
The phase tests redirect `/tmp/ucentral-led-phase` into each private fixture.
They cover global-off toggles before completion, explicit connect/done release,
completion while globally disabled, timer cadence restoration and cancellation
of identify without creating a boot phase.
