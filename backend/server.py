import json
import logging
import os
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


class CodeInspectorHandler(SimpleHTTPRequestHandler):
    _analyze_jobs: Dict[str, AnalyzeJobState] = {}
    _analyze_jobs_lock = threading.RLock()
    _analyze_job_ttl_sec = 1800
    _analyze_job_max_entries = 64
    _analyze_poll_interval_ms = 500

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

    @classmethod
    def _prune_analyze_jobs(cls) -> None:
        now = time.time()
        with cls._analyze_jobs_lock:
            stale = []
            for job_id, job in list(cls._analyze_jobs.items()):
                finished_ms = job.get("finished_at")
                if not finished_ms:
                    continue
                age_sec = now - (float(finished_ms) / 1000.0)
                if age_sec > cls._analyze_job_ttl_sec:
                    stale.append(job_id)
            for job_id in stale:
                cls._analyze_jobs.pop(job_id, None)
            while len(cls._analyze_jobs) > cls._analyze_job_max_entries:
                oldest = next(iter(cls._analyze_jobs))
                cls._analyze_jobs.pop(oldest, None)

    @classmethod
    def _compute_eta_ms(cls, progress: AnalyzeProgressPayload, started_at_ms: Optional[int]) -> Optional[int]:
        if not started_at_ms:
            return None
        total = max(0, cls._safe_int(progress.get("total_files", 0), 0))
        completed = max(0, cls._safe_int(progress.get("completed_files", 0), 0))
        if total <= 0 or completed <= 0:
            return None
        elapsed_ms = max(0, cls._epoch_ms() - int(started_at_ms))
        ratio = float(completed) / float(total)
        if ratio <= 0.0:
            return None
        return max(0, int(elapsed_ms * (1.0 - ratio) / ratio))

    @classmethod
    def _refresh_job_timing_locked(cls, job: AnalyzeJobState) -> None:
        started_at = job.get("started_at")
        timing = cast(AnalyzeTimingPayload, job.setdefault("timing", {}))
        if started_at:
            timing["elapsed_ms"] = max(0, cls._epoch_ms() - int(started_at))
        else:
            timing["elapsed_ms"] = 0
        timing["eta_ms"] = cls._compute_eta_ms(cast(AnalyzeProgressPayload, job.get("progress", {})), started_at)

    @classmethod
    def _public_analyze_job_view(cls, job: AnalyzeJobState) -> Dict[str, Any]:
        with cls._analyze_jobs_lock:
            cls._refresh_job_timing_locked(job)
            payload: Dict[str, Any] = {
                "job_id": str(job.get("job_id", "") or ""),
                "status": str(job.get("status", "unknown") or "unknown"),
                "request_id": str(job.get("request_id", "") or ""),
                "progress": dict(job.get("progress", {}) or {}),
                "timing": dict(job.get("timing", {}) or {}),
                "error": job.get("error"),
                "created_at": job.get("created_at"),
                "started_at": job.get("started_at"),
                "finished_at": job.get("finished_at"),
            }
            if payload["status"] == "completed" and isinstance(job.get("result"), dict):
                payload["result"] = job["result"]
            return payload

    def _parse_analyze_request_body(self, *, validate_selected_files: bool) -> Dict[str, Any]:
        body = self._read_json_body()
        if not isinstance(body, dict):
            raise ValueError("JSON body must be an object")
        typed_body = cast(AnalyzeRequestBody, body)
        mode = typed_body.get("mode", DEFAULT_MODE)
        selected_files = typed_body.get("selected_files", [])
        input_sources = typed_body.get("input_sources", [])
        if not isinstance(selected_files, list):
            raise ValueError("selected_files must be a list")

        allow_raw_txt = typed_body.get("allow_raw_txt", False)
        if not isinstance(allow_raw_txt, bool):
            raise ValueError("allow_raw_txt must be a boolean")
        enable_ctrlppcheck = typed_body.get("enable_ctrlppcheck", None)
        enable_live_ai = typed_body.get("enable_live_ai", None)
        ai_model_name = typed_body.get("ai_model_name", None)
        ai_with_context = typed_body.get("ai_with_context", False)
        defer_excel_reports = typed_body.get("defer_excel_reports", None)
        if enable_ctrlppcheck is not None and not isinstance(enable_ctrlppcheck, bool):
            raise ValueError("enable_ctrlppcheck must be a boolean")
        if enable_live_ai is not None and not isinstance(enable_live_ai, bool):
            raise ValueError("enable_live_ai must be a boolean")
        if not isinstance(ai_with_context, bool):
            raise ValueError("ai_with_context must be a boolean")
        if ai_model_name is not None and not isinstance(ai_model_name, str):
            raise ValueError("ai_model_name must be a string when provided")
        if defer_excel_reports is not None and not isinstance(defer_excel_reports, bool):
            raise ValueError("defer_excel_reports must be a boolean when provided")
        if validate_selected_files:
            self._validate_selected_files(selected_files, allow_raw_txt=allow_raw_txt)
        validated_input_sources = self._validate_input_sources(input_sources, allow_raw_txt=allow_raw_txt)

        return {
            "mode": mode,
            "selected_files": selected_files,
            "input_sources": validated_input_sources,
            "allow_raw_txt": allow_raw_txt,
            "enable_ctrlppcheck": enable_ctrlppcheck,
            "enable_live_ai": enable_live_ai,
            "ai_model_name": str(ai_model_name or "").strip() or None,
            "ai_with_context": ai_with_context,
            "defer_excel_reports": defer_excel_reports,
        }

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

    @staticmethod
    def _is_local_absolute_path(path_value: str) -> bool:
        if not isinstance(path_value, str) or not path_value.strip():
            return False
        if path_value.startswith("\\\\"):
            return False
        return os.path.isabs(path_value)

    @classmethod
    def _is_supported_input_file(cls, path_value: str, *, allow_raw_txt: bool) -> bool:
        lower = str(path_value or "").lower()
        if lower.endswith((".ctl", ".pnl", ".xml")):
            return True
        if lower.endswith(".txt"):
            name = os.path.basename(path_value)
            return allow_raw_txt or cls._is_normalized_txt(name)
        return False

    @classmethod
    def _folder_has_supported_targets(cls, folder_path: str, *, allow_raw_txt: bool) -> bool:
        for root, _dirs, files in os.walk(folder_path):
            for name in files:
                if cls._is_supported_input_file(os.path.join(root, name), allow_raw_txt=allow_raw_txt):
                    return True
        return False

    def _validate_input_sources(self, input_sources, allow_raw_txt=False):
        if input_sources is None:
            return []
        if not isinstance(input_sources, list):
            raise ValueError("input_sources must be a list")
        validated = []
        for item in input_sources:
            if not isinstance(item, dict):
                raise ValueError("input_sources entries must be objects")
            source_type = str(item.get("type", "") or "").strip()
            source_value = str(item.get("value", "") or "").strip()
            if source_type not in ("builtin_file", "file_path", "folder_path"):
                raise ValueError(f"Unsupported input source type: {source_type}")
            if not source_value:
                raise ValueError("input_sources value is required")
            if source_type != "builtin_file":
                if not self._is_local_absolute_path(source_value):
                    raise ValueError(f"input_sources path must be a local absolute path: {source_value}")
                normalized = os.path.normpath(source_value)
                if source_type == "file_path" and not os.path.isfile(normalized):
                    raise ValueError(f"Input file not found: {source_value}")
                if source_type == "folder_path" and not os.path.isdir(normalized):
                    raise ValueError(f"Input folder not found: {source_value}")
                source_value = normalized
                if source_type == "file_path" and source_value.lower().endswith(".txt") and not allow_raw_txt:
                    name = os.path.basename(source_value)
                    if self._is_txt(name) and not self._is_normalized_txt(name):
                        raise ValueError(f"Raw .txt selection is disabled: {source_value}")
                if source_type == "file_path" and not self._is_supported_input_file(source_value, allow_raw_txt=allow_raw_txt):
                    raise ValueError(f"Unsupported input file type: {source_value}")
                if source_type == "folder_path" and not self._folder_has_supported_targets(source_value, allow_raw_txt=allow_raw_txt):
                    raise ValueError(f"Input folder has no supported review files: {source_value}")
            validated.append({"type": source_type, "value": source_value})
        return validated

    def _read_multipart_files(self) -> Dict[str, Any]:
        content_type = str(self.headers.get("Content-Type", "") or "")
        if "multipart/form-data" not in content_type.lower():
            raise ValueError("multipart/form-data content type is required")
        try:
            content_length = int(self.headers.get("Content-Length", "0") or "0")
        except (TypeError, ValueError):
            raise ValueError("Invalid Content-Length")
        raw_body = self.rfile.read(content_length) if content_length > 0 else b""
        if not raw_body:
            return {"mode": "files", "files": []}

        message_bytes = (
            f"Content-Type: {content_type}\r\n"
            "MIME-Version: 1.0\r\n"
            "\r\n"
        ).encode("utf-8") + raw_body
        message = BytesParser(policy=policy.default).parsebytes(message_bytes)

        mode = "files"
        uploaded = []
        for part in message.iter_parts():
            if part.get_content_disposition() != "form-data":
                continue
            field_name = str(part.get_param("name", header="content-disposition") or "")
            filename = str(part.get_filename() or "")
            if field_name == "mode":
                mode_text = part.get_content()
                mode = str(mode_text or "files").strip() or "files"
                continue
            if field_name != "files" or not filename:
                continue
            payload = part.get_payload(decode=True)
            uploaded.append({"name": filename, "content": payload if isinstance(payload, bytes) else b""})
        return {"mode": mode, "files": uploaded}

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

    def _run_analyze_job(self, job_id: str, request_id: str, analyze_args: Dict[str, Any]) -> None:
        try:
            with self._analyze_jobs_lock:
                job = self._analyze_jobs.get(job_id)
                if not job:
                    return
                job["status"] = "running"
                job["started_at"] = self._epoch_ms()
                self._refresh_job_timing_locked(job)

            total_selected = max(0, self._safe_int(len(analyze_args.get("selected_files", []) or []), 0))
            total_inputs = total_selected + max(0, self._safe_int(len(analyze_args.get("input_sources", []) or []), 0))

            def progress_cb(event: Dict[str, Any]) -> None:
                with self._analyze_jobs_lock:
                    current = self._analyze_jobs.get(job_id)
                    if not current:
                        return
                    progress = cast(AnalyzeProgressPayload, current.setdefault("progress", {}))
                    total = max(1, self._safe_int(event.get("total_files", total_inputs), total_inputs or 1))
                    completed = max(0, self._safe_int(event.get("completed_files", 0), 0))
                    failed = max(0, self._safe_int(event.get("failed_files", 0), 0))
                    progress["total_files"] = total
                    progress["completed_files"] = completed
                    progress["failed_files"] = failed
                    progress["current_file"] = str(event.get("file", "") or "")
                    progress["phase"] = str(event.get("phase", "") or "")
                    progress["percent"] = max(0, min(100, int((float(completed) / float(total)) * 100)))
                    self._refresh_job_timing_locked(current)

            # Keep start-path behavior explicit: unknown file/raw-txt policy errors surface as failed job.
            self._validate_selected_files(
                analyze_args.get("selected_files", []),
                allow_raw_txt=bool(analyze_args.get("allow_raw_txt", False)),
            )
            result = self.app.run_directory_analysis(
                mode=analyze_args.get("mode", DEFAULT_MODE),
                selected_files=analyze_args.get("selected_files", []),
                input_sources=analyze_args.get("input_sources", []),
                allow_raw_txt=bool(analyze_args.get("allow_raw_txt", False)),
                enable_ctrlppcheck=analyze_args.get("enable_ctrlppcheck", None),
                enable_live_ai=analyze_args.get("enable_live_ai", None),
                ai_model_name=analyze_args.get("ai_model_name", None),
                ai_with_context=bool(analyze_args.get("ai_with_context", False)),
                request_id=request_id,
                defer_excel_reports=analyze_args.get("defer_excel_reports", None),
                progress_cb=progress_cb,
            )
            response_status = self._analysis_response_status(result)
            elapsed_ms = int((time.perf_counter() - float(analyze_args.get("_request_started", time.perf_counter()))) * 1000)
            if isinstance(result.get("metrics"), dict):
                timings = result["metrics"].setdefault("timings_ms", {})
                if isinstance(timings, dict) and not timings.get("server_total"):
                    timings["server_total"] = elapsed_ms
            result.setdefault("request_id", request_id)

            with self._analyze_jobs_lock:
                job = self._analyze_jobs.get(job_id)
                if not job:
                    return
                job["status"] = "completed" if int(response_status) < 500 else "failed"
                job["finished_at"] = self._epoch_ms()
                if job["status"] == "completed":
                    job["result"] = result
                    progress = cast(AnalyzeProgressPayload, job.setdefault("progress", {}))
                    total = max(1, self._safe_int(progress.get("total_files", total_selected), total_selected or 1))
                    progress["total_files"] = total
                    progress["percent"] = 100
                else:
                    job["error"] = "Analyze completed with internal errors"
                self._refresh_job_timing_locked(job)
                self._prune_analyze_jobs()
        except Exception as exc:
            with self._analyze_jobs_lock:
                job = self._analyze_jobs.get(job_id)
                if job:
                    job["status"] = "failed"
                    job["error"] = str(exc)
                    job["finished_at"] = self._epoch_ms()
                    self._refresh_job_timing_locked(job)
                    self._prune_analyze_jobs()
            logger.exception("Analyze async job failed id=%s request_id=%s error=%s", job_id, request_id, exc)

    def _handle_analyze_start(self, request_id: str, request_started: float) -> None:
        analyze_args = self._parse_analyze_request_body(validate_selected_files=False)
        selected_files = analyze_args.get("selected_files", []) or []
        logger.info(
            "Analyze async request start id=%s selected=%d allow_raw_txt=%s",
            request_id,
            len(selected_files),
            bool(analyze_args.get("allow_raw_txt", False)),
        )

        job_id = uuid.uuid4().hex
        created_at = self._epoch_ms()
        initial_total = max(0, self._safe_int(len(selected_files), 0)) + max(
            0,
            self._safe_int(len(analyze_args.get("input_sources", []) or []), 0),
        )
        with self._analyze_jobs_lock:
            self._prune_analyze_jobs()
            self._analyze_jobs[job_id] = cast(
                AnalyzeJobState,
                {
                    "job_id": job_id,
                    "status": "queued",
                    "created_at": created_at,
                    "started_at": None,
                    "finished_at": None,
                    "request": {
                        "selected_count": max(0, self._safe_int(len(selected_files), 0)),
                        "input_source_count": max(0, self._safe_int(len(analyze_args.get("input_sources", []) or []), 0)),
                        "enable_live_ai": bool(analyze_args.get("enable_live_ai", False)),
                        "enable_ctrlppcheck": bool(analyze_args.get("enable_ctrlppcheck", False)),
                        "allow_raw_txt": bool(analyze_args.get("allow_raw_txt", False)),
                    },
                    "progress": {
                        "total_files": initial_total,
                        "completed_files": 0,
                        "failed_files": 0,
                        "percent": 0,
                        "current_file": "",
                        "phase": "queued",
                    },
                    "timing": {"elapsed_ms": 0, "eta_ms": None},
                    "result": None,
                    "error": None,
                    "request_id": request_id,
                },
            )
        analyze_args["_request_started"] = request_started

        worker = threading.Thread(
            target=self._run_analyze_job,
            args=(job_id, request_id, analyze_args),
            daemon=True,
        )
        worker.start()
        self._send_json(
            getattr(HTTPStatus, "ACCEPTED", 202),
            {
                "job_id": job_id,
                "status": "queued",
                "progress": {"total_files": initial_total, "completed_files": 0, "failed_files": 0, "percent": 0, "current_file": "", "phase": "queued"},
                "poll_interval_ms": self._analyze_poll_interval_ms,
                "request_id": request_id,
            },
        )

    def _playwright_dependency_status(self) -> Dict[str, Any]:
        node_bin = shutil.which("node")
        if not node_bin:
            return {
                "available": False,
                "node_available": False,
                "package_available": False,
                "required_for": ["ui_benchmark"],
                "message": "node binary not found",
            }

        try:
            proc = subprocess.run(
                [node_bin, "-e", "require.resolve('playwright')"],
                cwd=BASE_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=3,
                check=False,
            )
        except Exception as exc:
            return {
                "available": False,
                "node_available": True,
                "package_available": False,
                "required_for": ["ui_benchmark"],
                "message": f"playwright package check failed: {exc}",
            }

        package_available = proc.returncode == 0
        return {
            "available": bool(package_available),
            "node_available": True,
            "package_available": bool(package_available),
            "required_for": ["ui_benchmark"],
            "message": "playwright package available" if package_available else "playwright package is not installed",
        }

    def _build_dependency_health_payload(self) -> Dict[str, Any]:
        excel_available = bool(self.app.reporter.is_excel_support_available())
        openpyxl_status = {
            "available": excel_available,
            "required_for": ["excel_report", "template_coverage"],
            "message": "openpyxl available" if excel_available else "openpyxl is not installed",
        }

        ctrl_binary = ""
        try:
            ctrl_binary = str(self.app.ctrl_tool._find_binary() or "")
        except Exception:
            ctrl_binary = ""
        ctrl_ready = bool(ctrl_binary)
        ctrl_status = {
            "available": ctrl_ready,
            "binary_path": ctrl_binary,
            "auto_install_on_missing": bool(getattr(self.app.ctrl_tool, "auto_install_on_missing", False)),
            "required_for": ["ctrlpp_analysis", "ctrlpp_regression"],
            "message": "CtrlppCheck binary available" if ctrl_ready else "CtrlppCheck binary not found",
        }

        playwright_status = self._playwright_dependency_status()
        capabilities = {
            "excel_report": {"ready": bool(openpyxl_status["available"]), "dependencies": ["openpyxl"]},
            "template_coverage": {"ready": bool(openpyxl_status["available"]), "dependencies": ["openpyxl"]},
            "ctrlpp_analysis": {"ready": bool(ctrl_status["available"]), "dependencies": ["ctrlppcheck"]},
            "ui_benchmark": {"ready": bool(playwright_status["available"]), "dependencies": ["playwright"]},
        }
        ready_count = sum(1 for item in capabilities.values() if bool(item.get("ready", False)))
        return {
            "status": "ok" if ready_count == len(capabilities) else "degraded",
            "generated_at_ms": self._epoch_ms(),
            "dependencies": {
                "openpyxl": openpyxl_status,
                "ctrlppcheck": ctrl_status,
                "playwright": playwright_status,
            },
            "capabilities": capabilities,
            "summary": {
                "ready_capabilities": ready_count,
                "total_capabilities": len(capabilities),
            },
        }

    def _resolve_latest_verification_summary(self) -> Dict[str, Any]:
        report_dir = Path(str(getattr(self.app.reporter, "output_base_dir", "") or "")).resolve()
        if not report_dir.exists() or not report_dir.is_dir():
            raise FileNotFoundError(f"verification report directory not found: {report_dir}")

        candidates = sorted(
            report_dir.glob("verification_summary_*.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            raise FileNotFoundError("verification summary not found")

        latest = candidates[0]
        try:
            payload = json.loads(latest.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError(f"failed to read verification summary: {latest.name}: {exc}") from exc

        if not isinstance(payload, dict):
            raise RuntimeError(f"invalid verification summary payload: {latest.name}")

        payload.setdefault("source_file", latest.name)
        payload.setdefault("source_path", str(latest))
        return payload

    def _handle_analyze_status(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        job_id = str(query.get("job_id", [""])[0] or "").strip()
        if not job_id:
            raise ValueError("job_id is required")
        with self._analyze_jobs_lock:
            self._prune_analyze_jobs()
            job = self._analyze_jobs.get(job_id)
            if not job:
                raise FileNotFoundError(f"Analyze job not found: {job_id}")
        self._send_json(HTTPStatus.OK, self._public_analyze_job_view(job))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/health/deps":
            self._send_json(HTTPStatus.OK, self._build_dependency_health_payload())
            return

        if parsed.path == "/api/verification/latest":
            try:
                self._send_json(HTTPStatus.OK, self._resolve_latest_verification_summary())
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            except RuntimeError as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
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
