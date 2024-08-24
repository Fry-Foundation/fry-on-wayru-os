#!/bin/bash

# Load config
repo=$(tomlq '.openwrt.repo' base-config.toml | tr -d '"')
tag=$(tomlq '.openwrt.tag' base-config.toml | tr -d '"')

# Clone and checkout tag
git clone $repo openwrt
cd openwrt
git checkout $tag
