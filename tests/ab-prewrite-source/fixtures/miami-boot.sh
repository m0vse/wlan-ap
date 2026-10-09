# Test-only renderer snapshot from Miami development commit 521dca53.
# This registers no installed model or production upgrade admission.
ab_miami_board() {
 [ "$1" = cambiumnetworks,x7-35x ] || return 1
 AB_SLOT0_OFFSET=0xc0000 AB_SLOT1_OFFSET=0x60c0000
}
ab_miami_boot_command() {
 local part offset
 case "$1" in 0) part=rootfs;offset=$AB_SLOT0_OFFSET;;1) part=rootfs_1;offset=$AB_SLOT1_OFFSET;;*)return 1;;esac
 printf "nand device 0 && setenv mtdids nand0=nand0 && setenv mtdparts 'mtdparts=nand0:0x6000000@%s(fs)' && ubi part fs && ubi read 0x60000000 kernel && setenv bootargs console=ttyMSM0,115200n8 ubi.mtd=%s root=/dev/ubiblock0_1 rootfstype=squashfs rootwait && bootm 0x60000000#config@mi01.6-acadia-slot%s\n" "$offset" "$part" "$1"
}
