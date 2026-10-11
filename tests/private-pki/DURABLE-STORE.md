# Durable store primitive — activation integration pending

The opt-in private PKI package supplies an owner-only file sealing and atomic
pointer helper. `seal DIRECTORY FILE...` syncs the named private files and their
directory. `commit DIRECTORY STAGED POINTER` syncs the staged file and directory,
renames within that same directory and syncs the directory again. It refuses
symlink directories/files, hard-linked files, unsafe owners/modes, path traversal,
empty or oversized files. Parents of the configured store must be root-owned and
the persistent certificate filesystem must already be mounted.

The helper does not validate certificates, authorize migration or prove gateway
acceptance. Its caller must validate the complete candidate and consume a fresh
server-verified management acceptance before committing `current.json`. The
existing materializer restores only the committed pointer. A pending generation
must never become the boot identity just because it exists.

The native tests interrupt immediately before and after rename and verify that
the pointer contains a complete old or new value, plus refusal of unsafe files
without changing the prior pointer. The fault hook is compile-time test-only;
the package build does not enable it. These are host filesystem tests, not proof
of AP flash power-loss recovery. Target compilation, sole-client candidate
activation, failed-proof rollback and reboot retention remain to be tested.

Run `python3 -B tests/private-pki/durable-store-test.py` with a native C compiler.
