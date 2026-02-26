import argparse
import datetime
import json
import os
import sys
from typing import Any, Dict, Optional, Tuple


BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from tools.winccoa_context_server import WinCCOAContextProvider


SERVER_NAME = "winccoa-context-mcp-bridge"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2024-11-05"
MIN_TEXT_BYTES = 1024


def _utc_now() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


class JsonRpcError(Exception):
    def __init__(self, code: int, message: str, data: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = int(code)
        self.message = str(message)
        self.data = data


class WinCCOAContextMCPBridge:
    """Minimal stdio JSON-RPC MCP bridge for WinCC OA context data."""

    def __init__(self, project_root: Optional[str] = None, max_text_bytes: int = 65536):
        self.project_root = os.path.abspath(project_root or PROJECT_ROOT)
        self.max_text_bytes = max(int(max_text_bytes or 65536), MIN_TEXT_BYTES)
        self.provider = WinCCOAContextProvider(project_root=self.project_root)
        self.shutdown_requested = False
        self.exit_requested = False

    def handle_request(self, method: str, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if method == "initialize":
            return self._handle_initialize(params)
        if method == "ping":
            return {"ok": True, "generated_at": _utc_now()}
        if method == "shutdown":
            self.shutdown_requested = True
            return {}
        if method == "resources/list":
            return {"resources": self._list_resources()}
        if method == "resources/read":
            return self._read_resource(params)
        if method == "tools/list":
            return {"tools": self._list_tools()}
        if method == "tools/call":
            return self._call_tool(params)
        if method == "prompts/list":
            return {"prompts": []}
        raise JsonRpcError(-32601, f"Method not found: {method}")

    def handle_notification(self, method: str, _params: Optional[Dict[str, Any]]) -> None:
        if method in ("notifications/initialized", "initialized"):
            return
        if method == "exit":
            self.exit_requested = True
            return
        # Ignore unknown notifications to keep fail-soft behavior.
        return

    def _handle_initialize(self, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        requested = ""
        if isinstance(params, dict):
            requested = str(params.get("protocolVersion") or "").strip()
        negotiated = requested or PROTOCOL_VERSION
        return {
            "protocolVersion": negotiated,
            "serverInfo": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
            },
            "capabilities": {
                "resources": {
                    "listChanged": False,
                    "subscribe": False,
                },
                "tools": {
                    "listChanged": False,
                },
                "prompts": {
                    "listChanged": False,
                },
            },
            "instructions": (
                "Read-only WinCC OA code review context bridge. "
                "Use resources for project/rule index and tools for rule/template queries."
            ),
        }

    def _list_resources(self) -> list:
        return [
            {
                "uri": "winccoa://project/context",
                "name": "winccoa-project-context",
                "description": "Project summary, datasets, and available review context interfaces",
                "mimeType": "application/json",
            },
            {
                "uri": "winccoa://rules/index",
                "name": "winccoa-rules-index",
                "description": "Rule ID index and Client/Server rule category counts",
                "mimeType": "application/json",
            },
        ]

    def _read_resource(self, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(params, dict):
            raise JsonRpcError(-32602, "resources/read requires params")
        uri = str(params.get("uri") or "").strip()
        if not uri:
            raise JsonRpcError(-32602, "resources/read requires uri")

        if uri == "winccoa://project/context":
            payload = self._fail_soft(self.provider.context_payload)
        elif uri == "winccoa://rules/index":
            payload = self._fail_soft(self.provider.rules_index)
        else:
            raise JsonRpcError(-32602, f"Unsupported resource URI: {uri}")

        text, _ = self._payload_to_text(payload, include_meta=True)
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": text,
                }
            ]
        }

    def _list_tools(self) -> list:
        return [
            {
                "name": "health",
                "description": "Return bridge/provider health and basic project counts (read-only)",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            },
            {
                "name": "list_review_drivers",
                "description": "List available read-only resources and review helper tools",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            },
            {
                "name": "get_rule",
                "description": "Resolve a WinCC OA review rule_id (e.g. PERF-02) into mapped items and sample rows",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "rule_id": {"type": "string", "description": "Rule ID such as PERF-02"},
                    },
                    "required": ["rule_id"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "find_template_coverage",
                "description": "Search template coverage mismatches by keyword and optional scope",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Keyword to search"},
                        "scope": {
                            "type": "string",
                            "enum": ["Client", "Server", "client", "server", "c", "s"],
                            "description": "Optional scope filter",
                        },
                        "refresh": {"type": "boolean", "description": "Refresh cached template coverage"},
                        "include_unmatched_rows": {
                            "type": "boolean",
                            "description": "Include unmatched row details",
                        },
                    },
                    "additionalProperties": False,
                },
            },
        ]

    def _call_tool(self, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(params, dict):
            raise JsonRpcError(-32602, "tools/call requires params")
        name = str(params.get("name") or "").strip()
        arguments = params.get("arguments", {})
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            raise JsonRpcError(-32602, "tools/call arguments must be an object")

        if name == "health":
            payload = self._tool_health()
            return self._tool_result(payload)
        if name == "list_review_drivers":
            payload = self._fail_soft(lambda: {"drivers": self.provider.list_review_drivers(), "read_only": True})
            return self._tool_result(payload)
        if name == "get_rule":
            rule_id = str(arguments.get("rule_id") or "").strip()
            if not rule_id:
                return self._tool_error_payload("rule_id is required")
            payload = self._fail_soft(lambda: self.provider.get_rule(rule_id))
            if isinstance(payload, dict) and payload.get("error") and not payload.get("found", True):
                return self._tool_result(payload, is_error=True)
            return self._tool_result(payload)
        if name == "find_template_coverage":
            query = str(arguments.get("query") or arguments.get("q") or "")
            scope = arguments.get("scope")
            refresh = self._as_bool(arguments.get("refresh", False))
            include_rows = self._as_bool(arguments.get("include_unmatched_rows", False))
            payload = self._fail_soft(
                lambda: self.provider.find_template_coverage(
                    query=query,
                    scope=None if scope is None else str(scope),
                    refresh=refresh,
                    include_unmatched_rows=include_rows,
                )
            )
            if isinstance(payload, dict) and payload.get("available") is False and payload.get("error"):
                return self._tool_result(payload, is_error=True)
            return self._tool_result(payload)

        return self._tool_error_payload(f"Unknown tool: {name}")

    def _tool_health(self) -> Dict[str, Any]:
        def _build() -> Dict[str, Any]:
            rules_index = self.provider.rules_index()
            counts = rules_index.get("counts", {}) if isinstance(rules_index, dict) else {}
            return {
                "ok": True,
                "generated_at": _utc_now(),
                "server": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                    "protocolVersion": PROTOCOL_VERSION,
                    "mode": "stdio-jsonrpc-readonly",
                    "max_text_bytes": self.max_text_bytes,
                },
                "project_root": self.project_root,
                "provider": {
                    "read_only": True,
                    "paths": {
                        "config": getattr(self.provider, "config_path", ""),
                        "parsed_rules": getattr(self.provider, "rules_path", ""),
                        "review_applicability": getattr(self.provider, "applicability_path", ""),
                    },
                    "counts": counts,
                },
            }

        return self._fail_soft(_build)

    @staticmethod
    def _fail_soft(func):
        try:
            return func()
        except Exception as exc:  # pragma: no cover - defensive fail-soft wrapper
            return {
                "ok": False,
                "read_only": True,
                "error": str(exc),
            }

    @staticmethod
    def _as_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        text = str(value or "").strip().lower()
        return text in {"1", "true", "yes", "on"}

    def _tool_result(self, payload: Any, is_error: bool = False) -> Dict[str, Any]:
        text, truncated = self._payload_to_text(payload, include_meta=True)
        result: Dict[str, Any] = {
            "content": [
                {
                    "type": "text",
                    "text": text,
                }
            ]
        }
        if not truncated:
            result["structuredContent"] = payload
        if is_error:
            result["isError"] = True
        return result

    def _tool_error_payload(self, message: str) -> Dict[str, Any]:
        return self._tool_result({"ok": False, "read_only": True, "error": str(message)}, is_error=True)

    def _payload_to_text(self, payload: Any, include_meta: bool = False):
        raw = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        encoded = raw.encode("utf-8", errors="replace")
        if len(encoded) <= self.max_text_bytes:
            return raw, False

        preview_bytes = encoded[: max(self.max_text_bytes - 256, MIN_TEXT_BYTES // 2)]
        preview = preview_bytes.decode("utf-8", errors="ignore")
        if include_meta:
            wrapper = {
                "truncated": True,
                "reason": f"Serialized JSON exceeds max_text_bytes={self.max_text_bytes}",
                "byte_length": len(encoded),
                "preview": preview,
            }
            return json.dumps(wrapper, ensure_ascii=False, indent=2), True

        suffix = (
            "\n\n... [truncated] "
            f"(serialized JSON {len(encoded)} bytes > max_text_bytes {self.max_text_bytes})"
        )
        return preview + suffix, True


class StdioJsonRpcLoop:
    def __init__(self, bridge: WinCCOAContextMCPBridge):
        self.bridge = bridge

    def serve_forever(self) -> int:
        while True:
            try:
                message = self._read_message(sys.stdin.buffer)
            except JsonRpcError as exc:
                self._write_error_response(None, exc)
                continue
            if message is None:
                return 0

            if not isinstance(message, dict):
                self._write_error_response(None, JsonRpcError(-32600, "Invalid Request"))
                continue

            msg_id = message.get("id")
            method = message.get("method")
            params = message.get("params")

            if not isinstance(method, str) or not method:
                if "id" in message:
                    self._write_error_response(msg_id, JsonRpcError(-32600, "Invalid Request: missing method"))
                continue

            is_notification = "id" not in message

            if is_notification:
                try:
                    self.bridge.handle_notification(method, params if isinstance(params, dict) else None)
                except Exception as exc:  # pragma: no cover - notification errors are logged only
                    self._log(f"notification error method={method}: {exc}")
                if self.bridge.exit_requested:
                    return 0
                continue

            try:
                if params is not None and not isinstance(params, dict):
                    raise JsonRpcError(-32602, "params must be an object")
                result = self.bridge.handle_request(method, params if isinstance(params, dict) else None)
                self._write_message({"jsonrpc": "2.0", "id": msg_id, "result": result})
                if self.bridge.shutdown_requested:
                    # Wait for `exit` notification; if client closes stdin we exit naturally.
                    pass
            except JsonRpcError as exc:
                self._write_error_response(msg_id, exc)
            except Exception as exc:  # pragma: no cover - defensive runtime protection
                self._write_error_response(msg_id, JsonRpcError(-32603, "Internal error", {"error": str(exc)}))

    def _read_message(self, stream) -> Optional[Dict[str, Any]]:
        headers: Dict[str, str] = {}

        while True:
            line = stream.readline()
            if not line:
                return None if not headers else None
            if line in (b"\r\n", b"\n"):
                break
            try:
                header_line = line.decode("ascii", errors="replace").strip()
            except Exception:
                raise JsonRpcError(-32700, "Invalid header encoding")
            if not header_line:
                break
            if ":" not in header_line:
                raise JsonRpcError(-32700, f"Malformed header: {header_line}")
            key, value = header_line.split(":", 1)
            headers[key.strip().lower()] = value.strip()

        if not headers:
            return None

        if "content-length" not in headers:
            raise JsonRpcError(-32700, "Missing Content-Length header")

        try:
            length = int(headers["content-length"])
        except ValueError as exc:
            raise JsonRpcError(-32700, "Invalid Content-Length header") from exc

        body = stream.read(length)
        if len(body) != length:
            raise JsonRpcError(-32700, "Incomplete message body")
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise JsonRpcError(-32700, f"Parse error: {exc.msg}") from exc
        return payload

    def _write_error_response(self, msg_id: Any, exc: JsonRpcError) -> None:
        error: Dict[str, Any] = {"code": exc.code, "message": exc.message}
        if exc.data is not None:
            error["data"] = exc.data
        self._write_message({"jsonrpc": "2.0", "id": msg_id, "error": error})

    @staticmethod
    def _write_message(payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        sys.stdout.buffer.write(header)
        sys.stdout.buffer.write(body)
        sys.stdout.buffer.flush()

    @staticmethod
    def _log(message: str) -> None:
        print(f"[{SERVER_NAME}] {message}", file=sys.stderr, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run WinCC OA read-only context MCP bridge (stdio JSON-RPC) for Codex/other MCP clients"
    )
    parser.add_argument(
        "--project-root",
        default=PROJECT_ROOT,
        help="Project root path (default: auto-detected repository root)",
    )
    parser.add_argument(
        "--max-text-bytes",
        type=int,
        default=65536,
        help="Max bytes for serialized JSON text returned to MCP clients (default: 65536)",
    )
    args = parser.parse_args()

    bridge = WinCCOAContextMCPBridge(project_root=args.project_root, max_text_bytes=args.max_text_bytes)
    loop = StdioJsonRpcLoop(bridge)
    loop.serve_forever()


if __name__ == "__main__":
    main()
