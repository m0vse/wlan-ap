# Stock OpenWrt to OpenWiFi settings bridge

This is a dedicated **clean migration** wrapper, not the ordinary OpenWiFi
updater. It reuses the previously qualified stock A/B writer and the shared
FORMAT2 settings stager. It never generates keys, requests certificates, or
requires OpenSSL on the outgoing stock firmware.

`prepare-bridge.py FAMILY STOCK_ROOT NEW_OUTPUT --release RELEASE` verifies
every original source member against the frozen approved outgoing ledger,
then generates the staging-only writer, transactional bridge, exact outgoing
and installed source sets, and executable/link/ELF-library closure. It needs
`readelf` on the qualification host, not on the AP. `--flavor xe3` selects the
separate Jaguar XE3-4 stock 2026.09.30.102 source contract; the default Jaguar
2026.09.29.0 contract admits only its already-qualified XV2-2/XV2-2T1 models.
Sage uses its existing E410/E410B source qualification. These are distinct
source contracts, not interchangeable roots or metadata-only approvals.

Generation does **not** add an image, IMAGE file or SHA256SUMS seal. Before
publishing an operator bundle, the release owner must verify the candidate's
revision, model admission, FIT selection, capacity, packages and native
first-boot/renewal implementation, add the verified image, and seal all bundle
files. Existing bundle seals must never be copied to a modified wrapper.

The sealed generated operator entry point is:

```
sh FAMILY-sysinstall.sh --check
sh FAMILY-sysinstall.sh --install /absolute/private/settings-directory
```

The protected directory follows the shared FORMAT2 contract. Source release
and contract hash are the two lines in the generated `source-contract`; job,
serial, slots and image binding must match the qualified transaction. Do not
put batch enrollment credentials in arguments, public artifacts or logs.

## Transaction

1. Authenticate the entire source and runtime tuple before sourcing AP code.
2. Read the complete environment successfully. Any pending installer field
   rejects a fresh install, including partial or malformed provenance.
3. Install and verify the updated bridge with its existing recoverable file
   journal. Snapshot the validated settings into a private same-boot archive.
4. In the *new sysupgrade process*, the platform hook reconstructs context
   from the protected descriptor and appends archive, descriptor, libraries
   and tools to the stock stage2 RAM copy. Revalidate again in the RAM writer.
5. Persist pending target/job/image in the existing checked writing batch,
   while keeping the source bank as the boot default. Write and read back only
   the inactive firmware.
6. Mount the verified inactive overlay, stage settings through the shared
   stager, sync and unmount. Only then call the existing one-shot trial armer.

A settings/mount/sync/unmount failure never reaches the armer. The source
remains recoverable and pending provenance remains intact. This wrapper does
not offer automatic destructive retry or a no-format rearm command. Reset or
reissue is a separate operator lifecycle, not deletion of pending state here.

Incoming OpenWiFi owns native enrollment, same-key retry, renewal and fresh
controller-configuration acceptance. The normal A/B guard cannot confirm a
pending migration until that acceptance succeeds. Ordinary certificate
retention and the shared Sage store policy remain unchanged.

## Qualification

Run `tests/check_handoff.py` and unittest discovery in `tests/`. Run
`tests/check_runtime.py STOCK_ROOT GENERATED_BUNDLE FAMILY` on cnbeacon to
exercise the actual outgoing ARM/AArch64 BusyBox privacy/archive ABI and
validate the runtime ledger. `tests/check_transaction.py BUNDLE ROOT FAMILY`
fault-tests every installed file and journal recovery in disposable roots;
run as root because deliberate read-only modes model installer conditions.

These are source/runtime and isolated fault tests, not hardware installation
or power-loss proof. No test should flash an AP, write its environment, or
publish a candidate automatically.
