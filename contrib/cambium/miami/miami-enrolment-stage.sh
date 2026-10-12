# Source this after the common settings library and OEM bank validation.
# Called only after both installed payloads have been independently read back.
miami_enrolment_stage() (
 set +x
 umask 077
 key=$1
 case "$key" in ''|*[!A-Za-z0-9_-]*) fail 'invalid enrolment key';; esac
 [ "${#key}" = 64 ] || fail 'invalid enrolment key'
 [ "${ENROLMENT_READY:-0}" = 1 ] || fail 'this image has no reviewed native enrolment integration'
 command -v get_esn >/dev/null || fail 'OEM serial reader missing'
 serial=$(get_esn) || fail 'OEM serial reader failed'
 serial=$(printf '%s' "$serial" | tr 'A-F' 'a-f')
 case "$serial" in ''|*[!0-9a-f]*|000000000000|ffffffffffff) fail 'invalid OEM serial';; esac
 [ "${#serial}" = 12 ] || fail 'invalid OEM serial'
 release=$(sed -n 's/^VERSION=//p' "$R/etc/version")
 case "$release" in ''|*[!A-Za-z0-9._~-]*) fail 'invalid OEM release';; esac
 [ "${#release}" -le 64 ] || fail 'invalid OEM release'
 case "$SLOT" in 0) descriptor=$PAIR0; descriptor_sha=$PAIR0_SHA ;; 1) descriptor=$PAIR1; descriptor_sha=$PAIR1_SHA ;; *) fail 'invalid target slot';; esac
 fetch "$descriptor" "$descriptor_sha" "$([ "$SLOT" = 0 ] && echo "$PAIR0_SIZE" || echo "$PAIR1_SIZE")"
 work=$(mktemp -d "$R/tmp/miami-enrolment.XXXXXX") || exit 1
 chmod 700 "$work"
 mounted=0
 cleanup_enrolment() {
  if [ "$mounted" = 1 ]; then umount "$work/overlay" || return 1; fi
  rm -rf "$work"
 }
 trap cleanup_enrolment EXIT
 data=$(volume rootfs_data) || fail 'missing target overlay'
 [ "${data##*_}" = 2 ] || fail 'wrong target overlay ID'
 mkdir "$work/overlay"
 mount -t ubifs "$R/dev/$data" "$work/overlay" || fail 'cannot mount target overlay'
 mounted=1
 existing=$work/overlay/upper/root/.cambium-installer-settings
 [ ! -e "$existing.pending" ] && [ ! -L "$existing.pending" ] || fail 'interrupted settings publication requires inspection'
 if [ -e "$existing" ] || [ -L "$existing" ]; then
  ow_settings_tree "$existing" || fail 'existing settings are unsafe'
  job=$OW_JOB
 else
  job=$(od -An -tx1 -N32 /dev/urandom | tr -d ' \n')
 fi
 case "$job" in ''|*[!0-9a-f]*) fail 'transaction random source failed';; esac
 [ "${#job}" = 64 ] || fail 'transaction random source failed'
 printf 'format\t2\nserial\t%s\nfamily\tmiami\nmodel\tX7-35X\nsource_operation\tproduction-oem-migration\nsource_release\t%s\nsource_contract_sha256\t%s\nsource_slot\t%s\ntarget_slot\t%s\nimage_sha256\t%s\njob_id\t%s\n' \
  "$serial" "$release" "$SOURCE_CONTRACT_SHA" "$img" "$SLOT" "$descriptor_sha" "$job" > "$work/binding.tsv"
 controller=${CAMBIUM_ENROLMENT_SERVER:-}
 case "$controller" in ''|*[!A-Za-z0-9.-]*|.*|*.) fail 'Set CAMBIUM_ENROLMENT_SERVER to the controller hostname';; esac
 printf '{"server":"%s:18443","tls_ca":"/etc/ssl/certs/ca-certificates.crt"}\n' "$controller" > "$work/est.json"
 printf '{"server":"%s","port":15002,"cert":"/etc/ucentral/operational.pem","ca":"/etc/ssl/certs/ca-certificates.crt","hostname_validate":1}\n' "$controller" > "$work/gateway.json"
 chmod 600 "$work"/*.json "$work/binding.tsv"
 ow_settings_prepare "$work/binding.tsv" "$work/est.json" "$work/gateway.json" "$key" "$work/seed" || fail 'native seed preparation failed'
 key=
 # The exact model, source, inactive bank and installed pair checks have
 # already run in the enclosing installer; this is not fleet qualification.
 OW_STAGE_ADMISSION=qualified
 OW_EXPECT_SERIAL=$serial OW_EXPECT_FAMILY=miami OW_EXPECT_MODEL=X7-35X
 OW_EXPECT_OPERATION=production-oem-migration OW_EXPECT_RELEASE=$release
 OW_EXPECT_CONTRACT=$SOURCE_CONTRACT_SHA OW_EXPECT_SOURCE=$img OW_EXPECT_TARGET=$SLOT
 OW_EXPECT_JOB=$job OW_EXPECT_TARGET_VOLUME=$data OW_EXPECT_TARGET_MTD=$T
 for field in image job target; do
  value=$(get "miami_installer_$field" || true)
  case "$field" in image) expected=$descriptor_sha ;; job) expected=$job ;; target) expected=$SLOT ;; esac
  [ -z "$value" ] || [ "$value" = "$expected" ] || fail 'different installer transaction already pending'
 done
 ow_settings_stage_overlay "$work/seed" "$R/tmp/$descriptor" "$work/overlay" || fail 'native seed staging failed'
 umount "$work/overlay" || fail 'target overlay did not unmount'
 mounted=0
 # Commit only after durable staging and unmount; arm is still the last step.
 put miami_installer_image "$descriptor_sha"
 put miami_installer_job "$job"
 put miami_installer_target "$SLOT"
)
