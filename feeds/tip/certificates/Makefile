include $(TOPDIR)/rules.mk

PKG_NAME:=certificates
PKG_RELEASE:=14

PKG_LICENSE:=BSD-3-Clause
PKG_MAINTAINER:=John Crispin <john@phrozen.org>

include $(INCLUDE_DIR)/package.mk

define Package/certificates
  SECTION:=ucentral
  CATEGORY:=uCentral
  TITLE:=TIP DigiCer certificate store
  DEPENDS:=+ucode +ucode-mod-fs +ucode-mod-ubus +openssl-util +flock +curl
endef

define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
endef

define Build/Compile/Default

endef
Build/Compile = $(Build/Compile/Default)

define Package/certificates/install
	$(CP) ./files/* $(1)
	# Git tracks executability, not exact modes under a group-write umask.
	$(INSTALL_BIN) ./files/usr/libexec/ucentral-secure-runtime $(1)/usr/libexec/ucentral-secure-runtime
	$(INSTALL_BIN) ./files/etc/init.d/early_boot $(1)/etc/init.d/early_boot
	# Recursive copies preserve checkout directory modes; normalize last.
	$(INSTALL_DIR) $(1)/etc/ucentral
endef

$(eval $(call BuildPackage,certificates))
