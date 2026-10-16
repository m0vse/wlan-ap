# Shared-band SSID renderer regression

Schema release 43 adds patch109 after the reviewed release42 sparse-band
regulatory repair. Generic `5G` can select both split Thor serving PHYs. The
old template assigned both the same UCI wifi-iface section, so the second PHY
overwrote the first. Explicit split aliases also failed the later base-band
match. The fix deduplicates selected logical PHYs, distinguishes repeated
bands by logical section, and matches aliases through the existing operating
PHY lookup. Ordinary single-PHY identities and MLO validation remain intact.

Run against an extracted, pre-patch109 rootfs with ucode, UCI and their target
libraries. No build, device access, enrollment or controller connection occurs:

```sh
python3 tests/shared-band-ssid/run-tests.py --root /absolute/path/to/rootfs
```

Python3, `patch` and `qemu-aarch64` are required. `--qemu`, `--patch` and
`--regulatory` may override paths. The suite requires the reviewed regulatory
helper SHA256 and installs it into the disposable renderer copy. It applies
patch109 with zero fuzz. Rootfs files remain unchanged; each UCI application
uses a separate temporary config and saved-state directory. Only generated
wireless commands are applied; unrelated network/service commands are not
part of this test. Fixture metadata describes model hardware, uses a synthetic
local MAC and synthetic SSID credentials, and contains no deployment identity.

Controls cover:

- Old renderer plus real UCI reproduces one surviving split-radio SSID.
- Fixed generic 5G, multiple SSIDs, explicit aliases, overlapping aliases,
  and lower-only/upper-only selection retain distinct expected interfaces.
- OWE transition peers are reciprocal and stay on their own PHY.
- Single 5G and independent tri-band/MLO-disabled configurations retain
  identical nonblank legacy renderer commands and final UCI identities.
- Thor enabled MLO remains rejected with the existing qualification error.
- A synthetic qualified Miami fixture retains identical legacy commands,
  two driver-indexed links and its existing `ml0_0` MLD group.

These are offline configuration controls, not new RF, DFS, reboot or hardware
acceptance evidence. Shared regulatory controls are in `tests/regulatory`.
