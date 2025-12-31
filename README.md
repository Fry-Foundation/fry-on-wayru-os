# Fry IoT

```
  ______              _____    _______
 |  ____|            |_   _|  |__   __|
 | |__ _ __ _   _      | |  ___  | |
 |  __| '__| | | |     | | / _ \ | |
 | |  | |  | |_| |    _| || (_) || |
 |_|  |_|   \__, |   |_____\___/ |_|
             __/ |
            |___/

 Debian 13 (Trixie) based Linux for IoT devices
 Contribute to Fry Networks - Bandwidth Mining & More
```

Fry IoT is a Debian 13 (Trixie) based Linux distribution designed for routers, single-board computers, and IoT devices. It enables users to run full Linux desktops, servers, and contribute to Fry Networks through bandwidth mining and other decentralized services.

## Features

- **Full Debian 13 (Trixie)** - Complete Linux experience with access to all Debian packages
- **Fry Networks Integration** - Built-in bandwidth mining and network contribution
- **Multi-Architecture Support** - x86_64, ARM64, ARMhf, and MIPS architectures
- **Router Ready** - Network configuration, hostapd, dnsmasq, and firewall included
- **Desktop Option** - Optional XFCE desktop environment for full desktop experience
- **Server Mode** - Docker, Podman, and server packages available
- **Easy Configuration** - TOML-based profile system for device customization
- **Systemd Native** - Modern init system with full systemd integration

## Fry Networks

Fry IoT includes integration with Fry Networks, enabling:

- **Bandwidth Mining** - Share your unused bandwidth and earn rewards
- **Node Operation** - Run a Fry Network node on your device
- **Web Dashboard** - Monitor your contributions via local web UI (port 8080)
- **Automatic Updates** - Stay up-to-date with the latest Fry software

## Supported Devices

### Generic Profiles
| Profile | Architecture | Description |
|---------|--------------|-------------|
| `x86-generic` | amd64 | PCs, VMs, and servers |
| `x86-desktop` | amd64 | Full desktop with XFCE |
| `arm64-generic` | arm64 | ARM64 SBCs (Pi 4, Orange Pi, etc.) |
| `genesis` | mipsel | MIPS-based routers |

### Legacy Hardware Profiles
The `profiles/` directory contains additional device profiles. See individual profile configurations for supported hardware.

## Quick Start

### Prerequisites

Install build dependencies:

```bash
# Install just (command runner)
cargo install just
# Or via package manager: apt install just

# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install system dependencies (Debian/Ubuntu)
just install-deps
```

### Building an Image

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Fry-Foundation/fry-iot.git
   cd fry-iot
   ```

2. **Set up the environment:**
   ```bash
   just setup
   ```

3. **Configure your profile:**
   ```bash
   cp .env.example .env
   # Edit .env and set PROFILE=x86-generic (or your preferred profile)
   ```

4. **Build the image:**
   ```bash
   PROFILE=x86-generic just full-build
   ```

5. **Test in QEMU (x86 only):**
   ```bash
   just test-qemu
   ```

### Writing to SD Card / USB

```bash
sudo dd if=output/fry-iot-x86-generic.img of=/dev/sdX bs=4M status=progress
sync
```

## Configuration

### Base Configuration

The `base-config.toml` file contains global settings:
- Debian mirror and suite configuration
- Core and IoT package lists
- Fry Networks integration settings
- Build output configuration

### Profile Configuration

Each profile in `profiles/<name>/profile-config.toml` defines:
- Device architecture and build options
- Additional packages to install
- Network configuration (ethernet, WiFi, VLANs)
- Hostapd and dnsmasq settings
- Fry Networks node configuration

### Example Profile

```toml
[general]
codename = "MyDevice"
brand = "Fry"
model = "Custom Router"

[build]
architecture = "arm64"
flavor = "minimal"
image_size = "4G"

[packages]
include = ["hostapd", "dnsmasq"]
exclude = ["podman"]

[network.ethernet]
interface = "eth0"
dhcp = true

[fry]
bandwidth_mining = true
node_type = "router"
```

## Available Commands

Run `just` to see all available commands:

```
just setup          # Set up Python environment
just install-deps   # Install system build dependencies
just configure      # Configure build for selected profile
just build          # Build complete image
just build-rootfs   # Build rootfs only (no disk image)
just test-qemu      # Test image in QEMU
just compress       # Compress built images
just upload-build   # Upload to cloud storage
just validate       # Validate built image
just clean          # Clean build artifacts
just reset          # Full reset
just info           # Show build information
```

## Default Credentials

- **Username:** `fry`
- **Password:** `fryiot`
- **Root password:** `fryiot`

**Important:** Change these passwords after first boot!

## Web Dashboard

After booting, access the Fry Dashboard at:
```
http://<device-ip>:8080
```

## Directory Structure

```
fry-iot/
├── base-config.toml      # Global configuration
├── justfile              # Build automation
├── pyproject.toml        # Python dependencies
├── profiles/             # Device profiles
│   ├── x86-generic/      # Generic x86 profile
│   ├── arm64-generic/    # Generic ARM64 profile
│   └── ...               # Additional profiles
├── tools/                # Build scripts
│   ├── build-image.py    # Main image builder
│   ├── configure.py      # Configuration generator
│   ├── configure-fry.py  # Fry Networks setup
│   └── ...               # Additional tools
├── resources/            # Shared resources
│   └── ascii-logo        # Boot banner
├── output/               # Built images (generated)
├── work/                 # Build workspace (generated)
└── cache/                # Package cache (generated)
```

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with `just build` and `just validate`
5. Submit a pull request

### Adding New Device Profiles

1. Create a new directory in `profiles/<device-name>/`
2. Add a `profile-config.toml` with device configuration
3. Optionally add custom files in `profiles/<device-name>/files/`
4. Test the build with `PROFILE=<device-name> just build`

## License

This project is licensed under the MIT License.

## Support

- **Issues:** [GitHub Issues](https://github.com/Fry-Foundation/fry-iot/issues)
- **Documentation:** [https://docs.fry.network/](https://docs.fry.network/)
- **Fry Networks:** [https://fry.network/](https://fry.network/)

## Acknowledgments

This project builds upon the foundation of the WayruOS project. We thank the original Wayru team for their contributions to open-source networking software.

---

**Note:** This project is open source and community-maintained. Join us in building the future of decentralized networking!
