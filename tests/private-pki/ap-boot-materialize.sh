#!/bin/sh
# EXPERIMENTAL isolated fixture only; not installed/enabled in firmware.
# Restore only a committed generation. Pending/failed proof generations cannot
# affect boot. Caller supplies trusted controller and public trust policy.
set -eu
store=${1:?committed generation store}
runtime=${2:?runtime directory}
trust=${3:?approved public trust bundle}
serial=${4:?expected serial}
server=${5:?approved controller hostname}
port=${6:-15002}
die() { echo "Private identity restore: $*" >&2; exit 1; }
case "$serial" in *[!0-9a-f]*|'') die 'invalid serial' ;; esac
[ "${#serial}" = 12 ] || die 'invalid serial length'
case "$server" in ''|*[!A-Za-z0-9.-]*|[-.]*|*.) die 'invalid controller hostname' ;; esac
case "$port" in ''|*[!0-9]*) die 'invalid controller port' ;; esac
[ "$port" -ge 1 ] && [ "$port" -le 65535 ] || die 'invalid controller port'
[ -f "$trust" ] && [ ! -L "$trust" ] || die 'missing approved trust'
private_dir() {
    [ -d "$1" ] && [ ! -L "$1" ] && LC_ALL=C ls -ldn "$1" |
        awk -v owner="$(id -u)" '$1=="drwx------" && $3==owner { ok=1 } END { exit !ok }'
}
private_dir "$store" || die 'unsafe store'
private_file() {
    [ -f "$1" ] && [ ! -L "$1" ] && LC_ALL=C ls -ldn "$1" |
        awk -v owner="$(id -u)" '$1=="-rw-------" && $3==owner { ok=1 } END { exit !ok }'
}
private_file "$store/current.json" || die 'unsafe committed pointer'
generation=$(ucode -e 'import * as fs from "fs"; let p=json(fs.readfile(ARGV[0])); if(p.serial!=ARGV[1] || !match(p.generation, /^generation-[0-9a-f]{16}$/)) die("invalid committed identity"); print(p.generation);' "$store/current.json" "$serial") || die 'invalid committed pointer'
generation=$store/$generation
private_dir "$generation" || die 'unsafe generation'
private_file "$generation/cert.pem" && private_file "$generation/key.pem" || die 'unsafe identity files'
work=$(mktemp -d /tmp/private-pki-restore.XXXXXX)
trap 'rm -rf "$work"' EXIT HUP INT TERM
openssl verify -x509_strict -purpose sslclient -CAfile "$trust" -untrusted "$generation/cert.pem" "$generation/cert.pem" > "$work/verified" 2>&1 || die 'identity chain/dates/purpose rejected'
openssl x509 -in "$generation/cert.pem" -noout -ext basicConstraints | grep -q '^[[:space:]]*CA:FALSE[[:space:]]*$' || die 'identity is not an end-entity certificate'
openssl x509 -in "$generation/cert.pem" -noout -ext extendedKeyUsage | grep -q '^[[:space:]]*TLS Web Client Authentication[[:space:]]*$' || die 'identity usage rejected'
[ "$(openssl x509 -in "$generation/cert.pem" -noout -subject -nameopt RFC2253)" = "subject=CN=$serial" ] || die 'identity serial mismatch'
openssl x509 -in "$generation/cert.pem" -noout -checkend 0 > /dev/null || die 'identity expired'
openssl x509 -in "$generation/cert.pem" -pubkey -noout > "$work/cert-public"
openssl pkey -in "$generation/key.pem" -pubout > "$work/key-public" 2>/dev/null
cmp -s "$work/cert-public" "$work/key-public" || die 'identity key mismatch'
mkdir -p "$runtime"
[ ! -L "$runtime" ] || die 'unsafe runtime'
if [ -e "$runtime/key.pem" ] || [ -L "$runtime/key.pem" ]; then
    [ -f "$runtime/key.pem" ] && [ ! -L "$runtime/key.pem" ] || die 'unsafe runtime key'
    openssl pkey -in "$runtime/key.pem" -pubout > "$work/runtime-public" 2>/dev/null
    cmp -s "$work/runtime-public" "$work/key-public" || die 'refusing to replace a different existing AP key'
fi
umask 077
# The stock client reads key.pem, while its certificate/CA paths come from
# gateway.json. Renewals keep the unique key; rotation needs a separate gate.
cp "$generation/key.pem" "$runtime/key.pem.private-new"
chmod 600 "$runtime/key.pem.private-new"
mv "$runtime/key.pem.private-new" "$runtime/key.pem"
ucode -e 'print({server:ARGV[0],port:int(ARGV[1]),cert:ARGV[2],ca:ARGV[3],valid:true,hostname_validate:1});' \
    "$server" "$port" "$generation/cert.pem" "$trust" > "$runtime/gateway.json.private-new"
chmod 600 "$runtime/gateway.json.private-new"
mv "$runtime/gateway.json.private-new" "$runtime/gateway.json"
echo 'PASS: committed identity restored for stock client; pending generations ignored'
