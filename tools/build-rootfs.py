#!/usr/bin/env python3
"""
Fry IoT Rootfs Builder

Builds Debian 13 (Trixie) rootfs for IoT devices without creating a disk image.
Useful for container deployments or custom image creation.
"""

import os
import sys
import subprocess
import json
from pathlib import Path

import toml

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
BASE_CONFIG_PATH = PROJECT_ROOT / "base-config.toml"
PROFILES_DIR = PROJECT_ROOT / "profiles"
WORK_DIR = PROJECT_ROOT / "work"
TMP_DIR = PROJECT_ROOT / "tmp"


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
    kernel = profile_config.get("build", {}).get("kernel_package")
    if kernel:
        return kernel

    kernel_mapping = {
        "amd64": "linux-image-amd64",
        "arm64": "linux-image-arm64",
        "armhf": "linux-image-armmp",
        "mipsel": "linux-image-mipsel",
    }
    return kernel_mapping.get(arch, "linux-image-generic")


def build_package_list(base_config: dict, profile_config: dict, arch: str) -> list:
    """Build the complete package list."""
    packages = []

    packages.extend(base_config.get("packages", {}).get("core", []))
    packages.extend(base_config.get("packages", {}).get("iot", []))
    packages.extend(profile_config.get("packages", {}).get("include", []))
    packages.append(get_kernel_package(arch, profile_config))

    flavor = profile_config.get("build", {}).get("flavor", "minimal")
    if flavor == "desktop":
        packages.extend(base_config.get("packages", {}).get("desktop", []))
    elif flavor == "server":
        packages.extend(base_config.get("packages", {}).get("server", []))

    exclude = profile_config.get("packages", {}).get("exclude", [])
    packages = [p for p in packages if p not in exclude]

    seen = set()
    unique_packages = []
    for p in packages:
        if p not in seen:
            seen.add(p)
            unique_packages.append(p)

    return unique_packages


def main():
    """Main rootfs build process."""
    profile_name = os.environ.get("PROFILE")
    if not profile_name:
        print("Error: PROFILE environment variable not set")
        print("Usage: PROFILE=<profile-name> python build-rootfs.py")
        sys.exit(1)

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                  Fry IoT Rootfs Builder                      ║
║              Debian 13 (Trixie) based Linux                  ║
╚══════════════════════════════════════════════════════════════╝
""")

    base_config = load_config()
    profile_config = load_profile_config(profile_name)

    arch = get_architecture(profile_config)
    suite = base_config.get("debian", {}).get("suite", "trixie")
    mirror = base_config.get("debian", {}).get("mirror", "https://deb.debian.org/debian")

    rootfs_path = WORK_DIR / "rootfs"

    # Ensure directories
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    # Clean previous rootfs
    if rootfs_path.exists():
        print("Cleaning previous rootfs...")
        subprocess.run(["sudo", "rm", "-rf", str(rootfs_path)], check=True)

    rootfs_path.mkdir(parents=True, exist_ok=True)

    # Build package list
    packages = build_package_list(base_config, profile_config, arch)
    print(f"Profile: {profile_name}")
    print(f"Architecture: {arch}")
    print(f"Installing {len(packages)} packages...")

    # Build mmdebstrap command
    cmd = [
        "sudo", "mmdebstrap",
        "--arch", arch,
        "--variant=minbase",
        "--include=" + ",".join(packages),
        "--components=main,contrib,non-free,non-free-firmware",
        suite,
        str(rootfs_path),
        mirror,
    ]

    print(f"\nRunning mmdebstrap...")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error building rootfs: {e}")
        sys.exit(1)

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                   Rootfs Build Complete!                     ║
╚══════════════════════════════════════════════════════════════╝

Rootfs location: {rootfs_path}
Profile: {profile_name}
Architecture: {arch}

To enter the rootfs:
  sudo systemd-nspawn -D {rootfs_path}

To create a tarball:
  sudo tar -C {rootfs_path} -czvf fry-iot-rootfs.tar.gz .

""")


if __name__ == "__main__":
    main()
