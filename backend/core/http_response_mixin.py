import json
from http import HTTPStatus
from typing import Any, List, Tuple


class HttpResponseMixin:
    """Shared JSON/CORS/download helpers for the HTTP handler."""

    def _send_json(self, status: int, payload: Any) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(data)

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, X-Autofix-Benchmark-Observe-Mode, "
            "X-Autofix-Benchmark-Tuning-Min-Confidence, "
            "X-Autofix-Benchmark-Tuning-Min-Gap, "
            "X-Autofix-Benchmark-Tuning-Max-Line-Drift, "
            "X-Autofix-Benchmark-Force-Structured-Instruction",
        )

    def _send_download_file(self, file_path: str, download_name: str, content_type: str) -> None:
        with open(file_path, "rb") as handle:
            data = handle.read()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(data)

    def end_headers(self) -> None:
        if not any(header == "Access-Control-Allow-Origin" for header, _ in self._headers_buffer_items()):
            self._send_cors_headers()
        super().end_headers()

    def _headers_buffer_items(self) -> List[Tuple[str, str]]:
        items = []
        for line in getattr(self, "_headers_buffer", []):
            decoded = line.decode("latin-1", errors="replace") if isinstance(line, bytes) else str(line)
            if ":" not in decoded:
                continue
            name, value = decoded.split(":", 1)
            items.append((name.strip(), value.strip()))
        return items
