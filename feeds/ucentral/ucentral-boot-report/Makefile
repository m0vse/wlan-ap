include $(TOPDIR)/rules.mk

PKG_NAME:=ucentral-boot-report
PKG_RELEASE:=3

PKG_MAINTAINER:=Phil Taylor <phil@m0vse.uk>
PKG_LICENSE:=BSD-3-Clause

include $(INCLUDE_DIR)/package.mk

define Package/ucentral-boot-report
  SECTION:=ucentral
  CATEGORY:=uCentral
  TITLE:=Bounded persistent OpenWiFi reboot and crash-evidence reporting
  DEPENDS:=+ucode +ucode-mod-fs +ucode-mod-ubus +ucentral-client +coreutils-timeout +ucentral-radio-crash
  PKGARCH:=all
endef

define Build/Compile

endef

define Package/ucentral-boot-report/install
	$(INSTALL_DIR) $(1)/usr/libexec $(1)/usr/share/ucentral $(1)/etc/init.d $(1)/etc/profile.d
	$(INSTALL_BIN) ./files/usr/libexec/ucentral-boot-report $(1)/usr/libexec/
	$(INSTALL_BIN) ./files/etc/init.d/ucentral-boot-report $(1)/etc/init.d/
	$(INSTALL_DATA) ./files/etc/profile.d/ucentral-reboot-history.sh $(1)/etc/profile.d/
	$(INSTALL_DATA) ./files/usr/share/ucentral/boot_reporting.uc $(1)/usr/share/ucentral/
	$(INSTALL_DIR) $(1)/lib/upgrade/keep.d
	$(INSTALL_DATA) ./files/lib/upgrade/keep.d/ucentral-boot-report $(1)/lib/upgrade/keep.d/
endef

$(eval $(call BuildPackage,ucentral-boot-report))
