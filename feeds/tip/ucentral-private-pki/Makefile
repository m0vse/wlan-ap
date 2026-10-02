include $(TOPDIR)/rules.mk

PKG_NAME:=ucentral-private-pki
PKG_RELEASE:=2
PKG_LICENSE:=BSD-3-Clause

include $(INCLUDE_DIR)/package.mk

define Package/ucentral-private-pki
  SECTION:=ucentral
  CATEGORY:=uCentral
  TITLE:=Opt-in committed private identity integration (experimental)
  DEPENDS:=+ucode +ucode-mod-fs +openssl-util +uci
endef

Build/Compile=

define Package/ucentral-private-pki/conffiles
/etc/ucentral/private-pki.json
endef

define Package/ucentral-private-pki/install
	$(INSTALL_DIR) $(1)/etc/ucentral $(1)/usr/libexec $(1)/etc/init.d
	$(INSTALL_CONF) ./files/private-pki.json $(1)/etc/ucentral/private-pki.json
	$(INSTALL_BIN) ./files/private-pki $(1)/usr/libexec/ucentral-private-pki
	$(INSTALL_BIN) ./files/materialize $(1)/usr/libexec/ucentral-private-pki-materialize
	$(INSTALL_BIN) ./files/private-pki-scheduler $(1)/usr/libexec/ucentral-private-pki-scheduler
	$(INSTALL_BIN) ./files/private-pki.init $(1)/etc/init.d/ucentral-private-pki
endef

$(eval $(call BuildPackage,ucentral-private-pki))
