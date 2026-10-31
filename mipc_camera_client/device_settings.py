"""Small, credential-free views of firmware settings."""

import re
from dataclasses import dataclass
from ipaddress import IPv4Address


@dataclass(frozen=True)
class NetworkInterface:
    """One reported interface, not a guessed default route."""

    token: str
    connection: str
    enabled: bool | None
    link_status: str | None
    mac_address: str | None
    ip_address: str | None


def network_interfaces(document: dict) -> tuple[NetworkInterface, ...]:
    """Exclude Wi-Fi keys, SSIDs and nearby APs from a network response."""
    result = []
    interfaces = document.get("ifs")
    if not isinstance(interfaces, list):
        return ()
    for item in interfaces:
        if not isinstance(item, dict) or not isinstance(item.get("token"), str):
            continue
        phy = item.get("phy", {})
        phy = phy.get("info", {}) if isinstance(phy, dict) else {}
        phy = phy if isinstance(phy, dict) else {}
        ipv4 = item.get("ipv4", {})
        ipv4 = ipv4.get("info", {}) if isinstance(ipv4, dict) else {}
        ipv4 = ipv4 if isinstance(ipv4, dict) else {}
        ip = ipv4.get("ip", {})
        address = ip.get("addr") if isinstance(ip, dict) else None
        try:
            address = str(IPv4Address(address)) if isinstance(address, str) else None
        except ValueError:
            address = None
        mac = phy.get("mac")
        if not isinstance(mac, str) or not re.fullmatch(
            r"(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}", mac
        ):
            mac = None
        enabled = item.get("enabled")
        status = phy.get("stat")
        # The client distinguishes interfaces by their configuration structure.
        connection = (
            "wifi"
            if "wifi_client" in item
            else "ethernet"
            if item["token"] == "eth0"
            else "unknown"
        )
        result.append(
            NetworkInterface(
                item["token"],
                connection,
                bool(enabled)
                if type(enabled) in (bool, int) and enabled in (0, 1)
                else None,
                status if isinstance(status, str) else None,
                mac.lower().replace("-", ":") if mac else None,
                address,
            )
        )
    return tuple(result)


def recording_mode(document: dict) -> str | None:
    """SD recording task mode; unrelated to external recording-box APIs."""
    task = document.get("task")
    schedule = task.get("sch") if isinstance(task, dict) else None
    if not isinstance(schedule, dict):
        return None
    enabled, full = schedule.get("enable"), schedule.get("full_time")
    if type(enabled) not in (int, bool) or enabled not in (0, 1):
        return None
    if not enabled:
        return "off"
    if type(full) not in (int, bool) or full not in (0, 1):
        return None
    return "continuous" if full else "scheduled"
