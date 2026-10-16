# Power mismatch severity

An RRM power reduction is not itself a fault. When firmware readback differs
from the requested power, report `radio_power_mismatch` as a warning only if
channel and width are both confirmed. Keep the score penalty and the exact
requested/reported values. Do not call the operating state confirmed.

Channel/width disagreement, a radio that did not start, and existing NAND or
other critical faults remain critical. Disabled radios remain excluded by
the existing collector. Missing readback is not invented success.

Patch 108 is additive: patch 107, all driver fixes, NAND, MLO and A/B source
are unchanged. Schema package release 41 includes the classification change
for every family. `test-health-operating.py` exercises the actual prepared
health sender using native ucode and synthetic transport/filesystem data.

Existing AP firmware is not modified by publishing this source. The controller
can display a compatibility warning for old `radio_operating_mismatch`
reports only with matching resource/radio and explicit power-only evidence;
the original report remains available as Raw JSON. AP-side reporting changes
take effect after a separately built and operator-installed firmware release.
