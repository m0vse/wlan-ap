include $(TOPDIR)/rules.mk

PKG_NAME:=ucentral-state
PKG_RELEASE:=6

PKG_MAINTAINER:=John Crispin <john@phrozen.org>
PKG_LICENSE:=BSD-3-Clause

include $(INCLUDE_DIR)/package.mk

define Package/ucentral-state
  SECTION:=ucentral
  CATEGORY:=uCentral
  TITLE:=uCentral state monitoring daemon
  DEPENDS:=+ucentral-schema +ucode +ucode-mod-fs +ucode-mod-ubus +ucode-mod-uci +ucode-mod-log +coreutils-timeout
endef

define Build/Prepare
	$(INSTALL_DIR) $(PKG_BUILD_DIR)
	$(CP) ./src $(PKG_BUILD_DIR)/
endef

define Build/Compile
	$(TARGET_CC) $(TARGET_CFLAGS) $(TARGET_LDFLAGS) -Wall -Wextra -o $(PKG_BUILD_DIR)/storage-probe $(PKG_BUILD_DIR)/src/storage-probe.c
endef

define Package/ucentral-state/install
	$(INSTALL_DIR) $(1)/usr/sbin $(1)/etc/init.d $(1)/etc/config $(1)/usr/libexec $(1)/usr/share/ucentral $(1)/etc/ucentral
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/storage-probe $(1)/usr/libexec/ucentral-storage-probe
	$(INSTALL_BIN) ./files/ucentral-faults $(1)/usr/libexec/
	$(INSTALL_BIN) ./files/ucentral-dfs-led $(1)/usr/libexec/
	$(INSTALL_DATA) ./files/dfs_led.uc $(1)/usr/share/ucentral/
	$(INSTALL_DATA) ./files/faults.uc $(1)/usr/share/ucentral/
	$(INSTALL_DATA) ./files/storage-canary.json $(1)/etc/ucentral/
	$(INSTALL_BIN) ./files/ucentral-state $(1)/usr/sbin/
	$(INSTALL_BIN) ./files/ucentral-pstore $(1)/usr/sbin/
	$(INSTALL_BIN) ./files/ucentral-state.init $(1)/etc/init.d/ucentral-state
	$(INSTALL_BIN) ./files/ucentral-state.config $(1)/etc/config/state
	$(INSTALL_BIN) ./files/log-helper.config $(1)/etc/config/log-helper
endef

$(eval $(call BuildPackage,ucentral-state))
