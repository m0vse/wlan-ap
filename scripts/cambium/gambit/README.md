# Gambit verification source

These are deliberate source test/reproducibility scripts from the E400 family work, not generated results or a firmware archive. They use isolated files, qualified extracted roots and target tools; read each script and provide its documented host paths before use. No AP operation is authorised here.

The original frozen .12 parent is f08f34561a8193029de2d63ae483cf8b6758e9b5 and generated OpenWrt source parent is 7b849a21e1d73c6b38122357dc87e5fd6d285bcd. Firmware digest is 6a89dd41cad4cd96852f33f5a4513551f03a04f989f2ca11c253d477959c0213. Original source history remains local on cnbeacon; corrected-main integration is a separate source change and is not a rebuilt/qualified original image.

Generated configs, source-tree snapshots, applied working diffs, test outputs and firmware binaries are intentionally absent. The maintained family integration profile/0140 patch and shared canonical patches supply active source configuration. Hardware recovery/acceptance remains pending.

Boot-counter safety: test-bootcount.py requires GAMBIT_TEST_MODULE pointing to the module extracted from patch 0140; CAMBIUM_TEST_SHELL may select a target-shell wrapper. Its fourteen mocked-environment/flash and rendered-command fault tests cover count 8/9, reset failure, preflight rejection, both bank commands and fallback save ordering. The matching Gambit nboot counter rule differs from Jaguar bootipq. Frozen .12/operator-r3 and obsolete operator-r4 drafts lack the pre-write/pre-nboot safeguard; these source tests do not qualify or modify those artifacts. No deployment is implied.

Rendered boot commands enter NAND boot/reset only after environment writes and counter/routing saves succeed. Failure returns without automatic reset, including when saved counter 9 remains. Matching Gambit U-Boot binary static inspection confirms bootcmd dispatch through hush, double-ampersand conditional token handling, short-circuit execution, and compiled if/then/fi support. Shell regressions are offline; no AP execution or hardware acceptance is implied.

Critical counter reads capture both stdout and exit status before writing and after readback. A failed getter printing either expected zero or stale nine refuses the write/erase path; the shared environment API is unchanged.
