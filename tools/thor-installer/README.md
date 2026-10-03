# Thor installer source

These reviewed source helpers implement the qualified Thor stock-to-OpenWiFi and preserving OpenWiFi routes. They are source inputs, not an assembled installer release. Do not run them as a complete operator bundle. Assemble with reviewed current A/B and certificate helpers, policy/route files, authenticated source/runtime manifests, IMAGE and the exact target firmware, then run the full offline qualification and seal the bundle. Generated manifests and firmware outputs are intentionally excluded. Shared contract changes must remain coordinated with other families.

Stock minimum:2026.09.29.0. OpenWiFi minimum:thor-2026.10.02.8. Stock route explicitly discards legacy configuration and credentials; preserving route validates identity and managed state.
