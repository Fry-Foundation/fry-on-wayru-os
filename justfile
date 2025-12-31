# Fry IoT Build System using just
# https://github.com/casey/just
# Build Debian 13 (Trixie) based IoT Linux for routers and embedded devices

set shell := ["bash", "-c"]

# Default variables
tools_dir := "tools"
output_dir := "output"
work_dir := "work"
cache_dir := "cache"

# Show available recipes
default:
    @just --list

# ============================================================
# SETUP RECIPES
# ============================================================

# Set up Python environment and install dependencies
setup:
    @echo "Setting up Python environment with uv..."
    uv sync
    @echo "Creating directory structure..."
    mkdir -p {{output_dir}} {{work_dir}} {{cache_dir}}

# Install host system dependencies (requires root)
install-deps:
    @echo "Installing build dependencies..."
    @echo "This requires root privileges."
    sudo apt-get update
    sudo apt-get install -y \
        debootstrap \
        mmdebstrap \
        qemu-user-static \
        binfmt-support \
        dosfstools \
        parted \
        fdisk \
        e2fsprogs \
        xz-utils \
        zstd \
        squashfs-tools \
        genimage \
        u-boot-tools \
        device-tree-compiler \
        kpartx \
        systemd-container

# ============================================================
# BUILD RECIPES
# ============================================================

# Build a complete Fry IoT image for the selected profile
build:
    @echo "Building Fry IoT image..."
    @if [ -z "$${PROFILE:-}" ]; then \
        echo "Error: PROFILE environment variable not set"; \
        echo "Usage: PROFILE=<profile-name> just build"; \
        echo "Available profiles:"; \
        ls -1 profiles/; \
        exit 1; \
    fi
    uv run python {{tools_dir}}/build-image.py

# Build rootfs only (no bootable image)
build-rootfs:
    @echo "Building Fry IoT rootfs..."
    uv run python {{tools_dir}}/build-rootfs.py

# Build for x86_64 (generic PC/VM)
build-x86:
    PROFILE=x86-generic just build

# Build for ARM64 (generic ARM devices)
build-arm64:
    PROFILE=arm64-generic just build

