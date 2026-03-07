import argparse
import datetime
import json
import math
import os
import re
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import parse_qs, urlparse


BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from core.heuristic_checker import HeuristicChecker


def _utc_now() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    text = str(value).strip()
    return text == "" or text.lower() in {"nan", "none"}


def _normalize_text(value: Any) -> str:
    return re.sub(r"[\s\r\n]+", "", str(value or "")).lower()


def _load_json(path: str, default: Any) -> Any:
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return default


def _relpath_or_abs(path: str, root: str) -> str:
    try:
        return os.path.relpath(path, root)
    except Exception:
        return path


def _default_template_coverage_loader(project_root: str) -> Dict[str, Any]:
    from tools import analyze_template_coverage as coverage_tool

    if coverage_tool.load_workbook is None:
        raise RuntimeError("openpyxl is required for template coverage")

    config = coverage_tool._load_config(project_root)
    paths = config.get("paths", {}) if isinstance(config.get("paths"), dict) else {}

    parsed_rules_path = os.path.join(project_root, "Config", "parsed_rules.json")
    if not os.path.exists(parsed_rules_path):
        raise FileNotFoundError(f"parsed_rules.json not found: {parsed_rules_path}")

    client_template = os.path.join(project_root, str(paths.get("client_template", "")))
    server_template = os.path.join(project_root, str(paths.get("server_template", "")))
    if not os.path.exists(client_template):
        raise FileNotFoundError(f"Client template not found: {client_template}")
    if not os.path.exists(server_template):
        raise FileNotFoundError(f"Server template not found: {server_template}")

    rules_by_type = coverage_tool._load_rules_by_type(parsed_rules_path)
    client_rows = coverage_tool._extract_template_rows(client_template)
    server_rows = coverage_tool._extract_template_rows(server_template)

    return {
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "inputs": {
            "parsed_rules": os.path.relpath(parsed_rules_path, project_root),
            "client_template": os.path.relpath(client_template, project_root),
            "server_template": os.path.relpath(server_template, project_root),
        },
        "coverage": {
            "Client": coverage_tool._analyze_one(rules_by_type.get("Client", []), client_rows),
            "Server": coverage_tool._analyze_one(rules_by_type.get("Server", []), server_rows),
        },
    }


