from pathlib import Path
import subprocess,argparse
p=argparse.ArgumentParser();p.add_argument('--sdk',required=True,type=Path);a=p.parse_args();root=a.sdk
module=root/'package/cambium/cambium-cheetah-support/files/cambium-ab-cheetah.sh'
for model,expected in [('21x','XV2-21X 00000023 config@mp03.3-ocelot 1 2 br-lan.1 br-lan'),('23t','XV2-23T 00000024 config@mp03.3-lynx 0 2 br-lan.1 br-lan'),('22h','XV2-22H 00000022 config@mp03.3-cheetah 0 0 br-lan')]:
 command='. "$1"; AB_QUALIFIED=0 AB_RADIOS=0 AB_LAN=br-lan; ab_cheetah_board "$2"; printf "%s %s %s %s %s %s" "$AB_MODEL" "$AB_SKU" "$AB_FIT" "$AB_QUALIFIED" "$AB_RADIOS" "$AB_LAN"'
 got=subprocess.check_output(['sh','-c',command,'sh',str(module),'cambiumnetworks,xv2-'+model],text=True);assert got==expected,(model,got)
cal=root/'target/linux/qualcommax/ipq50xx/base-files/etc/hotplug.d/firmware/11-ath11k-caldata'
body=cal.read_text().replace('. /lib/functions/caldata.sh', 'board_name() { echo "$TEST_BOARD"; }; caldata_extract() { printf "%s %s %s" "$1" "$2" "$3"; }')
for model in ['21x','23t']:
 for firmware,offset in [('IPQ5018/hw1.0/cal-ahb-c000000.wifi.bin','0x1000'),('QCN6122/hw1.0/cal-ahb-b00a040.wifi.bin','0x26800')]:
  import os
  got=subprocess.check_output(['sh','-c',body],env={**os.environ,'TEST_BOARD':'cambiumnetworks,xv2-'+model,'FIRMWARE':'ath11k/'+firmware},text=True);assert got=='0:ART '+offset+' 0x20000',got
network=(root/'target/linux/qualcommax/ipq50xx/base-files/etc/board.d/02_network').read_text();start=network.index('ipq50xx_setup_interfaces()');end=network.index('\nboard_config_update',start);function=network[start:end]
for model in ['21x','23t']:
 got=subprocess.check_output(['sh','-c','ucidef_set_interface_wan() { echo "WAN:$1"; }; '+function+'\nipq50xx_setup_interfaces "$1"','sh','cambiumnetworks,xv2-'+model],text=True).strip();assert got=='WAN:lan',got
print('Model/health policy3 + exact ART dispatch4 + WAN/DHCP mapping2: PASS')
