"""Route validator for comparing routing table snapshots.

This module provides the RouteValidator class, which builds
route maps from pre and post network snapshots for a single
device on each side, compares them by CIDR prefix, and
identifies changes in next-hops, protocols, and interfaces.

It uses TextFSM parsing for structured data extraction from
'show ip route' command outputs.

Module path: services/validators/route.py
"""

import re

from netcore import AutoParseTextFSM


class RouteValidator:
    """Validate and compare routes between two snapshots (single device per side)."""

    def __init__(self, pre_snapshot, post_snapshot, pre_device, post_device):
        """Initialize with pre/post snapshots and device names."""
        self.pre_snapshot = pre_snapshot
        self.post_snapshot = post_snapshot
        self.pre_device = pre_device
        self.post_device = post_device

        self.pre_routes = {}
        self.post_routes = {}

        self.results = []

    def compare(self):
        """Compare pre and post routes and populate results."""
        self.pre_routes = self._build_route_map(snapshot=self.pre_snapshot, device_name=self.pre_device)
        self.post_routes = self._build_route_map(snapshot=self.post_snapshot, device_name=self.post_device)
        all_prefixes = sorted(set(self.pre_routes.keys()) | set(self.post_routes.keys()))

        self.results = [
            self._build_result(
                prefix,
                self.pre_routes.get(prefix),
                self.post_routes.get(prefix),
            )
            for prefix in all_prefixes
        ]

    def render(self):
        """Return the comparison results."""
        return self.results

    def _build_result(self, prefix, pre, post):
        """Build a comparison result dict for a single prefix."""
        # Route only in PRE
        if pre and not post:
            return {
                "prefix": prefix,
                "status": "absent",
                "has_changes": False,
                "nexthops": self._diff_nexthops(pre.get("nexthops", []), []),
            }

        # Route only in POST
        if post and not pre:
            return {
                "prefix": prefix,
                "status": "new",
                "has_changes": True,
                "nexthops": self._diff_nexthops([], post.get("nexthops", [])),
            }

        # Present in BOTH - compare next-hop sets
        pre_nh = pre.get("nexthops", [])
        post_nh = post.get("nexthops", [])
        nexthops = self._diff_nexthops(pre_nh, post_nh)

        has_changes = any(nh["status"] != "same" for nh in nexthops)

        return {
            "prefix": prefix,
            "status": "present",
            "has_changes": has_changes,
            "nexthops": nexthops,
        }

    def _diff_nexthops(self, pre_list, post_list):
        """Diff two lists of next-hops, returning per-nexthop status."""
        def signature(nh):
            return (
                nh.get("nexthop"),
                nh.get("interface"),
                nh.get("protocol"),
                nh.get("vrf"),
            )

        pre_map = {signature(nh): nh for nh in pre_list}
        post_map = {signature(nh): nh for nh in post_list}

        all_sigs = set(pre_map.keys()) | set(post_map.keys())

        results = []
        for sig in all_sigs:
            pre_nh = pre_map.get(sig)
            post_nh = post_map.get(sig)

            if pre_nh and not post_nh:
                results.append({"pre": pre_nh, "post": None, "status": "missing"})
            elif post_nh and not pre_nh:
                results.append({"pre": None, "post": post_nh, "status": "new"})
            else:
                results.append({"pre": pre_nh, "post": post_nh, "status": "same"})

        return results

    def _build_route_map(self, snapshot, device_name):
        """Build a CIDR-prefix-to-route mapping from a single device snapshot."""
        routes = {}

        if not device_name:
            return routes

        device = snapshot["devices"].get(device_name)

        if not device:
            return routes

        output = device.get("outputs", {}).get("show ip route", "")
        device_type = device.get("device_type")

        if device_type == "cisco_nxos":
            # Regex 1: Matches the Prefix line
            prefix_pattern = re.compile(r'^(\d{1,3}(?:\.\d{1,3}){3}/\d{1,2})')

            # Regex 2: Matches the Next-Hop details
            nh_pattern = re.compile(r'\*?via\s+([^\s,]+)(?:,\s+([a-zA-Z][^\s,]*))?,\s+\[[^\]]+\],\s+[^,]+,\s+([^\s,]+)')

            current_prefix = None
            for line in output.splitlines():
                line = line.strip()
                if not line:
                    continue

                p_match = prefix_pattern.match(line)
                if p_match:
                    current_prefix = p_match.group(1)
                    routes[current_prefix] = {"prefix": current_prefix, "nexthops": []}
                    continue

                if current_prefix:
                    n_match = nh_pattern.search(line)
                    if n_match:
                        routes[current_prefix]["nexthops"].append({
                            "nexthop": n_match.group(1),
                            "interface": n_match.group(2),
                            "protocol": n_match.group(3),
                            "vrf": None
                        })
        else:
            route_table = AutoParseTextFSM(
                raw_string=output,
                cmd="show ip route",
                device_type=device_type,
                key="network",
            ).parse()

            for raw_prefix, route_data in route_table.items():
                prefix = self._build_cidr(raw_prefix, route_data)

                if not prefix:
                    continue

                nexthops = self._extract_nexthops(route_data)

                if not nexthops:
                    continue

                routes[prefix] = {
                    "prefix": prefix,
                    "nexthops": nexthops,
                }

        return routes

    @staticmethod
    def _build_cidr(raw_prefix, route_data):
        """Return prefix in CIDR form: network/mask.

        Handles templates that already give CIDR in the network field
        as well as templates that provide network and mask separately.
        """
        if not raw_prefix:
            return None

        # Already in CIDR form
        if "/" in str(raw_prefix):
            return str(raw_prefix)

        mask = route_data.get("mask") or route_data.get("prefix_length") or route_data.get("prefixlen")

        if mask:
            return f"{raw_prefix}/{mask}"

        return str(raw_prefix)

    @staticmethod
    def _extract_nexthops(route_data):
        """Extract a list of nexthop dicts from a parsed route entry.

        Handles both single-value and list-value (ECMP) fields produced
        by various TextFSM templates. Metric is intentionally excluded.
        """
        def as_list(value):
            if value is None or value == "":
                return []
            if isinstance(value, list):
                return value
            return [value]

        nexthop_ips = as_list(route_data.get("nexthop_ip") or route_data.get("nexthop"))
        interfaces = as_list(route_data.get("nexthop_if") or route_data.get("interface"))
        protocols = as_list(route_data.get("protocol") or route_data.get("type"))
        vrfs = as_list(route_data.get("vrf"))

        count = max(
            len(nexthop_ips),
            len(interfaces),
            len(protocols),
            1 if (nexthop_ips or interfaces or protocols) else 0,
        )

        def at(lst, i):
            if not lst:
                return None
            if i < len(lst):
                return lst[i]
            return lst[0] if len(lst) == 1 else None

        nexthops = []
        for i in range(count):
            nexthops.append({
                "nexthop": at(nexthop_ips, i),
                "interface": at(interfaces, i),
                "protocol": at(protocols, i),
                "vrf": at(vrfs, i),
            })

        return nexthops