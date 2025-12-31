#!/usr/bin/env python3
"""
Fry IoT Configuration Tool

Generates configuration files for building Fry IoT images.
Reads base-config.toml and profile-config.toml to create build artifacts.
"""

import os
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime

import toml

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
BASE_CONFIG_PATH = PROJECT_ROOT / "base-config.toml"
PROFILES_DIR = PROJECT_ROOT / "profiles"
WORK_DIR = PROJECT_ROOT / "work"
OUTPUT_DIR = PROJECT_ROOT / "output"
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


def ensure_directories():
    """Create necessary directories."""
    for directory in [WORK_DIR, OUTPUT_DIR, TMP_DIR]:
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


def generate_build_config(base_config: dict, profile_config: dict, profile_name: str):
    """Generate the build configuration file."""
    print("Generating build configuration...")

    os_name = base_config.get("general", {}).get("os_name", "fry-iot")
    os_version = base_config.get("general", {}).get("os_version", "1.0.0")
    arch = get_architecture(profile_config)
    codename = profile_config.get("general", {}).get("codename", profile_name)

    build_config = {
        "os": {
            "name": os_name,
            "version": os_version,
            "codename": codename,
            "build_date": datetime.utcnow().isoformat() + "Z",
        },
        "debian": {
            "suite": base_config.get("debian", {}).get("suite", "trixie"),
            "mirror": base_config.get("debian", {}).get("mirror", "https://deb.debian.org/debian"),
            "components": base_config.get("debian", {}).get("components", ["main", "contrib", "non-free", "non-free-firmware"]),
        },
        "build": {
            "architecture": arch,
            "profile": profile_name,
            "image_size": profile_config.get("build", {}).get("image_size", base_config.get("build", {}).get("image_size", "4G")),
            "rootfs_type": base_config.get("build", {}).get("rootfs_type", "ext4"),
            "compression": base_config.get("build", {}).get("compression", "xz"),
        },
        "device": {
            "name": codename,
            "brand": profile_config.get("general", {}).get("brand", "Fry"),
            "model": profile_config.get("general", {}).get("model", codename),
        },
        "fry": base_config.get("fry", {}),
    }

    # Merge packages
    packages = []
    packages.extend(base_config.get("packages", {}).get("core", []))
    packages.extend(base_config.get("packages", {}).get("iot", []))
    packages.extend(profile_config.get("packages", {}).get("include", []))

    # Handle flavor-specific packages
    flavor = profile_config.get("build", {}).get("flavor", "minimal")
    if flavor == "desktop":
        packages.extend(base_config.get("packages", {}).get("desktop", []))
    elif flavor == "server":
        packages.extend(base_config.get("packages", {}).get("server", []))

    # Remove excluded packages
    exclude = profile_config.get("packages", {}).get("exclude", [])
    packages = [p for p in packages if p not in exclude]

    # Remove duplicates
    packages = list(dict.fromkeys(packages))

    build_config["packages"] = packages

    # Write build config
    config_path = TMP_DIR / "build-config.json"
    with open(config_path, "w") as f:
        json.dump(build_config, f, indent=2)

    print(f"Build configuration written to: {config_path}")
    return build_config


def generate_device_info(profile_config: dict, profile_name: str, os_version: str):
    """Generate device info JSON."""
    print("Generating device info...")

    codename = profile_config.get("general", {}).get("codename", profile_name)

    device_info = {
        "name": codename,
        "brand": profile_config.get("general", {}).get("brand", "Fry"),
        "model": profile_config.get("general", {}).get("model", codename),
        "version": os_version,
        "architecture": get_architecture(profile_config),
    }

    info_path = TMP_DIR / "device.json"
    with open(info_path, "w") as f:
        json.dump(device_info, f, indent=2)

    print(f"Device info written to: {info_path}")
    return device_info


def generate_banner(base_config: dict, profile_config: dict, profile_name: str):
    """Generate system banner/MOTD."""
    print("Generating system banner...")

    os_version = base_config.get("general", {}).get("os_version", "1.0.0")
    codename = profile_config.get("general", {}).get("codename", profile_name)
    arch = get_architecture(profile_config)

    # Read ASCII logo if available
    logo_path = PROJECT_ROOT / "resources" / "ascii-logo"
    if logo_path.exists():
        logo = logo_path.read_text()
    else:
        logo = """
  ______              _____    _______
 |  ____|            |_   _|  |__   __|
 | |__ _ __ _   _      | |  ___  | |
 |  __| '__| | | |     | | / _ \\ | |
 | |  | |  | |_| |    _| || (_) || |
 |_|  |_|   \\__, |   |_____\\___/ |_|
             __/ |
            |___/
"""

    banner = f"""{logo}
 Fry IoT v{os_version} - {codename} ({arch})
 Debian 13 (Trixie) based Linux for IoT devices

 Contribute to Fry Networks: https://fry.network/
 Documentation: https://docs.fry.network/

 Default credentials: fry / fryiot
 SSH enabled on port 22

"""

    banner_path = TMP_DIR / "banner"
    banner_path.write_text(banner)
    print(f"Banner written to: {banner_path}")

    return banner


