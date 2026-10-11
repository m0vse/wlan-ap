include $(TOPDIR)/rules.mk

PKG_NAME:=cloud_discovery
PKG_RELEASE:=14

PKG_LICENSE:=BSD-3-Clause
PKG_MAINTAINER:=John Crispin <john@phrozen.org>

include $(INCLUDE_DIR)/package.mk

define Package/cloud_discovery
  SECTION:=ucentral
  CATEGORY:=uCentral
  TITLE:=TIP cloud_discovery
  DEPENDS:=+certificates +bind-dig
endef

Build/Compile=

define Package/cloud_discovery/conffiles
/etc/ucentral/discovery-policy.json
endef

define Package/cloud_discovery/install
	$(CP) ./files/* $(1)
	# Normalize only copied package-owned paths, never private runtime stores.
	find ./files -mindepth 1 -type d | while IFS= read -r path; do \
		$(INSTALL_DIR) "$(1)/$$$${path#./files/}" || exit 1; \
	done
	find ./files -type f | while IFS= read -r path; do \
		if [ -x "$$$$path" ]; then \
			$(INSTALL_BIN) "$$$$path" "$(1)/$$$${path#./files/}" || exit 1; \
		else \
			$(INSTALL_DATA) "$$$$path" "$(1)/$$$${path#./files/}" || exit 1; \
		fi; \
	done
	# Git executability does not constrain group-write checkout umasks.
	$(INSTALL_BIN) ./files/usr/bin/est_client $(1)/usr/bin/est_client
	# Recursive copies preserve checkout directory modes; normalize last.
	$(INSTALL_DIR) $(1)/etc/ucentral
	$(INSTALL_DATA) ./files/etc/ucentral/discovery-policy.json $(1)/etc/ucentral/discovery-policy.json
endef

$(eval $(call BuildPackage,cloud_discovery))
