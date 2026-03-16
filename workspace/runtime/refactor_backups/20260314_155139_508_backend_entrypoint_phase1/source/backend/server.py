import json
import logging
import os
import posixpath
import shutil
import subprocess
from email import policy
from email.parser import BytesParser
from pathlib import Path
import sys
import threading
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
from core.analyze_job_mixin import AnalyzeJobMixin
from core.request_validation_mixin import RequestValidationMixin
from core.health_check_mixin import HealthCheckMixin
from core.errors import ReviewerError

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
    input_sources: List[Dict[str, str]]
    allow_raw_txt: bool
    enable_ctrlppcheck: Optional[bool]
    enable_live_ai: Optional[bool]
    ai_model_name: Optional[str]
    ai_with_context: bool
    defer_excel_reports: Optional[bool]


class AIReviewApplyRequestBody(TypedDict, total=False):
    file: str
    object: str
    event: str
    review: str
    output_dir: Optional[str]


class AIReviewGenerateRequestBody(TypedDict, total=False):
    violation: Dict[str, Any]
    enable_live_ai: Optional[bool]
    ai_model_name: Optional[str]
    ai_with_context: bool


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


class RuleUpdateEntry(TypedDict, total=False):
    id: str
    enabled: bool


class RuleUpdateRequestBody(TypedDict, total=False):
    updates: List[RuleUpdateEntry]


class RuleRecordRequestBody(TypedDict, total=False):
    rule: Dict[str, Any]


class RuleDeleteRequestBody(TypedDict, total=False):
    id: str


class RuleImportRequestBody(TypedDict, total=False):
    rules: List[Dict[str, Any]]
    mode: str


class AnalyzeProgressPayload(TypedDict, total=False):
    total_files: int
    completed_files: int
    failed_files: int
    percent: int
    current_file: str
    phase: str


class AnalyzeTimingPayload(TypedDict, total=False):
    elapsed_ms: int
    eta_ms: Optional[int]


class AnalyzeJobState(TypedDict, total=False):
    job_id: str
    status: str
    created_at: int
    started_at: Optional[int]
    finished_at: Optional[int]
    request: Dict[str, Any]
    progress: AnalyzeProgressPayload
    timing: AnalyzeTimingPayload
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    request_id: str


