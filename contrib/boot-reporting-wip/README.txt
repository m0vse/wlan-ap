UNQUALIFIED SHARED BOOT/CRASH REPORTING SOURCE DRAFT

This directory preserves work in progress; it is NOT an enabled package,
qualified release, firmware artifact or authorization to operate an AP.
Base: wlan-ap b10b5e624fb34c96c0e12bcbf49b2b3bcf4de4d6.
Author/maintainer: Phil Taylor <phil@m0vse.uk>.

Integration map (not applied):
  package/ -> feeds/ucentral/ucentral-boot-report/
  client-Makefile -> feeds/ucentral/ucentral-client/Makefile
  client-changes.patch -> new ucentral-client package patch, against
    upstream cb48fe27b3516521f8de723596e8656dbf1f7c7b.
  ucentral.init -> ucentral-client/files/etc/init.d/ucentral
  schema-Makefile -> feeds/ucentral/ucentral-schema/Makefile
  schema-changes.patch -> new schema package patch AFTER existing patches
  reboot_cause.uc -> schema/files/usr/share/ucentral/reboot_cause.uc
  state-Makefile -> feeds/ucentral/ucentral-state/Makefile
  ucentral-pstore -> state/files/usr/libexec/ucentral-pstore

The durable reporter uses bounded history and request markers, not guessed
hardware causes. Unclassified boots are exactly unexpected-shutdown.
Crashes use crashlog/loglines, reboot history uses rebootLog/type/date/info.
The proposed transport confirms a full WebSocket write only; there is no
gateway storage acknowledgement or exactly-once guarantee.
No blanket BusyBox/binary reboot replacement. Only interactive profile
reboot calls are attributed; explicit /sbin/reboot can bypass that hook.

Synthetic checks must run only in a root-owned PRIVATE temporary fixture
directory with a compatible ucode runtime:
  ucode tests.uc /path/to/private-fixture
tests.uc uses TEST-labelled synthetic events and injected I/O. Never pass
real /etc/ucentral/boot-reporting or submit fixtures to a real controller.
55 module fixture checks pass on host and extracted ARM/AArch64 runtimes.
Actual isolated entrypoint/hooks, absent-pmsg include helper, C transport
controls and target syntax-only checks also pass. This is NOT a firmware
build or AP acceptance receipt. No persistent kernel backend is qualified.

Outstanding review/qualification:
  firmware package compilation and real gateway/AP transport acceptance;
  factory/reset intentionally wipes overlay-backed history unless preserved;
  transport success is not server storage acknowledgement; ambiguous writes
    may repeat after a persistence failure, and absent ACK prevents certainty;
  family-specific approved persistent crash backend and reset-cause hooks.
Do not guess ramoops RAM addresses or reuse certificate/OEM crash storage.
No hardware backend is qualified by this snapshot.

No credentials, private keys/certificates, real AP history, generated
build output or firmware binaries are included.
