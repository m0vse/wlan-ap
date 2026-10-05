include $(TOPDIR)/rules.mk

PKG_NAME:=ucentral-client
PKG_RELEASE:=14

PKG_SOURCE_URL=https://github.com/m0vse/wlan-ucentral-client.git
PKG_MIRROR_HASH:=537453c59f515013c2eb5fb6b106ab086700f5ea3b85d051aa79e25b76128150
PKG_SOURCE_PROTO:=git
PKG_SOURCE_SUBMODULES:=skip
PKG_SOURCE_DATE:=2026-10-04
PKG_SOURCE_VERSION:=176cab2f4e977929ce3827badeedd438767dbb88

PKG_LICENSE:=BSD-3-Clause
PKG_MAINTAINER:=John Crispin <john@phrozen.org>

include $(INCLUDE_DIR)/package.mk
include $(INCLUDE_DIR)/cmake.mk

define Package/ucentral-client
  SECTION:=ucentral
  CATEGORY:=uCentral
  TITLE:=OpenWrt uCentral websocket client
  DEPENDS:=+ucode +ucode-mod-fs +ucode-mod-ubus +ucode-mod-uci +ucode-mod-math +ucode-mod-resolv +ucode-mod-uloop \
	   +libubox +libwebsockets-openssl +libblobmsg-json +libubus
endef

define Package/ucentral-client/install
	$(INSTALL_DIR) $(1)/usr/sbin/
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/ucentral $(1)/usr/sbin/
	$(CP) ./files/* $(1)
	# Recursive copies preserve checkout directory modes; normalize last.
	$(INSTALL_DIR) $(1)/etc/ucentral
endef

$(eval $(call BuildPackage,ucentral-client))
