"""Guest Agent HTTP client for communicating with the Windows VM."""

from __future__ import annotations

import json
import logging
import urllib.request
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)

DEFAULT_PORT = 8765


@dataclass
class GuestApp:
    name: str
    path: str
    icon_b64: str = ""
    source: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> GuestApp:
        return cls(
            name=d.get("Name", ""),
            path=d.get("Path", ""),
            icon_b64=d.get("Icon", ""),
            source=d.get("Source", ""),
        )


class GuestClient:
    """HTTP client for the Windows guest agent."""

    def __init__(self, host: str = "127.0.0.1", port: int = DEFAULT_PORT, token: str = ""):
        self.base_url = f"http://{host}:{port}"
        self.token = token

    def health(self) -> bool:
        """Check if the guest agent is reachable."""
        try:
            req = urllib.request.Request(f"{self.base_url}/health")
            with urllib.request.urlopen(req, timeout=2) as resp:
                return resp.status == 200
        except Exception:
            return False

    def get_apps(self) -> list[GuestApp]:
        """Retrieve list of installed Windows applications."""
        data = self._get("/apps")
        if isinstance(data, list):
            return [GuestApp.from_dict(d) for d in data]
        return []

    def get_metrics(self) -> dict[str, Any]:
        """Get CPU/RAM/disk metrics from the guest."""
        return self._get("/metrics")  # type: ignore[return-value]

    def _get(self, path: str) -> Any:
        """Make an authenticated GET request."""
        req = urllib.request.Request(f"{self.base_url}{path}")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except Exception as e:
            log.warning("Guest agent request failed: %s", e)
            return {}

    def _post(self, path: str, data: dict[str, Any] | None = None) -> Any:
        """Make an authenticated POST request."""
        body = json.dumps(data or {}).encode()
        req = urllib.request.Request(
            f"{self.base_url}{path}", data=body, method="POST"
        )
        req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except Exception as e:
            log.warning("Guest agent POST failed: %s", e)
            return {}