class CodeInspectorHandler(AnalyzeJobMixin, RequestValidationMixin, HealthCheckMixin, SimpleHTTPRequestHandler):

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
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, X-Autofix-Benchmark-Observe-Mode, "
            "X-Autofix-Benchmark-Tuning-Min-Confidence, "
            "X-Autofix-Benchmark-Tuning-Min-Gap, "
            "X-Autofix-Benchmark-Tuning-Max-Line-Drift, "
            "X-Autofix-Benchmark-Force-Structured-Instruction",
        )

    @staticmethod
    def _safe_int(value, fallback=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _epoch_ms() -> int:
        return int(time.time() * 1000)


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

    def _handle_generate_ai_review(self, request_id: str):
        body = self._read_json_body()
        if not isinstance(body, dict):
            raise ValueError("JSON body must be an object")
        typed_body = cast(AIReviewGenerateRequestBody, body)
        violation = typed_body.get("violation", {})
        enable_live_ai = typed_body.get("enable_live_ai", None)
        ai_model_name = typed_body.get("ai_model_name", None)
        ai_with_context = typed_body.get("ai_with_context", False)

        if not isinstance(violation, dict):
            raise ValueError("violation must be an object")
        if enable_live_ai is not None and not isinstance(enable_live_ai, bool):
            raise ValueError("enable_live_ai must be a boolean when provided")
        if ai_model_name is not None and not isinstance(ai_model_name, str):
            raise ValueError("ai_model_name must be a string when provided")
        if not isinstance(ai_with_context, bool):
            raise ValueError("ai_with_context must be a boolean")

        logger.info(
            "AI generate request start id=%s issue_id=%s rule_id=%s",
            request_id,
            str((violation or {}).get("issue_id", "") or ""),
            str((violation or {}).get("rule_id", "") or ""),
        )
        result = self.app.generate_ai_review_for_violation(
            cast(Dict[str, Any], violation),
            enable_live_ai=enable_live_ai,
            ai_model_name=cast(Optional[str], ai_model_name),
            ai_with_context=bool(ai_with_context),
            request_id=request_id,
        )
        self._send_json(HTTPStatus.OK, result)
        logger.info("AI generate request done id=%s status=200 available=%s", request_id, bool(result.get("available", False)))

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
        benchmark_observe_mode = str(self.headers.get("X-Autofix-Benchmark-Observe-Mode", "") or "").strip().lower()
        tune_min_confidence_header = self.headers.get("X-Autofix-Benchmark-Tuning-Min-Confidence", None)
        tune_min_gap_header = self.headers.get("X-Autofix-Benchmark-Tuning-Min-Gap", None)
        tune_max_drift_header = self.headers.get("X-Autofix-Benchmark-Tuning-Max-Line-Drift", None)
        force_structured_header = self.headers.get("X-Autofix-Benchmark-Force-Structured-Instruction", None)

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
        if benchmark_observe_mode and benchmark_observe_mode not in ("strict_hash", "benchmark_relaxed"):
            raise ValueError("X-Autofix-Benchmark-Observe-Mode must be one of: strict_hash, benchmark_relaxed")
        benchmark_tuning_min_confidence = None
        benchmark_tuning_min_gap = None
        benchmark_tuning_max_line_drift = None
        benchmark_force_structured_instruction = False
        if tune_min_confidence_header not in (None, ""):
            try:
                benchmark_tuning_min_confidence = float(tune_min_confidence_header)
            except (TypeError, ValueError):
                raise ValueError("X-Autofix-Benchmark-Tuning-Min-Confidence must be a float")
            if not (0.5 <= benchmark_tuning_min_confidence <= 0.99):
                raise ValueError("X-Autofix-Benchmark-Tuning-Min-Confidence must be within [0.5, 0.99]")
        if tune_min_gap_header not in (None, ""):
            try:
                benchmark_tuning_min_gap = float(tune_min_gap_header)
            except (TypeError, ValueError):
                raise ValueError("X-Autofix-Benchmark-Tuning-Min-Gap must be a float")
            if not (0.0 <= benchmark_tuning_min_gap <= 0.5):
                raise ValueError("X-Autofix-Benchmark-Tuning-Min-Gap must be within [0.0, 0.5]")
        if tune_max_drift_header not in (None, ""):
            try:
                benchmark_tuning_max_line_drift = int(tune_max_drift_header)
            except (TypeError, ValueError):
                raise ValueError("X-Autofix-Benchmark-Tuning-Max-Line-Drift must be an integer")
            if not (10 <= benchmark_tuning_max_line_drift <= 2000):
                raise ValueError("X-Autofix-Benchmark-Tuning-Max-Line-Drift must be within [10, 2000]")
        if force_structured_header not in (None, ""):
            normalized_force = str(force_structured_header or "").strip().lower()
            if normalized_force in ("1", "true", "yes", "on"):
                benchmark_force_structured_instruction = True
            elif normalized_force in ("0", "false", "no", "off"):
                benchmark_force_structured_instruction = False
            else:
                raise ValueError(
                    "X-Autofix-Benchmark-Force-Structured-Instruction must be a boolean-like value"
                )

        logger.info("Autofix apply start id=%s proposal_id=%s", request_id, proposal_id)
        result = self.app.apply_autofix_proposal(
            proposal_id=proposal_id,
            session_id=session_id,
            file_name=file_name or "",
            expected_base_hash=expected_base_hash or "",
            apply_mode=apply_mode,
            block_on_regression=block_on_regression,
            check_ctrlpp_regression=check_ctrlpp_regression,
            benchmark_observe_mode=benchmark_observe_mode or "strict_hash",
            benchmark_tuning_min_confidence=benchmark_tuning_min_confidence,
            benchmark_tuning_min_gap=benchmark_tuning_min_gap,
            benchmark_tuning_max_line_drift=benchmark_tuning_max_line_drift,
            benchmark_force_structured_instruction=benchmark_force_structured_instruction,
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

    def _resolve_excel_download_path(self, output_dir: str, name: str) -> str:
        safe_output_dir = str(output_dir or "").strip()
        safe_name = str(name or "").strip()
        if not safe_output_dir:
            raise ValueError("output_dir is required")
        if not safe_name:
            raise ValueError("name is required")

        normalized_name = posixpath.basename(safe_name.replace("\\", "/"))
        if normalized_name != safe_name or not safe_name.lower().endswith(".xlsx"):
            raise ValueError("name must be an .xlsx file in the target output directory")

        output_root = os.path.abspath(
            str(getattr(getattr(self.app, "reporter", None), "output_base_dir", "") or os.path.join(BASE_DIR, "CodeReview_Report"))
        )
        target_output_dir = os.path.abspath(safe_output_dir)
        try:
            if os.path.commonpath([output_root, target_output_dir]) != output_root:
                raise ValueError("output_dir must be inside the report output directory")
        except ValueError as exc:
            raise ValueError("output_dir must be inside the report output directory") from exc

        report_path = os.path.abspath(os.path.join(target_output_dir, normalized_name))
        try:
            if os.path.commonpath([target_output_dir, report_path]) != target_output_dir:
                raise ValueError("name must resolve inside output_dir")
        except ValueError as exc:
            raise ValueError("name must resolve inside output_dir") from exc

        if not os.path.isfile(report_path):
            raise FileNotFoundError(f"Excel report not found: {normalized_name}")
        return report_path

    def _send_download_file(self, file_path: str, download_name: str, content_type: str):
        with open(file_path, "rb") as f:
            data = f.read()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(data)


    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/health/deps":
            self._send_json(HTTPStatus.OK, self._build_dependency_health_payload())
            return

        if parsed.path == "/api/rules/health":
            self._send_json(HTTPStatus.OK, self._build_rules_health_payload())
            return

        if parsed.path == "/api/rules/list":
            self._send_json(HTTPStatus.OK, self._build_rules_list_payload())
            return

        if parsed.path == "/api/rules/export":
            self._send_json(HTTPStatus.OK, self._export_rules_payload())
            return

        if parsed.path == "/api/verification/latest":
            try:
                self._send_json(HTTPStatus.OK, self._resolve_latest_verification_summary())
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            except RuntimeError as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            return

        if parsed.path == "/api/operations/latest":
            self._send_json(HTTPStatus.OK, self._resolve_latest_operational_results())
            return

        if parsed.path == "/api/analysis-diff/latest":
            try:
                self._send_json(HTTPStatus.OK, self._resolve_latest_analysis_diff())
            except RuntimeError as exc:
                self._send_json(HTTPStatus.OK, {"available": False, "message": str(exc), "latest": None, "previous": None, "delta": {"summary": {}}, "file_diffs": []})
            return

        if parsed.path == "/api/analysis-diff/runs":
            self._send_json(HTTPStatus.OK, self._resolve_analysis_diff_runs())
            return

        if parsed.path == "/api/analysis-diff/compare":
            query = parse_qs(parsed.query)
            latest_key = str(query.get("latest", [""])[0] or "")
            previous_key = str(query.get("previous", [""])[0] or "")
            try:
                self._send_json(HTTPStatus.OK, self._resolve_selected_analysis_diff(latest_key, previous_key))
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            except RuntimeError as exc:
                self._send_json(HTTPStatus.OK, {"available": False, "message": str(exc), "latest": None, "previous": None, "delta": {"summary": {}}, "file_diffs": []})
            return

        if parsed.path == "/api/analyze/status":
            try:
                self._handle_analyze_status()
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            return

        if parsed.path == "/api/files":
            query = parse_qs(parsed.query)
            allow_raw_txt = str(query.get("allow_raw_txt", ["false"])[0]).lower() in ("1", "true", "yes", "on")
            payload = {"files": self.app.list_available_files(allow_raw_txt=allow_raw_txt)}
            self._send_json(HTTPStatus.OK, payload)
            return

        if parsed.path == "/api/ai/models":
            self._send_json(HTTPStatus.OK, self.app.list_ai_models())
            return

        if parsed.path == "/api/report/excel/download":
            query = parse_qs(parsed.query)
            output_dir = str(query.get("output_dir", [""])[0] or "")
            name = str(query.get("name", [""])[0] or "")
            try:
                report_path = self._resolve_excel_download_path(output_dir, name)
                self._send_download_file(
                    report_path,
                    os.path.basename(report_path),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            return

        if parsed.path == "/api/file-content":
            query = parse_qs(parsed.query)
            name = str(query.get("name", [""])[0] or "")
            prefer_source = str(query.get("prefer_source", ["false"])[0]).lower() in ("1", "true", "yes", "on")
            output_dir = str(query.get("output_dir", [""])[0] or "")
            try:
                payload = self.app.get_viewer_content(
                    name,
                    prefer_source=prefer_source,
                    output_dir=output_dir or None,
                )
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
        if parsed.path == "/api/input-sources/stage":
            request_id = uuid.uuid4().hex
            try:
                payload = self._read_multipart_files()
                result = self.app.stage_input_files(payload.get("files", []), mode=str(payload.get("mode", "files") or "files"))
                result["request_id"] = request_id
                self._send_json(HTTPStatus.OK, result)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc), "request_id": request_id})
                logger.warning("Input source stage done id=%s status=400 error=%s", request_id, exc)
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc), "request_id": request_id})
                logger.error("Input source stage done id=%s status=500 error=%s", request_id, exc)
            return

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

        if parsed.path == "/api/ai-review/generate":
            request_id = uuid.uuid4().hex
            try:
                self._handle_generate_ai_review(request_id)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc), "request_id": request_id})
                logger.warning("AI generate request done id=%s status=400 error=%s", request_id, exc)
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc), "request_id": request_id})
                logger.warning("AI generate request done id=%s status=404 error=%s", request_id, exc)
            except ReviewerError as exc:
                self._send_json(HTTPStatus.OK, {"available": False, "message": str(exc), "request_id": request_id})
                logger.warning("AI generate request done id=%s status=200 fail-soft error=%s", request_id, exc)
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc), "request_id": request_id})
                logger.error("AI generate request done id=%s status=500 error=%s", request_id, exc)
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

        if parsed.path == "/api/rules/update":
            request_id = uuid.uuid4().hex
            try:
                body = self._read_json_body()
                if not isinstance(body, dict):
                    raise ValueError("JSON body must be an object")
                typed_body = cast(RuleUpdateRequestBody, body)
                result = self._update_rules_enabled_state(list(typed_body.get("updates", []) or []))
                result["request_id"] = request_id
                self._send_json(HTTPStatus.OK, result)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc), "request_id": request_id})
                logger.warning("Rules update done id=%s status=400 error=%s", request_id, exc)
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc), "request_id": request_id})
                logger.warning("Rules update done id=%s status=404 error=%s", request_id, exc)
            except RuntimeError as exc:
                self._send_json(getattr(HTTPStatus, "CONFLICT", 409), {"error": str(exc), "request_id": request_id})
                logger.warning("Rules update done id=%s status=409 error=%s", request_id, exc)
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc), "request_id": request_id})
                logger.error("Rules update done id=%s status=500 error=%s", request_id, exc)
            return

        if parsed.path == "/api/rules/create":
            request_id = uuid.uuid4().hex
            try:
                body = self._read_json_body()
                if not isinstance(body, dict):
                    raise ValueError("JSON body must be an object")
                typed_body = cast(RuleRecordRequestBody, body)
                result = self._create_rule(cast(Dict[str, Any], typed_body.get("rule", {})))
                result["request_id"] = request_id
                self._send_json(HTTPStatus.OK, result)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc), "request_id": request_id})
                logger.warning("Rules create done id=%s status=400 error=%s", request_id, exc)
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc), "request_id": request_id})
                logger.warning("Rules create done id=%s status=404 error=%s", request_id, exc)
            except RuntimeError as exc:
                self._send_json(getattr(HTTPStatus, "CONFLICT", 409), {"error": str(exc), "request_id": request_id})
                logger.warning("Rules create done id=%s status=409 error=%s", request_id, exc)
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc), "request_id": request_id})
                logger.error("Rules create done id=%s status=500 error=%s", request_id, exc)
            return

        if parsed.path == "/api/rules/replace":
            request_id = uuid.uuid4().hex
            try:
                body = self._read_json_body()
                if not isinstance(body, dict):
                    raise ValueError("JSON body must be an object")
                typed_body = cast(RuleRecordRequestBody, body)
                result = self._replace_rule(cast(Dict[str, Any], typed_body.get("rule", {})))
                result["request_id"] = request_id
                self._send_json(HTTPStatus.OK, result)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc), "request_id": request_id})
                logger.warning("Rules replace done id=%s status=400 error=%s", request_id, exc)
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc), "request_id": request_id})
                logger.warning("Rules replace done id=%s status=404 error=%s", request_id, exc)
            except RuntimeError as exc:
                self._send_json(getattr(HTTPStatus, "CONFLICT", 409), {"error": str(exc), "request_id": request_id})
                logger.warning("Rules replace done id=%s status=409 error=%s", request_id, exc)
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc), "request_id": request_id})
                logger.error("Rules replace done id=%s status=500 error=%s", request_id, exc)
            return

        if parsed.path == "/api/rules/delete":
            request_id = uuid.uuid4().hex
            try:
                body = self._read_json_body()
                if not isinstance(body, dict):
                    raise ValueError("JSON body must be an object")
                typed_body = cast(RuleDeleteRequestBody, body)
                result = self._delete_rule(str(typed_body.get("id", "") or ""))
                result["request_id"] = request_id
                self._send_json(HTTPStatus.OK, result)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc), "request_id": request_id})
                logger.warning("Rules delete done id=%s status=400 error=%s", request_id, exc)
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc), "request_id": request_id})
                logger.warning("Rules delete done id=%s status=404 error=%s", request_id, exc)
            except RuntimeError as exc:
                self._send_json(getattr(HTTPStatus, "CONFLICT", 409), {"error": str(exc), "request_id": request_id})
                logger.warning("Rules delete done id=%s status=409 error=%s", request_id, exc)
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc), "request_id": request_id})
                logger.error("Rules delete done id=%s status=500 error=%s", request_id, exc)
            return

        if parsed.path == "/api/rules/import":
            request_id = uuid.uuid4().hex
            try:
                body = self._read_json_body()
                if not isinstance(body, dict):
                    raise ValueError("JSON body must be an object")
                typed_body = cast(RuleImportRequestBody, body)
                result = self._import_rules_payload(
                    list(typed_body.get("rules", []) or []),
                    mode=str(typed_body.get("mode", "replace") or "replace"),
                )
                result["request_id"] = request_id
                self._send_json(HTTPStatus.OK, result)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc), "request_id": request_id})
                logger.warning("Rules import done id=%s status=400 error=%s", request_id, exc)
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc), "request_id": request_id})
                logger.warning("Rules import done id=%s status=404 error=%s", request_id, exc)
            except RuntimeError as exc:
                self._send_json(getattr(HTTPStatus, "CONFLICT", 409), {"error": str(exc), "request_id": request_id})
                logger.warning("Rules import done id=%s status=409 error=%s", request_id, exc)
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc), "request_id": request_id})
                logger.error("Rules import done id=%s status=500 error=%s", request_id, exc)
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
                request_id, len(selected_files), allow_raw_txt,
            )
            # File-type routing is handled in main.py: .ctl => Server, .txt => Client rules.
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
