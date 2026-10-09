# Assemble an operator release

Run release assembly on a host with the reviewed OpenWiFi source checkout and
the existing firmware assets. It packages files; it does not build firmware,
contact an AP, change an issuer or deploy a service.

## Exact-model status

Recognition is broader than implementation. This table describes source and
available baseline evidence, not an installable release. The release maps are
the authority for an operator's exact model and source version.

The following snapshot describes the reviewed source and retained provider
inputs as of 2026-10-09. An image version here identifies existing input bytes;
it is not a declaration that the image contains every newer migration or
readiness fix. Private provider receipts stay outside source Git. The source
status is based on reviewed unified entry points through the published Jaguar
return writer `e5ffc487`; a pending owner candidate does not enable a row.

| Exact models | Reviewed OEM source | Existing incoming input | Forward integration | Full OEM restore / confirmation |
|---|---|---|---|---|
| E410, E410B | 4.2.3.3-r10, exact factory variant | Sage 2026.10.07.1 | Private actual-data writer and enabled launcher validation complete | E410 bounded private return/confirmation data; clean reset and old-store retirement are separate. E410B reverse remains disabled |
| XV2-2, XV2-2T1, XE3-4 | 7.2-r1, exact product/build | Jaguar 2026.10.05.8 | Private actual-data writer and enabled launcher checks pass for both source slots; XE3-4 source-version capture provenance still needs corroboration | Private actual-data OEM return writer and generic checks pass for both source slots with explicitly scoped host identity/media actors; healthy OEM confirmation, defaults/reset and deployment remain separate |
| XV3-8 | 7.2-r1, exact product/build | Thor 2026.10.05.8 | Actual incoming payloads retained; published component helpers need the owner's final composed writer and exact provider schema | No enabled reverse or confirmation claim from component tests |
| XV2-21X | 7.2-r1, exact product/build | Cheetah 2026.10.05.7 | Actual incoming payloads retained; final composed family source/provider integration remains separate from legacy components | Keep reverse disabled until the final owner adapter and provider are validated |
| X7-35X | 7.2-r1, exact product/build | Existing reviewed Miami payload/PAIR objects | Private current backend assembly; required Linux replay remains pending | No inference of restore/confirmation or installed readiness from generated source |
| E400; E600, E430W, E700, E430H, E510; XV2-2T0, XE3-4TN; XV2-22H, XV2-23T | No enabled exact-source row | None admitted by sibling evidence | Recognized unsupported; reject before changes | Unsupported |

Use the operation-specific release maps, not this snapshot, to decide whether
an operator command is enabled. Keep unavailable rows disabled even when an
image includes that model's FIT configuration. Source, target layout, forward,
reverse, confirmation and installed normal-upgrade readiness are independent
claims. OpenWrt conversion retains its reviewed outgoing model-specific route;
the OEM entry point refuses an OpenWrt source.

The X7-35X b6 firmware's missing readiness hook must remain unsupported for
normal-upgrade readiness. Source tests for a new hook do not change installed
firmware. OEM restoration confirmation and clean factory reset also need
implemented exact-model handlers; framework dispatch alone is insufficient.
Sage forward migration does not require a new whole-bootloader hash capture.
The existing E410-A OEM restoration/defaults path retains its independent
bootloader proof; it does not qualify E410B restoration.

## Provider directory

Prepare a new immutable provider directory from existing reviewed assets. Its
`SHA256SUMS` uses one `sha256  relative/path` entry per file with two spaces
between the digest and path. Obtain the ledger digest independently of the
directory being verified. Do not include an onboarding key, per-unit backup,
private certificate/key, customer configuration or full per-unit firmware dump.

`models.tsv` is required. `restore-models.tsv`, `restore-confirm-models.tsv` and
`upgrade-models.tsv` describe separate operations. Each row has five tab-separated
fields: canonical SKU, family, exact model, adapter and exact source version.
Use `-` as the adapter for a recognized unsupported model. Do not enable a
row simply because its family has a shell file.

Supply the data required by the enabled adapter. Sage currently expects pinned
readers under `readers/sage`, exact-model profiles under `profiles/MODEL`, and
image/kernel/root payloads under `payloads/MODEL`. Restoration uses separately
pinned OEM payloads and shared-asset descriptors. Miami expects the current
generated backend named `miami-installer.sh`, exact X7-35X profiles, and the
payload/PAIR objects selected by that backend. Keep all descriptor names,
sizes and hashes tied to the same existing firmware release.

Provider files cannot replace framework `lib/` or `adapters/` code. The packager
copies those from the OpenWiFi checkout. Freeze and record that source commit
alongside the provider ledger and output launcher hashes. Validate space using
the actual files simultaneously staged for the selected model; do not assume
all models' images fit in an AP's RAM.

## Jaguar source-slot profiles

The authenticated physical profile is `profiles/MODEL/mtd-slot0.tsv` or
`mtd-slot1.tsv`. The suffix names the inspected **running source slot**, not the
target. Supply both profiles in one provider. With source slot 0, `rootfs` is
`active-oem` and `rootfs_1` is `target`; with source slot 1 those roles reverse.
All other model-specific physical rows remain unchanged. The adapter selects
and authenticates the matching file, then checks live parent, offset, geometry
and role bindings. There is no fallback to a fixed `mtd.tsv`.

Reverse profiles, when that operation is implemented and enabled, use the same
source-slot convention below `profiles/MODEL/restore/`. A running DTB or retained
capture from the exact model establishes that model's physical map; a sibling
FIT tree does not. Preserve the capture hash and source-version provenance in
the private receipt. XV2-2's 52 MiB banks and the T1/XE3-4 96 MiB banks must not
be interchanged.

