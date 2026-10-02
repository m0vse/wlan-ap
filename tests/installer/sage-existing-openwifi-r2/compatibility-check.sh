#!/bin/sh
# Incoming image is SHA-pinned to metadata1.0; no UCI mutation is allowed.
# Stock OpenWiFi sysupgrade starts SAVE_CONFIG=0 and enables -f afterwards,
# so its plain -T alone is insufficient for our explicit archive preservation.
sage_configuration_preservation_check() {
 local compatibility
 command -v uci >/dev/null || return 1
 uci -q show system >/dev/null 2>&1 || return 1
 compatibility=$(uci -q get 'system.@system[0].compat_version' 2>/dev/null) || compatibility=
 case "${compatibility:-1.0}" in
  1.0) return 0 ;;
  *) echo 'Only legacy OpenWiFi configuration1.0 is approved for preservation; refusing without UCI edits' >&2; return 1 ;;
 esac
}
