import json
import logging
import os
import sys
import time
import uuid
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, TypedDict, cast
from urllib.parse import parse_qs, urlparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from main import CodeInspectorApp, DEFAULT_MODE, AutoFixApplyError

logger = logging.getLogger(__name__)


class AnalyzeSummaryPayload(TypedDict, total=False):
    failed_file_count: int
    successful_file_count: int


class AnalyzeResultPayload(TypedDict, total=False):
    summary: AnalyzeSummaryPayload
    metrics: Dict[str, Any]
    request_id: str


class AnalyzeRequestBody(TypedDict, total=False):
    mode: str
    selected_files: List[str]
    allow_raw_txt: bool
    enable_ctrlppcheck: Optional[bool]
    enable_live_ai: Optional[bool]
    ai_with_context: bool
    defer_excel_reports: Optional[bool]


class AIReviewApplyRequestBody(TypedDict, total=False):
    file: str
    object: str
    event: str
    review: str
    output_dir: Optional[str]


class AutofixPrepareRequestBody(TypedDict, total=False):
    file: str
    object: str
    event: str
    review: str
    output_dir: Optional[str]
    session_id: Optional[str]
    issue_id: str
    generator_preference: str
    allow_fallback: Optional[bool]
    prepare_mode: str


class AutofixApplyRequestBody(TypedDict, total=False):
    proposal_id: str
    session_id: Optional[str]
    output_dir: Optional[str]
    file: str
    expected_base_hash: str
    apply_mode: str
    block_on_regression: Optional[bool]
    check_ctrlpp_regression: Optional[bool]


class ExcelFlushRequestBody(TypedDict, total=False):
    session_id: Optional[str]
    output_dir: Optional[str]
    wait: bool
    timeout_sec: Optional[int]


class CodeInspectorHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, app=None, frontend_dir=None, **kwargs):
        self.app = app
        self.frontend_dir = frontend_dir
        super().__init__(*args, directory=frontend_dir, **kwargs)

    def _send_json(self, status, payload: Any):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(data)

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    @staticmethod
    def _safe_int(value, fallback=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    def _analysis_response_status(self, result: Any):
        if not isinstance(result, dict):
            return HTTPStatus.OK
        typed_result = cast(AnalyzeResultPayload, result)
        summary = typed_result.get("summary", {})
        if not isinstance(summary, dict):
            return HTTPStatus.OK
        failed_count = self._safe_int(summary.get("failed_file_count", 0), 0)
        success_count = self._safe_int(summary.get("successful_file_count", 0), 0)
        if failed_count <= 0:
            return HTTPStatus.OK
        if success_count > 0:
            return getattr(HTTPStatus, "MULTI_STATUS", 207)
        return HTTPStatus.INTERNAL_SERVER_ERROR

    @staticmethod
    def _autofix_error_payload(exc: Exception, request_id: str) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"error": str(exc), "request_id": request_id}
        error_code = ""
        quality_metrics: Dict[str, Any] = {}
        if isinstance(exc, AutoFixApplyError):
            error_code = str(getattr(exc, "error_code", "") or "")
            maybe_qm = getattr(exc, "quality_metrics", {}) or {}
            if isinstance(maybe_qm, dict):
                quality_metrics = maybe_qm
        if not error_code:
            msg = str(exc or "")
            if "base hash mismatch" in msg.lower():
                error_code = "BASE_HASH_MISMATCH"
            elif "anchor mismatch" in msg.lower():
                error_code = "ANCHOR_MISMATCH"
            elif "semantic guard blocked" in msg.lower():
                error_code = "SEMANTIC_GUARD_BLOCKED"
            elif "supported only for .ctl" in msg.lower():
                error_code = "UNSUPPORTED_FILE_TYPE"
            elif "syntax precheck failed" in msg.lower():
                error_code = "SYNTAX_PRECHECK_FAILED"
            elif "regression" in msg.lower():
                error_code = "REGRESSION_BLOCKED"
        if error_code:
            payload["error_code"] = error_code
        if quality_metrics:
            payload["quality_metrics"] = quality_metrics
        return payload

    def _read_json_body(self) -> Any:
        length_header = self.headers.get("Content-Length", "0")
        try:
            length = int(length_header)
        except ValueError:
            raise ValueError("Invalid Content-Length")

        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON body: {exc}") from exc

    @staticmethod
    def _is_txt(name):
        return isinstance(name, str) and name.lower().endswith(".txt")

    @staticmethod
    def _is_normalized_txt(name):
        return isinstance(name, str) and (name.endswith("_pnl.txt") or name.endswith("_xml.txt"))

    def _validate_selected_files(self, selected_files, allow_raw_txt=False):
        if not isinstance(selected_files, list):
            raise ValueError("selected_files must be a list")

        # Validate existence against full known set first to keep explicit raw-txt policy errors.
        available_names = {item["name"] for item in self.app.list_available_files(allow_raw_txt=True)}
        invalid = [name for name in selected_files if not isinstance(name, str) or name not in available_names]
        if invalid:
            raise ValueError(f"Unknown file(s): {invalid}")

        if allow_raw_txt:
            return

        blocked_raw_txt = [
            name
            for name in selected_files
            if self._is_txt(name) and not self._is_normalized_txt(name)
        ]
        if blocked_raw_txt:
            raise ValueError(
                "Raw .txt selection is disabled. Set allow_raw_txt=true to analyze these files: "
                f"{blocked_raw_txt}"
            )

    def _handle_apply_ai_review(self, request_id: str):
        body = self._read_json_body()
        if not isinstance(body, dict):
            raise ValueError("JSON body must be an object")
        typed_body = cast(AIReviewApplyRequestBody, body)

        file_name = typed_body.get("file", "")
        object_name = typed_body.get("object", "")
        event_name = typed_body.get("event", "Global")
        review_text = typed_body.get("review", "")
        output_dir = typed_body.get("output_dir", None)

        if not isinstance(file_name, str) or not file_name.strip():
            raise ValueError("file must be a non-empty string")
        if not isinstance(object_name, str) or not object_name.strip():
            raise ValueError("object must be a non-empty string")
        if not isinstance(event_name, str) or not event_name.strip():
            raise ValueError("event must be a non-empty string")
        if not isinstance(review_text, str) or not review_text.strip():
            raise ValueError("review must be a non-empty string")
        if output_dir is not None and not isinstance(output_dir, str):
            raise ValueError("output_dir must be a string when provided")

        logger.info("AI apply request start id=%s file=%s object=%s event=%s", request_id, file_name, object_name, event_name)
        result = self.app.apply_ai_review_to_reviewed_file(
            file_name=file_name,
            object_name=object_name,
            event_name=event_name,
            review_text=review_text,
            output_dir=output_dir,
        )
        self._send_json(HTTPStatus.OK, result)
        logger.info("AI apply request done id=%s status=200 applied_blocks=%d", request_id, int(result.get('applied_blocks', 0)))

    def _handle_autofix_prepare(self, request_id: str):
        body = self._read_json_body()
        if not isinstance(body, dict):
            raise ValueError("JSON body must be an object")
        typed_body = cast(AutofixPrepareRequestBody, body)

        file_name = typed_body.get("file", "")
        object_name = typed_body.get("object", "")
        event_name = typed_body.get("event", "Global")
        review_text = typed_body.get("review", "")
        output_dir = typed_body.get("output_dir") or typed_body.get("session_id") or None
        issue_id = typed_body.get("issue_id", "")
        generator_preference = typed_body.get("generator_preference", None)
        allow_fallback = typed_body.get("allow_fallback", None)
        prepare_mode = typed_body.get("prepare_mode", None)

        if not isinstance(file_name, str) or not file_name.strip():
            raise ValueError("file must be a non-empty string")
        if not isinstance(object_name, str) or not object_name.strip():
            raise ValueError("object must be a non-empty string")
        if not isinstance(event_name, str) or not event_name.strip():
            raise ValueError("event must be a non-empty string")
        if not isinstance(review_text, str):
            raise ValueError("review must be a string")
        if output_dir is not None and not isinstance(output_dir, str):
            raise ValueError("output_dir/session_id must be a string when provided")
        if not isinstance(issue_id, str):
            raise ValueError("issue_id must be a string when provided")
        if generator_preference is not None and not isinstance(generator_preference, str):
            raise ValueError("generator_preference must be a string when provided")
        if allow_fallback is not None and not isinstance(allow_fallback, bool):
            raise ValueError("allow_fallback must be a boolean when provided")
        if prepare_mode is not None and not isinstance(prepare_mode, str):
            raise ValueError("prepare_mode must be a string when provided")
        normalized_pref = None
        normalized_prepare_mode = None
        if generator_preference is not None:
            normalized_pref = str(generator_preference or "").strip().lower()
            if normalized_pref not in ("auto", "llm", "rule"):
                raise ValueError("generator_preference must be one of: auto, llm, rule")
        if prepare_mode is not None:
            normalized_prepare_mode = str(prepare_mode or "").strip().lower()
            if normalized_prepare_mode not in ("single", "compare"):
                raise ValueError("prepare_mode must be one of: single, compare")
        if normalized_pref == "llm" and not str(review_text or "").strip():
            raise ValueError("review must be a non-empty string for llm autofix prepare")

        logger.info("Autofix prepare start id=%s file=%s object=%s event=%s", request_id, file_name, object_name, event_name)
        result = self.app.prepare_autofix_for_ai_review(
            file_name=file_name,
            object_name=object_name,
            event_name=event_name,
            review_text=review_text,
            output_dir=output_dir,
            issue_id=issue_id,
            generator_preference=normalized_pref,
            allow_fallback=allow_fallback,
            prepare_mode=normalized_prepare_mode,
        )
        result.setdefault("request_id", request_id)
        self._send_json(HTTPStatus.OK, result)
        logger.info("Autofix prepare done id=%s status=200 proposal_id=%s", request_id, result.get("proposal_id", ""))

    def _handle_autofix_apply(self, request_id: str):
        body = self._read_json_body()
        if not isinstance(body, dict):
            raise ValueError("JSON body must be an object")
        typed_body = cast(AutofixApplyRequestBody, body)

        proposal_id = typed_body.get("proposal_id", "")
        session_id = typed_body.get("session_id") or typed_body.get("output_dir") or None
        file_name = typed_body.get("file", "")
        expected_base_hash = typed_body.get("expected_base_hash", "")
        apply_mode = typed_body.get("apply_mode", "source_ctl")
        block_on_regression = typed_body.get("block_on_regression", None)
        check_ctrlpp_regression = typed_body.get("check_ctrlpp_regression", None)

        if not isinstance(proposal_id, str) or not proposal_id.strip():
            raise ValueError("proposal_id must be a non-empty string")
        if session_id is not None and not isinstance(session_id, str):
            raise ValueError("session_id/output_dir must be a string when provided")
        if file_name is not None and not isinstance(file_name, str):
            raise ValueError("file must be a string when provided")
        if expected_base_hash is not None and not isinstance(expected_base_hash, str):
            raise ValueError("expected_base_hash must be a string when provided")
        if not isinstance(apply_mode, str) or not apply_mode.strip():
            raise ValueError("apply_mode must be a non-empty string")
        if block_on_regression is not None and not isinstance(block_on_regression, bool):
            raise ValueError("block_on_regression must be a boolean when provided")
        if check_ctrlpp_regression is not None and not isinstance(check_ctrlpp_regression, bool):
            raise ValueError("check_ctrlpp_regression must be a boolean when provided")

        logger.info("Autofix apply start id=%s proposal_id=%s", request_id, proposal_id)
        result = self.app.apply_autofix_proposal(
            proposal_id=proposal_id,
            session_id=session_id,
            file_name=file_name or "",
            expected_base_hash=expected_base_hash or "",
            apply_mode=apply_mode,
            block_on_regression=block_on_regression,
            check_ctrlpp_regression=check_ctrlpp_regression,
        )
        result.setdefault("request_id", request_id)
        self._send_json(HTTPStatus.OK, result)
        logger.info("Autofix apply done id=%s status=200 file=%s", request_id, result.get("file", ""))

    def _handle_excel_report_flush(self, request_id: str):
        body = self._read_json_body()
        if not isinstance(body, dict):
            raise ValueError("JSON body must be an object")
        typed_body = cast(ExcelFlushRequestBody, body)

        session_id = typed_body.get("session_id") or None
        output_dir = typed_body.get("output_dir") or None
        wait = typed_body.get("wait", True)
        timeout_sec = typed_body.get("timeout_sec", None)

        if session_id is not None and not isinstance(session_id, str):
            raise ValueError("session_id must be a string when provided")
        if output_dir is not None and not isinstance(output_dir, str):
            raise ValueError("output_dir must be a string when provided")
        if not isinstance(wait, bool):
            raise ValueError("wait must be a boolean when provided")
        if timeout_sec is not None and (isinstance(timeout_sec, bool) or not isinstance(timeout_sec, int)):
            raise ValueError("timeout_sec must be an integer when provided")

        logger.info("Excel report flush start id=%s wait=%s", request_id, wait)
        result = self.app.flush_deferred_excel_reports(
            session_id=session_id,
            output_dir=output_dir,
            wait=wait,
            timeout_sec=timeout_sec,
        )
        result.setdefault("request_id", request_id)
        self._send_json(HTTPStatus.OK, result)
        logger.info("Excel report flush done id=%s status=200", request_id)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/files":
            query = parse_qs(parsed.query)
            allow_raw_txt = str(query.get("allow_raw_txt", ["false"])[0]).lower() in ("1", "true", "yes", "on")
            payload = {"files": self.app.list_available_files(allow_raw_txt=allow_raw_txt)}
            self._send_json(HTTPStatus.OK, payload)
            return

        if parsed.path == "/api/file-content":
            query = parse_qs(parsed.query)
            name = str(query.get("name", [""])[0] or "")
            prefer_source = str(query.get("prefer_source", ["false"])[0]).lower() in ("1", "true", "yes", "on")
            try:
                payload = self.app.get_viewer_content(name, prefer_source=prefer_source)
                self._send_json(HTTPStatus.OK, payload)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            return

        if parsed.path == "/api/autofix/file-diff":
            query = parse_qs(parsed.query)
            name = str(query.get("file", [""])[0] or "")
            session_id = str(query.get("session_id", [""])[0] or "")
            output_dir = str(query.get("output_dir", [""])[0] or "")
            proposal_id = str(query.get("proposal_id", [""])[0] or "")
            try:
                payload = self.app.get_autofix_file_diff(
                    file_name=name,
                    session_id=session_id or None,
                    output_dir=output_dir or None,
                    proposal_id=proposal_id or "",
                )
                self._send_json(HTTPStatus.OK, payload)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            except RuntimeError as exc:
                self._send_json(getattr(HTTPStatus, "CONFLICT", 409), {"error": str(exc)})
            return

        if parsed.path == "/api/autofix/stats":
            query = parse_qs(parsed.query)
            session_id = str(query.get("session_id", [""])[0] or "")
            output_dir = str(query.get("output_dir", [""])[0] or "")
            try:
                payload = self.app.get_autofix_stats(
                    session_id=session_id or None,
                    output_dir=output_dir or None,
                )
                self._send_json(HTTPStatus.OK, payload)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            except RuntimeError as exc:
                self._send_json(getattr(HTTPStatus, "CONFLICT", 409), {"error": str(exc)})
            return

        if parsed.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.end_headers()

    def end_headers(self):
        # Ensure CORS headers are present on static file responses as well.
        if not any(h == "Access-Control-Allow-Origin" for h, _ in self._headers_buffer_items()):
            self._send_cors_headers()
        super().end_headers()

    def _headers_buffer_items(self):
        """Extract header names already queued in the response buffer."""
        items = []
        for line in getattr(self, "_headers_buffer", []):
            decoded = line.decode("latin-1", errors="replace") if isinstance(line, bytes) else str(line)
            if ":" in decoded:
                items.append((decoded.split(":", 1)[0].strip(), decoded.split(":", 1)[1].strip()))
        return items

    def do_POST(self):
        parsed = urlparse(self.path)
        request_started = time.perf_counter()
        if parsed.path == "/api/ai-review/apply":
            request_id = uuid.uuid4().hex
            try:
                self._handle_apply_ai_review(request_id)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                logger.warning("AI apply request done id=%s status=400 error=%s", request_id, exc)
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
                logger.warning("AI apply request done id=%s status=404 error=%s", request_id, exc)
            except RuntimeError as exc:
                self._send_json(getattr(HTTPStatus, "CONFLICT", 409), {"error": str(exc)})
                logger.warning("AI apply request done id=%s status=409 error=%s", request_id, exc)
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
                logger.error("AI apply request done id=%s status=500 error=%s", request_id, exc)
            return

        if parsed.path == "/api/autofix/prepare":
            request_id = uuid.uuid4().hex
            try:
                self._handle_autofix_prepare(request_id)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc), "request_id": request_id})
                logger.warning("Autofix prepare done id=%s status=400 error=%s", request_id, exc)
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc), "request_id": request_id})
                logger.warning("Autofix prepare done id=%s status=404 error=%s", request_id, exc)
            except RuntimeError as exc:
                self._send_json(getattr(HTTPStatus, "CONFLICT", 409), {"error": str(exc), "request_id": request_id})
                logger.warning("Autofix prepare done id=%s status=409 error=%s", request_id, exc)
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc), "request_id": request_id})
                logger.error("Autofix prepare done id=%s status=500 error=%s", request_id, exc)
            return

        if parsed.path == "/api/autofix/apply":
            request_id = uuid.uuid4().hex
            try:
                self._handle_autofix_apply(request_id)
            except AutoFixApplyError as exc:
                self._send_json(getattr(HTTPStatus, "CONFLICT", 409), self._autofix_error_payload(exc, request_id))
                logger.warning(
                    "Autofix apply done id=%s status=409 error_code=%s error=%s",
                    request_id,
                    getattr(exc, "error_code", ""),
                    exc,
                )
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, self._autofix_error_payload(exc, request_id))
                logger.warning("Autofix apply done id=%s status=400 error=%s", request_id, exc)
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, self._autofix_error_payload(exc, request_id))
                logger.warning("Autofix apply done id=%s status=404 error=%s", request_id, exc)
            except RuntimeError as exc:
                self._send_json(getattr(HTTPStatus, "CONFLICT", 409), self._autofix_error_payload(exc, request_id))
                logger.warning("Autofix apply done id=%s status=409 error=%s", request_id, exc)
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc), "request_id": request_id})
                logger.error("Autofix apply done id=%s status=500 error=%s", request_id, exc)
            return

        if parsed.path == "/api/report/excel":
            request_id = uuid.uuid4().hex
            try:
                self._handle_excel_report_flush(request_id)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc), "request_id": request_id})
                logger.warning("Excel report flush done id=%s status=400 error=%s", request_id, exc)
            except RuntimeError as exc:
                self._send_json(getattr(HTTPStatus, "CONFLICT", 409), {"error": str(exc), "request_id": request_id})
                logger.warning("Excel report flush done id=%s status=409 error=%s", request_id, exc)
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc), "request_id": request_id})
                logger.error("Excel report flush done id=%s status=500 error=%s", request_id, exc)
            return

        if parsed.path != "/api/analyze":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not Found"})
            return

        request_id = uuid.uuid4().hex
        try:
            body = self._read_json_body()
            if not isinstance(body, dict):
                raise ValueError("JSON body must be an object")
            typed_body = cast(AnalyzeRequestBody, body)
            mode = typed_body.get("mode", DEFAULT_MODE)
            selected_files = typed_body.get("selected_files", [])
            if not isinstance(selected_files, list):
                raise ValueError("selected_files must be a list")

            allow_raw_txt = typed_body.get("allow_raw_txt", False)
            if not isinstance(allow_raw_txt, bool):
                raise ValueError("allow_raw_txt must be a boolean")
            enable_ctrlppcheck = typed_body.get("enable_ctrlppcheck", None)
            enable_live_ai = typed_body.get("enable_live_ai", None)
            ai_with_context = typed_body.get("ai_with_context", False)
            defer_excel_reports = typed_body.get("defer_excel_reports", None)
            logger.info(
                "Analyze request start id=%s selected=%d allow_raw_txt=%s",
                request_id, len(selected_files), allow_raw_txt,
            )
            if enable_ctrlppcheck is not None and not isinstance(enable_ctrlppcheck, bool):
                raise ValueError("enable_ctrlppcheck must be a boolean")
            if enable_live_ai is not None and not isinstance(enable_live_ai, bool):
                raise ValueError("enable_live_ai must be a boolean")
            if not isinstance(ai_with_context, bool):
                raise ValueError("ai_with_context must be a boolean")
            if defer_excel_reports is not None and not isinstance(defer_excel_reports, bool):
                raise ValueError("defer_excel_reports must be a boolean when provided")
            self._validate_selected_files(selected_files, allow_raw_txt=allow_raw_txt)
            # File-type routing is handled in main.py: .ctl => Server, .txt => Client rules.
            result = self.app.run_directory_analysis(
                mode=mode,
                selected_files=selected_files,
                allow_raw_txt=allow_raw_txt,
                enable_ctrlppcheck=enable_ctrlppcheck,
                enable_live_ai=enable_live_ai,
                ai_with_context=ai_with_context,
                request_id=request_id,
                defer_excel_reports=defer_excel_reports,
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
            logger.error("Analyze request done id=%s status=500 error=%s", request_id, exc)


def run_server(port=8765):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    app = CodeInspectorApp()
    frontend_dir = os.path.join(BASE_DIR, "frontend")

    def handler(*args, **kwargs):
        return CodeInspectorHandler(*args, app=app, frontend_dir=frontend_dir, **kwargs)

    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    logger.info("Server started: http://127.0.0.1:%d", port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run_server()
