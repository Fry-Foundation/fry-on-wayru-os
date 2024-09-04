OPENWRT_DIR := openwrt
TOOLS_DIR := tools

.PHONY: clone-openwrt configure update-feeds uninstall-feeds defconfig build upload-build clean-openwrt reset build-debug

clone-openwrt:
	$(TOOLS_DIR)/clone-openwrt.sh

configure:
	python $(TOOLS_DIR)/configure.py

update-feeds:
	cd $(OPENWRT_DIR) && ./scripts/feeds update -a
	cd $(OPENWRT_DIR) && ./scripts/feeds install -a

uninstall-feeds:
	cd $(OPENWRT_DIR) && ./scripts/feeds uninstall -a

defconfig:
	cd $(OPENWRT_DIR) && $(MAKE) defconfig

build:
	cd $(OPENWRT_DIR) && $(MAKE) -j$(nproc) download clean world

build-debug:
	cd $(OPENWRT_DIR) && $(MAKE) -j1 V=s

upload-build:
	python $(TOOLS_DIR)/upload-build.py

clean-openwrt:
	cd $(OPENWRT_DIR) && $(MAKE) clean

reset:
	rm -rf $(OPENWRT_DIR) || echo "OpenWRT directory not found, skipping..."
