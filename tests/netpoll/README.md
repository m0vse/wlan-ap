# Selected Ethernet netpoll source controls

Patch 0156 creates qca-nss-dp inner patch 010 and increases package release to 2.
It applies to pinned source 19c51af0. Thor/Jaguar use EDMA-v1; Cheetah selects
IPQ50xx SynGMAC, as confirmed by the actual saved object commands. EDMA-v2 is
unselected for these candidates and is not modified or claimed as qualified.

The EDMA-v1 zero-budget branch cleans TX completion rings and returns before RX,
refill, NAPI completion, queue wakeup or interrupt writes. The SynGMAC RX callback
returns immediately; its TX callback uses the existing internal bound 64, matching
its 64-entry cleanup arrays, then returns zero. This avoids passing zero into a
completion loop which clamps its count to zero but executes a do/while decrement.
Positive-budget source reconstructs the original byte-for-byte after removing
only the added guards.

Run `test-selected-callbacks.py OLD_THOR_C NEW_THOR_C OLD_SYNGMAC_C NEW_SYNGMAC_C`.
The test extracts the exact production callback bodies and compiles them with
harmless hardware functions. Ten controls cover zero/positive budgets, empty TX
rings, page refill, incomplete refill, NAPI completion and interrupt behavior.
Separately compile each selected modified C file with its actual retained target
compiler command, redirecting source/object/dependency paths to private fixtures.
Do not compile an unused EDMA-v2 file and call it Cheetah qualification.

This does not prove panic packet delivery or fix a dead/locked DMA engine. Thor's
single EDMA-v1 NAPI attaches to the first registered netdevice, so the configured
netconsole target must be the reviewed NAPI-owning wired port. No device name,
MAC or endpoint is selected automatically. No firmware build, AP reconfiguration,
intentional crash or reboot is part of these source controls.
