#!/usr/bin/env python3
"""
Fry IoT - Fry Networks Integration Configuration

Configures Fry Networks services including bandwidth mining,
node management, and network contribution features.
"""

import os
import sys
import json
from pathlib import Path

import toml

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
BASE_CONFIG_PATH = PROJECT_ROOT / "base-config.toml"
WORK_DIR = PROJECT_ROOT / "work"


def load_config():
    """Load base configuration."""
    with open(BASE_CONFIG_PATH) as f:
        return toml.load(f)


def generate_fry_config(base_config: dict):
    """Generate Fry Networks configuration files."""
    fry_config = base_config.get("fry", {})

    # Create Fry config directory
    fry_dir = WORK_DIR / "files" / "etc" / "fry"
    fry_dir.mkdir(parents=True, exist_ok=True)

    # Main configuration
    config = {
        "api_endpoint": fry_config.get("api_endpoint", "https://api.fry.network"),
        "bandwidth_mining": fry_config.get("bandwidth_mining", True),
        "node_type": fry_config.get("node_type", "router"),
        "auto_register": True,
        "telemetry": {
            "enabled": True,
            "interval": 60,
        },
        "bandwidth": {
            "enabled": fry_config.get("bandwidth_mining", True),
            "max_share_percent": 50,
            "min_bandwidth_mbps": 1,
        },
        "network": {
            "upnp": True,
            "nat_pmp": True,
            "stun_servers": [
                "stun:stun.l.google.com:19302",
                "stun:stun.fry.network:3478",
            ],
        },
    }

    config_path = fry_dir / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"Generated: {config_path}")


def generate_fry_services():
    """Generate systemd service files for Fry Networks."""
    systemd_dir = WORK_DIR / "files" / "etc" / "systemd" / "system"
    systemd_dir.mkdir(parents=True, exist_ok=True)

    # Fry Node Service
    fry_node_service = """[Unit]
Description=Fry Network Node
Documentation=https://docs.fry.network/
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=300
StartLimitBurst=5

[Service]
Type=simple
User=fry
Group=fry
ExecStart=/usr/bin/fry-node --config /etc/fry/config.json
Restart=always
RestartSec=10
Environment=FRY_LOG_LEVEL=info
Environment=FRY_DATA_DIR=/var/lib/fry

# Security hardening
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/var/lib/fry /var/log/fry
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
"""
    node_path = systemd_dir / "fry-node.service"
    node_path.write_text(fry_node_service)
    print(f"Generated: {node_path}")

    # Bandwidth Miner Service
    bandwidth_miner_service = """[Unit]
Description=Fry Bandwidth Miner
Documentation=https://docs.fry.network/bandwidth-mining
After=network-online.target fry-node.service
Wants=network-online.target
Requires=fry-node.service
StartLimitIntervalSec=300
StartLimitBurst=5

[Service]
Type=simple
User=fry
Group=fry
ExecStart=/usr/bin/bandwidth-miner --config /etc/fry/config.json
Restart=always
RestartSec=30
Environment=FRY_LOG_LEVEL=info
Environment=FRY_DATA_DIR=/var/lib/fry

# Security hardening
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/var/lib/fry /var/log/fry
PrivateTmp=yes

# Resource limits
MemoryMax=512M
CPUQuota=50%

[Install]
WantedBy=multi-user.target
"""
    miner_path = systemd_dir / "bandwidth-miner.service"
    miner_path.write_text(bandwidth_miner_service)
    print(f"Generated: {miner_path}")

    # Fry Dashboard Service (optional web UI)
    dashboard_service = """[Unit]
Description=Fry Dashboard Web UI
Documentation=https://docs.fry.network/dashboard
After=network-online.target fry-node.service
Wants=network-online.target

[Service]
Type=simple
User=fry
Group=fry
ExecStart=/usr/bin/fry-dashboard --port 8080
Restart=always
RestartSec=10
Environment=FRY_DASHBOARD_PORT=8080

# Security hardening
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/var/lib/fry
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
"""
    dashboard_path = systemd_dir / "fry-dashboard.service"
    dashboard_path.write_text(dashboard_service)
    print(f"Generated: {dashboard_path}")

    # Fry Update Timer
    update_timer = """[Unit]
Description=Fry IoT automatic update check

[Timer]
OnBootSec=5min
OnUnitActiveSec=6h
RandomizedDelaySec=30min

[Install]
WantedBy=timers.target
"""
    timer_path = systemd_dir / "fry-update.timer"
    timer_path.write_text(update_timer)
    print(f"Generated: {timer_path}")

    # Fry Update Service
    update_service = """[Unit]
Description=Fry IoT Update Check
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/fry-cli update --check
User=root
"""
    update_service_path = systemd_dir / "fry-update.service"
    update_service_path.write_text(update_service)
    print(f"Generated: {update_service_path}")


