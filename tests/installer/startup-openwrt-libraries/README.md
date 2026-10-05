# Startup guard with the real OpenWrt library environment

The installer boot guard sources OpenWrt shell libraries. Those libraries intentionally permit optional unset variables, including `IPKG_INSTROOT`; enabling shell nounset before sourcing them caused ordinary boot checks to abort and prevented both management services from starting. The guard retains `set -e`, operation validation and the existing pending-trial checks.

Run `test-startup-libraries.py /path/to/extracted/root /path/to/candidate/ucentral-installer-boot` with `OW_TEST_BUSYBOX` set to an executable BusyBox wrapper accepting `ash` and arguments. Use the packaged target BusyBox under its existing emulator/sysroot. Set `OW_TEST_BOARD` to the root's supported model, for example `cambiumnetworks,e410`, `cambiumnetworks,xv2-2`, `cambiumnetworks,xv2-21x` or `cambiumnetworks,xv3-8`.

The input root must contain the packaged installer boot helper and the real packaged `functions.sh`, `system.sh`, `uci.sh`, `jshn.sh`, family A/B modules and cloud/uCentral init scripts. With an older input root, the test reproduces the old failure with `IPKG_INSTROOT` absent, With a fixed input root, it instead verifies the corrected packaged baseline. It then runs normal, pending, fallback, malformed and unready paths plus both actual init functions using the candidate. Filesystem paths are redirected to synthetic fixtures. Hardware identity, environment reads, installer subprocesses, UCI/jsonfilter and procd are isolated; no AP, real boot environment, identity, trust, network or firmware build is touched.

Run the same fixture against each family's extracted or packaged root before its next image is released. Source-level success does not establish hardware reboot, network or image-release readiness.
