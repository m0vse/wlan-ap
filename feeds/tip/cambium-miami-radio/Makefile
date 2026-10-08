include $(TOPDIR)/rules.mk
PKG_NAME:=cambium-miami-radio
PKG_RELEASE:=8
PKG_LICENSE:=GPL-2.0-only
PKG_MAINTAINER:=Phil Taylor <phil@m0vse.uk>
include $(INCLUDE_DIR)/package.mk

define Package/cambium-miami-radio
  SECTION:=utils
  CATEGORY:=Utilities
  TITLE:=Cambium X7-35X own-unit radio provisioning
  DEPENDS:=@TARGET_ipq53xx +ubi-utils +flock +uci +jsonfilter
  PKGARCH:=all
endef

define Package/cambium-miami-radio/description
  Stage Miami split Q6 firmware, regional board/regulatory files and own-unit
  ART calibration before releasing ath12k. Read existing bank-local radio vaults without modifying flash.
  Use native OpenWiFi country and configuration; include no proprietary data.
endef

define Build/Compile
endef

define Package/cambium-miami-radio/install
	$(INSTALL_DIR) $(1)/lib/preinit $(1)/usr/sbin $(1)/usr/libexec $(1)/etc/init.d $(1)/etc/uci-defaults $(1)/etc/ucentral
	$(INSTALL_DATA) ./files/platform $(1)/etc/ucentral/platform
	$(INSTALL_DATA) ./files/compatible $(1)/etc/ucentral/compatible
	$(INSTALL_BIN) ./files/miami-radio-ready $(1)/usr/libexec/
	$(INSTALL_BIN) ./files/01-miami-ram-bootstrap $(1)/etc/uci-defaults/
	$(INSTALL_DATA) ./files/05_miami_radio_hold $(1)/lib/preinit/
	$(INSTALL_DATA) ./files/81_miami_radio_provision $(1)/lib/preinit/
	$(INSTALL_BIN) ./files/miami-board-data $(1)/usr/sbin/
	$(INSTALL_BIN) ./files/miami-wifi-profile $(1)/usr/sbin/
	$(INSTALL_BIN) ./files/miami-wifi-profile.init $(1)/etc/init.d/miami-wifi-profile
	$(INSTALL_BIN) ./files/miami-radio-start $(1)/usr/libexec/
	$(INSTALL_BIN) ./files/miami-radio.init $(1)/etc/init.d/miami-radio
endef
$(eval $(call BuildPackage,cambium-miami-radio))
