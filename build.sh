#!/bin/bash

set -ex
ROOT_PATH=${PWD}
BUILD_DIR=${ROOT_PATH}/openwrt
TARGET=${1}

if [ -z "$1" ]; then
	echo "Error: please specify TARGET"
	exit 1
fi

if [ ! "$(ls -A $BUILD_DIR)" ]; then
	python3 setup.py --setup || exit 1
    
else
	python3 setup.py --rebase
	echo "### OpenWrt repo already setup"
fi

cd ${BUILD_DIR}
"${ROOT_PATH}/scripts/check-init-backups.sh" "${BUILD_DIR}/package" "${ROOT_PATH}/feeds"
./scripts/gen_config.py ${TARGET} || exit 1
# DISTRIB_TIP is generated from the parent wlan-ap commit and release tag.
# An incremental build otherwise reuses base-files and can ship a stale
# TIP-devel/version string even after the source has been tagged.
make package/base-files/clean
cd -

echo "### Building image ..."
cd $BUILD_DIR
make -j$(nproc) V=s
for rootfs in "${BUILD_DIR}"/build_dir/target-*/root-*; do
	[ ! -d "$rootfs" ] || "${ROOT_PATH}/scripts/check-init-backups.sh" "$rootfs"
done
