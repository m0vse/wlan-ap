# Miami IPQ53xx development port

This branch preserves the current X7-35X source for OEM-preserving persistent development. It is not fleet-qualified. The canonical controller identity is `cambium_x7-35x`; the model is Cambium Networks X7-35X. Firmware and calibration assets are supplied from the device, never stored here.

Use software mode (`frame_mode=1`, `ppe_ds_enable=0`) and leave the optional PPE ath-client package unselected. Hardware offload stability and true MLO are unqualified. Sysupgrade after discarding the OEM bank is unqualified.

The persistent installer takes an operator-selected `CAMBIUM_INSTALL_SERVER` URL and a command-line enrolment key. No server URL, key, deployment country or live configuration is embedded in this source. Updates preserve existing overlay and certificates; a clean enrolment test requires the separately reviewed fresh-install mode. Never reload or unbind the radio driver to apply boot-only settings.

This sanitized source revision has its own Git hash. Earlier hardware and image receipts refer to their original revisions and are not release evidence for this branch. Historical host-specific receipts and stock snapshots remain local. Build and flash only after the current source and operator procedure are verified.

## Optional PPE offload experiment

This branch retains the matching SDK PPE ath-client package and its archive/header build dependencies. The experiment registered virtual ports but did not establish stable accelerated client traffic. It failed stability acceptance and remains disabled. It must not be selected in the normal profile or treated as a validated feature.
