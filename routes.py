"""
Routes for NetVerify snapshot management and rendering.

This module provides Flask route handlers for rendering pages,
creating snapshots, retrieving snapshot data, listing available
snapshots, and deleting snapshots. It interacts with the NetVerify
blueprint services and snapshot storage directory.

File Path: routes.py
"""

import json
import logging
import os
import zipfile

from datetime import datetime
from io import BytesIO

from flask import current_app, jsonify, render_template, request, session, send_file

logger = logging.getLogger(__name__)

def render_snapshots():
    """Render the snapshots page."""
    return render_template("netverify.html")


def get_snapshot(filename):
    """Retrieve a snapshot by filename."""
    netverify_bp = current_app.blueprints["netverify"]
    filepath = os.path.join(netverify_bp.SNAPSHOTS_DIR, filename)

    if not os.path.isfile(filepath):
        return jsonify({
            "success": False,
            "error": "Snapshot not found.",
        }), 404

    try:
        with open(filepath, "r", encoding="utf-8") as file:
            data = json.load(file)
        return jsonify({
            "success": True,
            "data": data,
        })

    except Exception as exc:
        logger.exception("Failed to load snapshot: %s",filename)
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500


def list_snapshots():
    """List all available snapshots."""
    netverify_bp = current_app.blueprints["netverify"]
    snapshots = []

    for filename in os.listdir(netverify_bp.SNAPSHOTS_DIR):
        if not filename.endswith(".json"):
            continue

        filepath = os.path.join(netverify_bp.SNAPSHOTS_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as file:
                data = json.load(file)

            meta = data.get("meta", {})
            meta["devices"] = []
            for device, info in data.get("devices", {}).items():
                meta["devices"].append(info.get("base_prompt", device))
            snapshots.append(meta)

        except Exception:
            logger.exception("Failed to process snapshot file: %s", filepath)

    snapshots.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return jsonify({
        "success": True,
        "data": snapshots,
    })


def delete_snapshot():
    """Delete a snapshot file."""
    payload = request.json or {}
    filename = payload.get("filename")

    if not filename:
        logger.warning("Delete snapshot request missing filename.")
        return jsonify({
            "success": False,
            "error": "Filename is required.",
        }), 400

    netverify_bp = current_app.blueprints["netverify"]
    filepath = os.path.join(netverify_bp.SNAPSHOTS_DIR,filename,)

    if not os.path.isfile(filepath):
        logger.warning("Snapshot not found for deletion: %s", filepath)
        return jsonify({
            "success": False,
            "error": "Snapshot not found.",
        }), 404

    try:
        os.remove(filepath)
        logger.info("Snapshot deleted successfully: %s", filename)
        return jsonify({
            "success": True,
            "message": "Snapshot deleted successfully.",
        })

    except Exception as exc:
        logger.exception("Failed to delete snapshot: %s",filename,)
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500


def create_snapshot():
    """Create a new snapshot."""
    payload = request.json or {}

    name = (payload.get("name") or "").strip()
    type = payload.get("type", "pre")
    devices = payload.get("devices", [])
    connector = payload.get("connector")

    if not name:
        return jsonify({
            "success": False,
            "error": "Snapshot name is required.",
        }), 400

    if not devices:
        return jsonify({
            "success": False,
            "error": "At least one device is required.",
        }), 400

    if not connector:
        return jsonify({
            "success": False,
            "error": "Connector is required.",
        }), 400
    netverify_bp = current_app.blueprints["netverify"]

    try:
        snapshot_service = netverify_bp.services.SnapshotService(
            name=name,
            type=type,
            devices=devices,
            connector=connector,
            creator=session.get("username", "anonymous"),
            dir=netverify_bp.SNAPSHOTS_DIR,
        )

        snapshot_service.create()
        logger.info("Snapshot created successfully: %s", name)
        return jsonify({
            "success": True,
            "data": snapshot_service.data["meta"],
        })

    except Exception as exc:
        logger.exception("Failed to create snapshot: %s", name)
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500


def download_snapshot(filename):
    """Download snapshot logs zip file."""
    netverify_bp = current_app.blueprints["netverify"]
    filepath = os.path.join(netverify_bp.SNAPSHOTS_DIR, filename)

    if not os.path.isfile(filepath):
        return jsonify({
            "success": False,
            "error": "Snapshot not found.",
        }), 404

    try:
        with open(filepath, "r", encoding="utf-8") as file:
            data = json.load(file)

        snapshot_name = data.get("meta", {}).get("name", "snapshot")
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            for device, info in data.get("devices", {}).items():
                base_prompt = info.get("base_prompt", device)
                log_filename = f"{snapshot_name}_{base_prompt}.log"
                log_content = ""
                for command, output in info.get("outputs", []).items():
                    log_content += f"{base_prompt}# {command}\n{output}\n"
                zip_file.writestr(log_filename, log_content)
        zip_buffer.seek(0)
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=f"{snapshot_name}_logs.zip",
            mimetype="application/zip"
        )
    except Exception as exc:
        logger.exception("Failed to create logs zip for snapshot: %s", filename)
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500

def validate_snapshots():
    """Validate snapshot data using the ValidationService."""
    payload = request.json or {}
    netverify_bp = current_app.blueprints["netverify"]
    reports_dir = os.path.join(session["userdata"].get("reports_dir"), "blueprint-netverify")
    try:
        service = netverify_bp.services.ValidationService(
            snapshots_dir=netverify_bp.SNAPSHOTS_DIR,
            reports_dir=reports_dir,
        )
        result = service.validate(payload)

        return jsonify(result)
    except Exception as exc:
        logger.exception("Validation failed")

        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500

def list_reports():
    """List all available validation reports."""
    reports_dir = os.path.join(session["userdata"].get("reports_dir"), "blueprint-netverify")
    os.makedirs(reports_dir, exist_ok=True)
    reports = []

    for filename in os.listdir(reports_dir):

        if not filename.endswith(".html"):
            continue

        filepath = os.path.join(reports_dir, filename)
        reports.append({
            "filename": filename,
            "date": datetime.fromtimestamp(os.path.getmtime(filepath)).strftime("%Y-%m-%d %H:%M:%S")
        })

    reports.sort(key=lambda x: x["date"], reverse=True)

    for report in reports:
        report["date"] = str(report["date"])

    return jsonify({
        "success": True,
        "data": reports
    })

def view_report(filename):
    """View a specific validation report by filename."""
    filepath = os.path.join(session["userdata"].get("reports_dir"), "blueprint-netverify", filename)
    if not os.path.isfile(filepath):
        return jsonify({
            "success": False,
            "error": "Report not found."
        }), 404

    with open(filepath, "r", encoding="utf-8") as file:
        html = file.read()

    return jsonify({
        "success": True,
        "html": html
    })

def download_report(filename):
    """Download a specific validation report by filename."""
    filepath = os.path.join(session["userdata"].get("reports_dir"), "blueprint-netverify", filename)
    return send_file(
        filepath,
        as_attachment=True
    )

def delete_report():
    """Delete a specific validation report by filename."""
    payload = request.json or {}
    filename = payload.get("filename")
    filepath = os.path.join(session["userdata"].get("reports_dir"), "blueprint-netverify", filename)

    if not os.path.isfile(filepath):
        return jsonify({
            "success": False,
            "error": "Report not found."
        }), 404

    os.remove(filepath)

    return jsonify({
        "success": True
    })