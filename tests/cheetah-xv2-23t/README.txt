XV2-23T candidate preparation

0195 extends the actual IPQ4019 MDIO sibling-clock guard to XV2-23T,
enables both inherited IPQ5018/QCN6122 radio nodes with distinct23T variants,
and dispatches the unit ART offsets0x1000/0x26800 (each0x20000). The existing
OEM board-data importer already selects full b24-lynx and b60.stock; the
truncated b60-lynx is neither selected nor padded. Public firmware contains
no unit ART or private OEM data.

The native default config selects WAN/WAN1 untagged with DHCP. board.d maps
23T WAN to lan exactly as21X, so native uCentral handles management rendering;
the historical OpenWISP-only17_cheetah_bridge_section is not installed or reused.
The23T A/B module supplies both management interface candidates and requires
both radios for health. AB_QUALIFIED stays0 until actual hardware acceptance.
The common A/B tools include enabled exact-model23T conversion support,
separate from AB_QUALIFIED (which stays0). AB_CONVERSION_SUPPORTED is reset
for every family lookup and enabled only in the23T board case. Conversion
still requires --yes, identity/layout checks, a matching off-device OEM
backup hash, a valid device-data vault, preserved working boot selection and
readback verification. The retired global --allow-untested escape remains
rejected. Conversion consumes the OEM bank only when deliberately invoked;
no conversion or AP writes happen during building or staging. Physical A/B
acceptance remains pending.

Stock RAM boot is supporting bring-up evidence, not full stock/OpenWiFi
qualification. Next hardware work: persistent boot, SSH/DHCP/radio acceptance,
then explicit each-bank trial, failed-trial rollback and config/vault retention.
No AP writes or environment changes are part of these source tests.
