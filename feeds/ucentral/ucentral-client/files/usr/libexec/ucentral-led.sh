#!/bin/sh
#
# ucentral-led.sh - drive the cloud/controller-managed indicator LED.
#
# Called with "on" or "off" by:
#   - /etc/init.d/ucentral   on service stop, and when no gateway is configured
#   - ucentral-state         on online/offline transitions (real connection state)
#
# Boards without a cloud LED, or with LEDs disabled globally, are a no-op.
#

. /lib/functions.sh

RUNNING_LED_PATH=
PHASE_LED_PATHS=

case "$(board_name)" in
cambiumnetworks,e400)
	# Preserve frozen E400 behavior; no blue or new phase mapping is inferred.
	case "$1" in managed|phase|running) exit 1 ;; esac
	for colour in green amber; do
		path="/sys/class/leds/$colour:status"
		[ -d "$path" ] || continue
		echo none > "$path/trigger"
		value=0
		if [ "$(uci -q get system.@system[-1].leds_off)" != 1 ]; then
			case "$1:$colour" in on:green|off:amber) value=1 ;; esac
		fi
		echo "$value" > "$path/brightness"
	done
	exit 0
	;;
cambiumnetworks,xv3-8|cambiumnetworks,xv2-21x)
	LED_PATH="/sys/class/leds/blue:status"
	RUNNING_LED_PATH="/sys/class/leds/green:status"
	PHASE_LED_PATHS="/sys/class/leds/orange:status"
	[ "$(board_name)" != cambiumnetworks,xv3-8 ] || PHASE_LED_PATHS="$PHASE_LED_PATHS /sys/class/leds/red:status"
	;;
cambium,e410|cambiumnetworks,e410|cambiumnetworks,e410b)
	LED_PATH="/sys/class/leds/blue:status"
	RUNNING_LED_PATH="/sys/class/leds/green:status"
	PHASE_LED_PATHS="/sys/class/leds/amber:status /sys/class/leds/red:status"
	;;
cambiumnetworks,xv2-2|cambiumnetworks,xv2-2t1|cambiumnetworks,xe3-4)
	LED_PATH="/sys/class/leds/jaguar:status:blue"
	RUNNING_LED_PATH="/sys/class/leds/jaguar:status:green"
	PHASE_LED_PATHS="/sys/class/leds/jaguar:status:orange /sys/class/leds/jaguar:status:red"
	;;
edgecore,eap104)
	LED_PATH="/sys/class/leds/green:cloud"
	;;
edgecore,eap105|\
edgecore,oap101|\
edgecore,oap101e|\
edgecore,eap111|\
edgecore,eap111e|\
edgecore,eap115|\
edgecore,eap115a)
	LED_PATH="/sys/class/leds/blue:cloud"
	;;
*)
	case "$1" in managed|phase|running) exit 1 ;; esac
	exit 0
	;;
esac

# Internal read-only probes used by the state service.
phase_active() {
	local path trigger brightness
	for path in $PHASE_LED_PATHS; do
		[ -d "$path" ] || continue
		trigger=$(cat "$path/trigger" 2>/dev/null)
		brightness=$(cat "$path/brightness" 2>/dev/null)
		case "$trigger" in
		*'[none]'*|none|'') [ "${brightness:-0}" -gt 0 ] && return 0 ;;
		*) return 0 ;;
		esac
	done
	return 1
}
case "$1" in
managed) [ -n "$RUNNING_LED_PATH" ]; exit $? ;;
running) [ -n "$RUNNING_LED_PATH" ] || exit 1; printf '%s\n' "${RUNNING_LED_PATH##*/}"; exit 0 ;;
phase) phase_active; exit $? ;;
esac

led_off() {
	[ -d "$1" ] || return 0
	echo none > "$1/trigger" && echo 0 > "$1/brightness"
}

restore=0
case "$1" in
restore-on) restore=1; set -- on ;;
restore-off) restore=1; set -- off ;;
esac

leds_off=$(uci -q get system.@system[-1].leds_off)
if [ -n "$RUNNING_LED_PATH" ]; then
	# Global off outranks normal, boot/upgrade/recovery and identify patterns.
	if [ "$leds_off" = 1 ] || [ "$1" = disabled ]; then
		for path in "$LED_PATH" "$RUNNING_LED_PATH" $PHASE_LED_PATHS; do
			led_off "$path" || exit 1
		done
		exit 0
	fi
	# Normal updates may not alter boot/flash/recovery or active patterns.
	if phase_active; then
		for path in "$LED_PATH" "$RUNNING_LED_PATH"; do
			if [ "$restore" = 1 ]; then led_off "$path" || exit 1; continue; fi
			case "$(cat "$path/trigger" 2>/dev/null)" in
			*'[timer]'*|timer) ;;
			*) led_off "$path" || exit 1 ;;
			esac
		done
		exit 0
	fi
	if [ "$1" = pattern ]; then
		led_off "$LED_PATH" && led_off "$RUNNING_LED_PATH"
		exit $?
	fi
	if [ "$restore" = 1 ]; then
		led_off "$LED_PATH" && led_off "$RUNNING_LED_PATH" || exit 1
	fi
	case "$(cat "$LED_PATH/trigger" "$RUNNING_LED_PATH/trigger" 2>/dev/null)" in
	*'[timer]'*|timer) exit 0 ;;
	esac
	case "$1" in
	on) active="$LED_PATH"; inactive="$RUNNING_LED_PATH" ;;
	*) active="$RUNNING_LED_PATH"; inactive="$LED_PATH" ;;
	esac
	led_off "$inactive" || exit 1
	[ -d "$active" ] || exit 0
	echo none > "$active/trigger" || exit 1
	cat "$active/max_brightness" > "$active/brightness"
	exit $?
fi

# Preserve existing cloud-only behavior for all other supported boards.
[ -d "$LED_PATH" ] || exit 0
[ "$leds_off" = 1 ] && set -- off
echo none > "$LED_PATH/trigger"
case "$1" in
on) cat "$LED_PATH/max_brightness" > "$LED_PATH/brightness" ;;
*) echo 0 > "$LED_PATH/brightness" ;;
esac
