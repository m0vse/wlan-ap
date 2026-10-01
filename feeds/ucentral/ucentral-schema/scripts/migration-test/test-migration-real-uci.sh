#!/bin/sh
# Exact stock schema and libuci execute in an isolated fixture tree.
# Absolute paths are mechanically redirected; only ubus/PHY/wifi detection
# are stubs. This is not a kernel boot or physical AP test.
set -eu
build=${1:?OpenWrt build root}
native=${2:?native UCI test root}
fixtures=${3:?fixture directory}
package_dir=$(cd "$fixtures/../.." && pwd)
baseline_script=$fixtures/zzz-migration
[ -f "$baseline_script" ] || baseline_script=$package_dir/../ucentral-client/files/etc/uci-defaults/zzz-ucentral
strict_patch=$fixtures/060-strict-boot-uci.patch
[ -f "$strict_patch" ] || strict_patch=$package_dir/patches/060-strict-boot-uci.patch
test_root=$(mktemp -d /tmp/openwifi-migration-test.XXXXXX)
if [ -d "$build/build_dir/target-aarch64_cortex-a53_musl" ]; then
	arch=aarch64_cortex-a53_musl; target=qualcommax; portbase=lan1
else
	arch=arm_cortex-a7+neon-vfpv4_musl_eabi; target=ipq40xx; portbase=eth0
fi
schema=$build/build_dir/target-$arch/ucentral-schema-2026.08.26~d1e90a04
ucode=$build/staging_dir/hostpkg/bin/ucode
export PATH="$native/bin:$PATH"

prepare() {
	name=$1
	root=$test_root/$name
	mkdir -p "$root/etc/ucentral" "$root/etc/config-shadow" "$root/tmp" "$root/usr/share/ucentral" "$root/lib"
	cp -a "$build/build_dir/target-$arch/root-$target/etc/config" "$root/etc/"
	cp -a "$build/build_dir/target-$arch/root-$target/etc/init.d" "$root/etc/"
	cp "$fixtures/network.fixture" "$root/etc/config/network"
	cp "$fixtures/system.fixture" "$root/etc/config/system"
	cp "$fixtures/wireless.fixture" "$root/etc/config/wireless"
	cp "$fixtures/ucentral.fixture" "$root/etc/config-shadow/ucentral"
	cp "$fixtures/board.fixture" "$root/etc/board.json"
	cp "$fixtures/capabilities.fixture" "$root/etc/ucentral/capabilities.json"
	sed -i "s|lan1|$portbase|g" "$root/etc/board.json" "$root/etc/ucentral/capabilities.json"
	cp "$fixtures/tagged.fixture" "$root/etc/ucentral/tagged.json"
	cp "$build/../feeds/ucentral/ucentral-schema/files/etc/ucentral/ucentral.cfg.0000000001" "$root/etc/ucentral/default.json"
	cp -a "$schema/renderer/"* "$root/usr/share/ucentral/"
	cp "$schema/schemareader.uc" "$root/usr/share/ucentral/"
	case "$name" in
		broken-*)
			if grep -q 'Cannot load baseline package' "$root/usr/share/ucentral/ucentral.uc"; then
				sed 's|renderer/ucentral.uc|ucentral.uc|g' "$strict_patch" | patch -s -R -p1 -d "$root/usr/share/ucentral"
			fi ;;
		*)
			if ! grep -q 'Cannot load baseline package' "$root/usr/share/ucentral/ucentral.uc"; then
				sed 's|renderer/ucentral.uc|ucentral.uc|g' "$strict_patch" | patch -s -p1 -d "$root/usr/share/ucentral"
			fi ;;
	esac
	# Rewrite environment paths only, not render or UCI command logic.
	find "$root/usr/share/ucentral" -name '*.uc' -type f -exec sed -i \
		-e "s|/tmp/|$root/tmp/|g" -e "s|/etc/|$root/etc/|g" \
		-e "s|/usr/share/ucentral/|$root/usr/share/ucentral/|g" \
		-e "s|/sbin/uci|$native/bin/uci|g" {} +
	sed -i "s|uci.cursor()|uci.cursor('$root/etc/config', '$root/tmp/.uci')|g" "$root/usr/share/ucentral/renderer.uc"
	cp "$fixtures/ubus.fixture" "$root/lib/ubus.uc"
	cp "$fixtures/phy.fixture" "$root/usr/share/ucentral/wifi/phy.uc"
	# Detection only copies our radio fixture, never touches host interfaces.
	printf '#!/bin/sh\ncp "%s/etc/config/wireless" "%s/tmp/config-shadow/"\n' "$root" "$root" > "$root/usr/share/ucentral/wifi_detect.sh"
	chmod +x "$root/usr/share/ucentral/wifi_detect.sh"
}

