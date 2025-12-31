#!/usr/bin/env python3
"""
Fry IoT Image Builder

Builds complete bootable Debian 13 (Trixie) images for IoT devices and routers.
Uses mmdebstrap for rootfs creation and creates bootable disk images.
"""

import os
import sys
import subprocess
import shutil
import json
from pathlib import Path
from typing import Optional

import toml
from tqdm import tqdm

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
BASE_CONFIG_PATH = PROJECT_ROOT / "base-config.toml"
PROFILES_DIR = PROJECT_ROOT / "profiles"
RESOURCES_DIR = PROJECT_ROOT / "resources"
WORK_DIR = PROJECT_ROOT / "work"
OUTPUT_DIR = PROJECT_ROOT / "output"
CACHE_DIR = PROJECT_ROOT / "cache"


def load_config():
    """Load base configuration."""
    with open(BASE_CONFIG_PATH) as f:
        return toml.load(f)


def load_profile_config(profile_name: str):
    """Load profile-specific configuration."""
    profile_path = PROFILES_DIR / profile_name / "profile-config.toml"
    if not profile_path.exists():
        print(f"Error: Profile '{profile_name}' not found at {profile_path}")
        sys.exit(1)
    with open(profile_path) as f:
        return toml.load(f)


def ensure_directories():
    """Create necessary directories."""
    for directory in [WORK_DIR, OUTPUT_DIR, CACHE_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


def get_architecture(profile_config: dict) -> str:
    """Get Debian architecture from profile config."""
    arch_mapping = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "arm64": "arm64",
        "aarch64": "arm64",
        "armhf": "armhf",
        "arm": "armhf",
        "mipsel": "mipsel",
        "mips": "mips",
    }
    arch = profile_config.get("build", {}).get("architecture", "amd64")
    return arch_mapping.get(arch, arch)


def get_kernel_package(arch: str, profile_config: dict) -> str:
    """Get the appropriate kernel package for the architecture."""
    # Check if profile specifies a kernel
    kernel = profile_config.get("build", {}).get("kernel_package")
    if kernel:
        return kernel

    # Default kernels by architecture
    kernel_mapping = {
        "amd64": "linux-image-amd64",
        "arm64": "linux-image-arm64",
        "armhf": "linux-image-armmp",
        "mipsel": "linux-image-mipsel",
    }
    return kernel_mapping.get(arch, "linux-image-generic")


def build_package_list(base_config: dict, profile_config: dict, arch: str) -> list:
    """Build the complete package list for the image."""
    packages = []

    # Core packages from base config
    packages.extend(base_config.get("packages", {}).get("core", []))

    # IoT packages
    packages.extend(base_config.get("packages", {}).get("iot", []))

    # Profile-specific packages
    packages.extend(profile_config.get("packages", {}).get("include", []))

    # Kernel package
    packages.append(get_kernel_package(arch, profile_config))

    # Profile flavor packages
    flavor = profile_config.get("build", {}).get("flavor", "minimal")
    if flavor == "desktop":
        packages.extend(base_config.get("packages", {}).get("desktop", []))
    elif flavor == "server":
        packages.extend(base_config.get("packages", {}).get("server", []))

    # Remove excluded packages
    exclude = profile_config.get("packages", {}).get("exclude", [])
    packages = [p for p in packages if p not in exclude]

    # Remove duplicates while preserving order
    seen = set()
    unique_packages = []
    for p in packages:
        if p not in seen:
            seen.add(p)
            unique_packages.append(p)

    return unique_packages


def create_apt_sources(base_config: dict, rootfs_path: Path):
    """Create APT sources.list for Debian Trixie."""
    suite = base_config.get("debian", {}).get("suite", "trixie")
    mirror = base_config.get("debian", {}).get("mirror", "https://deb.debian.org/debian")
    security_mirror = base_config.get("debian", {}).get("security_mirror", "https://deb.debian.org/debian-security")
    components = base_config.get("debian", {}).get("components", ["main", "contrib", "non-free", "non-free-firmware"])
    components_str = " ".join(components)

    sources_content = f"""# Fry IoT - Debian {suite} sources
deb {mirror} {suite} {components_str}
deb {mirror} {suite}-updates {components_str}
deb {security_mirror} {suite}-security {components_str}
"""

    sources_path = rootfs_path / "etc" / "apt" / "sources.list"
    sources_path.parent.mkdir(parents=True, exist_ok=True)
    sources_path.write_text(sources_content)