class WinCCOAContextProvider:
    """Read-only HTTP context provider used by MCPContextClient fail-soft integration."""

    def __init__(
        self,
        project_root: Optional[str] = None,
        template_coverage_loader: Optional[Callable[[str], Dict[str, Any]]] = None,
    ):
        self.project_root = os.path.abspath(project_root or PROJECT_ROOT)
        self.config_path = os.path.join(self.project_root, "Config", "config.json")
        self.rules_path = os.path.join(self.project_root, "Config", "parsed_rules.json")
        self.applicability_path = os.path.join(self.project_root, "Config", "review_applicability.json")
        self.template_coverage_loader = template_coverage_loader or _default_template_coverage_loader
        self._cache_lock = threading.Lock()
        self._template_coverage_cache: Optional[Dict[str, Any]] = None
        self._template_coverage_error: Optional[str] = None
        self._template_coverage_checked_at: Optional[str] = None

        self.config = _load_json(self.config_path, {})
        if not isinstance(self.config, dict):
            self.config = {}
        self.parsed_rules = _load_json(self.rules_path, [])
        if not isinstance(self.parsed_rules, list):
            self.parsed_rules = []
        self.applicability = _load_json(self.applicability_path, {})
        if not isinstance(self.applicability, dict):
            self.applicability = {}

        self._technical_patterns = self._load_technical_patterns()
        self._build_indexes()

    def _load_technical_patterns(self) -> Dict[str, Dict[str, Any]]:
        try:
            checker = HeuristicChecker(self.rules_path)
            patterns = getattr(checker, "technical_patterns", {})
            return patterns if isinstance(patterns, dict) else {}
        except Exception:
            return {}

    def _build_indexes(self) -> None:
        self.rows_by_item_norm: Dict[str, List[Dict[str, Any]]] = {}
        self.item_display_by_norm: Dict[str, str] = {}
        self.item_types_by_norm: Dict[str, set] = {}
        self.categories_by_type: Dict[str, Dict[str, int]] = {"Client": {}, "Server": {}}
        self.rows_by_type: Dict[str, int] = {"Client": 0, "Server": 0}

        for row in self.parsed_rules:
            if not isinstance(row, dict):
                continue
            rule_type = str(row.get("type") or "").strip()
            if rule_type not in ("Client", "Server"):
                continue
            item_value = row.get("item")
            if _is_empty_value(item_value):
                continue
            item_text = str(item_value).strip()
            norm_item = _normalize_text(item_text)
            if not norm_item:
                continue

            self.rows_by_type[rule_type] = self.rows_by_type.get(rule_type, 0) + 1
            category = str(row.get("category") or "").strip()
            if category:
                bucket = self.categories_by_type.setdefault(rule_type, {})
                bucket[category] = int(bucket.get(category, 0)) + 1

            self.item_display_by_norm.setdefault(norm_item, item_text)
            self.item_types_by_norm.setdefault(norm_item, set()).add(rule_type)
            self.rows_by_item_norm.setdefault(norm_item, []).append(self._compact_rule_row(row))

        raw_items = self.applicability.get("items", {})
        if not isinstance(raw_items, dict):
            raw_items = {}

        self.rule_ids_by_item_norm: Dict[str, List[str]] = {}
        self.items_by_rule_id: Dict[str, List[str]] = {}
        for item_name, cfg in raw_items.items():
            if _is_empty_value(item_name) or not isinstance(cfg, dict):
                continue
            norm_item = _normalize_text(item_name)
            if not norm_item:
                continue
            rule_ids_raw = cfg.get("required_rule_ids", [])
            if not isinstance(rule_ids_raw, list):
                continue

            cleaned_ids: List[str] = []
            for rule_id in rule_ids_raw:
                value = str(rule_id or "").strip().upper()
                if not value:
                    continue
                if value not in cleaned_ids:
                    cleaned_ids.append(value)
                self.items_by_rule_id.setdefault(value, [])
                if norm_item not in [_normalize_text(item) for item in self.items_by_rule_id[value]]:
                    self.items_by_rule_id[value].append(str(item_name).strip())
            if cleaned_ids:
                self.rule_ids_by_item_norm[norm_item] = cleaned_ids

        self._rule_ids_sorted = sorted(self.items_by_rule_id.keys())

    def _compact_rule_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        checkpoints: List[str] = []
        raw_checkpoints = row.get("check_points", [])
        if isinstance(raw_checkpoints, list):
            for item in raw_checkpoints[:5]:
                if isinstance(item, dict):
                    content = item.get("content")
                    if not _is_empty_value(content):
                        checkpoints.append(str(content).strip())
        payload = {
            "type": str(row.get("type") or "").strip(),
            "category": str(row.get("category") or "").strip(),
            "sub_category": str(row.get("sub_category") or "").strip(),
            "item": "" if _is_empty_value(row.get("item")) else str(row.get("item")).strip(),
            "check_points": checkpoints,
        }
        raw_criteria = row.get("raw_criteria")
        if not _is_empty_value(raw_criteria):
            payload["raw_criteria"] = str(raw_criteria).strip()[:1200]
        return payload

    def _mcp_config_summary(self) -> Dict[str, Any]:
        cfg = self.config.get("mcp", {})
        if not isinstance(cfg, dict):
            cfg = {}
        return {
            "enabled_default": bool(cfg.get("enabled_default", False)),
            "url": str(cfg.get("url", "http://localhost:3000") or "http://localhost:3000"),
            "timeout_sec": int(cfg.get("timeout_sec", 2) or 2),
            "max_drivers_in_prompt": int(cfg.get("max_drivers_in_prompt", 20) or 20),
        }

    def _paths_summary(self) -> Dict[str, Any]:
        cfg_paths = self.config.get("paths", {})
        if not isinstance(cfg_paths, dict):
            cfg_paths = {}
        summary = {}
        for key, value in cfg_paths.items():
            if not isinstance(value, str):
                continue
            summary[key] = value
        return summary

    def list_review_drivers(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "PROJECT_CONTEXT",
                "kind": "resource",
                "uri": "resource://project/context",
                "endpoint": "/resources/project/context",
                "read_only": True,
            },
            {
                "name": "RULE_INDEX",
                "kind": "resource",
                "uri": "resource://rules/index",
                "endpoint": "/resources/rules/index",
                "read_only": True,
                "rule_id_count": len(self._rule_ids_sorted),
            },
            {
                "name": "GET_RULE",
                "kind": "tool",
                "tool": "get_rule",
                "endpoint": "/tools/get_rule?rule_id=<RULE_ID>",
                "read_only": True,
            },
            {
                "name": "TEMPLATE_COVERAGE",
                "kind": "tool",
                "tool": "find_template_coverage",
                "endpoint": "/tools/find_template_coverage?q=<keyword>",
                "read_only": True,
                "mode": "lazy",
            },
            {
                "name": "CLIENT_RULE_ROWS",
                "kind": "dataset",
                "count": self.rows_by_type.get("Client", 0),
                "read_only": True,
            },
            {
                "name": "SERVER_RULE_ROWS",
                "kind": "dataset",
                "count": self.rows_by_type.get("Server", 0),
                "read_only": True,
            },
            {
                "name": "REVIEW_APPLICABILITY",
                "kind": "dataset",
                "rule_id_count": len(self._rule_ids_sorted),
                "read_only": True,
            },
        ]

    def project_context(self) -> Dict[str, Any]:
        return {
            "projectName": "WinCC OA Code Inspector",
            "project_root": self.project_root,
            "generated_at": _utc_now(),
            "read_only": True,
            "mcp_integration_mode": "http-context-fail-soft",
            "mcp_config": self._mcp_config_summary(),
            "paths": self._paths_summary(),
            "datasets": {
                "parsed_rules_path": _relpath_or_abs(self.rules_path, self.project_root),
                "review_applicability_path": _relpath_or_abs(self.applicability_path, self.project_root),
                "client_rule_rows": self.rows_by_type.get("Client", 0),
                "server_rule_rows": self.rows_by_type.get("Server", 0),
                "unique_rule_ids": len(self._rule_ids_sorted),
            },
            "interfaces": {
                "resources": [
                    "resource://project/context",
                    "resource://rules/index",
                ],
                "tools": [
                    "tool:get_rule(rule_id)",
                    "tool:find_template_coverage(query, scope?)",
                    "tool:list_review_drivers()",
                ],
                "http_endpoints": {
                    "health": "/health",
                    "context": "/context",
                    "drivers": "/drivers",
                    "project_context_resource": "/resources/project/context",
                    "rules_index_resource": "/resources/rules/index",
                    "list_review_drivers": "/tools/list_review_drivers",
                    "get_rule": "/tools/get_rule?rule_id=PERF-02",
                    "find_template_coverage": "/tools/find_template_coverage?q=dp&scope=Client",
                },
            },
        }

    def rules_index(self) -> Dict[str, Any]:
        type_summary = {}
        for rule_type in ("Client", "Server"):
            categories = self.categories_by_type.get(rule_type, {})
            category_rows = [{"name": k, "count": categories[k]} for k in sorted(categories.keys())]
            type_summary[rule_type] = {
                "row_count": int(self.rows_by_type.get(rule_type, 0)),
                "category_count": len(category_rows),
                "categories": category_rows[:200],
            }

        rule_id_to_items = {
            rule_id: sorted(items)
            for rule_id, items in sorted(self.items_by_rule_id.items(), key=lambda item: item[0])
        }

        return {
            "generated_at": _utc_now(),
            "read_only": True,
            "counts": {
                "parsed_rule_rows": len([row for row in self.parsed_rules if isinstance(row, dict)]),
                "indexed_items": len(self.rows_by_item_norm),
                "rule_id_count": len(self._rule_ids_sorted),
            },
            "types": type_summary,
            "rule_ids": self._rule_ids_sorted,
            "rule_id_to_items": rule_id_to_items,
        }

    def get_rule(self, rule_id: str) -> Dict[str, Any]:
        normalized_id = str(rule_id or "").strip().upper()
        if not normalized_id:
            return {"found": False, "error": "rule_id is required"}

        mapped_items = self.items_by_rule_id.get(normalized_id, [])
        item_entries: List[Dict[str, Any]] = []
        for item_name in mapped_items:
            norm_item = _normalize_text(item_name)
            sample_rows = self.rows_by_item_norm.get(norm_item, [])
            item_entries.append(
                {
                    "item": item_name,
                    "types": sorted(self.item_types_by_norm.get(norm_item, set())),
                    "sample_rows": sample_rows[:3],
                }
            )

        technical_pattern = self._technical_patterns.get(normalized_id)
        technical_payload = None
        if isinstance(technical_pattern, dict):
            technical_payload = {
                "message": str(technical_pattern.get("message") or ""),
                "severity": str(technical_pattern.get("severity") or ""),
                "rule_item": str(technical_pattern.get("rule_item") or ""),
                "pattern": str(technical_pattern.get("pattern") or ""),
            }

        found = bool(item_entries or technical_payload)
        payload = {
            "found": found,
            "rule_id": normalized_id,
            "read_only": True,
            "items": item_entries,
        }
        if technical_payload:
            payload["technical_pattern"] = technical_payload
        if not found:
            payload["error"] = f"Unknown rule_id: {normalized_id}"
        return payload

    def _load_template_coverage(self, refresh: bool = False) -> Dict[str, Any]:
        with self._cache_lock:
            if self._template_coverage_cache is not None and not refresh:
                return self._template_coverage_cache

            self._template_coverage_checked_at = _utc_now()
            try:
                raw = self.template_coverage_loader(self.project_root)
                if not isinstance(raw, dict):
                    raise RuntimeError("template coverage loader returned invalid payload")
                payload = {
                    "available": True,
                    "checked_at": self._template_coverage_checked_at,
                    **raw,
                }
                self._template_coverage_cache = payload
                self._template_coverage_error = None
                return payload
            except Exception as exc:
                self._template_coverage_error = str(exc)
                self._template_coverage_cache = {
                    "available": False,
                    "checked_at": self._template_coverage_checked_at,
                    "error": str(exc),
                }
                return self._template_coverage_cache

    @staticmethod
    def _normalize_scope(scope: Optional[str]) -> Optional[str]:
        if scope is None:
            return None
        value = str(scope).strip().lower()
        if value in {"client", "c"}:
            return "Client"
        if value in {"server", "s"}:
            return "Server"
        return None

    def find_template_coverage(
        self,
        query: str = "",
        scope: Optional[str] = None,
        refresh: bool = False,
        include_unmatched_rows: bool = False,
    ) -> Dict[str, Any]:
        payload = self._load_template_coverage(refresh=refresh)
        if not payload.get("available"):
            return {
                "available": False,
                "read_only": True,
                "error": payload.get("error", "template coverage unavailable"),
                "checked_at": payload.get("checked_at"),
            }

        coverage = payload.get("coverage", {})
        if not isinstance(coverage, dict):
            return {
                "available": False,
                "read_only": True,
                "error": "invalid coverage payload",
                "checked_at": payload.get("checked_at"),
            }

        normalized_scope = self._normalize_scope(scope)
        normalized_query = _normalize_text(query)
        selected_types = [normalized_scope] if normalized_scope else ["Client", "Server"]

        summary = {}
        matches: List[Dict[str, Any]] = []
        for rule_type in selected_types:
            if not rule_type:
                continue
            item = coverage.get(rule_type, {})
            if not isinstance(item, dict):
                continue
            summary[rule_type] = {
                "rule_count": int(item.get("rule_count", 0) or 0),
                "matched_rule_count": int(item.get("matched_rule_count", 0) or 0),
                "rule_coverage_pct": float(item.get("rule_coverage_pct", 0.0) or 0.0),
                "unmatched_rule_count": len(item.get("unmatched_rules", []) or []),
                "unmatched_template_row_count": len(item.get("unmatched_template_rows", []) or []),
            }

            if not normalized_query:
                continue

            for rule_name in item.get("unmatched_rules", []) or []:
                if _normalize_text(rule_name).find(normalized_query) >= 0:
                    matches.append(
                        {
                            "scope": rule_type,
                            "kind": "unmatched_rule",
                            "rule": str(rule_name),
                        }
                    )

            for row in item.get("unmatched_template_rows", []) or []:
                if not isinstance(row, dict):
                    continue
                row_text = "{} {}".format(row.get("item", ""), row.get("condition", "")).strip()
                if _normalize_text(row_text).find(normalized_query) < 0:
                    continue
                match_row = {
                    "scope": rule_type,
                    "kind": "unmatched_template_row",
                    "row": int(row.get("row", 0) or 0),
                    "item": str(row.get("item", "") or ""),
                }
                if include_unmatched_rows:
                    match_row["condition"] = str(row.get("condition", "") or "")
                matches.append(match_row)
                if len(matches) >= 50:
                    break
            if len(matches) >= 50:
                break

        response = {
            "available": True,
            "read_only": True,
            "generated_at": payload.get("generated_at"),
            "checked_at": payload.get("checked_at"),
            "inputs": payload.get("inputs", {}),
            "summary": summary,
            "query": str(query or ""),
            "scope": normalized_scope or "all",
            "match_count": len(matches),
            "matches": matches,
        }
        if include_unmatched_rows and not normalized_query:
            details = {}
            for rule_type in selected_types:
                item = coverage.get(rule_type, {})
                if isinstance(item, dict):
                    details[rule_type] = {
                        "unmatched_rules": item.get("unmatched_rules", []),
                        "unmatched_template_rows": item.get("unmatched_template_rows", []),
                    }
            response["details"] = details
        return response

    def context_payload(self) -> Dict[str, Any]:
        return self.project_context()

    def drivers_payload(self) -> Dict[str, Any]:
        return {"drivers": self.list_review_drivers()}


