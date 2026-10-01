#!/bin/sh
# Run with unshare -nm in private network/mount namespaces. No AP access.
set -eu
mount --make-rprivate /
mount -t sysfs sysfs /sys
sysctl -qw net.ipv6.conf.all.disable_ipv6=1
sysctl -qw net.ipv6.conf.default.disable_ipv6=1
ip link set lo up
ip link add filtered type bridge vlan_filtering 1
[ "$(cat /sys/class/net/filtered/bridge/vlan_filtering)" = 1 ]
[ "$(cat /sys/class/net/filtered/bridge/default_pvid)" = 1 ]
# Model stock netifd: configured bridge-vlans enable filtering and netifd
# removes the automatic VLAN 1 from the bridge and each newly attached port.
bridge vlan del dev filtered vid 1 self
ip link add trunk type veth peer name peer
ip link set trunk master filtered
bridge vlan del dev trunk vid 1
ip link set trunk up
ip link set peer up
ip link set filtered up
unshare -n sleep 60 &
peer_pid=$!
server_pid=
cleanup() {
	[ -z "$server_pid" ] || kill "$server_pid" 2>/dev/null || true
	kill "$peer_pid" 2>/dev/null || true
}
trap cleanup EXIT
while [ "$(readlink /proc/$peer_pid/ns/net)" = "$(readlink /proc/self/ns/net)" ]; do
	kill -0 "$peer_pid"
	sleep 0.05
done
# Move the remote end out of this namespace: otherwise local routing bypasses
# the veth/bridge and is not a meaningful network test.
ip link set peer netns "$peer_pid"
remote() { nsenter -t "$peer_pid" -n "$@"; }
remote sysctl -qw net.ipv6.conf.all.disable_ipv6=1
remote sysctl -qw net.ipv6.conf.default.disable_ipv6=1
remote ip link set peer up
# An attached port must have no implicit VLAN before memberships are set.
! bridge vlan show dev trunk | grep -Eq '[[:space:]]1[[:space:]]'
bridge vlan add dev trunk vid 37
bridge vlan add dev filtered vid 37 self
ip link add link filtered name mgmt type vlan id 37
remote ip link add link peer name sender type vlan id 37
ip addr add 198.18.0.1/24 dev mgmt
remote ip addr add 198.18.0.2/24 dev sender
ip link set mgmt up
remote ip link set sender up
remote ping -c 2 -W 1 -I sender 198.18.0.1

# Saturate with unrelated tagged multicast, while permitted management works.
remote ip link add link peer name noise type vlan id 203
remote ip addr add 198.19.0.2/24 dev noise
remote ip link set noise up
udp_noise() {
	remote python3 -c 'import socket,time; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET,socket.SO_BINDTODEVICE,b"noise\0"); s.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_IF,socket.inet_aton("198.19.0.2")); end=time.monotonic()+3; payload=b"x"*512
while time.monotonic()<end: s.sendto(payload,("239.69.1.1",5004))'
}
noise_before=$(cat /sys/class/net/filtered/statistics/rx_packets)
udp_noise
noise_after=$(cat /sys/class/net/filtered/statistics/rx_packets)
# Management uses a VLAN netdev; undeclared multicast must not reach bridge L3.
[ "$noise_before" = "$noise_after" ]
udp_noise &
noise_pid=$!
remote ping -c 3 -W 1 -I sender 198.18.0.1
wait "$noise_pid" || true
fixture_dir=$(dirname "$0")
nsenter -t "$peer_pid" -n busybox udhcpd -f "$fixture_dir/dhcp-tagged.conf" >/dev/null 2>&1 &
server_pid=$!
# Give the fixture server time to bind before flooding/requesting DHCP.
sleep 1
kill -0 "$server_pid"
udp_noise &
noise_pid=$!
busybox udhcpc -i mgmt -n -q -f -t 3 -T 1 -s "$fixture_dir/dhcp-hook.sh"
wait "$noise_pid"
kill "$server_pid"
wait "$server_pid" 2>/dev/null || true
server_pid=

# Default untagged recovery: internal VID is not a site/native VLAN assumption.
remote ip link set sender down
bridge vlan del dev trunk vid 37
bridge vlan del dev filtered vid 37 self
bridge vlan add dev trunk vid 4090 pvid untagged
bridge vlan add dev filtered vid 4090 self
ip link add link filtered name bootstrap type vlan id 4090
ip addr add 198.18.1.1/24 dev bootstrap
remote ip addr add 198.18.1.2/24 dev peer
ip link set bootstrap up
remote ping -c 2 -W 1 -I peer 198.18.1.1
nsenter -t "$peer_pid" -n busybox udhcpd -f "$fixture_dir/dhcp-untagged.conf" >/dev/null 2>&1 &
server_pid=$!
sleep 1
kill -0 "$server_pid"
busybox udhcpc -i bootstrap -n -q -f -t 3 -T 1 -s "$fixture_dir/dhcp-hook.sh"
bridge vlan show
printf '%s\n' 'Namespace tests passed: declared tagged management, unrelated tagged multicast isolation, filtered untagged bootstrap'
