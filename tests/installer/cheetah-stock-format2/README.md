# Cheetah FORMAT2 stock migration qualification

Qualified source route: converted XV2-21X (`cambiumnetworks,xv2-21x`, SKU `00000023`), stock `2026.09.29.0`, source `aff0cccda079fea3fbbe6b1b305fd5d2f3a7abf0`. Other XV2 models and direct OEM migration are refused by this source route.

`tools/stock-migration/cheetah/prepare-cheetah-bridge.py` verifies the frozen source and executable ledgers before generating an unsealed installer source bundle. It reuses the central FORMAT2 settings library and stock handoff. Outgoing tools never generate a key/CSR or contact EST. Firmware readback precedes settings staging; trial activation follows successful staging, sync and unmount. Existing pending provenance refuses fresh formatting.

Set `WLAN_AP_SOURCE_DIR`, `CHEETAH_BUILD_ROOT` and `CHEETAH_GENERATED_BRIDGE` to the selected source repository, existing retained build directory and generated unsealed bridge. Run these Python tests on the build server with QEMU AArch64 and the approved outgoing capture under `outgoing-source/rootfs`:

- `test-central-metadata.py`: seven checks using actual stock ARM64 shell/ls/awk.
- `test-cheetah-handoff.py`: twelve source/provenance/RAM refusal cases.
- `test-cheetah-writer.py`: twelve actual generated writer callback fault paths.
- `test-cheetah-bank-stage.py`: ten bank mapping, settings publication and mount/sync/unmount fault paths.
- `test-cheetah-ram.py`: actual stock ARM64 RAM-copy function with copy recording and pivot blocked.

The common stager regression suite additionally covers eight permission, manifest, staging and identity-preserving retry cases. Boundary tests use synthetic authorization and temporary files; they do not mount an AP volume, write an environment, flash, reboot or enroll hardware. Generated bundles receive neither an image nor a checksum seal. Candidate image admission and physical first-boot/rollback acceptance remain separate.
