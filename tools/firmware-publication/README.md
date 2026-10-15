# Per-family publication gate

Every Sage, Jaguar, Cheetah, Thor and Miami publication must finish through
`family_gate.py`. Run it for **each family**, after its own immutable images
and catalogue transaction. Do not carry a previous family's successful cache
check forward. Do not release the next family or report publication complete
while this gate is failing. Gambit is not included.

This is controller publication, not authorization to upgrade, reconnect,
reconfigure or reboot an AP. Only the existing FMS container is restarted.
Gateway, security, provisioning, radio and RRM services are never restarted.
Existing FMS runtime settings and image stay unchanged. A currently running
family AP may be checked read-only; its normal gateway ping repopulates the
device cache after refresh. Never force an AP reconnect to populate that cache.

## Why the gate is mandatory

Direct catalogue SQL does not update FMS's in-memory latest cache. A manifest
refresh also skips releases already inserted into the database. A correct
download, `latest=true` database row or visible firmware list therefore does
not prove the firmware-age badge is correct. Refreshing once for a batch is
insufficient when further families are inserted afterward.

Use the supported ingestion path where possible. With the current deployed
FMS, there is no tested in-process cache reload, so this gate performs one
targeted FMS-only restart per family and checks the effective authenticated
APIs afterward. An upload-only script is not the publication-completion step.

## Inputs

Prepare a JSON receipt from that family's reviewed immutable release evidence:

```json
{
  "family": "thor",
  "firmwares": [{
    "deviceType": "cambium_xv3-8",
    "id": "EXACT-CATALOGUE-ID",
    "revision": "EXACT FULL EMBEDDED REVISION",
    "image": "EXACT-IMMUTABLE-FILENAME.bin",
    "imageDate": 1234567890,
    "uri": "https://firmware.example/EXACT-IMMUTABLE-FILENAME.bin",
    "firmwareHash": "REPLACE_WITH_64_LOWERCASE_HEX_CHARACTERS",
    "size": 12345
  }],
  "devices": []
}
```

The sample is deliberately not executable release evidence: replace every
placeholder with reviewed values. Include **all qualified model aliases** in
`firmwares`. Do not add speculative models. Where a prior release exists,
include `previousRevision` and `previousImageDate` in each firmware item to
verify the prior release's exact, bounded, non-negative age too.

Only add `devices` entries for APs known to be running this exact release:
`{"serialNumber":"MAC_WITHOUT_COLONS","deviceType":"EXACT-MODEL"}`.
An older AP is not expected to be latest and must never be upgraded by the gate.

## Run on the controller host

Supply an **existing approved operator session token on stdin**, through the
established operator-session mechanism. Do not paste it into shell arguments,
save it in Git, print it in logs, manufacture a token or change permissions to
get past authentication. Endpoint, CA path and retained trusted Python runtime
image are explicit deployment inputs; no private deployment defaults are stored
in the repository. The probe image is never pulled automatically.

```sh
python3 family_gate.py \
  --manifest FAMILY-QUALIFIED-PUBLICATION.json \
  --receipt NEW-FAMILY-FMS-COMPLETION.json \
  --fms-url "$FMS_URL" \
  --ca "$FMS_CA_FILE" \
  --probe-image "$RETAINED_PYTHON_IMAGE" \
  --publisher sh REVIEWED-FAMILY-UPLOAD-AND-CATALOGUE.sh
```

The operator-session mechanism must feed stdin to this command. The
`--publisher` option is last: remaining arguments are the already-reviewed,
family-scoped immutable uploader/catalogue command. That command retains its
existing catalogue backup, guarded transaction, old objects and rollback.
Alternatively omit `--publisher` immediately after a separately completed
guarded publication; the cache refresh and live checks are still mandatory.

Expected success: `publication_complete: true`, one FMS refresh receipt and an
exact verified entry for every model. Nonzero exit or no success receipt means
**incomplete publication**, not permission to skip the failed check.

`--verify-only` audits an already-refreshed publication without another restart.
It always emits `publication_complete: false` and cannot run an uploader; an
audit is not a substitute for the per-family refresh receipt.

## Checks and failure behaviour

- Existing operator authentication must work before an uploader or restart.
- Public HTTPS image bytes must match the exact qualified SHA256 and size.
- Only the container labelled as the `owfms` Compose service can be restarted.
  Its image and identity must remain unchanged; every other Compose container's
  identity, image and start time must remain unchanged.
- The live latest API must match model, ID, full revision, immutable URI, image,
  date, hash and size, with `latest: true`.
- Current-revision age must be `latest: true`, `age: 0` and the exact latest ID.
  Unknown revisions must not appear current. Listed serials must agree too.
- Wait only for normal pings when the serial cache is empty. Retries are bounded;
  no AP-side operation is attempted. An unsigned underflow age is a hard failure.

If authentication expires, refresh fails, any model is wrong, a download differs
or a device cache remains missing, stop and retain the immutable files and backup.
Do not restore an entire catalogue over unrelated later changes. Correct only
the proven failing publication/cache step, then rerun and keep a new receipt.
Neither a password change nor an AP reboot is a cache repair.

Tests (synthetic only, no Docker/network/AP access):

```sh
cd tools/firmware-publication
python3 -B -m unittest -v test_family_gate.py
```
