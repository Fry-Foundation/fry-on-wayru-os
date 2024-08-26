.PHONY: clone-openwrt configure update-feeds defconfig build upload-build clean-openwrt reset

clone-openwrt:
	./tools/clone-openwrt.sh

configure:
	python tools/configure.py

update-feeds:
	cd openwrt && ./scripts/feeds update -a
	cd openwrt && ./scripts/feeds install -a

defconfig:
	cd openwrt && make defconfig

build:
	cd openwrt && make -j$(nproc) download clean world

upload-build:
	python tools/upload-build.py

clean-openwrt:
	cd openwrt && make clean

reset:
	rm -rf openwrt