render_boot() {
	if "$ucode" -L "$native/lib" -L "$root/lib" -L "$root/usr/share/ucentral" -- "$root/usr/share/ucentral/ucentral.uc" "$root/etc/ucentral/$1.json" --boot > "$root/render.log" 2>&1; then
		return 0
	fi
	cat "$root/render.log" >&2
	return 1
}

complete_baseline() {
	# Execute the actual migration script with filesystem/tool paths redirected.
	sed -e "s|/etc/|$root/etc/|g" \
		-e "s|^uci commit$|$native/bin/uci -c $root/etc/config -t $root/tmp/.uci commit|" \
		"$baseline_script" > "$root/migrate.sh"
	sh "$root/migrate.sh"
	cmp "$fixtures/ucentral.fixture" "$root/etc/config-shadow/ucentral"
	for file in network system dhcp firewall dropbear; do
		test -f "$root/etc/config-shadow/$file"
	done
}

# Reproduce .6 with its real stock renderer and the physical partial-shadow
# layout. uci batch emits failures but returns 0, and the old code marks ready.
prepare broken-partial
render_boot default
test -s "$root/tmp/ucentral-network.ready"
! "$native/bin/uci" -c "$root/etc/config" -t "$root/tmp/.uci" -q get network.up0v0.proto
grep -q 'Entry not found' "$root/render.log"
printf '%s\n' 'Reproduced .6: partial baseline, real UCI errors, false ready marker, no management interface'

for profile in default tagged; do
	prepare fixed-$profile
	complete_baseline
	render_boot "$profile"
	test -s "$root/tmp/ucentral-network.ready"
	test ! -s "$root/tmp/ucentral-uci.errors"
	if [ "$profile" = default ]; then iface=up0v0; vid=4090; port=$portbase; else iface=up0v37; vid=37; port=$portbase:t; fi
	test "$("$native/bin/uci" -c "$root/etc/config" -t "$root/tmp/.uci" get network.$iface.proto)" = dhcp
	! "$native/bin/uci" -c "$root/etc/config" -t "$root/tmp/.uci" -q get network.up.vlan_filtering
	"$native/bin/uci" -c "$root/etc/config" -t "$root/tmp/.uci" show network | grep "vlan='$vid'"
	"$native/bin/uci" -c "$root/etc/config" -t "$root/tmp/.uci" show network | grep "ports='$port'"
	printf '%s\n' "$profile migration and explicit management render passed"
done

# The batch CLI still returns 0 on bad input. The corrected renderer must not
# commit live network settings or mark ready in that case.
prepare invalid-batch
complete_baseline
sed -i "s|let batch = state ? renderer.render(state, logs) : '';|let batch = state ? renderer.render(state, logs) + '\\\\nset nonexistent.bad.option=1\\\\n' : '';|" "$root/usr/share/ucentral/ucentral.uc"
if render_boot default; then
	echo 'ERROR: batch command failure was accepted' >&2
	exit 1
fi
test ! -e "$root/tmp/ucentral-network.ready"
test -s "$root/tmp/ucentral-uci.errors"
! "$native/bin/uci" -c "$root/etc/config" -t "$root/tmp/.uci" -q get network.up0v0.proto
printf '%s\n' 'Real batch command error rejected with diagnostics, no ready marker and no live management changes'
echo MIGRATION_TEST_ROOT="$test_root"
