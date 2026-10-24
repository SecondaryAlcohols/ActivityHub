"""地理计算与 IP 网段校验。"""

from __future__ import annotations

import ipaddress
from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_M = 6_371_008.8


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """两点球面距离（米）。"""
    phi1, phi2 = radians(lat1), radians(lat2)
    d_phi = radians(lat2 - lat1)
    d_lambda = radians(lon2 - lon1)
    a = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(sqrt(a))


def parse_cidrs(values: list[str]) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    """解析 CIDR 列表，非法项直接忽略（写入时已做校验）。"""
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for value in values:
        try:
            networks.append(ipaddress.ip_network(value.strip(), strict=False))
        except ValueError:
            continue
    return networks


def ip_in_networks(ip: str, networks: list[str]) -> bool:
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False

    return any(
        address.version == network.version and address in network
        for network in parse_cidrs(networks)
    )


def normalize_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    try:
        return str(ipaddress.ip_address(ip))
    except ValueError:
        return None
