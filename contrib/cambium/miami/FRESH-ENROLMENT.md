# Existing Miami trial: fresh OEM enrollment retest

Source-only procedure. Server native identity/batch reset is owned by the CA/operator procedure; this installer performs no server deletion or revocation. Use the current independently verified generated installer and matching current/prior kernel-root pair pins. Never use an older unseeded storage-only script.

From the running retained OEM bank, the explicit operation is:

```sh
CAMBIUM_INSTALL_SERVER="$OPERATOR_BUNDLE_URL" sh "$VERIFIED_INSTALLER" install --yes --replace-inactive-bank --backed-up --fresh-enrolment
CAMBIUM_INSTALL_SERVER="$OPERATOR_BUNDLE_URL" CAMBIUM_ENROLMENT_SERVER="$OPERATOR_CONTROLLER_HOST" sh "$VERIFIED_INSTALLER" arm --yes --enrolment-key "$FRESH_ENROLMENT_KEY"
```

These are review templates, not ready-to-run commands: operator URL, independently verified installer/payload hashes, fresh key and exact target bank must first be supplied by the release/operator owners. Do not embed these values in Git. Check the OEM serial/selector/cmdline, target MTD/offset/geometry, complete own-device recovery copies and approved server reset before use. The installer must retain its existing refusal for a fully converted A/B device; do not clear `miami_ab_version` to bypass it.

Run the verified installer's `check --fresh-enrolment` first. This explicit read-only inspection permits a complete same-target old installer triplet; ordinary `check` still refuses it. Inspection never clears metadata, resets volumes or arms boot. Remove only the proven idle target rootfs ubiblock mapping reported by that check (the exact resolved `/dev/ubiN_1`); do not remove a guessed mapping or unmount active filesystems. Installation refuses mounted/open target devices, unhealthy UBI volumes, unknown layouts/payload pairs, malformed/different-target old enrollment metadata, active storage transactions and insufficient space.

Fresh mode requires an existing exact 64-LEB target certificate store and a matching independently pinned current/prior kernel-root pair. It journals and syncs before mutations, removes only the target certificates and the existing explicitly approved kernel/root/overlay volumes, creates a new empty overlay and certificate store, and preserves the running OEM bank, ART and own-unit radio vault. Old overlay seed/key/CSR/certificate state is lost deliberately. Old installer target/job/image metadata is removed only after verified writes/preservation, while the storage journal remains on failures. A failed transaction refuses arm/retry; do not manually clear the journal.

The separate `arm --enrolment-key` uses the common protected FORMAT2 producer and stages/validates settings before guarded boot selection. Verify the current served script actually includes that producer and the image contains shared Miami native worker/model/store support. No automatic reboot occurs; the operator controls reboot/serial capture after successful checks. Observe native enrollment, durable identity, authenticated applied configuration and subsequent renewal independently; source fixtures do not prove hardware success.
