Validated Cheetah runtime preservation

Two deliberately scoped source changes restore behavior shipped in .13 source4a893a76: factory-label hostname/serial initializer and the XV2-21X controller-status LED mapping. Existing shared rtty improvements, private-identity hooks, certificate allocator, discovery6, DFS and Thor topology changes remain unchanged.

The initializer is byte-identical to .13 (SHA256356f28e975a71e47f8ddf343cf609799e62f5b74b99a5a06927147c3ffa4ac97). Existing source fixture checks valid uppercase label produces MAC and lowercase12hex hostname/serial, and absent/short/invalid labels fail before UCI writes. Run sh tests/cheetah-runtime/test-hostname.sh feeds/ucentral/ucentral-schema/files/etc/uci-defaults/99-ucentral-hostname. The four fixture cases pass during this source-only audit.

The LED script is byte-identical to .13 (SHA25666b609dcf2de827f24e0caad3fa1d37d5228f1368c99d5b55848e5809aaaee84). Its mapping uses the existing qualified XV2-21X blue:status LED, checks node presence, respects the global LED switch and is called by existing controller connection transitions. Actual extracted .13 image contains these bytes; hardware DTS defines blue/status GPIO24. This audit does not claim new physical controller/LED testing.

No rebuild, firmware replacement, AP action or shared publication occurs in this audit. Generated test outputs and firmware/configuration artifacts are not committed. Package release increments for a future firmware are a repository-owner release decision.
