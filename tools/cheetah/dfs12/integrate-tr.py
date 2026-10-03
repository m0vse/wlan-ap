from pathlib import Path
b=Path('/home/phil/openwifi-cheetah-build/wlan-ap')
p=b/'patches-25.12/0126-qualcommax-add-Cambium-Cheetah-OpenWiFi-family.patch'
s=p.read_text();old=" RAMFS_COPY_BIN='dumpimage fw_printenv fw_setenv head seq'\n"
assert old in s
s=s.replace(old,"-RAMFS_COPY_BIN='dumpimage fw_printenv fw_setenv head seq'\n+RAMFS_COPY_BIN='tr dumpimage fw_printenv fw_setenv head seq'\n",1);p.write_text(s)
p=b/'openwrt/target/linux/qualcommax/ipq50xx/base-files/lib/upgrade/platform.sh'
s=p.read_text();old="RAMFS_COPY_BIN='dumpimage fw_printenv fw_setenv head seq'";assert old in s
p.write_text(s.replace(old,"RAMFS_COPY_BIN='tr dumpimage fw_printenv fw_setenv head seq'",1))
