#!/usr/bin/env python3
"""
Fry IoT Image Validation Tool

Validates built images for correctness and completeness.
"""

import os
import sys
import subprocess
import hashlib
import json
from pathlib import Path

import toml

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
BASE_CONFIG_PATH = PROJECT_ROOT / "base-config.toml"
OUTPUT_DIR = PROJECT_ROOT / "output"
TMP_DIR = PROJECT_ROOT / "tmp"
WORK_DIR = PROJECT_ROOT / "work"


def load_config():
    """Load base configuration."""
    with open(BASE_CONFIG_PATH) as f:
        return toml.load(f)


class ValidationResult:
    def __init__(self, name: str, passed: bool, message: str = ""):
        self.name = name
        self.passed = passed
        self.message = message

    def __str__(self):
        status = "✓" if self.passed else "✗"
        result = f"  {status} {self.name}"
        if self.message:
            result += f": {self.message}"
        return result


def check_image_exists() -> ValidationResult:
    """Check if image file exists."""
    images = list(OUTPUT_DIR.glob("*.img")) + list(OUTPUT_DIR.glob("*.img.*"))
    if images:
        return ValidationResult("Image file exists", True, images[0].name)
    return ValidationResult("Image file exists", False, "No image found")


def check_image_size() -> ValidationResult:
    """Check if image size is reasonable."""
    images = list(OUTPUT_DIR.glob("*.img"))
    if not images:
        return ValidationResult("Image size", False, "No image found")

    image_path = images[0]
    size_mb = image_path.stat().st_size / (1024 * 1024)

    if size_mb < 100:
        return ValidationResult("Image size", False, f"{size_mb:.1f} MB (too small)")
    elif size_mb > 16000:
        return ValidationResult("Image size", False, f"{size_mb:.1f} MB (too large)")
    else:
        return ValidationResult("Image size", True, f"{size_mb:.1f} MB")


def check_checksums() -> ValidationResult:
    """Verify checksums file exists and is valid."""
    checksums_path = OUTPUT_DIR / "SHA256SUMS"
    if not checksums_path.exists():
        return ValidationResult("Checksums file", False, "SHA256SUMS not found")

    try:
        with open(checksums_path) as f:
            lines = f.readlines()
        if len(lines) == 0:
            return ValidationResult("Checksums file", False, "Empty")
        return ValidationResult("Checksums file", True, f"{len(lines)} entries")
    except Exception as e:
        return ValidationResult("Checksums file", False, str(e))


def check_manifest() -> ValidationResult:
    """Check if manifest.json exists and is valid."""
    manifest_path = OUTPUT_DIR / "manifest.json"
    if not manifest_path.exists():
        return ValidationResult("Manifest file", False, "manifest.json not found")

    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
        required_keys = ["name", "version", "codename", "architecture"]
        missing = [k for k in required_keys if k not in manifest]
        if missing:
            return ValidationResult("Manifest file", False, f"Missing keys: {missing}")
        return ValidationResult("Manifest file", True, f"{manifest['name']} v{manifest['version']}")
    except json.JSONDecodeError as e:
        return ValidationResult("Manifest file", False, f"Invalid JSON: {e}")


def check_device_info() -> ValidationResult:
    """Check if device.json was generated."""
    device_path = TMP_DIR / "device.json"
    if not device_path.exists():
        return ValidationResult("Device info", False, "device.json not found")

    try:
        with open(device_path) as f:
            device = json.load(f)
        return ValidationResult("Device info", True, f"{device.get('name', 'Unknown')}")
    except Exception as e:
        return ValidationResult("Device info", False, str(e))


def check_rootfs() -> ValidationResult:
    """Check if rootfs exists and has basic structure."""
    rootfs_path = WORK_DIR / "rootfs"
    if not rootfs_path.exists():
        return ValidationResult("Rootfs", False, "Not found")

    required_dirs = ["bin", "etc", "lib", "usr", "var"]
    missing = [d for d in required_dirs if not (rootfs_path / d).exists()]

    if missing:
        return ValidationResult("Rootfs", False, f"Missing: {missing}")
    return ValidationResult("Rootfs", True, "Structure valid")


def check_fry_config() -> ValidationResult:
    """Check if Fry configuration exists."""
    fry_config = WORK_DIR / "files" / "etc" / "fry" / "config.json"
    if not fry_config.exists():
        return ValidationResult("Fry config", False, "config.json not found")

    try:
        with open(fry_config) as f:
            config = json.load(f)
        if config.get("bandwidth_mining"):
            return ValidationResult("Fry config", True, "Bandwidth mining enabled")
        return ValidationResult("Fry config", True, "Valid")
    except Exception as e:
        return ValidationResult("Fry config", False, str(e))


def check_systemd_services() -> ValidationResult:
    """Check if systemd services are configured."""
    systemd_dir = WORK_DIR / "files" / "etc" / "systemd" / "system"
    if not systemd_dir.exists():
        return ValidationResult("Systemd services", False, "Directory not found")

    services = list(systemd_dir.glob("*.service"))
    timers = list(systemd_dir.glob("*.timer"))

    if not services:
        return ValidationResult("Systemd services", False, "No services found")

    return ValidationResult("Systemd services", True, f"{len(services)} services, {len(timers)} timers")


def verify_sha256_checksum(file_path: Path, expected_hash: str) -> bool:
    """Verify a file's SHA256 checksum."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest() == expected_hash


def check_checksum_verification() -> ValidationResult:
    """Verify checksums match actual files."""
    checksums_path = OUTPUT_DIR / "SHA256SUMS"
    if not checksums_path.exists():
        return ValidationResult("Checksum verification", False, "No checksums file")

    verified = 0
    failed = 0

    with open(checksums_path) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 2:
                expected_hash = parts[0]
                filename = parts[1].lstrip("*")
                file_path = OUTPUT_DIR / filename

                if file_path.exists():
                    if verify_sha256_checksum(file_path, expected_hash):
                        verified += 1
                    else:
                        failed += 1
                else:
                    failed += 1

    if failed > 0:
        return ValidationResult("Checksum verification", False, f"{failed} failed, {verified} passed")
    elif verified == 0:
        return ValidationResult("Checksum verification", False, "No files verified")
    else:
        return ValidationResult("Checksum verification", True, f"{verified} files verified")


def main():
    """Main validation process."""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║               Fry IoT Image Validation Tool                  ║
╚══════════════════════════════════════════════════════════════╝
""")

    results = []

    print("Running validation checks...")
    print()

    # Run all checks
    checks = [
        check_image_exists,
        check_image_size,
        check_checksums,
        check_manifest,
        check_device_info,
        check_rootfs,
        check_fry_config,
        check_systemd_services,
        check_checksum_verification,
    ]

    for check in checks:
        result = check()
        results.append(result)
        print(result)

    # Summary
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)

    print()
    print(f"Results: {passed} passed, {failed} failed")

    if failed > 0:
        print("\n⚠ Some validation checks failed. Please review the output above.")
        sys.exit(1)
    else:
        print("\n✓ All validation checks passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
