#!/bin/sh
case "$1" in
    bound|renew) printf 'DHCP_LEASE=%s interface=%s\n' "$ip" "$interface" ;;
esac
