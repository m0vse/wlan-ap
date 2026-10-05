#!/bin/sh
# Source-side FORMAT2 authorization staging only. No key/CSR/EST operation.
# The authenticated family wrapper supplies trusted OW_EXPECT_* context after
# exact source/model qualification and inactive image readback. No production
# wrapper loads this library until its full source/storage contract is qualified.

ow_settings_fail() { echo 'Installer settings refused.' >&2; return 1; }
# Old qualified stock BusyBox lacks stat. Numeric ls is already available;
# decode only the two accepted private modes, not arbitrary permission text.
# Absolute paths prevent option interpretation; one complete output row is
# mandatory. File type, symlinks and single-link files remain checked by caller.
ow_settings_metadata() {
    local listing
    case "$1" in /*) ;; *) return 1 ;; esac
    listing=$(LC_ALL=C ls -ldn "$1") || return 1
    printf '%s\n' "$listing" | awk '
        NR==1 && NF>=4 && $2~/^[0-9]+$/ && $3~/^[0-9]+$/ && $4~/^[0-9]+$/ {
            if($1=="-rw-------")mode="600"
            else if($1=="drwx------")mode="700"
            else exit 1
            result=$3 ":" mode ":" $2;good=1
        }
        END {if(NR!=1 || !good)exit 1;print result}'
}
ow_settings_private() {
    [ -f "$1" ] && [ ! -L "$1" ] &&
    [ "$(ow_settings_metadata "$1")" = "${OW_SETTINGS_OWNER:-0}:600:1" ] &&
    [ "$(wc -c < "$1")" -le 131072 ]
}
ow_settings_hash() { sha256sum < "$1" | awk '{print $1}'; }
ow_settings_binding() {
    local key value extra tab
    ow_settings_private "$1" || return 1
    [ "$(wc -c < "$1")" -le 2048 ] && [ "$(wc -l < "$1")" -eq 11 ] || return 1
    awk -F '\t' '
        BEGIN {split("format serial family model source_operation source_release source_contract_sha256 source_slot target_slot image_sha256 job_id",keys," ")}
        NF!=2 || $1!=keys[NR] {bad=1}
        END {exit bad || NR!=11}
    ' "$1" || return 1
    tab=$(printf '\t')
    while IFS="$tab" read -r key value extra; do
        case "$key" in
            format) [ "$value" = 2 ] || return 1 ;;
            serial) OW_SERIAL=$value ;;
            family) OW_FAMILY=$value ;;
            model) OW_MODEL=$value ;;
            source_operation) OW_OPERATION=$value ;;
            source_release) OW_RELEASE=$value ;;
            source_contract_sha256) OW_CONTRACT=$value ;;
            source_slot) OW_SOURCE=$value ;;
            target_slot) OW_TARGET=$value ;;
            image_sha256) OW_IMAGE=$value ;;
            job_id) OW_JOB=$value ;;
            *) return 1 ;;
        esac
    done < "$1"
    case "$OW_SERIAL" in ''|*[!0-9a-f]*) return 1 ;; esac
    [ "${#OW_SERIAL}" = 12 ] || return 1
    case "$OW_FAMILY" in sage|jaguar|cheetah|thor) ;; *) return 1 ;; esac
    case "$OW_MODEL" in ''|*[!A-Za-z0-9-]*) return 1 ;; esac
    case "$OW_OPERATION" in production-oem-migration|production-stock-openwrt-migration) ;; *) return 1 ;; esac
    case "$OW_RELEASE" in ''|*[!A-Za-z0-9._~-]*) return 1 ;; esac
    [ "${#OW_RELEASE}" -le 64 ] || return 1
    case "$OW_SOURCE:$OW_TARGET" in 0:1|1:0) ;; *) return 1 ;; esac
    for value in "$OW_CONTRACT" "$OW_IMAGE" "$OW_JOB"; do
        case "$value" in ''|*[!0-9a-f]*) return 1 ;; esac
        [ "${#value}" = 64 ] || return 1
    done
}
ow_settings_tree() {
    local tree=$1 path name count=0
    [ -d "$tree" ] && [ ! -L "$tree" ] &&
    [ "$(ow_settings_metadata "$tree" | awk -F: '{print $1 ":" $2}')" = "${OW_SETTINGS_OWNER:-0}:700" ] &&
    [ "$(readlink -f "$tree")" = "$tree" ] || return 1
    for path in "$tree"/* "$tree"/.[!.]* "$tree"/..?*; do
        [ -e "$path" ] || [ -L "$path" ] || continue
        name=${path##*/}
        case "$name" in binding.tsv|files.sha256|est.json|gateway.json|est-bootstrap.conf|insta.pem|server-ca.pem) ;; *) return 1 ;; esac
        ow_settings_private "$path" || return 1
        count=$((count+1))
    done
    for name in binding.tsv files.sha256 est.json gateway.json est-bootstrap.conf; do
        ow_settings_private "$tree/$name" || return 1
    done
    ow_settings_binding "$tree/binding.tsv" || return 1
    awk '
        NF!=2 || length($1)!=64 || $1~/[^0-9a-f]/ || seen[$2]++ {bad=1}
        $2!~/^(binding.tsv|est.json|gateway.json|est-bootstrap.conf|insta.pem|server-ca.pem)$/ {bad=1}
        END {exit bad}
    ' "$tree/files.sha256" || return 1
    [ "$(wc -l < "$tree/files.sha256")" -eq "$((count-1))" ] || return 1
    (cd "$tree" && sha256sum -c files.sha256 >/dev/null 2>&1) || return 1
    # Validate only the fixed native credential envelope here, never print it.
    # Native CA-owned firstboot validation owns JSON/trust semantics.
    [ "$(wc -c < "$tree/est-bootstrap.conf")" -eq "$(( ${#OW_SERIAL} + 75 ))" ] || return 1
    awk -v serial="$OW_SERIAL" '
        NR==1 && length($0)==length(serial)+74 &&
        substr($0,1,length(serial)+9)=="user = \"" serial ":" &&
        substr($0,length($0),1)=="\"" {
            key=substr($0,length(serial)+10,64)
            if(key !~ /[^A-Za-z0-9_-]/)good=1
        }
        END {exit !(NR==1 && good)}
    ' "$tree/est-bootstrap.conf" || return 1
}
ow_settings_context() {
    [ "${OW_STAGE_ADMISSION:-}" = qualified ] || return 1
    [ "$OW_SERIAL" = "${OW_EXPECT_SERIAL:-}" ] &&
    [ "$OW_FAMILY" = "${OW_EXPECT_FAMILY:-}" ] &&
    [ "$OW_MODEL" = "${OW_EXPECT_MODEL:-}" ] &&
    [ "$OW_OPERATION" = "${OW_EXPECT_OPERATION:-}" ] &&
    [ "$OW_RELEASE" = "${OW_EXPECT_RELEASE:-}" ] &&
    [ "$OW_CONTRACT" = "${OW_EXPECT_CONTRACT:-}" ] &&
    [ "$OW_SOURCE" = "${OW_EXPECT_SOURCE:-}" ] &&
    [ "$OW_TARGET" = "${OW_EXPECT_TARGET:-}" ] &&
    [ "$OW_JOB" = "${OW_EXPECT_JOB:-}" ] &&
    [ "$OW_IMAGE" = "$(ow_settings_hash "$1")" ]
}
ow_settings_stage_overlay() {
    local input=$1 image=$2 mnt=$3 sys=${OW_SETTINGS_SYS:-/sys/class/ubi} volume dest pending path
    # All admission/input/mount checks precede even directory creation.
    ow_settings_tree "$input" && ow_settings_context "$image" || return 1
    volume=${OW_EXPECT_TARGET_VOLUME:-}
    case "$volume" in ubi[0-9]_[0-9]*) ;; *) return 1 ;; esac
    [ "$(cat "$sys/${volume%_*}/mtd_num")" = "${OW_EXPECT_TARGET_MTD:-}" ] || return 1
    case "$OW_FAMILY:$(cat "$sys/$volume/name")" in
        sage:rootfs_data"$OW_TARGET"|jaguar:rootfs_data|cheetah:rootfs_data|thor:rootfs_data) ;;
        *) return 1 ;;
    esac
    [ -d "$mnt" ] && [ ! -L "$mnt" ] && [ "$(readlink -f "$mnt")" = "$mnt" ] || return 1
    awk -v mnt="$mnt" -v dev="${OW_SETTINGS_DEV:-/dev}/$volume" '
        $2==mnt {n++;if($1==dev && $3=="ubifs" && $4~/(^|,)rw(,|$)/)good=1}
        index($2,mnt "/")==1 {bad=1}
        END {exit !(n==1 && good && !bad)}
    ' "${OW_SETTINGS_MOUNTS:-/proc/mounts}" || return 1
    umask 077
    for path in "$mnt/upper" "$mnt/upper/root"; do
        [ ! -L "$path" ] && { [ -d "$path" ] || mkdir "$path"; } || return 1
    done
    dest=$mnt/upper/root/.cambium-installer-settings
    pending=$dest.pending
    [ ! -e "$pending" ] && [ ! -L "$pending" ] || return 1
    if [ -e "$dest" ] || [ -L "$dest" ]; then
        # Same-job resume is read-only. Never format the candidate identity
        # store or erase a different authorization/issuer-bound identity.
        ow_settings_tree "$dest" && ow_settings_context "$image" &&
        [ "$(ow_settings_hash "$dest/files.sha256")" = "$(ow_settings_hash "$input/files.sha256")" ] || return 1
        printf 'Protected installer settings already staged.\n'
        return 0
    fi
    mkdir -m 700 "$pending" || return 1
    cp "$input"/* "$pending/" || return 1
    chmod 600 "$pending"/* || return 1
    ow_settings_tree "$pending" && ow_settings_context "$image" || return 1
    sync || return 1
    mv "$pending" "$dest" || return 1
    sync || return 1
    ow_settings_tree "$dest" && ow_settings_context "$image" || return 1
    [ "$(ow_settings_hash "$dest/files.sha256")" = "$(ow_settings_hash "$input/files.sha256")" ] || return 1
    # The caller must still unmount/verify the bank, append provenance to its
    # checked pending environment transaction, and arm only after success.
    printf 'Protected installer settings staged.\n'
}
