include $(TOPDIR)/rules.mk
PKG_NAME:=ucentral-netconsole
PKG_RELEASE:=1
PKG_MAINTAINER:=Phil Taylor <phil@m0vse.uk>
PKG_LICENSE:=BSD-3-Clause
include $(INCLUDE_DIR)/package.mk
define Package/ucentral-netconsole
  SECTION:=ucentral
  CATEGORY:=uCentral
  TITLE:=Opt-in kernel network crash capture
  DEPENDS:=+kmod-netconsole +kmod-fs-configfs +ucode +ucode-mod-fs +ucode-mod-uci
  PKGARCH:=all
endef
define Package/ucentral-netconsole/conffiles
/etc/config/netconsole
endef
define Build/Compile
endef
define Package/ucentral-netconsole/install
	$(INSTALL_DIR) $(1)/usr/libexec $(1)/etc/init.d $(1)/etc/config
	$(INSTALL_BIN) ./files/usr/libexec/ucentral-netconsole $(1)/usr/libexec/
	$(INSTALL_BIN) ./files/etc/init.d/ucentral-netconsole $(1)/etc/init.d/
	$(INSTALL_CONF) ./files/etc/config/netconsole $(1)/etc/config/
endef
$(eval $(call BuildPackage,ucentral-netconsole))