# Build for all profiles
build-all:
    @echo "Building all profiles..."
    @for profile in profiles/*/; do \
        profile_name=$$(basename "$$profile"); \
        echo "Building profile: $$profile_name"; \
        PROFILE=$$profile_name just build || true; \
    done

# ============================================================
# CONFIGURATION RECIPES
# ============================================================

# Configure the build for a specific profile
configure:
    @echo "Configuring build..."
    uv run python {{tools_dir}}/configure.py

# Generate network configuration for the profile
configure-network:
    @echo "Generating network configuration..."
    uv run python {{tools_dir}}/configure-network.py

# Add Fry Networks services to the image
configure-fry:
    @echo "Configuring Fry Networks services..."
    uv run python {{tools_dir}}/configure-fry.py

# ============================================================
# IMAGE MANAGEMENT
# ============================================================

# Convert rootfs to various image formats
convert-image format="img":
    @echo "Converting to {{format}} format..."
    uv run python {{tools_dir}}/convert-image.py --format {{format}}

# Create a compressed archive of the image
compress:
    @echo "Compressing image..."
    uv run python {{tools_dir}}/compress-image.py

# Upload build artifacts to cloud storage
upload-build:
    @echo "Uploading build artifacts..."
    uv run python {{tools_dir}}/upload-build.py

# ============================================================
# TESTING AND VALIDATION
# ============================================================

# Test the image in QEMU
test-qemu:
    @echo "Testing image in QEMU..."
    @if [ ! -f "{{output_dir}}/fry-iot.img" ]; then \
        echo "Error: No image found. Run 'just build' first."; \
        exit 1; \
    fi
    qemu-system-x86_64 \
        -enable-kvm \
        -m 2048 \
        -smp 2 \
        -drive file={{output_dir}}/fry-iot.img,format=raw \
        -netdev user,id=net0,hostfwd=tcp::2222-:22 \
        -device virtio-net-pci,netdev=net0 \
        -nographic

# Test ARM64 image in QEMU
test-qemu-arm64:
    @echo "Testing ARM64 image in QEMU..."
    qemu-system-aarch64 \
        -M virt \
        -cpu cortex-a72 \
        -m 2048 \
        -smp 2 \
        -drive file={{output_dir}}/fry-iot.img,format=raw \
        -netdev user,id=net0,hostfwd=tcp::2222-:22 \
        -device virtio-net-pci,netdev=net0 \
        -nographic

# Validate the generated image
validate:
    @echo "Validating image..."
    uv run python {{tools_dir}}/validate-image.py

# ============================================================
# CLEANING AND RESET
# ============================================================

# Clean build artifacts
clean:
    @echo "Cleaning build artifacts..."
    rm -rf {{work_dir}}/*
    @echo "Build artifacts cleaned."

# Clean output images
clean-output:
    @echo "Cleaning output images..."
    rm -rf {{output_dir}}/*
    @echo "Output cleaned."

# Clean package cache
clean-cache:
    @echo "Cleaning package cache..."
    rm -rf {{cache_dir}}/*
    @echo "Cache cleaned."

# Full reset - remove all generated files
reset: clean clean-output clean-cache
    @echo "Full reset complete."

# ============================================================
# DEVELOPMENT RECIPES
# ============================================================

# Enter a shell inside the rootfs (using systemd-nspawn)
shell-rootfs:
    @echo "Entering rootfs shell..."
    @if [ ! -d "{{work_dir}}/rootfs" ]; then \
        echo "Error: No rootfs found. Run 'just build-rootfs' first."; \
        exit 1; \
    fi
    sudo systemd-nspawn -D {{work_dir}}/rootfs

# Mount the image for inspection
mount-image:
    @echo "Mounting image..."
    sudo mkdir -p /mnt/fry-iot
    sudo mount -o loop,offset=$$((512*2048)) {{output_dir}}/fry-iot.img /mnt/fry-iot
    @echo "Image mounted at /mnt/fry-iot"

# Unmount the image
unmount-image:
    @echo "Unmounting image..."
    sudo umount /mnt/fry-iot
    @echo "Image unmounted."

# ============================================================
# UTILITY RECIPES
# ============================================================

# Check Python environment and dependencies
check:
    @echo "Checking Python environment..."
    uv run python --version
    @echo "Checking dependencies..."
    uv pip list
    @echo ""
    @echo "Checking build tools..."
    @which debootstrap || echo "debootstrap: NOT FOUND (run 'just install-deps')"
    @which mmdebstrap || echo "mmdebstrap: NOT FOUND (run 'just install-deps')"
    @which qemu-system-x86_64 || echo "qemu-system-x86_64: NOT FOUND"

# Run linting and formatting
lint:
    uv run python -m py_compile {{tools_dir}}/*.py

# Show build information
info:
    @echo "Fry IoT Build System"
    @echo "===================="
    @echo "Based on: Debian 13 (Trixie)"
    @echo ""
    @echo "Directories:"
    @echo "  Output: {{output_dir}}"
    @echo "  Work:   {{work_dir}}"
    @echo "  Cache:  {{cache_dir}}"
    @echo "  Tools:  {{tools_dir}}"
    @echo ""
    @echo "Python environment:"
    @uv run python --version || echo "Python not available"
    @echo ""
    @echo "Available profiles:"
    @ls -1 profiles/ 2>/dev/null || echo "No profiles directory found"

# Show disk usage
disk-usage:
    @echo "Disk usage:"
    @du -sh {{output_dir}} {{work_dir}} {{cache_dir}} 2>/dev/null || true

# ============================================================
# COMPLETE WORKFLOWS
# ============================================================

# Full build workflow: setup -> configure -> build -> compress
full-build: setup configure build compress
    @echo "Full build complete!"

# Development build: quick rebuild with existing cache
dev-build: configure build
    @echo "Development build complete!"

# Release build: full clean build with upload
release-build: reset setup configure build compress upload-build
    @echo "Release build complete and uploaded!"
