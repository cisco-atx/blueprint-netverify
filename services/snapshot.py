"""Snapshot collection service.

This module provides functionality for collecting network device
snapshots concurrently and storing command outputs in JSON format.
It uses a threaded execution model to improve collection speed across
multiple devices and supports proxy-based connectivity through
GenericHandler.

File Path: services/snapshot.py
"""

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from netcore import GenericHandler

logger = logging.getLogger(__name__)

class SnapshotService:
    """Service for collecting and storing network device snapshots."""

    REQUIRED_COMMANDS = [
        "show run",
        "show interface status",
        "show mac address-table dynamic",
        "show ip route",
        "show ip arp",
    ]

    def __init__(self, name, type, devices, connector, creator, dir, custom_commands=None):
        """Initialize the snapshot service."""
        self.name = name
        self.type = type
        self.devices = devices
        self.connector = connector
        self.creator = creator
        self.dir = dir
        self.custom_commands = custom_commands or []
        self.data = {}

    @property
    def commands(self):
        """Combined list of required + custom commands (deduplicated, order preserved)."""
        seen = set()
        combined = []
        for cmd in list(self.REQUIRED_COMMANDS) + list(self.custom_commands):
            cmd = cmd.strip()
            if cmd and cmd not in seen:
                seen.add(cmd)
                combined.append(cmd)
        return combined

    def create(self):
        """Create a snapshot file with collected device outputs."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H.%M")
        filename = f"{self.name}_{self.type}_{timestamp}.json"
        filepath = os.path.join(self.dir, filename)

        logger.info("Starting snapshot creation: %s", filename)

        self.data = {
            "meta": {
                "filename": filename,
                "name": self.name,
                "type": self.type,
                "creator": self.creator,
                "timestamp": timestamp,
                "required_commands": self.REQUIRED_COMMANDS,
                "custom_commands": self.custom_commands,
            },
            "devices": {},
        }

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {
                executor.submit(self._collect_outputs, device): device for device in self.devices
            }

            for future, device in futures.items():
                try:
                    logger.info("Collecting outputs from device: %s", device)
                    output = future.result()
                    self.data["devices"][device] = output
                except Exception as exc:
                    logger.exception("Error collecting data from %s: %s", device, exc)
                    self.data["devices"][device] = {"error": str(exc)}

        try:
            with open(filepath, "w", encoding="utf-8") as file:
                json.dump(self.data, file, indent=4)
        except OSError as exc:
            logger.exception("Failed to write snapshot file %s: %s", filepath, exc)
            raise

    def _collect_outputs(self, device):
        """Collect command outputs from a network device."""
        try:
            logger.info("Connecting to device: %s", device)
            handler = GenericHandler(
                hostname=device,
                username=self.connector["network_username"],
                password=self.connector["network_password"],
                proxy={
                    "hostname": self.connector["jumphost_ip"],
                    "username": self.connector["jumphost_username"],
                    "password": self.connector["jumphost_password"],
                },
                handler="NETMIKO",
            )
            logger.info("Connected to device successfully: %s", device)

            outputs = {}
            for command in self.commands:
                try:
                    response = handler.send_command(command).strip()
                    outputs[command] = response
                except Exception as cmd_exc:
                    logger.exception("Failed to run '%s' on %s", command, device)
                    outputs[command] = f"ERROR: {cmd_exc}"

            return {
                "base_prompt": handler.base_prompt,
                "device_type": handler.device_type,
                "outputs": outputs,
            }

        except Exception as exc:
            logger.exception("Error connecting to device %s: %s", device, exc)
            return {"error": str(exc)}