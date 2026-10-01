#!/bin/sh
set -eu
collector=${1:?collector}
fixture=$(mktemp -d)
trap 'rm -rf "$fixture"' EXIT
ip() { echo '1: lo: UP'; }
grep() {
	if [ "$1" = '^DISTRIB_TIP=' ]; then echo "DISTRIB_TIP='test'"; else command grep "$@"; fi
}
logread() {
	echo 'ucentral: secret-token-DO-NOT-SAVE'
	n=0
	while [ "$n" -lt 4000 ]; do
		printf 'daemon.notice netifd: diagnostic: interface up0v0 protocol pid=%s state=1 wait_status=15\n' "$n"
		n=$((n + 1))
	done
}
UCENTRAL_TRACE_DIR=$fixture
export UCENTRAL_TRACE_DIR
(. "$collector")
test "$(wc -c < "$fixture/network-boot.trace")" -eq 131072
test "$(stat -c %a "$fixture/network-boot.trace")" = 600
! command grep -q secret-token "$fixture/network-boot.trace"
command grep -q wait_status=15 "$fixture/network-boot.trace"
echo 'Trace cap, private mode, process status and credential-filter checks passed'
