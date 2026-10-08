include $(TOPDIR)/rules.mk
include $(INCLUDE_DIR)/kernel.mk

PKG_NAME:=qca-nss-ppe-ath-clients
PKG_VERSION:=1.0
PKG_RELEASE:=2

# Use the exact same SDK archive and commit as qca-nss-ppe. Build the
# client separately to avoid a core-PPE / PPE-VP build dependency cycle.
PKG_SOURCE_PROTO:=git
PKG_SOURCE_URL:=https://git.codelinaro.org/clo/qsdk/oss/lklm/nss-ppe
PKG_SOURCE_VERSION:=d53eff24bf257a8bb1b2f68beb3aa06332bfd567
PKG_SOURCE_SUBDIR:=qca-nss-ppe-1.0
PKG_SOURCE:=qca-nss-ppe-1.0.tar.zst
PKG_MIRROR_HASH:=8546d17c60978d56d30f21cd4a21f1d1936be348d0f92119802691688402edc1

# The shared archive retains qca-nss-ppe-1.0 as its top-level directory.
# Extract directly into this package's own build directory.
PKG_UNPACK=zstdcat $(DL_DIR)/$(PKG_SOURCE) | $(HOST_TAR) -C $(PKG_BUILD_DIR) --strip-components=1 -xf -

include $(INCLUDE_DIR)/package.mk

define KernelPackage/qca-nss-ppe-ath-clients
  SECTION:=kernel
  CATEGORY:=Kernel modules
  SUBMENU:=Network Devices
  TITLE:=Qualcomm SDK PPE Wi-Fi virtual-port client
  DEPENDS:=@TARGET_ipq95xx||TARGET_ipq53xx||TARGET_ipq54xx||TARGET_ipq96xx||TARGET_ipq52xx +kmod-qca-nss-ppe +kmod-qca-nss-ppe-vp +kmod-cfg80211
  FILES:=$(PKG_BUILD_DIR)/clients/ath_client/qca-nss-ppe-ath-clients.ko
  AUTOLOAD:=$(call AutoLoad,54,qca-nss-ppe-ath-clients)
endef

define KernelPackage/qca-nss-ppe-ath-clients/description
Register the SDK Wi-Fi netdevice notifier that allocates PPE virtual
ports. Hardware Direct Switch remains subject to each radio's capability
and its boot-time frame-mode configuration.
endef

EXTRA_CFLAGS+= \
	-I$(STAGING_DIR)/usr/include/qca-ssdk \
	-I$(STAGING_DIR)/usr/include/qca-ssdk/fal \
	-I$(STAGING_DIR)/usr/include/qca-ssdk/init \
	-I$(STAGING_DIR)/usr/include/nat46 \
	-I$(STAGING_DIR)/usr/include/qca-nss-ppe \
	-I$(STAGING_DIR)/usr/include/qca-nss-ppe-vp

define Build/Compile
	$(KERNEL_MAKE) \
		M="$(PKG_BUILD_DIR)" \
		EXTRA_CFLAGS="$(EXTRA_CFLAGS)" \
		SoC="$(CONFIG_TARGET_BOARD)" \
		ath_clients=m \
		modules
endef

$(eval $(call KernelPackage,qca-nss-ppe-ath-clients))