def create_fry_apt_sources(rootfs_path: Path):
    """Create Fry Networks APT repository configuration."""
    fry_sources = """# Fry Networks Repository
deb [signed-by=/usr/share/keyrings/fry-archive-keyring.gpg] https://apt.fry.network/debian trixie main
"""
    sources_path = rootfs_path / "etc" / "apt" / "sources.list.d" / "fry.list"
    sources_path.parent.mkdir(parents=True, exist_ok=True)
    sources_path.write_text(fry_sources)


def build_rootfs(base_config: dict, profile_config: dict, profile_name: str) -> Path:
    """Build the Debian rootfs using mmdebstrap."""
    print(f"\n=== Building rootfs for {profile_name} ===")

    arch = get_architecture(profile_config)
    suite = base_config.get("debian", {}).get("suite", "trixie")
    mirror = base_config.get("debian", {}).get("mirror", "https://deb.debian.org/debian")

    rootfs_path = WORK_DIR / "rootfs"

    # Clean previous rootfs
    if rootfs_path.exists():
        print("Cleaning previous rootfs...")
        subprocess.run(["sudo", "rm", "-rf", str(rootfs_path)], check=True)

    rootfs_path.mkdir(parents=True, exist_ok=True)

    # Build package list
    packages = build_package_list(base_config, profile_config, arch)
    print(f"Installing {len(packages)} packages...")

    # Build mmdebstrap command
    cmd = [
        "sudo", "mmdebstrap",
        "--arch", arch,
        "--variant=minbase",
        "--include=" + ",".join(packages),
        "--components=main,contrib,non-free,non-free-firmware",
    ]

    # Add QEMU for cross-architecture builds
    if arch != "amd64":
        cmd.append("--architectures=" + arch)

    # Use cache if available
    cache_path = CACHE_DIR / f"apt-cache-{arch}"
    if cache_path.exists():
        cmd.append(f"--aptopt=Dir::Cache::archives \"{cache_path}\"")

    cmd.extend([suite, str(rootfs_path), mirror])

    print(f"Running: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error building rootfs: {e}")
        sys.exit(1)

    return rootfs_path


def configure_rootfs(base_config: dict, profile_config: dict, profile_name: str, rootfs_path: Path):
    """Configure the rootfs with system settings."""
    print("\n=== Configuring rootfs ===")

    os_name = base_config.get("general", {}).get("os_name", "fry-iot")
    os_version = base_config.get("general", {}).get("os_version", "1.0.0")
    codename = profile_config.get("general", {}).get("codename", profile_name)

    # Set hostname
    hostname = profile_config.get("system", {}).get("hostname", f"fry-{codename.lower()}")
    hostname_path = rootfs_path / "etc" / "hostname"
    hostname_path.write_text(f"{hostname}\n")

    # Configure hosts
    hosts_path = rootfs_path / "etc" / "hosts"
    hosts_content = f"""127.0.0.1   localhost
127.0.1.1   {hostname}

# IPv6
::1         localhost ip6-localhost ip6-loopback
ff02::1     ip6-allnodes
ff02::2     ip6-allrouters
"""
    hosts_path.write_text(hosts_content)

    # Create os-release
    os_release_path = rootfs_path / "etc" / "os-release"
    os_release_content = f"""PRETTY_NAME="Fry IoT {os_version} ({codename})"
NAME="Fry IoT"
VERSION_ID="{os_version}"
VERSION="{os_version} ({codename})"
VERSION_CODENAME="{codename.lower()}"
ID=fry-iot
ID_LIKE=debian
HOME_URL="https://fry.network/"
SUPPORT_URL="https://github.com/Fry-Foundation/fry-iot/issues"
BUG_REPORT_URL="https://github.com/Fry-Foundation/fry-iot/issues"
"""
    os_release_path.write_text(os_release_content)

    # Create Fry IoT info directory
    fry_dir = rootfs_path / "etc" / "fry-iot"
    fry_dir.mkdir(parents=True, exist_ok=True)

    # Device info
    device_info = {
        "name": codename,
        "brand": profile_config.get("general", {}).get("brand", "Fry"),
        "model": profile_config.get("general", {}).get("model", codename),
        "version": os_version,
        "architecture": get_architecture(profile_config),
        "build_date": subprocess.check_output(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"]).decode().strip(),
    }
    device_info_path = fry_dir / "device.json"
    device_info_path.write_text(json.dumps(device_info, indent=2))

    # Create banner
    banner_path = rootfs_path / "etc" / "motd"
    banner_content = f"""
  ______              _____    _______
 |  ____|            |_   _|  |__   __|
 | |__ _ __ _   _      | |  ___  | |
 |  __| '__| | | |     | | / _ \\ | |
 | |  | |  | |_| |    _| || (_) || |
 |_|  |_|   \\__, |   |_____\\___/ |_|
             __/ |
            |___/

 Fry IoT v{os_version} - {codename}
 Debian 13 (Trixie) based Linux for IoT devices

 Contribute to Fry Networks: https://fry.network/
 Documentation: https://docs.fry.network/

"""
    banner_path.write_text(banner_content)

    # Copy profile-specific files
    profile_files = PROFILES_DIR / profile_name / "files"
    if profile_files.exists():
        print("Copying profile-specific files...")
        for src_file in profile_files.rglob("*"):
            if src_file.is_file():
                rel_path = src_file.relative_to(profile_files)
                dst_file = rootfs_path / rel_path
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)


