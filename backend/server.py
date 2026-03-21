import argparse
import logging
import os
import sys
import time
import uuid
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from main import CodeInspectorApp, DEFAULT_MODE
from core.ai_review_http_mixin import AIReviewHttpMixin
from core.analyze_job_mixin import AnalyzeJobMixin
from core.api_dispatch_mixin import ApiDispatchMixin
from core.autofix_http_mixin import AutofixHttpMixin
from core.health_check_mixin import HealthCheckMixin
from core.http_response_mixin import HttpResponseMixin
from core.p1_triage_http_mixin import P1TriageHttpMixin
from core.request_validation_mixin import RequestValidationMixin

logger = logging.getLogger(__name__)


class CodeInspectorHandler(
    AnalyzeJobMixin,
    RequestValidationMixin,
    HealthCheckMixin,
    HttpResponseMixin,
    AIReviewHttpMixin,
    AutofixHttpMixin,
    P1TriageHttpMixin,
    ApiDispatchMixin,
    SimpleHTTPRequestHandler,
):
    def __init__(self, *args, app=None, frontend_dir=None, **kwargs):
        self.app = app
        self.frontend_dir = frontend_dir
        super().__init__(*args, directory=frontend_dir, **kwargs)

    @staticmethod
    def _safe_int(value, fallback=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _epoch_ms() -> int:
        return int(time.time() * 1000)

    def do_GET(self):
        parsed = urlparse(self.path)
        if self._dispatch_get_request(parsed):
            return
        return super().do_GET()

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        request_started = time.perf_counter()
        if self._dispatch_post_request(parsed, request_started):
            return

        if parsed.path == "/api/analyze/start":
            request_id = uuid.uuid4().hex
            try:
                self._handle_analyze_start(request_id, request_started)
                logger.info("Analyze async request accepted id=%s status=202", request_id)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc), "request_id": request_id})
                logger.warning("Analyze async request done id=%s status=400 error=%s", request_id, exc)
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc), "request_id": request_id})
                logger.error("Analyze async request done id=%s status=500 error=%s", request_id, exc)
            return

        if parsed.path != "/api/analyze":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not Found"})
            return

        request_id = uuid.uuid4().hex
        try:
            analyze_args = self._parse_analyze_request_body(validate_selected_files=True)
            selected_files = analyze_args.get("selected_files", [])
            allow_raw_txt = bool(analyze_args.get("allow_raw_txt", False))
            logger.info(
                "Analyze request start id=%s selected=%d allow_raw_txt=%s",
                request_id,
                len(selected_files),
                allow_raw_txt,
            )
            result = self.app.run_directory_analysis(
                mode=analyze_args.get("mode", DEFAULT_MODE),
                selected_files=selected_files,
                input_sources=analyze_args.get("input_sources", []),
                allow_raw_txt=allow_raw_txt,
                enable_ctrlppcheck=analyze_args.get("enable_ctrlppcheck", None),
                enable_live_ai=analyze_args.get("enable_live_ai", None),
                ai_model_name=analyze_args.get("ai_model_name", None),
                ai_with_context=bool(analyze_args.get("ai_with_context", False)),
                request_id=request_id,
                defer_excel_reports=analyze_args.get("defer_excel_reports", None),
            )
            response_status = self._analysis_response_status(result)
            result.setdefault("request_id", request_id)
            elapsed_ms = int((time.perf_counter() - request_started) * 1000)
            if isinstance(result.get("metrics"), dict):
                timings = result["metrics"].setdefault("timings_ms", {})
                if isinstance(timings, dict) and not timings.get("server_total"):
                    timings["server_total"] = elapsed_ms
            self._send_json(response_status, result)
            logger.info("Analyze request done id=%s status=%d", request_id, int(response_status))
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc), "request_id": request_id})
            logger.warning("Analyze request done id=%s status=400 error=%s", request_id, exc)
        except Exception as exc:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc), "request_id": request_id})
            logger.exception("Analyze request done id=%s status=500 error=%s", request_id, exc)


def build_server_arg_parser():
    parser = argparse.ArgumentParser(
        description="Run the WinCC OA code review HTTP server",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind")
    parser.add_argument("--port", type=int, default=8765, help="TCP port to bind")
    return parser


def parse_server_args(argv=None):
    return build_server_arg_parser().parse_args(argv)


def run_server(host="127.0.0.1", port=8765):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    app = CodeInspectorApp()
    frontend_dir = os.path.join(BASE_DIR, "frontend")

    def handler(*args, **kwargs):
        return CodeInspectorHandler(*args, app=app, frontend_dir=frontend_dir, **kwargs)

    server = ThreadingHTTPServer((host, port), handler)
    logger.info("Server started: http://%s:%d", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv=None):
    args = parse_server_args(argv)
    run_server(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
