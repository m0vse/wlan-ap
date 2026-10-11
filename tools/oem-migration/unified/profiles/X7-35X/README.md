# X7-35X OEM 7.2-r1 profile

Exact release/build and physical ranges are transcribed from the retained OEM
report SHA256 `7deeec60c09d426b5f9920551fdc222b8767612ab1adf1e7d7556516487e98f0`.
The private report itself, serial, customer data and firmware are not copied.
NAND erase/page geometry is reported by the OEM kernel; NOR write size 1 is the
physical chip interface and must still match the live sysfs check. The report
is not claimed to contain a complete sysfs attribute capture.

Whole NAND/NOR masters are containers, never write targets. `mtd-slot0.tsv` and
`mtd-slot1.tsv` assign target/source roles from the actual selector. Live sysfs
chip identity, sizes, type, erase/write and offsets (or unique live boot ranges)
are checked independently. Unknown physical children/aliases refuse. No
partition is invented for the unnamed NOR tail.

ART, manufacturing and boot environment are the only off-device backup items.
Other unchanged physical partitions remain protected; model-shared radio data
is supplied by the existing reviewed image/vault/provider, not a rootfs dump.
This profile alone is not a released migration bundle: the current pinned
provider must also implement bounded prefetch/local-only operation, actual
payload/descriptor binding and reviewed boot selection.
