#!/usr/bin/env python3
"""
Fry IoT Network Configuration Tool

Generates systemd-networkd configuration files for IoT devices.
"""

import os
import sys
from pathlib import Path

import toml

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
PROFILES_DIR = PROJECT_ROOT / "profiles"
WORK_DIR = PROJECT_ROOT / "work"


def load_profile_config(profile_name: str):
    """Load profile-specific configuration."""
    profile_path = PROFILES_DIR / profile_name / "profile-config.toml"
    if not profile_path.exists():
        print(f"Error: Profile '{profile_name}' not found at {profile_path}")
        sys.exit(1)
    with open(profile_path) as f:
        return toml.load(f)


def generate_network_configs(profile_config: dict, profile_name: str):
    """Generate systemd-networkd configuration files."""
    network_dir = WORK_DIR / "files" / "etc" / "systemd" / "network"
    network_dir.mkdir(parents=True, exist_ok=True)

    network_config = profile_config.get("network", {})

    # Generate ethernet configuration
    eth_config = network_config.get("ethernet", {})
    eth_interface = eth_config.get("interface", "eth0")
    eth_dhcp = eth_config.get("dhcp", True)

    eth_network = f"""[Match]
Name={eth_interface}

[Network]
"""
    if eth_dhcp:
        eth_network += "DHCP=yes\n"
    else:
        eth_network += f"""Address={eth_config.get('address', '192.168.1.1/24')}
Gateway={eth_config.get('gateway', '192.168.1.254')}
DNS={eth_config.get('dns', '8.8.8.8')}
"""

    eth_path = network_dir / "10-ethernet.network"
    eth_path.write_text(eth_network)
    print(f"Generated: {eth_path}")

    # Generate wireless configuration if enabled
    wifi_config = network_config.get("wifi", {})
    if wifi_config.get("enabled", False):
        wifi_interface = wifi_config.get("interface", "wlan0")

        wifi_network = f"""[Match]
Name={wifi_interface}

[Network]
DHCP=yes
"""
        wifi_path = network_dir / "20-wireless.network"
        wifi_path.write_text(wifi_network)
        print(f"Generated: {wifi_path}")

    # Generate bridge configuration if needed
    bridge_config = network_config.get("bridge", {})
    if bridge_config.get("enabled", False):
        bridge_name = bridge_config.get("name", "br0")
        bridge_members = bridge_config.get("members", ["eth0"])

        # Bridge netdev
        bridge_netdev = f"""[NetDev]
Name={bridge_name}
Kind=bridge
"""
        netdev_path = network_dir / "05-bridge.netdev"
        netdev_path.write_text(bridge_netdev)
        print(f"Generated: {netdev_path}")

        # Bridge network
        bridge_network = f"""[Match]
Name={bridge_name}

[Network]
"""
        if bridge_config.get("dhcp", True):
            bridge_network += "DHCP=yes\n"
        else:
            bridge_network += f"""Address={bridge_config.get('address', '192.168.1.1/24')}
Gateway={bridge_config.get('gateway', '192.168.1.254')}
"""
        bridge_network_path = network_dir / "15-bridge.network"
        bridge_network_path.write_text(bridge_network)
        print(f"Generated: {bridge_network_path}")

        # Member interfaces
        for i, member in enumerate(bridge_members):
            member_network = f"""[Match]
Name={member}

[Network]
Bridge={bridge_name}
"""
            member_path = network_dir / f"10-{member}.network"
            member_path.write_text(member_network)
            print(f"Generated: {member_path}")

    # Generate VLAN configurations if defined
    vlans = network_config.get("vlans", [])
    for vlan in vlans:
        vlan_id = vlan.get("id")
        vlan_name = vlan.get("name", f"vlan{vlan_id}")
        parent = vlan.get("parent", "eth0")

        # VLAN netdev
        vlan_netdev = f"""[NetDev]
Name={vlan_name}
Kind=vlan

[VLAN]
Id={vlan_id}
"""
        netdev_path = network_dir / f"05-{vlan_name}.netdev"
        netdev_path.write_text(vlan_netdev)
        print(f"Generated: {netdev_path}")

        # VLAN network
        vlan_network = f"""[Match]
Name={vlan_name}

[Network]
"""
        if vlan.get("dhcp", False):
            vlan_network += "DHCP=yes\n"
        else:
            vlan_network += f"""Address={vlan.get('address', f'192.168.{vlan_id}.1/24')}
"""
        vlan_network_path = network_dir / f"20-{vlan_name}.network"
        vlan_network_path.write_text(vlan_network)
        print(f"Generated: {vlan_network_path}")


def generate_hostapd_config(profile_config: dict):
    """Generate hostapd configuration for AP mode."""
    hostapd_config = profile_config.get("hostapd", {})
    if not hostapd_config.get("enabled", False):
        return

    hostapd_dir = WORK_DIR / "files" / "etc" / "hostapd"
    hostapd_dir.mkdir(parents=True, exist_ok=True)

    ssid = hostapd_config.get("ssid", "FryIoT")
    password = hostapd_config.get("password", "frynetwork")
    interface = hostapd_config.get("interface", "wlan0")
    channel = hostapd_config.get("channel", 6)
    hw_mode = hostapd_config.get("hw_mode", "g")

    config = f"""interface={interface}
driver=nl80211
ssid={ssid}
hw_mode={hw_mode}
channel={channel}
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase={password}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
"""

    config_path = hostapd_dir / "hostapd.conf"
    config_path.write_text(config)
    print(f"Generated: {config_path}")


def generate_dnsmasq_config(profile_config: dict):
    """Generate dnsmasq configuration for DHCP server."""
    dnsmasq_config = profile_config.get("dnsmasq", {})
    if not dnsmasq_config.get("enabled", False):
        return

    dnsmasq_dir = WORK_DIR / "files" / "etc" / "dnsmasq.d"
    dnsmasq_dir.mkdir(parents=True, exist_ok=True)

    interface = dnsmasq_config.get("interface", "eth0")
    dhcp_range = dnsmasq_config.get("dhcp_range", "192.168.1.50,192.168.1.150,12h")

    config = f"""interface={interface}
dhcp-range={dhcp_range}
dhcp-option=option:router,{dnsmasq_config.get('gateway', '192.168.1.1')}
dhcp-option=option:dns-server,{dnsmasq_config.get('dns', '8.8.8.8,8.8.4.4')}
"""

    config_path = dnsmasq_dir / "fry-iot.conf"
    config_path.write_text(config)
    print(f"Generated: {config_path}")


def main():
    """Main network configuration process."""
    profile_name = os.environ.get("PROFILE")
    if not profile_name:
        print("Error: PROFILE environment variable not set")
        print("Usage: PROFILE=<profile-name> python configure-network.py")
        sys.exit(1)

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║             Fry IoT Network Configuration Tool               ║
╚══════════════════════════════════════════════════════════════╝
""")

    print(f"Configuring network for profile: {profile_name}")

    profile_config = load_profile_config(profile_name)

    WORK_DIR.mkdir(parents=True, exist_ok=True)

    generate_network_configs(profile_config, profile_name)
    generate_hostapd_config(profile_config)
    generate_dnsmasq_config(profile_config)

    print("\nNetwork configuration complete!")


if __name__ == "__main__":
    main()
