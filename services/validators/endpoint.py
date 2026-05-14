"""Endpoint validator for comparing network endpoint snapshots.

This module provides the EndpointValidator class, which builds
endpoint maps from pre and post network snapshots, compares them
by MAC address, and identifies changes in fields such as VLAN,
IP address, hostname, device, interface, speed, and duplex.

It uses TextFSM parsing for structured data extraction from
command outputs and supports DNS resolution with caching.

Module path: services/validators/endpoint.py
"""

import socket

from netcore import AutoParseTextFSM


class EndpointValidator:
    """Validate and compare endpoints between two snapshots."""

    COMPARE_FIELDS = [
        "vlan",
        "ip_address",
        "hostname",
        "device",
        "interface",
        "speed",
        "duplex",
    ]

    def __init__(self, pre_snapshot, post_snapshot, pre_devices, post_devices):
        """Initialize with pre/post snapshots and device lists."""
        self.pre_snapshot = pre_snapshot
        self.post_snapshot = post_snapshot
        self.pre_devices = pre_devices
        self.post_devices = post_devices

        self.pre_endpoints = {}
        self.post_endpoints = {}

        self.results = []
        self.dns_cache = {}

    def compare(self):
        """Compare pre and post endpoints and populate results."""
        self.pre_endpoints = self._build_endpoint_map(snapshot=self.pre_snapshot, devices=self.pre_devices)
        self.post_endpoints = self._build_endpoint_map(snapshot=self.post_snapshot, devices=self.post_devices)
        all_macs = sorted(set(self.pre_endpoints.keys())| set(self.post_endpoints.keys()))

        self.results = [
            self._build_result(
                mac,
                self.pre_endpoints.get(mac),
                self.post_endpoints.get(mac),
            )
            for mac in all_macs
        ]

    def render(self):
        """Return the comparison results."""
        return self.results

    def _build_result(self, mac, pre, post):
        """Build a comparison result dict for a single MAC."""
        # MAC only in PRE
        if pre and not post:
            return {
                "mac": mac,
                "status": "absent",
                "has_changes": False,
                "fields": {
                    field: self._build_field(
                        pre.get(field), None
                    )
                    for field in self.COMPARE_FIELDS
                },
            }

        # MAC only in POST
        if post and not pre:
            return {
                "mac": mac,
                "status": "new",
                "has_changes": False,
                "fields": {
                    field: self._build_field(
                        None, post.get(field)
                    )
                    for field in self.COMPARE_FIELDS
                },
            }

        # Present in BOTH
        fields = {}
        has_changes = False

        for field in self.COMPARE_FIELDS:
            field_result = self._build_field(pre.get(field), post.get(field))

            if field_result["status"] == "changed":
                has_changes = True

            fields[field] = field_result

        return {
            "mac": mac,
            "status": "present",
            "has_changes": has_changes,
            "fields": fields,
        }

    def _build_field(self, pre, post):
        """Build a field comparison dict with status."""
        if pre and not post:
            return {"pre": pre, "post": None, "status": "missing"}

        if post and not pre:
            return {"pre": None, "post": post, "status": "new"}

        if pre != post:
            return {"pre": pre, "post": post, "status": "changed"}

        return {"pre": pre, "post": post, "status": "same"}

    def _build_endpoint_map(self, snapshot, devices):
        """Build a MAC-to-endpoint mapping from a snapshot."""
        endpoints = {}

        for device_name in devices:
            device = snapshot["devices"].get(device_name)

            if not device:
                continue

            outputs = device.get("outputs", {})
            device_type = device.get("device_type")

            mac_table = AutoParseTextFSM(
                raw_string=outputs.get("show mac address-table dynamic", ""),
                cmd="show mac address-table",
                device_type=device_type,
                key="mac_address",
            ).parse()

            arp_table = AutoParseTextFSM(
                raw_string=outputs.get("show ip arp", ""),
                cmd="show ip arp",
                device_type=device_type,
                key="mac_address",
            ).parse()

            interface_status = AutoParseTextFSM(
                raw_string=outputs.get("show interface status", ""),
                cmd="show interface status",
                device_type=device_type,
                key="interface",
            ).parse()

            for mac, mac_data in mac_table.items():
                if mac_data.get("type", "").lower() != "dynamic":
                    continue

                normalized_mac = self._normalize_mac(mac)
                port = mac_data.get("ports")
                vlan = mac_data.get("vlan")
                ip_address = (arp_table.get(normalized_mac, {}).get("ip_address"))
                interface = (interface_status.get(port, {}).get("interface"))

                endpoint = {
                    "vlan": vlan,
                    "device": snapshot["devices"][device_name].get("base_prompt") or device_name,
                    "ip_address": ip_address,
                    "hostname": self._resolve_hostname(ip_address),
                    "interface": interface,
                    "speed": interface_status.get(interface, {}).get("speed"),
                    "duplex": interface_status.get(interface, {}).get("duplex"),
                }
                endpoints[normalized_mac] = endpoint

        return endpoints

    def _resolve_hostname(self, ip_address):
        """Resolve hostname for an IP address with caching."""
        if not ip_address:
            return None

        if ip_address in self.dns_cache:
            return self.dns_cache[ip_address]
        try:
            # hostname = socket.getfqdn(ip_address)
            # if hostname == ip_address:
            #     hostname = None
            hostname = None
        except Exception:
            hostname = None

        self.dns_cache[ip_address] = hostname
        return hostname

    @staticmethod
    def _normalize_mac(mac):
        """Normalize a MAC address to dotted format."""
        if not mac:
            return None

        mac = mac.lower().replace(":", "").replace("-", "").replace(".", "")

        if len(mac) != 12:
            return None

        return f"{mac[0:4]}.{mac[4:8]}.{mac[8:12]}"
