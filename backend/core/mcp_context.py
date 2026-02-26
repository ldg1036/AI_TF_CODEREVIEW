import json
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional


class MCPContextClient:
    """HTTP MCP context client (fail-soft)."""

    @staticmethod
    def _safe_int(value, fallback: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    def __init__(self, mcp_config: Optional[Dict[str, Any]] = None):
        cfg = mcp_config if isinstance(mcp_config, dict) else {}
        self.enabled_default = bool(cfg.get("enabled_default", False))
        self.url = str(cfg.get("url", "http://localhost:3000") or "http://localhost:3000").rstrip("/")
        self.timeout_sec = self._safe_int(cfg.get("timeout_sec", 2) or 2, 2)
        self.max_drivers_in_prompt = self._safe_int(cfg.get("max_drivers_in_prompt", 20) or 20, 20)

    def _get_json(self, endpoint: str) -> Dict[str, Any]:
        req = urllib.request.Request(
            url=f"{self.url}{endpoint}",
            method="GET",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
            raw = resp.read().decode("utf-8")
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise RuntimeError(f"Invalid MCP payload at {endpoint}")
        return parsed

    @staticmethod
    def _normalize_project(payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return {}
        return payload

    @staticmethod
    def _normalize_drivers(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        drivers = payload.get("drivers", payload)
        if isinstance(drivers, list):
            normalized = [item for item in drivers if isinstance(item, dict)]
            return normalized
        return []

    def fetch_context(self) -> Dict[str, Any]:
        """Fetch MCP context in fail-soft mode."""
        result = {
            "enabled": False,
            "project": {},
            "drivers": [],
            "error": None,
        }
        try:
            project_payload = self._get_json("/context")
            drivers_payload = self._get_json("/drivers")
            drivers = self._normalize_drivers(drivers_payload)
            if self.max_drivers_in_prompt > 0:
                drivers = drivers[: self.max_drivers_in_prompt]
            result["project"] = self._normalize_project(project_payload)
            result["drivers"] = drivers
            result["enabled"] = True
            return result
        except Exception as exc:
            result["error"] = str(exc)
            return result
