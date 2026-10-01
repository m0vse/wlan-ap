#!/bin/sh
set -eu
build=${1:?OpenWrt build root}
test_root=$(mktemp -d /tmp/openwifi-native-uci.XXXXXX)
cp -a "$build/build_dir/target-aarch64_cortex-a53_musl/uci-2025.12.02~66127cd7" "$test_root/uci-src"
cp -a "$build/build_dir/target-aarch64_cortex-a53_musl/libubox-2026.03.13~81563384" "$test_root/ubox-src"
mkdir "$test_root/libubox" "$test_root/lib" "$test_root/bin"
cp "$test_root/ubox-src/"*.h "$test_root/libubox/"
cd "$test_root/ubox-src"
cc -shared -fPIC -O2 -o "$test_root/lib/libubox.so" avl.c avl-cmp.c blob.c blobmsg.c uloop.c usock.c ustream.c ustream-fd.c vlist.c utils.c safe_list.c runqueue.c md5.c kvlist.c ulog.c base64.c udebug.c udebug-remote.c
cd "$test_root/uci-src"
cc -shared -fPIC -O2 -I. -I"$test_root" -L"$test_root/lib" -Wl,-rpath,"$test_root/lib" -o "$test_root/lib/libuci.so" libuci.c file.c util.c delta.c parse.c blob.c -lubox
cc -O2 -I. -I"$test_root" -L"$test_root/lib" -Wl,-rpath,"$test_root/lib" -o "$test_root/bin/uci" cli.c -luci -lubox
cc -shared -fPIC -O2 -I"$test_root/uci-src" -I"$build/staging_dir/hostpkg/include" -I"$build/staging_dir/host/include" -L"$test_root/lib" -L"$build/staging_dir/hostpkg/lib" -Wl,-rpath,"$test_root/lib:$build/staging_dir/hostpkg/lib" -o "$test_root/lib/uci.so" "$build/build_dir/hostpkg/ucode-2026.01.16~85922056/lib/uci.c" -luci -lucode
echo NATIVE_UCI_ROOT="$test_root"
