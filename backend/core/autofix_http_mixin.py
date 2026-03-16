import logging
import os
import posixpath
from http import HTTPStatus
from typing import Any, Dict, cast

from core.api_types import AutofixApplyRequestBody, AutofixPrepareRequestBody, ExcelFlushRequestBody

logger = logging.getLogger(__name__)


class AutofixHttpMixin:
    """Autofix and Excel report request handlers extracted from backend/server.py."""

    def _handle_autofix_prepare(self, request_id: str) -> None:
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

    def _handle_autofix_apply(self, request_id: str) -> None:
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
            except (TypeError, ValueError) as exc:
                raise ValueError("X-Autofix-Benchmark-Tuning-Min-Confidence must be a float") from exc
            if not (0.5 <= benchmark_tuning_min_confidence <= 0.99):
                raise ValueError("X-Autofix-Benchmark-Tuning-Min-Confidence must be within [0.5, 0.99]")
        if tune_min_gap_header not in (None, ""):
            try:
                benchmark_tuning_min_gap = float(tune_min_gap_header)
            except (TypeError, ValueError) as exc:
                raise ValueError("X-Autofix-Benchmark-Tuning-Min-Gap must be a float") from exc
            if not (0.0 <= benchmark_tuning_min_gap <= 0.5):
                raise ValueError("X-Autofix-Benchmark-Tuning-Min-Gap must be within [0.0, 0.5]")
        if tune_max_drift_header not in (None, ""):
            try:
                benchmark_tuning_max_line_drift = int(tune_max_drift_header)
            except (TypeError, ValueError) as exc:
                raise ValueError("X-Autofix-Benchmark-Tuning-Max-Line-Drift must be an integer") from exc
            if not (10 <= benchmark_tuning_max_line_drift <= 2000):
                raise ValueError("X-Autofix-Benchmark-Tuning-Max-Line-Drift must be within [10, 2000]")
        if force_structured_header not in (None, ""):
            normalized_force = str(force_structured_header or "").strip().lower()
            if normalized_force in ("1", "true", "yes", "on"):
                benchmark_force_structured_instruction = True
            elif normalized_force in ("0", "false", "no", "off"):
                benchmark_force_structured_instruction = False
            else:
                raise ValueError("X-Autofix-Benchmark-Force-Structured-Instruction must be a boolean-like value")

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

    def _handle_excel_report_flush(self, request_id: str) -> None:
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

        default_report_root = os.path.join(str(getattr(self.app, "base_dir", "") or ""), "CodeReview_Report")
        output_root = os.path.abspath(
            str(getattr(getattr(self.app, "reporter", None), "output_base_dir", "") or default_report_root)
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
