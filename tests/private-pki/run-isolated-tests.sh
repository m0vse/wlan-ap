#!/bin/sh
# Run inside the pinned test image, with --network none and no host ports.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
for test in test_enrollment_store.py private-pki-prototype.py test_operator_enrollment.py test_renewal_policy.py test_generation_lifecycle.py; do
    python "$here/$test"
done
