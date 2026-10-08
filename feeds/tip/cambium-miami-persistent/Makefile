include $(TOPDIR)/rules.mk
PKG_NAME:=cambium-miami-persistent
PKG_RELEASE:=6
PKG_LICENSE:=GPL-2.0-only
PKG_MAINTAINER:=Phil Taylor <phil@m0vse.uk>
include $(INCLUDE_DIR)/package.mk

define Package/cambium-miami-persistent
  SECTION:=utils
  CATEGORY:=Utilities
  TITLE:=Cambium X7-35X OEM-preserving persistent storage pilot
  DEPENDS:=@TARGET_ipq53xx +cambium-miami-radio +cambium-ab
  PKGARCH:=all
endef

define Build/Compile
endef

define Package/cambium-miami-persistent/install
	$(INSTALL_DIR) $(1)/lib/functions $(1)/usr/libexec
	$(INSTALL_DATA) ./files/cambium-ab-miami.sh $(1)/lib/functions/
	$(INSTALL_BIN) ./files/miami-country-defaults $(1)/usr/libexec/
	$(INSTALL_BIN) ./files/ucentral-deferred-miami $(1)/usr/libexec/
endef
$(eval $(call BuildPackage,cambium-miami-persistent))