def generate_fry_scripts():
    """Generate helper scripts for Fry Networks."""
    bin_dir = WORK_DIR / "files" / "usr" / "local" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    # First boot registration script
    first_boot_script = """#!/bin/bash
# Fry IoT First Boot Setup

set -e

FRY_STATE_DIR="/var/lib/fry-iot"
FIRST_BOOT_DONE="$FRY_STATE_DIR/first-boot-done"

# Check if first boot already done
if [ -f "$FIRST_BOOT_DONE" ]; then
    echo "First boot already completed."
    exit 0
fi

echo "Running Fry IoT first boot setup..."

# Create necessary directories
mkdir -p /var/lib/fry
mkdir -p /var/log/fry
mkdir -p "$FRY_STATE_DIR"

# Create fry user if not exists
if ! id -u fry &>/dev/null; then
    useradd -r -s /bin/false -d /var/lib/fry -c "Fry Network Node" fry
fi

# Set ownership
chown -R fry:fry /var/lib/fry
chown -R fry:fry /var/log/fry

# Generate SSH host keys if not present
if [ ! -f /etc/ssh/ssh_host_rsa_key ]; then
    echo "Generating SSH host keys..."
    ssh-keygen -A
fi

# Generate machine ID if not present
if [ ! -s /etc/machine-id ]; then
    echo "Generating machine ID..."
    systemd-machine-id-setup
fi

# Resize root partition to fill disk (for SD card installations)
if command -v growpart &> /dev/null; then
    ROOT_DEV=$(findmnt -n -o SOURCE /)
    ROOT_DISK=$(echo "$ROOT_DEV" | sed 's/[0-9]*$//')
    ROOT_PART=$(echo "$ROOT_DEV" | grep -o '[0-9]*$')
    echo "Attempting to expand root partition..."
    growpart "$ROOT_DISK" "$ROOT_PART" 2>/dev/null || true
    resize2fs "$ROOT_DEV" 2>/dev/null || true
fi

# Enable Fry services
echo "Enabling Fry services..."
systemctl enable fry-node.service
systemctl enable bandwidth-miner.service
systemctl enable fry-dashboard.service
systemctl enable fry-update.timer

# Start services
echo "Starting Fry services..."
systemctl start fry-node.service
systemctl start bandwidth-miner.service
systemctl start fry-dashboard.service
systemctl start fry-update.timer

# Register with Fry Network (if fry-node is available)
if command -v fry-node &> /dev/null; then
    echo "Registering with Fry Network..."
    fry-node register || echo "Registration will be attempted on next boot."
fi

# Mark first boot as done
touch "$FIRST_BOOT_DONE"

echo "First boot setup complete!"
echo "Dashboard available at: http://$(hostname -I | awk '{print $1}'):8080"
"""
    first_boot_path = bin_dir / "fry-first-boot.sh"
    first_boot_path.write_text(first_boot_script)
    first_boot_path.chmod(0o755)
    print(f"Generated: {first_boot_path}")

    # Status check script
    status_script = """#!/bin/bash
# Fry IoT Status Check

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    Fry IoT Status                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# System info
echo "System Information:"
echo "  Hostname: $(hostname)"
echo "  IP Address: $(hostname -I | awk '{print $1}')"
echo "  Uptime: $(uptime -p)"
echo ""

# Service status
echo "Service Status:"
for service in fry-node bandwidth-miner fry-dashboard; do
    status=$(systemctl is-active $service.service 2>/dev/null || echo "not installed")
    case $status in
        active) icon="●" ;;
        inactive) icon="○" ;;
        *) icon="?" ;;
    esac
    printf "  %s %-20s %s\\n" "$icon" "$service" "$status"
done
echo ""

# Resource usage
echo "Resource Usage:"
echo "  CPU: $(top -bn1 | grep 'Cpu(s)' | awk '{print $2}')%"
echo "  Memory: $(free -m | awk 'NR==2{printf "%.1f%% (%dMB/%dMB)", $3*100/$2, $3, $2}')"
echo "  Disk: $(df -h / | awk 'NR==2{print $5 " (" $3 "/" $2 ")"}')"
echo ""

# Network status
echo "Network Status:"
echo "  Interfaces: $(ip -brief link show | grep -v lo | awk '{print $1}' | tr '\\n' ' ')"
echo ""

# Dashboard URL
echo "Dashboard: http://$(hostname -I | awk '{print $1}'):8080"
echo ""
"""
    status_path = bin_dir / "fry-status"
    status_path.write_text(status_script)
    status_path.chmod(0o755)
    print(f"Generated: {status_path}")


def generate_first_boot_service():
    """Generate first boot systemd service."""
    systemd_dir = WORK_DIR / "files" / "etc" / "systemd" / "system"
    systemd_dir.mkdir(parents=True, exist_ok=True)

    first_boot_service = """[Unit]
Description=Fry IoT First Boot Setup
After=local-fs.target network.target
Before=fry-node.service
ConditionPathExists=!/var/lib/fry-iot/first-boot-done

[Service]
Type=oneshot
ExecStart=/usr/local/bin/fry-first-boot.sh
RemainAfterExit=yes
StandardOutput=journal+console
StandardError=journal+console

[Install]
WantedBy=multi-user.target
"""
    service_path = systemd_dir / "fry-first-boot.service"
    service_path.write_text(first_boot_service)
    print(f"Generated: {service_path}")


def main():
    """Main Fry configuration process."""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           Fry Networks Integration Configuration             ║
╚══════════════════════════════════════════════════════════════╝
""")

    base_config = load_config()

    WORK_DIR.mkdir(parents=True, exist_ok=True)

    generate_fry_config(base_config)
    generate_fry_services()
    generate_fry_scripts()
    generate_first_boot_service()

    print("\nFry Networks configuration complete!")
    print("\nServices configured:")
    print("  - fry-node.service       : Main Fry network node")
    print("  - bandwidth-miner.service: Bandwidth mining daemon")
    print("  - fry-dashboard.service  : Web dashboard (port 8080)")
    print("  - fry-update.timer       : Automatic update checks")
    print("  - fry-first-boot.service : First boot initialization")


if __name__ == "__main__":
    main()
