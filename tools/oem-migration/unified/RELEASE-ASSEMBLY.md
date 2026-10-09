# Assemble an operator release

Run release assembly on a host with the reviewed OpenWiFi source checkout and
the existing firmware assets. It packages files; it does not build firmware,
contact an AP, change an issuer or deploy a service.

## Exact-model status

Recognition is broader than implementation. This table describes source and
available baseline evidence, not an installable release. The release maps are
the authority for an operator's exact model and source version.

| Family | Recognized models | Current release integration requirement |
|---|---|---|
| Gambit | E400 | No migration/restoration adapter; keep disabled |
| Sage | E410, E410B | Existing writers and captured OEM 4.2.3.3-r10 evidence; exact factory variant, runtime, geometry, native source boot contract and payload profiles required |
| Sage | E600, E430W, E700, E430H, E510 | No inference from E410; keep disabled without their own implemented path |
| Jaguar | XV2-2, XV2-2T0, XV2-2T1, XE3-4, XE3-4TN | Adapter checks OEM 7.2-r1; each SKU needs its own actual profile and payloads |
| Thor | XV3-8 | Actual boot generator tests exist; they do not establish a complete OEM installer or restore path |
| Cheetah | XV2-21X | Selector/update/boot component fixtures exist; complete pinned migration provider remains required |
| Cheetah | XV2-22H, XV2-23T | Keep disabled; sibling geometry and payloads are not substitutes |
| Miami | X7-35X | OEM 7.2-r1 exact-build profile and generated storage backend; package the current local-only/numeric-cache fixes with existing payloads |

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

## Package and verify

For the common metadata-first release, include a pinned `payload-map.tsv` and
use `--metadata-first`. Each six-column tab-separated row contains exact model,
operation (`install`, `restore` or `confirm`), local relative data path, remote
relative object name, byte count and SHA256. All declared files must match the
provider ledger before packaging. Code cannot be a downloaded payload. The
packager retains the authenticated map and framework but omits all declared
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
