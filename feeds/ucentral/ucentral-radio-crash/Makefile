include $(TOPDIR)/rules.mk

PKG_NAME:=ucentral-radio-crash
PKG_RELEASE:=2
PKG_MAINTAINER:=Phil Taylor <phil@m0vse.uk>
PKG_LICENSE:=BSD-3-Clause

include $(INCLUDE_DIR)/package.mk

define Package/ucentral-radio-crash
  SECTION:=ucentral
  CATEGORY:=uCentral
  TITLE:=Optional bounded persistent radio dump retention
  DEPENDS:=+coreutils-timeout +coreutils-stat +flock
endef

define Package/ucentral-radio-crash/conffiles
/etc/config/radio-crash
endef

define Build/Prepare
	$(INSTALL_DIR) $(PKG_BUILD_DIR)
	$(CP) ./src/collector.c $(PKG_BUILD_DIR)/
endef

define Build/Compile
	$(TARGET_CC) $(TARGET_CPPFLAGS) $(TARGET_CFLAGS) $(TARGET_LDFLAGS) -o $(PKG_BUILD_DIR)/ucentral-radio-crash-capture $(PKG_BUILD_DIR)/collector.c
endef

define Package/ucentral-radio-crash/install
	$(INSTALL_DIR) $(1)/usr/libexec $(1)/etc/init.d $(1)/etc/config $(1)/etc/hotplug.d/devcoredump $(1)/lib/upgrade/keep.d
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/ucentral-radio-crash-capture $(1)/usr/libexec/
	$(INSTALL_BIN) ./files/usr/libexec/ucentral-radio-crash-dispatch $(1)/usr/libexec/
	$(INSTALL_BIN) ./files/etc/init.d/ucentral-radio-crash $(1)/etc/init.d/
	$(INSTALL_DATA) ./files/etc/config/radio-crash $(1)/etc/config/
	$(INSTALL_DATA) ./files/etc/hotplug.d/devcoredump/90-radio-crash $(1)/etc/hotplug.d/devcoredump/
	$(INSTALL_DATA) ./files/lib/upgrade/keep.d/ucentral-radio-crash $(1)/lib/upgrade/keep.d/
endef

$(eval $(call BuildPackage,ucentral-radio-crash))