def copy_profile_files(profile_name: str):
    """Copy profile-specific files to work directory."""
    print("Copying profile files...")

    profile_dir = PROFILES_DIR / profile_name
    work_files_dir = WORK_DIR / "files"

    # Clean and create work files directory
    if work_files_dir.exists():
        shutil.rmtree(work_files_dir)
    work_files_dir.mkdir(parents=True, exist_ok=True)

    # Copy files from profile
    profile_files = profile_dir / "files"
    if profile_files.exists():
        for src_file in profile_files.rglob("*"):
            if src_file.is_file():
                rel_path = src_file.relative_to(profile_files)
                dst_file = work_files_dir / rel_path
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)
                print(f"  Copied: {rel_path}")

    # Copy systemd units from profile
    systemd_dir = profile_dir / "systemd"
    if systemd_dir.exists():
        dst_systemd = work_files_dir / "etc" / "systemd" / "system"
        dst_systemd.mkdir(parents=True, exist_ok=True)
        for unit_file in systemd_dir.glob("*.service"):
            shutil.copy2(unit_file, dst_systemd / unit_file.name)
            print(f"  Copied systemd unit: {unit_file.name}")
        for unit_file in systemd_dir.glob("*.timer"):
            shutil.copy2(unit_file, dst_systemd / unit_file.name)
            print(f"  Copied systemd timer: {unit_file.name}")

    # Copy network configuration from profile
    network_dir = profile_dir / "network"
    if network_dir.exists():
        dst_network = work_files_dir / "etc" / "systemd" / "network"
        dst_network.mkdir(parents=True, exist_ok=True)
        for network_file in network_dir.glob("*.network"):
            shutil.copy2(network_file, dst_network / network_file.name)
            print(f"  Copied network config: {network_file.name}")


def generate_sources_list(base_config: dict):
    """Generate APT sources.list."""
    print("Generating APT sources...")

    suite = base_config.get("debian", {}).get("suite", "trixie")
    mirror = base_config.get("debian", {}).get("mirror", "https://deb.debian.org/debian")
    security_mirror = base_config.get("debian", {}).get("security_mirror", "https://deb.debian.org/debian-security")
    components = base_config.get("debian", {}).get("components", ["main", "contrib", "non-free", "non-free-firmware"])
    components_str = " ".join(components)

    sources_content = f"""# Fry IoT - Debian {suite} sources
# Auto-generated by configure.py

deb {mirror} {suite} {components_str}
deb {mirror} {suite}-updates {components_str}
deb {security_mirror} {suite}-security {components_str}
"""

    sources_path = TMP_DIR / "sources.list"
    sources_path.write_text(sources_content)
    print(f"APT sources written to: {sources_path}")

    # Generate Fry repository configuration
    fry_sources = """# Fry Networks Repository
deb [signed-by=/usr/share/keyrings/fry-archive-keyring.gpg] https://apt.fry.network/debian trixie main
"""
    fry_sources_path = TMP_DIR / "fry.list"
    fry_sources_path.write_text(fry_sources)
    print(f"Fry sources written to: {fry_sources_path}")


def main():
    """Main configuration process."""
    profile_name = os.environ.get("PROFILE")
    if not profile_name:
        print("Error: PROFILE environment variable not set")
        print("Usage: PROFILE=<profile-name> python configure.py")
        print("\nAvailable profiles:")
        for profile in sorted(PROFILES_DIR.iterdir()):
            if profile.is_dir() and (profile / "profile-config.toml").exists():
                print(f"  - {profile.name}")
        sys.exit(1)

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                 Fry IoT Configuration Tool                   ║
╚══════════════════════════════════════════════════════════════╝
""")

    print(f"Configuring profile: {profile_name}")

    # Load configurations
    base_config = load_config()
    profile_config = load_profile_config(profile_name)

    # Ensure directories exist
    ensure_directories()

    # Generate configurations
    os_version = base_config.get("general", {}).get("os_version", "1.0.0")

    build_config = generate_build_config(base_config, profile_config, profile_name)
    device_info = generate_device_info(profile_config, profile_name, os_version)
    banner = generate_banner(base_config, profile_config, profile_name)
    generate_sources_list(base_config)
    copy_profile_files(profile_name)

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                 Configuration Complete!                      ║
╚══════════════════════════════════════════════════════════════╝

Profile: {profile_name}
Device: {device_info['name']} ({device_info['brand']} {device_info['model']})
Architecture: {device_info['architecture']}
Image size: {build_config['build']['image_size']}

Configuration files generated in: {TMP_DIR}

Next step: Run 'just build' to build the image.
""")


if __name__ == "__main__":
    main()
