import ipaddress
import os
from typing import Optional

_API_KEY = os.environ.get("MCP_API_KEY", "")
_ALLOWED_CIDR = [
    s.strip()
    for s in os.environ.get("MCP_ALLOWED_CIDRS", "10.0.0.0/8,192.168.0.0/16").split(",")
    if s.strip()
]
_NETWORKS = [ipaddress.ip_network(c, strict=False) for c in _ALLOWED_CIDR]


def verify_api_key(key: Optional[str]) -> None:
    if not _API_KEY:
        return  # not configured — allow (dev mode)
    if key != _API_KEY:
        raise PermissionError("Invalid API key")


def verify_ip(ip: Optional[str]) -> None:
    if not _NETWORKS or not ip:
        return  # not configured — allow (dev mode)
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        raise PermissionError(f"Invalid IP address: {ip}")
    if not any(addr in net for net in _NETWORKS):
        raise PermissionError(f"IP not allowed: {ip}")
