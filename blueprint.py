"""NetVerify Flask Blueprint module.

Provides the NetVerify Flask blueprint configuration, route registration,
and application directory setup for snapshots and reports.

File path: blueprint.py
"""
import os

from flask import Blueprint

from . import routes, services

class NetVerify(Blueprint):
    """Define the NetVerify Flask blueprint."""
    meta = {
        "name": "NetVerify",
        "description": "Compare Validate And Assure.",
        "version": "1.0.0",
        "icon": "netverify.ico",
        "url_prefix": "/netverify",
    }

    def __init__(self, **kwargs):
        """Initialize NetVerify blueprint with required setup."""
        super().__init__(
            "netverify",
            __name__,
            url_prefix="/netverify",
            template_folder="templates",
            static_folder="static",
            **kwargs,
        )

        self.routes = routes
        self.services = services

        self.setup_paths()
        self.setup_directories()
        self.setup_routes()

    def setup_paths(self):
        """Set up directory paths for NetVerify."""
        self.HOME_DIR = os.path.join(os.path.expanduser("~"), ".netverify",)
        self.SNAPSHOTS_DIR = os.path.join(self.HOME_DIR, "snapshots",)

    def setup_directories(self):
        """Ensure required directories exist."""
        directories = [
            self.HOME_DIR,
            self.SNAPSHOTS_DIR
        ]
        for directory in directories:
            os.makedirs(directory, exist_ok=True)

    def setup_routes(self):
        """Register application routes."""
        self.add_url_rule(
            "/",
            view_func=self.routes.render_snapshots,
            methods=["GET"],
        )

        self.add_url_rule(
            "/snapshots",
            view_func=self.routes.render_snapshots,
            methods=["GET"],
        )

        self.add_url_rule(
            "/api/snapshot/<filename>",
            view_func=self.routes.get_snapshot,
            methods=["GET"],
        )

        self.add_url_rule(
            "/api/snapshots",
            view_func=self.routes.list_snapshots,
            methods=["GET"],
        )

        self.add_url_rule(
            "/api/snapshots",
            view_func=self.routes.create_snapshot,
            methods=["POST"],
        )

        self.add_url_rule(
            "/api/snapshots",
            view_func=self.routes.delete_snapshot,
            methods=["DELETE"],
        )

        self.add_url_rule(
            "/api/snapshot/download/<filename>",
            view_func=self.routes.download_snapshot,
            methods=["GET"],
        )

        self.add_url_rule(
            "/api/validate",
            view_func=self.routes.validate_snapshots,
            methods=["POST"],
        )

        self.add_url_rule(
            "/api/reports",
            view_func=routes.list_reports,
            methods=["GET"]
        )

        self.add_url_rule(
            "/api/report/<filename>",
            view_func=routes.view_report,
            methods=["GET"]
        )

        self.add_url_rule(
            "/api/report/download/<filename>",
            view_func=routes.download_report,
            methods=["GET"]
        )

        self.add_url_rule(
            "/api/reports",
            view_func=routes.delete_report,
            methods=["DELETE"]
        )