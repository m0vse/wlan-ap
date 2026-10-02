XE3-4 converted clean stock OpenWrt -> Jaguar OpenWiFi .3
Installer-only extension, revision 1. No firmware rebuild.

Entry point: sh jaguar-sysinstall.sh --check
Explicit operator installation after PASS: sh jaguar-sysinstall.sh --install
The wrapper's default is --check. No force, configuration fence override,
environment edits, or unsupported-model bypass is permitted.

Stock minimum: Jaguar 2026.09.30.102, qualcommax/ipq60xx,
aarch64_cortex-a53. Newer compatible release metadata is accepted; reviewed
updater scripts and executable/library/link runtime must match a compatible
implementation. A new number alone does not permit unknown updater code.
Only XE3-4 / SKU32, protected 96MiB converted A/B banks, valid device-data
vault and stable confirmed boot state are admitted by existing A/B preflight.
XV2 models, XE3-4TN, OEM/unconverted layouts and managed identity markers
are outside this clean route. Do not use it on existing OpenWiFi firmware.

Installation discards stock configuration via sysupgrade -n, no -f archive.
It transactionally updates five outgoing updater files, validates the installed
tuple, then runs the normal metadata/platform preflight and A/B upgrade.
Calibration and the device-data vault are protected. The clean certificate
export is strictly empty and boot/bank-bound; outgoing credentials, endpoint,
redirector and trust configuration are not imported. The new AP requires
authorised unique onboarding. No test credentials or shared key are bundled.

Default --check may create private temporary extraction/snapshot fixtures,
but does not install files, flash, arm a trial or reboot. Explicit recovery
repairs only this bundle's authenticated own bridge transaction; it cannot
override an unrelated or unknown interrupted updater.

Hardware support is reused from the existing Jaguar/XE3-4 implementation.
Offline tests establish migration contracts, not physical boot, RAM pivot,
power-loss or rollback acceptance. Live --check must PASS before --install;
then verify new firmware, confirmed slot, networking and secure onboarding.
