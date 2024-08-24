.PHONY: configure-build upload-build

clone-openwrt:
	./tools/clone-openwrt.sh

configure:
	python tools/configure.py

upload-build:
	python tools/upload-build.py

clean-openwrt:
	rm -rf openwrt
