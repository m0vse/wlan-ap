#!/bin/sh
set -eu
umask 077
file=/lib/functions/cambium-ab.sh
work=$(mktemp -d /tmp/miami-mtd-repair.XXXXXX)
trap 'rm -rf "$work"' EXIT
{ sed -n '/^ab_mtd_index()/,/^}/p' "$file"; sed -n '/^ab_mtd_geometry()/,/^}/p' "$file"; } > "$work/old"
[ "$(sha256sum "$work/old" | cut -d ' ' -f1)" = "ccd52f989adcbb57c5a19a5ef1c0b62bebd6970dffb7ef5af1c8243a03f215c6" ] || { echo 'Unexpected lookup implementation; no changes made'; exit 1; }
cat > "$work/defs" <<'MIAMI_DEFS'
# UBI-exported MTD views repeat names but are not physical flash partitions.
ab_mtd_index() {
	awk -v wanted="\"$1\"" -v sys="${AB_MTD_SYS:-/sys/class/mtd}" '
	$4 == wanted {
		idx=$1; sub(/^mtd/, "", idx); sub(/:$/, "", idx)
		path=sys "/mtd" idx "/type"
		kind=""; getline kind < path; close(path)
		if (kind != "ubi") print idx
	}' "${AB_PROC_MTD:-/proc/mtd}"
}
ab_mtd_geometry() {
	awk -v wanted="\"$1\"" -v sys="${AB_MTD_SYS:-/sys/class/mtd}" '
	$4 == wanted {
		idx=$1; sub(/^mtd/, "", idx); sub(/:$/, "", idx)
		path=sys "/mtd" idx "/type"
		kind=""; getline kind < path; close(path)
		if (kind != "ubi") print $2, $3
	}' "${AB_PROC_MTD:-/proc/mtd}"
}
MIAMI_DEFS
awk 'FNR==NR {defs=defs $0 "\n";next}
/^ab_mtd_(index|geometry)\(\) \{/ {if(!printed){printf "%s",defs;printed=1};skip=1;next}
skip && /^}$/ {skip=0;next}
skip {next}
{print}' "$work/defs" "$file" > "$work/new"
sh -n "$work/new"
cp "$file" "$work/backup"
cp "$work/new" "$file.miami-new"
chmod 0644 "$file.miami-new"
mv "$file.miami-new" "$file"
echo "Physical partition lookup repaired; backup: $work/backup"
# Keep backup after successful repair.
trap - EXIT
