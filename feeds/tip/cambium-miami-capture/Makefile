# SPDX-License-Identifier: GPL-2.0-only
include $(TOPDIR)/rules.mk
PKG_NAME:=cambium-miami-capture
PKG_RELEASE:=3
PKG_LICENSE:=GPL-2.0-only
PKG_MAINTAINER:=Phil Taylor <phil@m0vse.uk>
include $(INCLUDE_DIR)/package.mk

define Package/cambium-miami-capture
  SECTION:=utils
  CATEGORY:=Utilities
  TITLE:=Miami off-device kernel and NAND failure capture
  DEPENDS:=@TARGET_ipq53xx +kmod-netconsole +uci +ubox
endef

define Package/cambium-miami-capture/conffiles
/etc/config/miami_capture
endef

define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
	$(CP) ./files/monitor.c $(PKG_BUILD_DIR)/
endef

define Build/Compile
	$(TARGET_CC) $(TARGET_CFLAGS) -Os -Wall -Wextra -Werror -static -o $(PKG_BUILD_DIR)/miami-capture-monitor $(PKG_BUILD_DIR)/monitor.c $(TARGET_LDFLAGS)
endef

define Package/cambium-miami-capture/install
	$(INSTALL_DIR) $(1)/usr/libexec $(1)/etc/init.d $(1)/etc/config
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/miami-capture-monitor $(1)/usr/libexec/
	$(INSTALL_BIN) ./files/miami-netconsole-setup $(1)/usr/libexec/
	$(INSTALL_BIN) ./files/miami-capture-launch $(1)/usr/libexec/
	$(INSTALL_BIN) ./files/miami-capture.init $(1)/etc/init.d/miami-capture
	$(INSTALL_CONF) ./files/miami_capture $(1)/etc/config/miami_capture
endef
$(eval $(call BuildPackage,cambium-miami-capture))