def configure_users(rootfs_path: Path, profile_config: dict):
    """Configure system users."""
    print("\n=== Configuring users ===")

    # Set root password (default: fryiot)
    root_password = profile_config.get("system", {}).get("root_password", "fryiot")

    # Create user setup script
    user_script = f"""#!/bin/bash
echo 'root:{root_password}' | chpasswd

# Create fry user
useradd -m -s /bin/bash -G sudo,adm,dialout,cdrom,floppy,audio,dip,video,plugdev,netdev fry
echo 'fry:{root_password}' | chpasswd

# Enable passwordless sudo for fry user (for initial setup)
echo 'fry ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/fry
chmod 440 /etc/sudoers.d/fry
"""
    script_path = rootfs_path / "tmp" / "setup-users.sh"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(user_script)
    script_path.chmod(0o755)

    # Run script in chroot
    subprocess.run([
        "sudo", "chroot", str(rootfs_path), "/tmp/setup-users.sh"
    ], check=True)

    # Clean up
    script_path.unlink()


def configure_network(rootfs_path: Path, profile_config: dict):
    """Configure network settings."""
    print("\n=== Configuring network ===")

    # Enable NetworkManager
    services_to_enable = [
        "NetworkManager",
        "ssh",
        "systemd-networkd",
        "systemd-resolved",
    ]

    for service in services_to_enable:
        subprocess.run([
            "sudo", "chroot", str(rootfs_path),
            "systemctl", "enable", service
        ], capture_output=True)

    # Create default network configuration
    network_config = rootfs_path / "etc" / "network" / "interfaces.d" / "setup"
    network_config.parent.mkdir(parents=True, exist_ok=True)
    network_config.write_text("""# Fry IoT default network configuration
# Managed by NetworkManager

auto lo
iface lo inet loopback
""")


