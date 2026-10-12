# Confirming a retained Miami OEM boot

This step is for X7-35X entered through the reviewed `enter-oem-once.sh` route
from the retained b6 OpenWiFi image. The initial one-shot boot preserves the
OpenWiFi bank and its exact boot function. OEM startup may save its own slot in
`image`; confirmation still requires the preserved OpenWiFi default and the
matching source/target entry fields.

After the OEM console shows a healthy boot, run from the verified kit directory:

```sh
./confirm-oem-entry.sh --yes
```

The command checks the existing 7.2-r1 build tuple, physical layout, running
read-only OEM root and kernel, global IPv4, default route and bounded gateway
reachability. No local HTTP service is required. If gateway ping is unavailable,
use the existing installer endpoint:

```sh
./confirm-oem-entry.sh --yes --network-url https://INSTALLER/EXISTING_PUBLIC_OBJECT
```

The endpoint must already exist and be reachable with normal TLS verification.
Do not enable a service, change credentials or bypass TLS verification for this
step. `--yes` confirms that the operator has inspected the healthy OEM console.

For OEM's gluebi root view, the helper uses the actual UBI parent link when
available. Without that link, it checks the volume/view geometry and SquashFS
header, then streams the complete meaningful extent for byte counts and hashes
against the identified running OEM child. It does not copy or back up rootfs.
A known wrong parent, mismatched image, malformed header or short read refuses
confirmation before environment changes.

Success prints the confirmed OEM slot. It saves that slot with `bootcmd=bootipq`,
clears the changing marker and marks this entry confirmed. The original OpenWiFi
bank, certificates, calibration and boot function stay intact. No firmware write
or reboot occurs. The existing seed `update` command retains its strict requirement
that the running OEM bank and saved selector match.

If proof or reachability fails, inspect the output and keep the preserved
OpenWiFi route. If a confirmation write/readback fails, the helper restores and
checks that route. A reported uncertain rollback requires inspection before
rebooting. These commands do not perform full OEM reconstruction or factory reset.

Kit assembly includes `confirm-oem-entry.sh`, the qualified X7-35X source and
physical profiles, and the existing common/protection/network readers under
`shared/oem-*.sh`. All are covered by the kit's existing authenticated ledger.
Host fixture tests exercise parsing, media preservation and ENV failure paths;
actual operator acceptance remains a separate result.
