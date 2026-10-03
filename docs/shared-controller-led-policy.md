# Controller status LED arbitration

This source policy uses mutually exclusive blue for a connected client and steady
green for an operational disconnected device only on supplied qualified mappings:
ThorXV3-8; CheetahXV2-21X; SageE410/E410B; JaguarXV2-2/XV2-2T1/XE3-4. Model-specific
physical color acceptance remains required where not previously performed. Other
advertised siblings are not enabled. No GPIO or device-tree mapping is changed.

The helper/state service is the single normal-color owner. Existing boot/upgrade/
recovery phase channels and identify/factory-reset timers outrank normal updates.
GlobalLEDoff outranks all mapped status channels and is reversible on reload.
Connection changes during a timed pattern update service state but do not cancel
that pattern. A pattern timeout restores the current connection color. Mapped
running-node lookup also works with color/function DT nodes lacking legacy labels.

Helper interface:
- on/off: connected blue / disconnected green on mapped blue+green boards.
- pattern: release normal channels before the state service starts identification.
- restore-on/restore-off: restore normal display at a trusted pattern timeout.
- disabled: global-off output; clear mapped status channels and triggers.
- managed/phase/running: read-only state-service probes, no LED writes.

GambitE400 preserves the exact frozen source policy: connected green, disconnected
amber, global-off both zero, unknown ordinary argument both zero. It does not opt
into new phase mapping or the blue/green arbitration. No blue, red/amber equivalence,
or physical acceptance is inferred. Existing generic pattern handlers remain.

Client authentication is a separate mandatory dependency: the online notification
must occur after existing peer/hostname checks and websocket assignment. Shared
reporting owner supplies that client patch. State accepts a nonnegative integer
connected-age field, including zero; absent or invalid fields are disconnected.
This does not weaken TLS policy. Existing online before validation must not ship
with the new color policy.

Offline results at source preparation: 21 full-state ARM controls, 210 helper ARM
controls including eight mapped model-name variants and frozen Gambit cases. No
firmware build, AP LED write, service restart, radio operation or reboot occurred.
Independent family validation and physical patterns remain coordinator gates.

Phase ownership survives global LED suppression in a private volatile directory at `/tmp/ucentral-led-phase`. The diagnostic lifecycle hook in patch 0143 records preinit, failsafe, upgrade and reboot ownership; `connect` or `done` releases it. A suppressed timer restores its original delay values once, without restarting on every normal status update. Cancelling an identify/reset pattern uses `disabled-pattern` so that its timer cannot become a retained boot phase. No persistent flash writes or AP operations are part of the fixtures.
