# Optional private certificate activation challenge

The uCentral client accepts UCENTRAL_PRIVATE_ACTIVATION_NONCE only when it is
exactly 64 lowercase hexadecimal characters. The environment value is consumed
and removed on the first connect attempt, including malformed values. A valid
value is included as privateActivationNonce in the existing native connect
notification. The temporary copy is cleared, and transmit debug logging redacts
messages containing that field. With the variable absent, normal connect fields
and transport are unchanged. This hook contains no default endpoint or secret.

The private lifecycle orchestrator must obtain a fresh challenge using the
candidate certificate, stop the old client, start the sole client with the
candidate identity and challenge, and verify the protected gateway receipt
before committing the durable identity generation. The orchestrator must also
remove its service-level environment override after the attempt and roll back
on failure. A nonce alone never authorizes enrollment or proves acceptance.

Validation: apply existing patch 010 then patch 020 to the pinned upstream client
source; run python3 tests/private-pki/private-activation-nonce-test.py PATCHED_SOURCE.
The test compiles the actual C helper and checks absent, short, long, uppercase,
nonhex, valid and repeated attempts, including removal from the environment.
Validated in an isolated native GCC container on 2026-10-04. Full firmware/package
build and physical AP activation remain pending; no family builds are implied.
