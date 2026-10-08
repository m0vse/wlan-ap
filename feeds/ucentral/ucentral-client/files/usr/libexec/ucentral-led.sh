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
PHASE_STATE=/tmp/ucentral-led-phase

case "$(board_name)" in
cambiumnetworks,e400)
	# Preserve frozen E400 behavior; no blue or new phase mapping is inferred.
	case "$1" in managed|phase|running) exit 1 ;; phase-*|disabled-pattern) exit 0 ;; esac
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
cambiumnetworks,xv3-8|cambiumnetworks,xv2-21x|cambiumnetworks,x7-35x)
	LED_PATH="/sys/class/leds/blue:status"
	RUNNING_LED_PATH="/sys/class/leds/green:status"
	PHASE_LED_PATHS="/sys/class/leds/orange:status"
	case "$(board_name)" in
	cambiumnetworks,xv3-8|cambiumnetworks,x7-35x) PHASE_LED_PATHS="$PHASE_LED_PATHS /sys/class/leds/red:status" ;;
	esac
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
	case "$1" in managed|phase|running) exit 1 ;; phase-*|disabled-pattern) exit 0 ;; esac
	exit 0
	;;
esac

# Internal read-only probes used by the state service.
phase_visible() {
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
phase_saved() {
	[ ! -L "$PHASE_STATE" ] && [ -d "$PHASE_STATE" ] &&
		[ "$(stat -c %u "$PHASE_STATE" 2>/dev/null)" = "$(id -u)" ] &&
		[ "$(stat -c %a "$PHASE_STATE" 2>/dev/null)" = 700 ]
}
phase_active() { phase_saved || phase_visible; }

# Keep ownership separate from the outputs which global-off suppresses. Never
# source saved data; only qualified channel names and validated scalar values
# are read. The standard diagnostic connect/done events release this state.
phase_save() {
	local path name trigger selected value prop
	phase_saved && return 0
	umask 077
	mkdir -m 700 "$PHASE_STATE" 2>/dev/null || return 1
	for path in $PHASE_LED_PATHS; do
		[ -d "$path" ] || continue
		name=${path##*/}; selected=none
		trigger=$(cat "$path/trigger" 2>/dev/null)
		for value in $trigger; do
			case "$value" in \[*\]) selected=${value#\[}; selected=${selected%\]} ;; esac
		done
		case "$trigger" in none|timer|heartbeat|default-on) selected=$trigger ;; esac
		case "$selected" in ''|*[!a-zA-Z0-9_-]*) return 1 ;; esac
		printf '%s\n' "$selected" > "$PHASE_STATE/$name.trigger" || return 1
		cat "$path/brightness" > "$PHASE_STATE/$name.brightness" || return 1
		if [ "$selected" = timer ]; then
			for prop in delay_on delay_off; do
				[ ! -f "$path/$prop" ] || cat "$path/$prop" > "$PHASE_STATE/$name.$prop" || return 1
			done
		fi
	done
}
phase_restore() {
	local path name trigger value prop
	phase_saved || return 0
	[ -f "$PHASE_STATE/suppressed" ] || return 0
	for path in $PHASE_LED_PATHS; do
		[ -d "$path" ] || continue
		name=${path##*/}
		[ -f "$PHASE_STATE/$name.trigger" ] || continue
		trigger=$(cat "$PHASE_STATE/$name.trigger")
		value=$(cat "$PHASE_STATE/$name.brightness")
		case "$trigger" in ''|*[!a-zA-Z0-9_-]*) return 1 ;; esac
		case "$value" in ''|*[!0-9]*) return 1 ;; esac
		echo "$value" > "$path/brightness" && echo "$trigger" > "$path/trigger" || return 1
		for prop in delay_on delay_off; do
			[ -f "$PHASE_STATE/$name.$prop" ] || continue
			value=$(cat "$PHASE_STATE/$name.$prop")
			case "$value" in ''|*[!0-9]*) return 1 ;; esac
			echo "$value" > "$path/$prop" || return 1
		done
	done
	rm -f "$PHASE_STATE/suppressed"
}
phase_clear() {
	local path name
	phase_saved || return 0
	for path in $PHASE_LED_PATHS; do
		name=${path##*/}
		rm -f "$PHASE_STATE/$name.trigger" "$PHASE_STATE/$name.brightness" "$PHASE_STATE/$name.delay_on" "$PHASE_STATE/$name.delay_off" || return 1
	done
	rm -f "$PHASE_STATE/suppressed" || return 1
	rmdir "$PHASE_STATE"
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
	case "$1" in
	phase-connect|phase-done)
		phase_clear || exit 1
		for path in $PHASE_LED_PATHS; do led_off "$path" || exit 1; done
		if [ "$leds_off" = 1 ]; then led_off "$LED_PATH" && led_off "$RUNNING_LED_PATH" || exit 1; fi
		exit 0 ;;
	phase-preinit|phase-preinit_regular|phase-failsafe|phase-upgrade|phase-reboot)
		phase_clear && phase_save || exit 1
		led_off "$LED_PATH" && led_off "$RUNNING_LED_PATH" || exit 1
		[ "$leds_off" = 1 ] || exit 0 ;;
	phase-*) exit 0 ;;
	esac
	# Global off outranks normal, boot/upgrade/recovery and identify patterns.
	if [ "$leds_off" = 1 ] || [ "$1" = disabled ] || [ "$1" = disabled-pattern ]; then
		if [ "$1" != disabled-pattern ] && phase_visible; then phase_save || exit 1; fi
		if phase_saved; then : > "$PHASE_STATE/suppressed" || exit 1; fi
		for path in "$LED_PATH" "$RUNNING_LED_PATH" $PHASE_LED_PATHS; do
			led_off "$path" || exit 1
		done
		exit 0
	fi
	# Normal updates may not alter boot/flash/recovery or active patterns.
	if phase_active; then
		phase_restore || exit 1
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

case "$1" in phase-*|disabled-pattern) exit 0 ;; esac

# Preserve existing cloud-only behavior for all other supported boards.
[ -d "$LED_PATH" ] || exit 0
[ "$leds_off" = 1 ] && set -- off
echo none > "$LED_PATH/trigger"
case "$1" in
on) cat "$LED_PATH/max_brightness" > "$LED_PATH/brightness" ;;
*) echo 0 > "$LED_PATH/brightness" ;;
esac
