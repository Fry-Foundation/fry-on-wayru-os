#!/usr/bin/env python3
"""
Fry IoT Image Compression Tool

Compresses built images using various formats (xz, gzip, zstd).
"""

import os
import sys
import subprocess
import hashlib
from pathlib import Path
from datetime import datetime

import toml
from tqdm import tqdm

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
BASE_CONFIG_PATH = PROJECT_ROOT / "base-config.toml"
OUTPUT_DIR = PROJECT_ROOT / "output"


def load_config():
    """Load base configuration."""
    with open(BASE_CONFIG_PATH) as f:
        return toml.load(f)


def calculate_sha256(file_path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def compress_file(file_path: Path, compression: str = "xz") -> Path:
    """Compress a file using the specified algorithm."""
    output_path = Path(str(file_path) + f".{compression}")

    if output_path.exists():
        print(f"  Compressed file already exists: {output_path.name}")
        return output_path

    file_size = file_path.stat().st_size
    print(f"  Compressing: {file_path.name} ({file_size / (1024*1024):.1f} MB)")

    if compression == "xz":
        cmd = ["xz", "-k", "-9", "-T0", str(file_path)]
    elif compression == "gz" or compression == "gzip":
        cmd = ["gzip", "-k", "-9", str(file_path)]
        output_path = Path(str(file_path) + ".gz")
    elif compression == "zstd":
        cmd = ["zstd", "-k", "-19", "-T0", str(file_path)]
        output_path = Path(str(file_path) + ".zst")
    else:
        print(f"  Unknown compression format: {compression}")
        return file_path

    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"  Compression failed: {e}")
        return file_path

    compressed_size = output_path.stat().st_size
    ratio = (1 - compressed_size / file_size) * 100
    print(f"  Created: {output_path.name} ({compressed_size / (1024*1024):.1f} MB, {ratio:.1f}% smaller)")

    return output_path


def main():
    """Main compression process."""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║               Fry IoT Image Compression Tool                 ║
╚══════════════════════════════════════════════════════════════╝
""")

    # Load config
    base_config = load_config()
    compression = base_config.get("build", {}).get("compression", "xz")

    print(f"Compression format: {compression}")
    print()

    # Find uncompressed images
    images = list(OUTPUT_DIR.glob("*.img"))
    if not images:
        print("No uncompressed images found in output directory.")
        sys.exit(0)

    print(f"Found {len(images)} image(s) to compress:")
    for img in images:
        print(f"  - {img.name}")
    print()

    # Compress each image
    compressed_files = []
    for image_path in images:
        compressed_path = compress_file(image_path, compression)
        compressed_files.append(compressed_path)

    print()
    print("Generating checksums...")

    # Generate checksums
    checksums_path = OUTPUT_DIR / "SHA256SUMS"
    with open(checksums_path, "w") as f:
        for file_path in compressed_files:
            sha256 = calculate_sha256(file_path)
            f.write(f"{sha256}  {file_path.name}\n")
            print(f"  {file_path.name}: {sha256[:16]}...")

    print(f"\nChecksums written to: {checksums_path}")

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                  Compression Complete!                       ║
╚══════════════════════════════════════════════════════════════╝

Compressed {len(compressed_files)} image(s).
Output directory: {OUTPUT_DIR}
""")


if __name__ == "__main__":
    main()
