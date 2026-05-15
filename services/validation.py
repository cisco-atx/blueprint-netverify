"""Validation service for comparing network snapshots.

This module provides the ValidationService class, which orchestrates
the comparison of pre and post network snapshots. It supports
configuration diffing, endpoint validation, and route validation,
generating HTML reports of the differences found.

Reports are rendered using Flask templates and saved to disk.

Module path: services/validation.py
"""

import json
import os
from datetime import datetime

from flask import render_template

from .validators import ConfigDiffer, EndpointValidator, RouteValidator


class ValidationService:
    """Service for validating and comparing network snapshots."""

    def __init__(self, snapshots_dir, reports_dir):
        """Initialize with snapshot and report directory paths."""
        self.snapshots_dir = snapshots_dir
        self.reports_dir = reports_dir

    def validate(self, payload):
        """Run validation based on payload and generate a report."""
        pre_snapshot = self._load_snapshot(payload["pre_snapshot"])
        post_snapshot = self._load_snapshot(payload["post_snapshot"])

        report = {
            "meta": self._build_report_meta(pre_snapshot, post_snapshot),
            "sections": {},
        }

        config_compare = payload.get("config_compare")
        endpoint_compare = payload.get("endpoint_validation")
        route_compare = payload.get("route_validation")

        if config_compare:
            report["sections"]["config"] = self._run_config_validation(
                pre_snapshot, post_snapshot, config_compare
            )

        if endpoint_compare:
            report["sections"]["endpoint"] = self._run_endpoint_validation(
                pre_snapshot, post_snapshot, endpoint_compare
            )

        if route_compare:
            report["sections"]["route"] = self._run_route_validation(
                pre_snapshot, post_snapshot, route_compare
            )

        report_content = render_template("netverify.content.html", report=report)
        full_html = render_template("netverify.report.html", report=report)

        filename = f"{report['meta']['name']}.html"
        filepath = os.path.join(self.reports_dir, filename)

        with open(filepath, "w", encoding="utf-8") as file:
            file.write(full_html)

        return {
            "success": True,
            "report": {
                "filename": filename,
                "meta": report["meta"],
                "html": report_content,
            },
        }

    def _load_snapshot(self, filename):
        """Load and parse a snapshot JSON file."""
        filepath = os.path.join(self.snapshots_dir, filename)

        if not os.path.isfile(filepath):
            raise FileNotFoundError(
                f"Snapshot not found: {filename}"
            )

        with open(filepath, "r", encoding="utf-8") as file:
            return json.load(file)

    def _build_report_meta(self, pre_snapshot, post_snapshot):
        """Build metadata dictionary for the report."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H.%M")
        return {
            "name": (
                f"{pre_snapshot['meta']['name']}-pre"
                f"_vs_"
                f"{post_snapshot['meta']['name']}-post"
                f"_{timestamp}"
            ),
            "timestamp": timestamp,
            "pre_snapshot": pre_snapshot["meta"]["filename"],
            "post_snapshot": post_snapshot["meta"]["filename"],
        }

    def _run_config_validation(self, pre_snapshot, post_snapshot, config_compare):
        """Run configuration diff and return rendered HTML."""
        pre_device = config_compare.get("pre_device")
        post_device = config_compare.get("post_device")

        pre_config = pre_snapshot["devices"].get(pre_device, {}).get("outputs", {}).get("show run", "")
        post_config = post_snapshot["devices"].get(post_device, {}).get("outputs", {}).get("show run", "")

        differ = ConfigDiffer(pre_config=pre_config, post_config=post_config)
        differ.compare()

        return render_template(
            "netverify.content.config.html",
            pre_config=pre_config,
            post_config=post_config,
            diff_html=differ.render(),
        )

    def _run_endpoint_validation(self, pre_snapshot, post_snapshot, endpoint_compare):
        """Run endpoint validation and return rendered HTML."""
        validator = EndpointValidator(
            pre_snapshot=pre_snapshot,
            post_snapshot=post_snapshot,
            pre_devices=endpoint_compare.get("pre_devices", []),
            post_devices=endpoint_compare.get("post_devices", []),
        )
        validator.compare()

        return render_template(
            "netverify.content.endpoint.html",
            endpoints=validator.render(),
        )

    def _run_route_validation(self, pre_snapshot, post_snapshot, route_compare):
        """Run route validation and return rendered HTML."""
        validator = RouteValidator(
            pre_snapshot=pre_snapshot,
            post_snapshot=post_snapshot,
            pre_device=route_compare.get("pre_device"),
            post_device=route_compare.get("post_device"),
        )
        validator.compare()

        return render_template(
            "netverify.content.route.html",
            routes=validator.render(),
            pre_device=route_compare.get("pre_device"),
            post_device=route_compare.get("post_device"),
        )