def configure_fry_services(base_config: dict, rootfs_path: Path):
    """Configure Fry Networks services."""
    print("\n=== Configuring Fry Networks services ===")

    fry_config = base_config.get("fry", {})

    # Create Fry configuration
    fry_conf_dir = rootfs_path / "etc" / "fry"
    fry_conf_dir.mkdir(parents=True, exist_ok=True)

    fry_config_content = {
        "api_endpoint": fry_config.get("api_endpoint", "https://api.fry.network"),
        "bandwidth_mining": fry_config.get("bandwidth_mining", True),
        "node_type": fry_config.get("node_type", "router"),
    }

    config_path = fry_conf_dir / "config.json"
    config_path.write_text(json.dumps(fry_config_content, indent=2))

    # Create Fry node service
    fry_node_service = """[Unit]
Description=Fry Network Node
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/fry-node
Restart=always
RestartSec=10
User=fry
Group=fry

[Install]
WantedBy=multi-user.target
"""
    service_path = rootfs_path / "etc" / "systemd" / "system" / "fry-node.service"
    service_path.parent.mkdir(parents=True, exist_ok=True)
    service_path.write_text(fry_node_service)

    # Create bandwidth miner service
    bandwidth_miner_service = """[Unit]
Description=Fry Bandwidth Miner
After=network-online.target fry-node.service
Wants=network-online.target
Requires=fry-node.service

[Service]
Type=simple
ExecStart=/usr/bin/bandwidth-miner
Restart=always
RestartSec=30
User=fry
Group=fry

[Install]
WantedBy=multi-user.target
"""
    miner_service_path = rootfs_path / "etc" / "systemd" / "system" / "bandwidth-miner.service"
    miner_service_path.write_text(bandwidth_miner_service)

    # Create first-boot setup script
    first_boot_script = """#!/bin/bash
# Fry IoT First Boot Setup

set -e

# Generate SSH host keys if not present
if [ ! -f /etc/ssh/ssh_host_rsa_key ]; then
    ssh-keygen -A
fi

# Resize root partition to fill disk
if command -v growpart &> /dev/null; then
    ROOT_DEV=$(findmnt -n -o SOURCE /)
    ROOT_DISK=$(echo $ROOT_DEV | sed 's/[0-9]*$//')
    ROOT_PART=$(echo $ROOT_DEV | grep -o '[0-9]*$')
    growpart $ROOT_DISK $ROOT_PART || true
    resize2fs $ROOT_DEV || true
fi

# Generate machine ID
if [ ! -s /etc/machine-id ]; then
    systemd-machine-id-setup
fi

# Register with Fry Network (if configured)
if [ -f /etc/fry/config.json ] && command -v fry-node &> /dev/null; then
    fry-node register || true
fi

# Disable this script after first run
systemctl disable fry-first-boot.service

echo "First boot setup complete!"
"""
    first_boot_path = rootfs_path / "usr" / "local" / "bin" / "fry-first-boot.sh"
    first_boot_path.parent.mkdir(parents=True, exist_ok=True)
    first_boot_path.write_text(first_boot_script)
    first_boot_path.chmod(0o755)

    # Create first-boot service
    first_boot_service = """[Unit]
Description=Fry IoT First Boot Setup
After=local-fs.target
Before=network.target
ConditionPathExists=!/var/lib/fry-iot/first-boot-done

[Service]
Type=oneshot
ExecStart=/usr/local/bin/fry-first-boot.sh
ExecStartPost=/bin/touch /var/lib/fry-iot/first-boot-done
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
"""
    first_boot_service_path = rootfs_path / "etc" / "systemd" / "system" / "fry-first-boot.service"
    first_boot_service_path.write_text(first_boot_service)

    # Create state directory
    state_dir = rootfs_path / "var" / "lib" / "fry-iot"
    state_dir.mkdir(parents=True, exist_ok=True)


