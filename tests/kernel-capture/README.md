# Kernel capture source tests

`test-helper.py ROOT HELPER_SOURCE` executes the real target ucode interpreter
with synthetic UCI, sysfs and configfs boundaries. It checks opt-in validation,
missing/down/wireless devices, carrier, numeric endpoint and port checks,
unicast next-hop MAC, dynamic backend availability, disable/reload and failure
rollback. No kernel module or configfs target is loaded by these fixtures.

`test-collector.py tools/kernel-capture/collector.py` checks durable raw datagram
storage, allowlisting, mode-700/600 isolation, interrupted append recovery,
retention bounds, explicit truncation and sync failure. It opens no socket.

Kernel package patch application, actual helper runtime and Ethernet/netpoll
source capability checks must be recorded separately for each family. Synthetic
checks do not demonstrate a real panic or reset-retention result. Keep generated
fixtures, logs and expanded source outside source commits.