class WinCCOAContextHandler(BaseHTTPRequestHandler):
    server_version = "WinCCOAContextServer/0.1"

    def __init__(self, *args, provider: WinCCOAContextProvider, **kwargs):
        self.provider = provider
        super().__init__(*args, **kwargs)

    def log_message(self, _format, *_args):  # pragma: no cover
        return

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def _as_bool(value: Optional[str]) -> bool:
        return str(value or "").strip().lower() in {"1", "true", "yes", "on"}

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if parsed.path == "/":
            self._send_json(
                HTTPStatus.OK,
                {
                    "service": "WinCC OA Context Server",
                    "read_only": True,
                    "endpoints": [
                        "/health",
                        "/context",
                        "/drivers",
                        "/resources/project/context",
                        "/resources/rules/index",
                        "/tools/list_review_drivers",
                        "/tools/get_rule?rule_id=PERF-02",
                        "/tools/find_template_coverage?q=dp&scope=Client",
                    ],
                },
            )
            return

        if parsed.path == "/health":
            self._send_json(
                HTTPStatus.OK,
                {"ok": True, "service": "winccoa-context", "read_only": True, "generated_at": _utc_now()},
            )
            return

        if parsed.path in ("/context", "/resources/project/context"):
            self._send_json(HTTPStatus.OK, self.provider.context_payload())
            return

        if parsed.path in ("/drivers", "/tools/list_review_drivers"):
            self._send_json(HTTPStatus.OK, self.provider.drivers_payload())
            return

        if parsed.path == "/resources/rules/index":
            self._send_json(HTTPStatus.OK, self.provider.rules_index())
            return

        if parsed.path == "/tools/get_rule":
            rule_id = query.get("rule_id", [""])[0]
            if not str(rule_id).strip():
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "rule_id is required"})
                return
            self._send_json(HTTPStatus.OK, self.provider.get_rule(rule_id))
            return

        if parsed.path == "/tools/find_template_coverage":
            payload = self.provider.find_template_coverage(
                query=query.get("q", [""])[0],
                scope=query.get("scope", [None])[0],
                refresh=self._as_bool(query.get("refresh", ["false"])[0]),
                include_unmatched_rows=self._as_bool(query.get("include_unmatched_rows", ["false"])[0]),
            )
            self._send_json(HTTPStatus.OK, payload)
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not Found"})


def run_server(host: str = "127.0.0.1", port: int = 3000, project_root: Optional[str] = None) -> None:
    provider = WinCCOAContextProvider(project_root=project_root)

    def handler(*args, **kwargs):
        return WinCCOAContextHandler(*args, provider=provider, **kwargs)

    httpd = ThreadingHTTPServer((host, port), handler)
    print(f"[*] WinCC OA Context Server started: http://{host}:{port}")
    print("[*] Read-only endpoints: /context, /drivers, /resources/*, /tools/*")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run WinCC OA read-only context HTTP server for AI/MCP workflows")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=3000, help="Bind port (default: 3000)")
    parser.add_argument(
        "--project-root",
        default=PROJECT_ROOT,
        help="Project root path (default: auto-detected repository root)",
    )
    args = parser.parse_args()

    run_server(host=args.host, port=args.port, project_root=args.project_root)


if __name__ == "__main__":
    main()
