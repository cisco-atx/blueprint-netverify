import json
import logging
import os
from datetime import datetime

from flask import render_template

from .validators import ConfigDiffer

class ValidationService:
    def __init__(self, snapshots_dir, reports_dir):
        self.snapshots_dir = snapshots_dir
        self.reports_dir = reports_dir

    def validate(self, payload):
        pre_snapshot = self._load_snapshot(payload["pre_snapshot"])
        post_snapshot = self._load_snapshot(payload["post_snapshot"])

        report = {
            "meta": self._build_report_meta(pre_snapshot, post_snapshot),
            "sections": {}
        }

        config_compare = payload.get("config_compare")

        if config_compare:
            report["sections"]["config"] = self._run_config_validation(pre_snapshot, post_snapshot, config_compare)

        report_content = render_template("netverify.content.html",report=report)
        full_html = render_template("netverify.report.html",report=report)

        filename = f"{report['meta']['name']}.html"
        filepath = os.path.join(self.reports_dir, filename)

        with open(filepath, "w", encoding="utf-8") as file:
            file.write(full_html)

        return {
            "success": True,
            "report": {
                "filename": filename,
                "meta": report["meta"],
                "html": report_content
            }
        }

    def _load_snapshot(self, filename):
        filepath = os.path.join(self.snapshots_dir, filename)
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"Snapshot not found: {filename}")

        with open(filepath, "r", encoding="utf-8") as file:
            return json.load(file)

    def _run_config_validation(self, pre_snapshot, post_snapshot, config_compare):
        pre_device = config_compare.get("pre_device")
        post_device = config_compare.get("post_device")
        pre_config = (pre_snapshot["devices"].get(pre_device, {}).get("outputs", {}).get("show run", ""))
        post_config = (post_snapshot["devices"].get(post_device, {}).get("outputs", {}).get("show run", ""))

        differ = ConfigDiffer(pre_config=pre_config, post_config=post_config)
        differ.compare()

        return render_template(
            "netverify.content.config.html",
            pre_config=pre_config,
            post_config=post_config,
            diff_html=differ.render()
        )

    def _build_report_meta(self, pre_snapshot, post_snapshot):
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
            "post_snapshot": post_snapshot["meta"]["filename"]
        }