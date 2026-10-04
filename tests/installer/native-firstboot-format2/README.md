# Native first-boot FORMAT2 regressions

These tests create synthetic identities and exercise localhost HTTPS only. Never supply a real enrollment key, AP identity or issuer. No AP, service, firmware build or deployment is used.

Stage the committed runtime files into a fresh temporary directory:

```sh
python3 stage-source.py /path/to/wlan-ap /tmp/native-firstboot-fixture
export NATIVE_FIRSTBOOT_SOURCE_DIR=/tmp/native-firstboot-fixture
python3 test-services.py
python3 test-mount.py
python3 test-worker.py
```

For the actual native EST/first-boot helper test, use an existing ARM target root containing ucode/modules and curl, host OpenSSL and qemu-arm. Set `NATIVE_TEST_ROOT` to that target root and `NATIVE_TEST_UCODE` to its existing executable ucode emulator wrapper. Run `test-native-firstboot.py` as Root with these three environment values preserved. Its private temporary files contain only freshly generated synthetic test identities. It verifies failed enrollment/reboot retries, cached CSR integrity, independent HTTPS trust, leaf persistence, native applied-config confirmation and resumable confirmed cleanup.

For the native status callback test, set `NATIVE_CLIENT_SOURCE_DIR` to an isolated checkout of pinned native client 176cab2f with the committed `001-installer-trial-reapply.patch` applied. Run `test-status-width.py` with a host C compiler.

JSON receipts are written into the staging directory. Mount, hardware, UCI, ENV, native status/process and service boundaries are isolated where needed. The HTTPS test executes the actual packaged mount helper with an isolated active-volume mount table, actual native EST dispatch/curl/OpenSSL and the committed identity helper. These tests establish source behavior; they do not establish hardware power-loss, package closure, production onboarding or release readiness.