def create_disk_image(rootfs_path: Path, profile_name: str, profile_config: dict) -> Path:
    """Create a bootable disk image from the rootfs."""
    print("\n=== Creating disk image ===")

    image_size = profile_config.get("build", {}).get("image_size", "4G")
    image_path = OUTPUT_DIR / f"fry-iot-{profile_name}.img"

    # Create empty image file
    print(f"Creating {image_size} disk image...")
    subprocess.run([
        "sudo", "dd", "if=/dev/zero", f"of={image_path}",
        "bs=1M", f"count={int(image_size.rstrip('G')) * 1024}",
        "status=progress"
    ], check=True)

    # Create partition table
    print("Creating partition table...")
    subprocess.run([
        "sudo", "parted", "-s", str(image_path),
        "mklabel", "gpt",
        "mkpart", "EFI", "fat32", "1MiB", "257MiB",
        "set", "1", "esp", "on",
        "mkpart", "root", "ext4", "257MiB", "100%"
    ], check=True)

    # Set up loop device
    print("Setting up loop device...")
    loop_output = subprocess.check_output([
        "sudo", "losetup", "-fP", "--show", str(image_path)
    ]).decode().strip()
    loop_device = loop_output

    try:
        # Format partitions
        print("Formatting partitions...")
        subprocess.run(["sudo", "mkfs.fat", "-F32", f"{loop_device}p1"], check=True)
        subprocess.run(["sudo", "mkfs.ext4", "-L", "fry-root", f"{loop_device}p2"], check=True)

        # Mount and copy rootfs
        mount_point = WORK_DIR / "mnt"
        mount_point.mkdir(parents=True, exist_ok=True)

        subprocess.run(["sudo", "mount", f"{loop_device}p2", str(mount_point)], check=True)

        # Create and mount EFI partition
        efi_mount = mount_point / "boot" / "efi"
        subprocess.run(["sudo", "mkdir", "-p", str(efi_mount)], check=True)
        subprocess.run(["sudo", "mount", f"{loop_device}p1", str(efi_mount)], check=True)

        # Copy rootfs
        print("Copying rootfs to image...")
        subprocess.run([
            "sudo", "rsync", "-aHAX", "--info=progress2",
            f"{rootfs_path}/", f"{mount_point}/"
        ], check=True)

        # Install bootloader
        print("Installing bootloader...")
        arch = get_architecture(profile_config)
        if arch == "amd64":
            subprocess.run([
                "sudo", "chroot", str(mount_point),
                "apt-get", "install", "-y", "grub-efi-amd64"
            ], check=True)
            subprocess.run([
                "sudo", "chroot", str(mount_point),
                "grub-install", "--target=x86_64-efi", "--efi-directory=/boot/efi",
                "--bootloader-id=fry-iot", "--removable"
            ], capture_output=True)
            subprocess.run([
                "sudo", "chroot", str(mount_point),
                "update-grub"
            ], check=True)

        # Generate fstab
        print("Generating fstab...")
        root_uuid = subprocess.check_output([
            "sudo", "blkid", "-s", "UUID", "-o", "value", f"{loop_device}p2"
        ]).decode().strip()
        efi_uuid = subprocess.check_output([
            "sudo", "blkid", "-s", "UUID", "-o", "value", f"{loop_device}p1"
        ]).decode().strip()

        fstab_content = f"""# Fry IoT fstab
UUID={root_uuid}    /           ext4    errors=remount-ro   0   1
UUID={efi_uuid}     /boot/efi   vfat    umask=0077          0   1
"""
        fstab_path = mount_point / "etc" / "fstab"
        subprocess.run(["sudo", "bash", "-c", f"echo '{fstab_content}' > {fstab_path}"], check=True)

    finally:
        # Unmount and cleanup
        print("Cleaning up...")
        subprocess.run(["sudo", "umount", "-R", str(mount_point)], capture_output=True)
        subprocess.run(["sudo", "losetup", "-d", loop_device], check=True)

    print(f"Image created: {image_path}")
    return image_path


def main():
    """Main build process."""
    profile_name = os.environ.get("PROFILE")
    if not profile_name:
        print("Error: PROFILE environment variable not set")
        print("Usage: PROFILE=<profile-name> python build-image.py")
        sys.exit(1)

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                   Fry IoT Image Builder                      ║
║              Debian 13 (Trixie) based Linux                  ║
╚══════════════════════════════════════════════════════════════╝
""")

    # Load configurations
    print(f"Loading configuration for profile: {profile_name}")
    base_config = load_config()
    profile_config = load_profile_config(profile_name)

    # Ensure directories exist
    ensure_directories()

    # Build rootfs
    rootfs_path = build_rootfs(base_config, profile_config, profile_name)

    # Configure rootfs
    configure_rootfs(base_config, profile_config, profile_name, rootfs_path)
    configure_users(rootfs_path, profile_config)
    configure_network(rootfs_path, profile_config)
    configure_fry_services(base_config, rootfs_path)

    # Create disk image
    image_path = create_disk_image(rootfs_path, profile_name, profile_config)

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                     Build Complete!                          ║
╚══════════════════════════════════════════════════════════════╝

Image: {image_path}
Profile: {profile_name}
Architecture: {get_architecture(profile_config)}

To test in QEMU:
  just test-qemu

To write to SD card:
  sudo dd if={image_path} of=/dev/sdX bs=4M status=progress

""")


if __name__ == "__main__":
    main()
