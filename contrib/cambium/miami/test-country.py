from pathlib import Path
import subprocess
p=Path(__file__).resolve().parents[3] / "feeds/tip/cambium-miami-radio/files/miami-board-data"
s=p.read_text();country=s[s.index('country() {'):s.index('\n# OEM setup_bdf')]
mock='''cat() { [ "$1" = /etc/ucentral/country ] || return 99; printf '%s' "$NATIVE"; }
uci() {
 case "$*" in
 '-q show wireless') printf '%s\\n' 'wireless.pci=wifi-device' 'wireless.ahb=wifi-device';;
 '-q get wireless.pci.country') printf '%s' "$PCI";;
 '-q get wireless.ahb.country') printf '%s' "$AHB";;
 *) return 99;;
 esac
}
'''
cases=[('GB','GB','GB',True),('GB','','',True),('','GB','GB',True),('gb','gb','gb',True),('','','',False),('00','00','00',False),('GB','US','GB',False),('','US','GB',False),('GB;bad','','',False)]
for native,pci,ahb,ok in cases:
 import os
 r=subprocess.run(['sh','-c',mock+country+'\ncountry'],env={**os.environ,'NATIVE':native,'PCI':pci,'AHB':ahb},capture_output=True,text=True)
 assert (r.returncode==0)==ok,(native,pci,ahb,r)
 if ok:assert r.stdout.strip()=='GB'
print('PASS: 9 native/rendered country agreement and fail-closed tests')
