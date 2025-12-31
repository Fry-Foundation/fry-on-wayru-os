#!/usr/bin/env python3
"""
Fry IoT Build Upload Tool

Uploads built Fry IoT images to cloud storage (Azure Blob Storage or S3-compatible).
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime

import toml
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
BASE_CONFIG_PATH = PROJECT_ROOT / "base-config.toml"
OUTPUT_DIR = PROJECT_ROOT / "output"
TMP_DIR = PROJECT_ROOT / "tmp"

# Azure configuration
AZURE_CONNECTION_STRING = os.getenv("AZURE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("CONTAINER_NAME", "fry-iot-images")

# Image name template
IMAGE_NAME_TEMPLATE = "fry-iot-{codename}-{version}"


def load_config():
    """Load base configuration."""
    with open(BASE_CONFIG_PATH) as f:
        return toml.load(f)


def load_device_info():
    """Load device info from build artifacts."""
    device_json_path = TMP_DIR / "device.json"
    if not device_json_path.exists():
        print("Error: device.json not found. Run 'just configure' first.")
        sys.exit(1)

    with open(device_json_path) as f:
        return json.load(f)


def calculate_sha256(file_path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def find_images() -> list:
    """Find all built images in the output directory."""
    images = []

    if not OUTPUT_DIR.exists():
        return images

    # Look for .img and compressed variants
    for pattern in ["*.img", "*.img.xz", "*.img.gz", "*.tar.gz", "*.tar.xz"]:
        images.extend(OUTPUT_DIR.glob(pattern))

    return sorted(images)


def check_blob_exists(blob_service_client, container_name: str, blob_path: str) -> bool:
    """Check if a blob already exists."""
    try:
        container_client = blob_service_client.get_container_client(container_name)
        blobs = list(container_client.list_blobs(name_starts_with=blob_path))
        return len(blobs) > 0
    except Exception:
        return False


def upload_file_to_azure(
    file_path: Path,
    blob_service_client,
    container_name: str,
    blob_path: str,
    overwrite: bool = False,
):
    """Upload a file to Azure Blob Storage with progress bar."""
    if not overwrite and check_blob_exists(blob_service_client, container_name, blob_path):
        print(f"  Blob already exists: {blob_path}")
        response = input("  Overwrite? (yes/no): ").strip().lower()
        if response != "yes":
            print("  Skipped.")
            return False

    blob_client = blob_service_client.get_blob_client(
        container=container_name, blob=blob_path
    )

    file_size = file_path.stat().st_size
    print(f"  Uploading: {file_path.name} ({file_size / (1024*1024):.1f} MB)")

    with open(file_path, "rb") as data:
        with tqdm(total=file_size, unit="B", unit_scale=True, desc="  Progress") as pbar:
            blob_client.upload_blob(
                data,
                overwrite=True,
                max_concurrency=4,
                length=file_size,
            )
            pbar.update(file_size)

    print(f"  Uploaded to: {blob_path}")
    return True


def create_manifest(images: list, device_info: dict, base_config: dict) -> dict:
    """Create a manifest file for the build."""
    version = base_config.get("general", {}).get("os_version", "1.0.0")
    codename = device_info.get("name", "unknown")

    manifest = {
        "name": f"Fry IoT {codename}",
        "version": version,
        "codename": codename,
        "architecture": device_info.get("architecture", "unknown"),
        "build_date": datetime.utcnow().isoformat() + "Z",
        "debian_suite": base_config.get("debian", {}).get("suite", "trixie"),
        "images": [],
    }

    for image_path in images:
        image_info = {
            "filename": image_path.name,
            "size": image_path.stat().st_size,
            "sha256": calculate_sha256(image_path),
        }
        manifest["images"].append(image_info)

    return manifest


def main():
    """Main upload process."""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                  Fry IoT Build Uploader                      ║
╚══════════════════════════════════════════════════════════════╝
""")

    # Check Azure configuration
    if not AZURE_CONNECTION_STRING:
        print("Error: AZURE_CONNECTION_STRING environment variable not set.")
        print("Please set it in your .env file or environment.")
        sys.exit(1)

    # Load configurations
    base_config = load_config()
    device_info = load_device_info()

    version = base_config.get("general", {}).get("os_version", "1.0.0")
    codename = device_info.get("name", "unknown")

    print(f"Device: {codename}")
    print(f"Version: {version}")
    print(f"Architecture: {device_info.get('architecture', 'unknown')}")
    print()

    # Find images
    images = find_images()
    if not images:
        print("Error: No images found in output directory.")
        print("Run 'just build' first to create images.")
        sys.exit(1)

    print(f"Found {len(images)} image(s):")
    for img in images:
        print(f"  - {img.name} ({img.stat().st_size / (1024*1024):.1f} MB)")
    print()

    # Create manifest
    manifest = create_manifest(images, device_info, base_config)
    manifest_path = OUTPUT_DIR / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Created manifest: {manifest_path}")

    # Create SHA256SUMS file
    sha256sums_path = OUTPUT_DIR / "SHA256SUMS"
    with open(sha256sums_path, "w") as f:
        for image_info in manifest["images"]:
            f.write(f"{image_info['sha256']}  {image_info['filename']}\n")
    print(f"Created checksums: {sha256sums_path}")
    print()

    # Connect to Azure
    print("Connecting to Azure Blob Storage...")
    try:
        blob_service_client = BlobServiceClient.from_connection_string(
            AZURE_CONNECTION_STRING
        )
    except Exception as e:
        print(f"Error connecting to Azure: {e}")
        sys.exit(1)

    # Upload files
    blob_prefix = f"releases/{codename}/{version}"
    print(f"Uploading to: {CONTAINER_NAME}/{blob_prefix}/")
    print()

    uploaded_count = 0

    # Upload images
    for image_path in images:
        blob_path = f"{blob_prefix}/{image_path.name}"
        if upload_file_to_azure(
            image_path, blob_service_client, CONTAINER_NAME, blob_path
        ):
            uploaded_count += 1

    # Upload manifest
    manifest_blob_path = f"{blob_prefix}/manifest.json"
    upload_file_to_azure(
        manifest_path, blob_service_client, CONTAINER_NAME, manifest_blob_path, overwrite=True
    )
    uploaded_count += 1

    # Upload checksums
    sha256sums_blob_path = f"{blob_prefix}/SHA256SUMS"
    upload_file_to_azure(
        sha256sums_path, blob_service_client, CONTAINER_NAME, sha256sums_blob_path, overwrite=True
    )
    uploaded_count += 1

    print()
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    Upload Complete!                          ║
╚══════════════════════════════════════════════════════════════╝

Uploaded {uploaded_count} file(s) to Azure Blob Storage.
Location: {CONTAINER_NAME}/{blob_prefix}/

Download URL (if public):
  https://<storage-account>.blob.core.windows.net/{CONTAINER_NAME}/{blob_prefix}/
""")


if __name__ == "__main__":
    main()
