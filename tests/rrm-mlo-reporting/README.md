# RRM MLO interface and BSS reporting

The native GET_INTERFACE snapshot and the existing qualified normal-state
producer already report both MLO links. The old rrmd cache instead copied one
`hostapd.<ifname> get_status` reply into one interface row and emitted one BSS
addition. A shared hostapd object can answer for only its secondary link.
`reload` did nothing and there was no link lifecycle reconciliation.

The fix keeps the real transport dictionary keys unchanged. For an MLO
transport, `rrm interfaces` now includes `mlo_links`, with independently proven
BSSID, link ID, actual ifname, physical/logical PHY, driver radio index, generated
UCI section, band, frequency, channel and available native power/width fields.
`rrm bsses` exposes the same BSS views keyed by BSSID. Existing BSS lifecycle
emission also uses those views, so the fix is not confined to a new optional API.
Legacy interface rows retain their existing shape and hostapd paths.

The existing schema `mlo_health.collect` provides exact generated-configuration,
per-link control-socket and native-interface identity proof. Link IDs are never
assumed to equal driver radio indexes. The generated wifi-mld group need not
have an explicit ifname. Unavailable, inconsistent or ambiguous proof withdraws
stale link records; it cannot fall back to a phantom MLD/parent BSSID. Neighbor
reports are included only when a fresh shared-object reply proves the exact
BSSID/channel; another link's cached report is never copied.

Refreshes use a fresh read-only UCI cursor, one native snapshot per MLO transport
and a bounded status read per native link. Status queries share a five-second
cache; the MLO-only timer and explicit reload reconcile add/remove/change events.
An unchanged reload emits no duplicate additions, and removing one link emits
one deletion while retaining its peer. Removing the transport removes remaining
BSSs and cancels its timer. Legacy-only reporting requires no MLO/native sampler.

Power resolution, the native link-selector codec and strict ACK handling are
unchanged. Shared ubus `switch_chan` has no proven per-link selector: MLO channel
requests fail closed. This does not introduce MLO channel switching, alter scan
or client-steering policy, or claim per-link station counter support. Ordinary
non-MLO channel handling remains available with fresh target proof.

## Offline controls

```
python3 tests/rrm-mlo-reporting/run-tests.py \
  --repo /path/to/source --root /path/to/qualified/extracted/rootfs \
  --output /private/path/to/results
```

The actual target ucode/UCI runtime and schema43 renderer generate a synthetic
qualified MLO configuration. A disposable copy is reversed before patch109 to
retain the existing renderer's old/new negative controls; the runtime/rootfs
remain unchanged. The reporting test runs the complete actual local module,
view helper and event wrapper with the unchanged qualified health implementation.
Native, control-socket, ubus and timer IO are injected; no AP is used or changed.
The original exact-link power setter is exercised as well. Link IDs 0/7 versus
driver indexes 0/1 expose accidental assumptions. Controls include object and
link lifecycle, generated-section removal/restoration, reload, one scoped channel
event, malformed/failing snapshots, and ordinary 2/5/6GHz interfaces.

`--generated` reuses the synthetic UCI output from an earlier renderer run.
`--baseline-local` runs the actual installed pre-fix local module as a negative
control: it must fail at the missing second link view. Never supply real AP
configuration or credentials as a published fixture.

## Controller path and scope

rrmd's existing event wrapper invokes native `ucentral.event`. The qualified
client queues/forwards it as JSON-RPC `event`, with `data.event=[time,{type,payload}]`.
Retained gateway source `AP_WS_Process_event.cpp` routes `rrm.*` events to Kafka
`rrm`. This source trace is not a new deployed-gateway acceptance test.

The current Java RRM DataCollector separately consumes normal `state` records,
including `interfaces[].ssids[]` and `radios[]`. Read-only observation confirmed
both Miami BSSIDs there before this fix. No schema/state producer, gateway,
controller, native codec, firmware, NAND or radio configuration changes are
part of this source-only reporting repair. A later build/deployment and live
acceptance require the owner's separate decision.

## Production loader regression

The deployed release exposed a test boundary error: injecting `io.health` hid
an invalid absolute-filename `require`. The helper now adds the packaged search
pattern lazily and loads `mlo_health` by module name. Run this mandatory separate
process after generating the synthetic UCI fixture:

```
python3 tests/rrm-mlo-reporting/default-loader.py \
  --repo /path/to/source --root /path/to/qualified/extracted/rootfs \
  --generated /private/results/generated-wireless.synthetic.json \
  --output /private/results/default-loader
```

This uses actual target ucode, real module lookup and the packaged health helper
(including its fs import). It neither injects `io.health`, preloads the helper,
nor supplies its search pattern. Only native/status/sysfs boundaries are
synthetic. `--installed` tests the helper in the extracted new image;
`--installed --expect-old-failure` must reject the actual deployed .16.2 helper.
The complete lifecycle suite also changes and restores each link's simulated
native power, verifying selector/ACK/mBm and unchanged peer power/channel/link
identity after each request. These offline controls do not establish live RF
acceptance: after installation, change and restore one band at a time through
RRM, checking both live link powers, health and channels at each step.