## Minimal backup and shared OEM assets

Use one reviewed OEM recovery asset set per exact model/release with each
unit's own critical data. Routine unique backups contain ART/calibration,
manufacturing identity, boot environment and only indispensable boot-selection
records. Jaguar's bounded plan is ART 512 KiB, MFG 64 KiB and ENV 64 KiB; Thor's
named BOOTCONFIG pair is capped at 128 KiB per record. An explicit unique-data
exception must appear in the model plan. No routine per-unit root filesystem,
whole firmware bank, whole flash dump, customer configuration or issued AP
private key belongs in this provider or ordinary backup relay.

OEM return must restore the reviewed OEM boot-environment defaults as well as
the firmware. Preserve unrelated and device-specific environment fields unless
the exact reviewed restoration plan says otherwise. Confirmation precedes the
separate factory reset; do not clear the prior identity or configuration during
an unconfirmed one-shot attempt. Factory reset does not itself prove that a
shared native certificate store or stale vendor configuration backup was retired.

## Package and verify

For the common metadata-first release, include a pinned `payload-map.tsv` and
use `--metadata-first`. Each six-column tab-separated row contains exact model,
operation (`install`, `restore` or `confirm`), local relative data path, remote
relative object name, byte count and SHA256. All declared files must match the
provider ledger before packaging. Code cannot be a downloaded payload. Known
radio leaves such as `bdwlan.*`,
`regdb.bin*`, and reviewed split `q6_fw`/`iu_fw` members may be selected only in
the detected model's firmware asset paths. The existing Thor role
`payloads/shared-radio/thor-bdwlan.*` is restricted to XV3-8. Executable helpers,
PEM/key files and another model's assets remain forbidden. The generic map does
not replace family-specific `radio-assets.tsv`, `vault-assets.tsv`, `stage.tsv`
or payload descriptors: those must still bind the exact logical firmware paths,
byte counts and hashes consumed by the family adapter.

The packager retains the authenticated map and framework but omits all declared
payload bytes from the initial release; undeclared firmware files refuse.
The generic launcher detects the model and stages only its operation rows,
using bounded fetches and an aggregate byte check before key input, backup or
writes. Cached objects remain usable when the provider disappears. Selected
object hashes and the original map are checked again before the writer.

Run `prepare-release.py --help` for the host command. It takes the provider
directory, its independent ledger digest, a new output directory, and explicit
controller, download and critical-backup URLs. The output directory must not
already exist. Site values remain in this private output, outside source Git.

The packager verifies provider members before copying, checks copied hashes,
freezes framework helpers, checks shell syntax, and creates canonical launchers
with the output ledger pin embedded. `LAUNCHER-HASHES.txt` records the launchers
for independent operator verification. These checks authenticate the package;
they do not prove every enabled model's runtime prerequisites.

Run the complete source harness from the frozen checkout, then inspect every
enabled mapping against its actual adapter, profile, descriptors and payloads.
Keep source-fixture results separate from AP acceptance. On the chosen pilot,
start with the published read-only `check` command and review its exact source
and target summary. A missing profile, unsupported source or unsafe return path
must refuse before key input or backup. The operator explicitly authorizes any
subsequent device migration, reboot or reset.

Use the [operator quick starts](README.md) for migration and restoration.
Factory reset is a separate explicit OEM-side step after healthy confirmation;
confirmation itself must not run a rebooting vendor reset script.

## Retire an old native identity for a clean test

Keep the previous OpenWiFi identity through the unconfirmed OEM trial. After
healthy OEM confirmation and the separate factory reset, the shared Sage
`certificates` volume still exists. A fresh forward install must refuse it.
The operator must first complete the reviewed named-store retirement procedure;
do not erase the parent UBI device or use
another AP's identity. The exact store cleanup is a separate action, requiring
the matching live parent/name/volume, mount/alias checks and explicit consent.
The current generic confirmation command does not authorize or perform it.

Routine critical backups remain ART/MFG/ENV and indispensable boot-selection
records. Replaceable issued certificates and private keys are not a routine
backup prerequisite and must never go through the ordinary HTTP backup relay.
Keep their existing store intact until healthy OEM confirmation; explicit
retirement may then clear the named unused OpenWiFi store. An optional AP-key
recovery copy needs a separately approved encrypted/private destination. This
does not replace the reset tool's existing private server-state backup.

Then use the already-delivered `/app/reset_native_enrollment.py` inside the
existing PKI service's Root operator shell. Obtain this AP's exact serial and
current leaf fingerprint from its authoritative enrollment record. The tool
defaults to a read-only dry run:

```sh
python3 /app/reset_native_enrollment.py --state /state/issuer.sqlite \
  --serial "$SERIAL" --expected-leaf "$LEAF"
```

After the AP is on OEM/offline, the old private identity has been cleared and
will not be restored, and a new backup destination under a Root-private parent
has been selected, the operator explicitly applies the fresh dry-run binding:

```sh
python3 /app/reset_native_enrollment.py --state /state/issuer.sqlite \
  --serial "$SERIAL" --expected-leaf "$LEAF" --apply \
  --expected-binding "$BINDING" --backup-dir "$NEW_PRIVATE_BACKUP_DIR" \
  --offline-identity-cleared
```

These variables are the exact reviewed values, not a reusable example AP or an
onboarding key. The existing tool creates a private database recovery copy,
retains signing/revocation/audit history and resets only the named AP's old
active membership/grant/cache state. It does not clear AP storage or enforce
instant gateway-session revocation. The normal authenticated operator workflow
then prepares a fresh approved batch, and the common installer privately
prompts for its key. No issuer, AP identity or database reset is part of release
assembly or the source fixtures.
