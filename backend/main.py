import argparse
import collections
import concurrent.futures
import datetime
import difflib
import glob
import hashlib
import json
import logging
import os
import shutil
import tempfile
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, TypedDict, Tuple

from core.ctrl_wrapper import CtrlppWrapper
from core.heuristic_checker import HeuristicChecker
from core.llm_reviewer import LLMReviewer
from core.mcp_context import MCPContextClient
from core.pnl_parser import PnlParser
from core.reporter import Reporter
from core.analysis_pipeline import DirectoryAnalysisPipeline
from core.autofix_apply_engine import apply_with_engine
from core.autofix_instruction import (
    instruction_to_hunks,
    normalize_instruction,
    validate_instruction,
)
from core.autofix_semantic_guard import evaluate_semantic_delta
from core.autofix_tokenizer import locate_anchor_line_by_tokens, normalize_anchor_text
from core.xml_parser import XmlParser

DEFAULT_MODE = "AI 보조"

logger = logging.getLogger(__name__)


class TimingMetrics(TypedDict, total=False):
    total: int
    collect: int
    convert: int
    mcp_context: int
    analyze: int
    report: int
    heuristic: int
    ctrlpp: int
    ai: int
    excel_copy: int
    excel_load: int
    excel_save: int
    server_total: int


class CacheCounterMetrics(TypedDict, total=False):
    hits: int
    misses: int


class PerFileMetricEntry(TypedDict, total=False):
    file: str
    file_type: str
    timings_ms: Dict[str, int]
    bytes_read: int
    bytes_written: int
    llm_calls: int
    ctrlpp_calls: int


class AnalysisMetrics(TypedDict, total=False):
    request_id: str
    file_count: int
    timings_ms: TimingMetrics
    llm_calls: int
    ctrlpp_calls: int
    bytes_read: int
    bytes_written: int
    convert_cache: CacheCounterMetrics
    excel_template_cache: CacheCounterMetrics
    per_file: List[PerFileMetricEntry]


class ExcelTimingMeta(TypedDict, total=False):
    copy: int
    load: int
    save: int


class ExcelReportMeta(TypedDict, total=False):
    generated: bool
    template_cache_hit: bool
    timings_ms: ExcelTimingMeta


class AutoFixQualityMetrics(TypedDict, total=False):
    proposal_id: str
    generator_type: str
    anchors_match: bool
    hash_match: bool
    syntax_check_passed: bool
    heuristic_regression_count: int
    ctrlpp_regression_count: int
    applied: bool
    rejected_reason: str
    validation_errors: List[str]
    locator_mode: str
    apply_engine_mode: str
    apply_engine_fallback_reason: str
    token_fallback_attempted: bool
    token_fallback_confidence: float
    token_fallback_candidates: int
    semantic_check_passed: bool
    semantic_blocked_reason: str
    semantic_violation_count: int
    token_min_confidence_used: float
    token_min_gap_used: float
    token_max_line_drift_used: int
    benchmark_tuning_applied: bool
    token_prefer_nearest_tie_used: bool
    token_hint_bias_used: float
    token_force_nearest_on_ambiguous_used: bool
    benchmark_structured_instruction_forced: bool
    instruction_mode: str
    instruction_validation_errors: List[str]
    instruction_operation: str
    instruction_operation_count: int
    instruction_apply_success: bool
    instruction_path_reason: str
    instruction_failure_stage: str
    instruction_candidate_hunk_count: int
    instruction_applied_hunk_count: int


class AutoFixApplyError(RuntimeError):
    def __init__(self, message: str, error_code: str, quality_metrics: Optional[AutoFixQualityMetrics] = None):
        super().__init__(message)
        self.error_code = str(error_code or "INTERNAL_ERROR")
        self.quality_metrics = quality_metrics or {}


class CodeInspectorApp:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.data_dir = os.path.join(self.base_dir, "CodeReview_Data")
        self.app_config = self._load_app_config()

        self.pnl_parser = PnlParser()
        self.xml_parser = XmlParser()
        self.checker = HeuristicChecker()
        self.ctrl_tool = CtrlppWrapper()
        self.reporter = Reporter()

        ctrlpp_cfg = self.app_config.get("ctrlppcheck", {})
        self.ctrlpp_enabled_default = bool(ctrlpp_cfg.get("enabled_default", False))

        ai_cfg = self.app_config.get("ai", {})
        self.live_ai_enabled_default = bool(ai_cfg.get("enabled_default", False))
        self.ai_tool = LLMReviewer(ai_config=ai_cfg, base_dir=self.base_dir)
        self.ai_focus_snippet_window_lines = max(1, self._safe_int(ai_cfg.get("focus_snippet_window_lines", 8), 8))
        self.ai_focus_snippet_max_lines = max(5, self._safe_int(ai_cfg.get("focus_snippet_max_lines", 80), 80))
        self.live_ai_batch_groups_per_file = max(1, self._safe_int(ai_cfg.get("batch_groups_per_file", 1), 1))
        mcp_cfg = self.app_config.get("mcp", {})
        self.mcp_tool = MCPContextClient(mcp_config=mcp_cfg)
        # Legacy lock kept for compatibility; conversion now uses per-source locks.
        self._analysis_lock = threading.Lock()
        perf_cfg = self.app_config.get("performance", {}) if isinstance(self.app_config.get("performance"), dict) else {}
        cpu_hint = max(1, int(os.cpu_count() or 4))
        self.analysis_max_workers = self._safe_int(perf_cfg.get("analysis_max_workers", min(4, cpu_hint)), min(4, cpu_hint))
        self.ctrlpp_max_workers = self._safe_int(perf_cfg.get("ctrlpp_max_workers", 1), 1)
        self.live_ai_max_workers = self._safe_int(perf_cfg.get("live_ai_max_workers", 1), 1)
        self.report_max_workers = self._safe_int(perf_cfg.get("report_max_workers", 1), 1)
        self.excel_report_max_workers = self._safe_int(perf_cfg.get("excel_report_max_workers", 1), 1)
        # Deferred Excel generation is intentionally disabled (reports are generated immediately).
        self.defer_excel_reports_default = False
        self._ctrlpp_semaphore = threading.Semaphore(max(1, self.ctrlpp_max_workers))
        self._live_ai_semaphore = threading.Semaphore(max(1, self.live_ai_max_workers))
        self._reporter_semaphore = threading.Semaphore(max(1, self.report_max_workers))
        self._excel_report_semaphore = threading.Semaphore(max(1, self.excel_report_max_workers))
        self._excel_report_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max(1, self.excel_report_max_workers),
            thread_name_prefix="excel-report",
        )
        self._metrics_lock = threading.Lock()

        self._conversion_cache = {}
        self._conversion_cache_lock = threading.Lock()
        self._conversion_locks = {}
        self._conversion_locks_guard = threading.Lock()

        autofix_cfg = self.app_config.get("autofix", {}) if isinstance(self.app_config.get("autofix"), dict) else {}
        self.autofix_enabled_default = bool(autofix_cfg.get("enabled_default", True))
        self.autofix_block_on_regression_default = bool(autofix_cfg.get("block_on_regression_default", True))
        self.autofix_ctrlpp_regression_check_default = bool(autofix_cfg.get("ctrlpp_regression_check_default", False))
        self.autofix_proposal_limit_per_session = max(1, self._safe_int(autofix_cfg.get("proposal_limit_per_session", 50), 50))
        self.review_session_ttl_sec = max(60, self._safe_int(autofix_cfg.get("session_ttl_sec", 3600), 3600))
        self.review_session_max_entries = max(1, self._safe_int(autofix_cfg.get("session_max_entries", 32), 32))
        self.autofix_prepare_generator_default = str(autofix_cfg.get("prepare_generator_default", "auto") or "auto").strip().lower()
        if self.autofix_prepare_generator_default not in ("auto", "llm", "rule"):
            self.autofix_prepare_generator_default = "auto"
        self.autofix_allow_fallback_default = bool(autofix_cfg.get("allow_fallback_default", True))
        engine_cfg = autofix_cfg.get("engine", {}) if isinstance(autofix_cfg.get("engine"), dict) else {}
        self.autofix_structured_instruction_enabled = bool(
            engine_cfg.get("structured_instruction_enabled", False)
        )

        self._last_output_dir = ""
        self._review_session_cache = collections.OrderedDict()
        self._review_session_cache_lock = threading.Lock()

    def _load_app_config(self):
        config_path = os.path.join(self.base_dir, "Config", "config.json")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _safe_int(value, fallback=0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _now_ts() -> float:
        return time.time()

    @staticmethod
    def _iso_now() -> str:
        return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    @staticmethod
    def _perf_now() -> float:
        return time.perf_counter()

    @classmethod
    def _elapsed_ms(cls, started: float) -> int:
        return max(0, int((cls._perf_now() - started) * 1000))

    @staticmethod
    def _sha256_text(text: str) -> str:
        return hashlib.sha256(str(text or "").encode("utf-8", errors="ignore")).hexdigest()

    @staticmethod
    def _sha256_file(path: str) -> str:
        digest = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _source_signature(path: str) -> Tuple[int, int]:
        st = os.stat(path)
        return (int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000))), int(st.st_size))

    def _get_conversion_lock(self, source_path: str) -> threading.Lock:
        key = os.path.normpath(str(source_path))
        with self._conversion_locks_guard:
            lock = self._conversion_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._conversion_locks[key] = lock
            return lock

    def _new_metrics(self, request_id: Optional[str] = None) -> AnalysisMetrics:
        return {
            "request_id": str(request_id or uuid.uuid4().hex),
            "file_count": 0,
            "timings_ms": {
                "total": 0,
                "collect": 0,
                "convert": 0,
                "mcp_context": 0,
                "analyze": 0,
                "report": 0,
                "heuristic": 0,
                "ctrlpp": 0,
                "ai": 0,
                "excel_copy": 0,
                "excel_load": 0,
                "excel_save": 0,
            },
            "llm_calls": 0,
            "ctrlpp_calls": 0,
            "bytes_read": 0,
            "bytes_written": 0,
            "convert_cache": {"hits": 0, "misses": 0},
            "excel_template_cache": {"hits": 0, "misses": 0},
            "per_file": [],
        }

    def _metrics_add_timing(self, metrics: Optional[AnalysisMetrics], key: str, ms: int):
        if not isinstance(metrics, dict):
            return
        with self._metrics_lock:
            timings = metrics.setdefault("timings_ms", {})
            timings[key] = self._safe_int(timings.get(key, 0), 0) + self._safe_int(ms, 0)

    def _metrics_inc(self, metrics: Optional[AnalysisMetrics], key: str, amount: int = 1):
        if not isinstance(metrics, dict):
            return
        with self._metrics_lock:
            metrics[key] = self._safe_int(metrics.get(key, 0), 0) + self._safe_int(amount, 0)

    def _metrics_inc_nested(self, metrics: Optional[AnalysisMetrics], parent: str, key: str, amount: int = 1):
        if not isinstance(metrics, dict):
            return
        with self._metrics_lock:
            target = metrics.setdefault(parent, {})
            if not isinstance(target, dict):
                target = {}
                metrics[parent] = target
            target[key] = self._safe_int(target.get(key, 0), 0) + self._safe_int(amount, 0)

    def _metrics_add_per_file(self, metrics: Optional[AnalysisMetrics], payload: PerFileMetricEntry):
        if not isinstance(metrics, dict) or not isinstance(payload, dict):
            return
        with self._metrics_lock:
            per_file = metrics.setdefault("per_file", [])
            if isinstance(per_file, list):
                per_file.append(payload)

    def _metrics_apply_excel_report_meta(self, metrics: Optional[AnalysisMetrics], excel_meta: Optional[ExcelReportMeta]):
        if not isinstance(metrics, dict) or not isinstance(excel_meta, dict):
            return
        timings = excel_meta.get("timings_ms", {})
        if isinstance(timings, dict):
            self._metrics_add_timing(metrics, "excel_copy", self._safe_int(timings.get("copy", 0), 0))
            self._metrics_add_timing(metrics, "excel_load", self._safe_int(timings.get("load", 0), 0))
            self._metrics_add_timing(metrics, "excel_save", self._safe_int(timings.get("save", 0), 0))
        cache_hit = bool(excel_meta.get("template_cache_hit", False))
        self._metrics_inc_nested(metrics, "excel_template_cache", "hits" if cache_hit else "misses", 1)

    def _new_review_session(self, output_dir: str) -> Dict:
        return {
            "output_dir": os.path.normpath(str(output_dir or "")),
            "created_at": self._now_ts(),
            "last_accessed_at": self._now_ts(),
            "files": {},
            "autofix": {
                "proposals": collections.OrderedDict(),
                "latest_by_file": {},
                "stats": {
                    "prepare_compare_count": 0,
                    "prepare_compare_generated_candidates_total": 0,
                    "selected_generator_counts": {"rule": 0, "llm": 0},
                    "compare_apply_count": 0,
                    "anchor_mismatch_count": 0,
                    "token_fallback_attempt_count": 0,
                    "token_fallback_success_count": 0,
                    "token_fallback_ambiguous_count": 0,
                    "apply_engine_structure_success_count": 0,
                    "apply_engine_text_fallback_count": 0,
                    "selected_apply_engine_mode": {"structure_apply": 0, "text_fallback": 0},
                },
            },
            "report_jobs": {
                "excel": collections.OrderedDict(),
            },
            "lock": threading.RLock(),
            "file_locks": {},
        }

    def _touch_review_session(self, session: Dict):
        if isinstance(session, dict):
            session["last_accessed_at"] = self._now_ts()

    def _prune_review_sessions(self):
        now_ts = self._now_ts()
        with self._review_session_cache_lock:
            expired_keys = []
            for key, session in list(self._review_session_cache.items()):
                last_ts = float(session.get("last_accessed_at", session.get("created_at", 0)) or 0)
                if (now_ts - last_ts) > self.review_session_ttl_sec:
                    expired_keys.append(key)
            for key in expired_keys:
                self._review_session_cache.pop(key, None)
            while len(self._review_session_cache) > self.review_session_max_entries:
                self._review_session_cache.popitem(last=False)

    def _ensure_review_session(self, output_dir: str) -> Dict:
        session_key = os.path.normpath(str(output_dir or ""))
        if not session_key:
            raise RuntimeError("Invalid review session key")
        self._prune_review_sessions()
        with self._review_session_cache_lock:
            session = self._review_session_cache.get(session_key)
            if session is None:
                session = self._new_review_session(session_key)
                self._review_session_cache[session_key] = session
            else:
                self._review_session_cache.move_to_end(session_key, last=True)
                self._touch_review_session(session)
            return session

    def _get_review_session(self, output_dir: str) -> Optional[Dict]:
        session_key = os.path.normpath(str(output_dir or ""))
        if not session_key:
            return None
        self._prune_review_sessions()
        with self._review_session_cache_lock:
            session = self._review_session_cache.get(session_key)
            if session is None:
                return None
            self._review_session_cache.move_to_end(session_key, last=True)
            self._touch_review_session(session)
            return session

    def _get_session_file_lock(self, session: Dict, filename: str):
        if not isinstance(session, dict):
            return threading.Lock()
        with session["lock"]:
            key = os.path.basename(str(filename or ""))
            lock = session["file_locks"].get(key)
            if lock is None:
                lock = threading.Lock()
                session["file_locks"][key] = lock
            return lock

    def _store_review_cache_file(self, session_key: str, filename: str, payload: Dict):
        session = self._ensure_review_session(session_key)
        if not isinstance(payload, dict):
            return
        with session["lock"]:
            session["files"][filename] = payload
            self._touch_review_session(session)

    @classmethod
    def _extract_review_code_block(cls, review_text: str) -> str:
        try:
            return LLMReviewer._extract_first_code_block(review_text)  # type: ignore[attr-defined]
        except Exception:
            return ""

    @classmethod
    def _extract_review_summary(cls, review_text: str) -> str:
        try:
            return LLMReviewer._extract_summary_line(review_text)  # type: ignore[attr-defined]
        except Exception:
            return str(review_text or "").strip().splitlines()[0] if str(review_text or "").strip() else ""

    @staticmethod
    def _indent_lines(code_block: str, indent: str) -> List[str]:
        result = []
        for line in str(code_block or "").splitlines():
            if line.strip():
                result.append(f"{indent}{line}")
            else:
                result.append("")
        return result

    @staticmethod
    def _line_indent(line: str) -> str:
        stripped = str(line or "")
        return stripped[: len(stripped) - len(stripped.lstrip(" \t"))]

    @staticmethod
    def _basic_syntax_check(text: str) -> bool:
        sample = str(text or "")
        return sample.count("{") == sample.count("}") and sample.count("(") == sample.count(")")

    def _build_focus_snippet(
        self,
        code_content: str,
        violations: List[Dict],
        window_lines: Optional[int] = None,
        max_lines: Optional[int] = None,
    ) -> str:
        window_lines = self.ai_focus_snippet_window_lines if window_lines is None else max(1, int(window_lines))
        max_lines = self.ai_focus_snippet_max_lines if max_lines is None else max(5, int(max_lines))
        lines = str(code_content or "").splitlines()
        if not lines:
            return ""

        wanted_ranges: List[Tuple[int, int]] = []
        for violation in violations or []:
            if not isinstance(violation, dict):
                continue
            line_no = self._safe_int(violation.get("line", 0), 0)
            if line_no <= 0:
                continue
            start = max(1, line_no - max(1, window_lines))
            end = min(len(lines), line_no + max(1, window_lines))
            wanted_ranges.append((start, end))

        if not wanted_ranges:
            sample_end = min(len(lines), max(1, max_lines))
            return "\n".join(f"{idx:4d}: {lines[idx - 1]}" for idx in range(1, sample_end + 1))

        wanted_ranges.sort(key=lambda item: (item[0], item[1]))
        merged: List[Tuple[int, int]] = []
        for start, end in wanted_ranges:
            if not merged:
                merged.append((start, end))
                continue
            prev_start, prev_end = merged[-1]
            if start <= (prev_end + 1):
                merged[-1] = (prev_start, max(prev_end, end))
            else:
                merged.append((start, end))

        rendered: List[str] = []
        budget = max(1, max_lines)
        for start, end in merged:
            if budget <= 0:
                break
            take_end = min(end, start + budget - 1)
            rendered.append(f"// lines {start}-{take_end}")
            for idx in range(start, take_end + 1):
                rendered.append(f"{idx:4d}: {lines[idx - 1]}")
            budget -= (take_end - start + 1)
            if take_end < end:
                rendered.append("// ...")
        return "\n".join(rendered)

    def _build_autofix_hunks_for_insertion(
        self,
        original_lines: List[str],
        new_lines: List[str],
        insert_line: int,
        inserted_lines: List[str],
    ) -> List[Dict]:
        line_count = len(original_lines)
        insert_line = max(1, min(max(line_count, 1), int(insert_line or 1)))
        before_line = original_lines[insert_line - 2] if insert_line >= 2 and (insert_line - 2) < line_count else ""
        anchor_line = original_lines[insert_line - 1] if line_count and (insert_line - 1) < line_count else ""
        after_line = original_lines[insert_line] if line_count and insert_line < line_count else ""
        return [
            {
                "start_line": insert_line,
                "end_line": insert_line,
                "context_before": before_line,
                "context_after": anchor_line or after_line,
                "replacement_text": "\n".join(inserted_lines),
            }
        ]

    @staticmethod
    def _build_structured_instruction_from_hunks(
        *,
        proposal: Dict,
        file_name: str,
        object_name: str,
        event_name: str,
    ) -> Optional[Dict]:
        hunks = proposal.get("hunks", []) if isinstance(proposal, dict) else []
        valid_hunks = [h for h in (hunks or []) if isinstance(h, dict)]
        if not valid_hunks:
            return None
        try:
            operations: List[Dict[str, Any]] = []
            for hunk in valid_hunks:
                start_line = max(1, int(hunk.get("start_line", 1) or 1))
                operations.append(
                    {
                        "operation": "replace",
                        "locator": {
                            "kind": "anchor_context",
                            "start_line": start_line,
                            "context_before": str(hunk.get("context_before", "") or ""),
                            "context_after": str(hunk.get("context_after", "") or ""),
                        },
                        "payload": {
                            "code": str(hunk.get("replacement_text", "") or ""),
                        },
                    }
                )
            instruction_raw = {
                "target": {
                    "file": str(file_name or ""),
                    "object": str(object_name or ""),
                    "event": str(event_name or "Global"),
                },
                "operations": operations,
                "safety": {"requires_hash_match": True},
            }
            return normalize_instruction(instruction_raw)
        except Exception:
            return None

    @staticmethod
    def _normalize_autofix_generator_preference(value: Optional[str], fallback: str = "auto") -> str:
        normalized = str(value or fallback or "auto").strip().lower()
        return normalized if normalized in ("auto", "llm", "rule") else str(fallback or "auto")

    @staticmethod
    def _normalize_autofix_prepare_mode(value: Optional[str], fallback: str = "single") -> str:
        normalized = str(value or fallback or "single").strip().lower()
        return normalized if normalized in ("single", "compare") else str(fallback or "single")

    @staticmethod
    def _autofix_error_code_from_exception_message(message: str) -> str:
        msg = str(message or "").lower()
        if "base hash mismatch" in msg:
            return "BASE_HASH_MISMATCH"
        if "anchor mismatch" in msg:
            return "ANCHOR_MISMATCH"
        if "semantic guard blocked" in msg:
            return "SEMANTIC_GUARD_BLOCKED"
        if "syntax precheck failed" in msg:
            return "SYNTAX_PRECHECK_FAILED"
        if "apply engine failed" in msg:
            return "APPLY_ENGINE_FAILED"
        if "heuristic regression detected" in msg or "ctrlppcheck regression detected" in msg:
            return "REGRESSION_BLOCKED"
        if "supported only for .ctl" in msg:
            return "UNSUPPORTED_FILE_TYPE"
        if "session cache" in msg or "run analysis first" in msg:
            return "SESSION_NOT_FOUND"
        return "INTERNAL_ERROR"

    @classmethod
    def _new_autofix_quality_metrics(
        cls,
        proposal_id: str = "",
        generator_type: str = "llm",
        *,
        anchors_match: bool = True,
        hash_match: bool = True,
        syntax_check_passed: bool = True,
        heuristic_regression_count: int = 0,
        ctrlpp_regression_count: int = 0,
        applied: bool = False,
        rejected_reason: str = "",
        validation_errors: Optional[List[str]] = None,
        locator_mode: str = "anchor",
        apply_engine_mode: str = "",
        apply_engine_fallback_reason: str = "",
        token_fallback_attempted: bool = False,
        token_fallback_confidence: float = 0.0,
        token_fallback_candidates: int = 0,
        semantic_check_passed: bool = True,
        semantic_blocked_reason: str = "",
        semantic_violation_count: int = 0,
        token_min_confidence_used: float = 0.8,
        token_min_gap_used: float = 0.15,
        token_max_line_drift_used: int = 0,
        benchmark_tuning_applied: bool = False,
        token_prefer_nearest_tie_used: bool = False,
        token_hint_bias_used: float = 0.0,
        token_force_nearest_on_ambiguous_used: bool = False,
        instruction_mode: str = "off",
        instruction_validation_errors: Optional[List[str]] = None,
        instruction_operation: str = "",
        instruction_operation_count: int = 0,
        instruction_apply_success: bool = False,
        instruction_path_reason: str = "off",
        instruction_failure_stage: str = "none",
        instruction_candidate_hunk_count: int = 0,
        instruction_applied_hunk_count: int = 0,
    ) -> AutoFixQualityMetrics:
        return {
            "proposal_id": str(proposal_id or ""),
            "generator_type": str(generator_type or "llm"),
            "anchors_match": bool(anchors_match),
            "hash_match": bool(hash_match),
            "syntax_check_passed": bool(syntax_check_passed),
            "heuristic_regression_count": int(heuristic_regression_count or 0),
            "ctrlpp_regression_count": int(ctrlpp_regression_count or 0),
            "applied": bool(applied),
            "rejected_reason": str(rejected_reason or ""),
            "validation_errors": list(validation_errors or []),
            "locator_mode": str(locator_mode or "anchor"),
            "apply_engine_mode": str(apply_engine_mode or ""),
            "apply_engine_fallback_reason": str(apply_engine_fallback_reason or ""),
            "token_fallback_attempted": bool(token_fallback_attempted),
            "token_fallback_confidence": float(token_fallback_confidence or 0.0),
            "token_fallback_candidates": int(token_fallback_candidates or 0),
            "semantic_check_passed": bool(semantic_check_passed),
            "semantic_blocked_reason": str(semantic_blocked_reason or ""),
            "semantic_violation_count": int(semantic_violation_count or 0),
            "token_min_confidence_used": float(token_min_confidence_used or 0.8),
            "token_min_gap_used": float(token_min_gap_used or 0.15),
            "token_max_line_drift_used": int(token_max_line_drift_used or 0),
            "benchmark_tuning_applied": bool(benchmark_tuning_applied),
            "token_prefer_nearest_tie_used": bool(token_prefer_nearest_tie_used),
            "token_hint_bias_used": float(token_hint_bias_used or 0.0),
            "token_force_nearest_on_ambiguous_used": bool(token_force_nearest_on_ambiguous_used),
            "instruction_mode": str(instruction_mode or "off"),
            "instruction_validation_errors": list(instruction_validation_errors or []),
            "instruction_operation": str(instruction_operation or ""),
            "instruction_operation_count": int(instruction_operation_count or 0),
            "instruction_apply_success": bool(instruction_apply_success),
            "instruction_path_reason": str(instruction_path_reason or "off"),
            "instruction_failure_stage": str(instruction_failure_stage or "none"),
            "instruction_candidate_hunk_count": int(instruction_candidate_hunk_count or 0),
            "instruction_applied_hunk_count": int(instruction_applied_hunk_count or 0),
        }

    def _autofix_apply_error(
        self,
        message: str,
        *,
        error_code: str = "",
        quality_metrics: Optional[AutoFixQualityMetrics] = None,
    ) -> "AutoFixApplyError":
        code = str(error_code or self._autofix_error_code_from_exception_message(message))
        return AutoFixApplyError(message, code, quality_metrics=quality_metrics)

    def _build_autofix_proposal_from_candidate(
        self,
        *,
        session_output_dir: str,
        session: Dict,
        file_name: str,
        source_path: str,
        source_content: str,
        candidate_content: str,
        summary: str,
        source_tag: str,
        generator_type: str,
        generator_reason: str,
        risk_level: str,
        quality_preview: Optional[Dict] = None,
        extra_private_fields: Optional[Dict] = None,
        llm_meta: Optional[Dict] = None,
    ) -> Dict:
        source_hash = self._sha256_text(source_content)
        # Use keepends=True so EOF-newline-only changes still produce a visible diff.
        diff_text = "".join(
            difflib.unified_diff(
                source_content.splitlines(keepends=True),
                candidate_content.splitlines(keepends=True),
                fromfile=file_name,
                tofile=f"{file_name} (autofix)",
                n=3,
            )
        )
        if not diff_text and source_content != candidate_content:
            # Fallback for edge cases where the unified diff renderer collapses formatting-only changes.
            diff_text = (
                f"--- {file_name}\n"
                f"+++ {file_name} (autofix)\n"
                "@@ -1 +1 @@\n"
                "-<content differs>\n"
                "+<content differs>\n"
            )

        hunks: List[Dict] = []
        source_lines = source_content.splitlines()
        candidate_lines = candidate_content.splitlines()
        for group in difflib.SequenceMatcher(a=source_lines, b=candidate_lines).get_opcodes():
            tag, i1, i2, j1, j2 = group
            if tag == "equal":
                continue
            start_line = max(1, i1 + 1)
            context_before = source_lines[i1 - 1] if i1 > 0 and (i1 - 1) < len(source_lines) else ""
            context_after = source_lines[i1] if i1 < len(source_lines) else ""
            hunks.append(
                {
                    "start_line": start_line,
                    "end_line": max(start_line, i2),
                    "context_before": context_before,
                    "context_after": context_after,
                    "replacement_text": "\n".join(candidate_lines[j1:j2]),
                }
            )
        if not hunks and source_content != candidate_content:
            hunks = [
                {
                    "start_line": 1,
                    "end_line": max(1, len(source_lines)),
                    "context_before": "",
                    "context_after": source_lines[0] if source_lines else "",
                    "replacement_text": candidate_content,
                }
            ]

        proposal_id = uuid.uuid4().hex
        preview = quality_preview if isinstance(quality_preview, dict) else {}
        preview = {
            "anchors_match": bool(preview.get("anchors_match", True)),
            "hash_match": bool(preview.get("hash_match", True)),
            "syntax_check_passed": bool(preview.get("syntax_check_passed", self._basic_syntax_check(candidate_content))),
            "heuristic_regression_count": self._safe_int(preview.get("heuristic_regression_count", 0), 0),
            "ctrlpp_regression_count": self._safe_int(preview.get("ctrlpp_regression_count", 0), 0),
            "errors": list(preview.get("errors", []) or []),
        }
        quality_preview_payload = self._new_autofix_quality_metrics(
            proposal_id=proposal_id,
            generator_type=generator_type,
            anchors_match=preview.get("anchors_match", True),
            hash_match=preview.get("hash_match", True),
            syntax_check_passed=preview.get("syntax_check_passed", True),
            heuristic_regression_count=preview.get("heuristic_regression_count", 0),
            ctrlpp_regression_count=preview.get("ctrlpp_regression_count", 0),
            applied=False,
            rejected_reason="",
            validation_errors=list(preview.get("errors", []) or []),
        )
        proposal = {
            "proposal_id": proposal_id,
            "session_id": session_output_dir,
            "output_dir": session_output_dir,
            "file": file_name,
            "source": source_tag,
            "base_hash": source_hash,
            "summary": str(summary or "").strip(),
            "unified_diff": diff_text,
            "hunks": hunks,
            "risk_level": str(risk_level or "medium"),
            "status": "Prepared",
            "validation_preview": preview,  # backward compatible
            "quality_preview": quality_preview_payload,
            "generator_type": str(generator_type or "llm"),
            "generator_reason": str(generator_reason or ""),
            "created_at": self._iso_now(),
            "_candidate_content": candidate_content,
        }
        if isinstance(llm_meta, dict):
            proposal["llm_meta"] = json.loads(json.dumps(llm_meta, ensure_ascii=False))
        if isinstance(extra_private_fields, dict):
            for key, val in extra_private_fields.items():
                proposal[key] = val

        with session["lock"]:
            self._store_autofix_proposal(session, proposal)
            self._touch_review_session(session)
        return proposal

    @staticmethod
    def _rule_autofix_normalize_text(text: str) -> Tuple[str, Dict[str, int]]:
        source = str(text or "")
        lines = source.splitlines()
        stats = {"trailing_whitespace_lines": 0, "tabs_normalized": 0, "blank_line_runs_trimmed": 0, "eof_newline_added": 0}

        normalized_lines: List[str] = []
        blank_run = 0
        for raw in lines:
            line = raw
            if line.rstrip(" \t") != line:
                stats["trailing_whitespace_lines"] += 1
                line = line.rstrip(" \t")
            if "\t" in line:
                tab_count = line.count("\t")
                stats["tabs_normalized"] += tab_count
                line = line.replace("\t", "    ")
            if not line.strip():
                blank_run += 1
                if blank_run > 2:
                    stats["blank_line_runs_trimmed"] += 1
                    continue
            else:
                blank_run = 0
            normalized_lines.append(line)

        new_text = "\n".join(normalized_lines)
        if source.endswith("\n"):
            new_text += "\n"
        elif source:
            stats["eof_newline_added"] = 1
            new_text += "\n"
        return new_text, stats

    def _proposal_public_view(self, proposal: Dict) -> Dict:
        if not isinstance(proposal, dict):
            return {}
        return {
            "proposal_id": proposal.get("proposal_id", ""),
            "session_id": proposal.get("session_id", ""),
            "output_dir": proposal.get("output_dir", ""),
            "file": proposal.get("file", ""),
            "source": proposal.get("source", "live-ai"),
            "base_hash": proposal.get("base_hash", ""),
            "summary": proposal.get("summary", ""),
            "unified_diff": proposal.get("unified_diff", ""),
            "hunks": proposal.get("hunks", []),
            "risk_level": proposal.get("risk_level", "medium"),
            "status": proposal.get("status", "Prepared"),
            "validation_preview": proposal.get("validation_preview", {}),
            "quality_preview": proposal.get("quality_preview", {}),
            "generator_type": proposal.get("generator_type", "llm"),
            "generator_reason": proposal.get("generator_reason", ""),
            "instruction_preview": proposal.get("instruction_preview", {}),
            "compare_score": proposal.get("compare_score", {}),
            "selection_reason": proposal.get("selection_reason", ""),
            "llm_meta": proposal.get("llm_meta", {}),
            "created_at": proposal.get("created_at"),
        }

    def _instruction_preview_for_proposal(self, proposal: Dict, expected_file: str) -> Dict[str, Any]:
        raw = proposal.get("_structured_instruction") if isinstance(proposal, dict) else None
        if not isinstance(raw, dict):
            return {"available": False, "valid": False, "operation": "", "errors": ["missing_instruction"]}
        normalized = normalize_instruction(raw)
        valid, errors = validate_instruction(normalized)
        target_file = os.path.basename(str((normalized.get("target", {}) or {}).get("file", "") or ""))
        if target_file and target_file != os.path.basename(str(expected_file or "")):
            valid = False
            errors = list(errors) + ["target.file must match proposal file"]
        return {
            "available": True,
            "valid": bool(valid),
            "operation": str(normalized.get("operation", "") or ""),
            "operation_count": len(normalized.get("operations", []) or []),
            "supported_ops": sorted(
                {
                    str((op or {}).get("operation", "") or "")
                    for op in (normalized.get("operations", []) or [])
                    if isinstance(op, dict)
                }
            ),
            "errors": [str(e) for e in (errors or [])],
        }

    def _select_compare_proposal(self, proposals: List[Dict], file_name: str) -> Tuple[Dict, str]:
        if not proposals:
            return {}, "none"
        for item in proposals:
            if isinstance(item, dict):
                item["instruction_preview"] = self._instruction_preview_for_proposal(item, file_name)

        def _score(item: Dict) -> Tuple[int, int, int]:
            preview = item.get("instruction_preview", {}) if isinstance(item, dict) else {}
            quality = item.get("quality_preview", {}) if isinstance(item, dict) else {}
            valid_instruction = 1 if bool(preview.get("valid", False)) else 0
            syntax_ok = 1 if bool(quality.get("syntax_check_passed", True)) else 0
            prefer_rule = 1 if str(item.get("generator_type", "")).lower() == "rule" else 0
            item["compare_score"] = {
                "instruction_valid": valid_instruction,
                "syntax_ok": syntax_ok,
                "prefer_rule": prefer_rule,
                "total": (valid_instruction * 100) + (syntax_ok * 10) + prefer_rule,
            }
            return (valid_instruction, syntax_ok, prefer_rule)

        selected = max([p for p in proposals if isinstance(p, dict)], key=_score)
        selected["selection_reason"] = "max(score=instruction_valid*100 + syntax_ok*10 + prefer_rule)"
        return selected, "instruction_validity_then_syntax_then_rule"

    def _store_autofix_proposal(self, session: Dict, proposal: Dict):
        autofix = session.setdefault("autofix", {})
        proposals = autofix.setdefault("proposals", collections.OrderedDict())
        latest_by_file = autofix.setdefault("latest_by_file", {})
        if not isinstance(proposals, collections.OrderedDict):
            proposals = collections.OrderedDict(proposals)
            autofix["proposals"] = proposals
        pid = str(proposal.get("proposal_id", ""))
        if not pid:
            raise RuntimeError("Invalid proposal id")
        proposals[pid] = proposal
        proposals.move_to_end(pid, last=True)
        latest_by_file[str(proposal.get("file", ""))] = pid
        while len(proposals) > self.autofix_proposal_limit_per_session:
            old_pid, _ = proposals.popitem(last=False)
            for file_key, val in list(latest_by_file.items()):
                if val == old_pid:
                    latest_by_file.pop(file_key, None)

    def _autofix_session_stats(self, session: Dict) -> Dict:
        autofix = session.setdefault("autofix", {}) if isinstance(session, dict) else {}
        stats = autofix.setdefault("stats", {}) if isinstance(autofix, dict) else {}
        stats.setdefault("prepare_compare_count", 0)
        stats.setdefault("prepare_compare_generated_candidates_total", 0)
        selected = stats.setdefault("selected_generator_counts", {"rule": 0, "llm": 0})
        if not isinstance(selected, dict):
            selected = {"rule": 0, "llm": 0}
            stats["selected_generator_counts"] = selected
        selected.setdefault("rule", 0)
        selected.setdefault("llm", 0)
        stats.setdefault("compare_apply_count", 0)
        stats.setdefault("anchor_mismatch_count", 0)
        stats.setdefault("token_fallback_attempt_count", 0)
        stats.setdefault("token_fallback_success_count", 0)
        stats.setdefault("token_fallback_ambiguous_count", 0)
        stats.setdefault("apply_engine_structure_success_count", 0)
        stats.setdefault("apply_engine_text_fallback_count", 0)
        stats.setdefault("multi_hunk_attempt_count", 0)
        stats.setdefault("multi_hunk_success_count", 0)
        stats.setdefault("multi_hunk_blocked_count", 0)
        stats.setdefault("semantic_guard_checked_count", 0)
        stats.setdefault("semantic_guard_blocked_count", 0)
        stats.setdefault("instruction_attempt_count", 0)
        stats.setdefault("instruction_apply_success_count", 0)
        stats.setdefault("instruction_fallback_to_hunk_count", 0)
        stats.setdefault("instruction_validation_fail_count", 0)
        stats.setdefault("instruction_operation_total_count", 0)
        stats.setdefault("instruction_engine_fail_count", 0)
        stats.setdefault("instruction_convert_fail_count", 0)
        mode_counts = stats.setdefault("instruction_mode_counts", {"off": 0, "attempted": 0, "applied": 0, "fallback_hunks": 0})
        if not isinstance(mode_counts, dict):
            mode_counts = {"off": 0, "attempted": 0, "applied": 0, "fallback_hunks": 0}
            stats["instruction_mode_counts"] = mode_counts
        mode_counts.setdefault("off", 0)
        mode_counts.setdefault("attempted", 0)
        mode_counts.setdefault("applied", 0)
        mode_counts.setdefault("fallback_hunks", 0)
        validation_fail_by_reason = stats.setdefault("instruction_validation_fail_by_reason", {})
        if not isinstance(validation_fail_by_reason, dict):
            validation_fail_by_reason = {}
            stats["instruction_validation_fail_by_reason"] = validation_fail_by_reason
        engine_counts = stats.setdefault("selected_apply_engine_mode", {"structure_apply": 0, "text_fallback": 0})
        if not isinstance(engine_counts, dict):
            engine_counts = {"structure_apply": 0, "text_fallback": 0}
            stats["selected_apply_engine_mode"] = engine_counts
        engine_counts.setdefault("structure_apply", 0)
        engine_counts.setdefault("text_fallback", 0)
        return stats

    def _resolve_review_session_and_file(
        self,
        file_name: str,
        output_dir: Optional[str] = None,
    ) -> Tuple[str, Dict, str, Dict]:
        target_output_dir = output_dir or self._last_output_dir
        if not target_output_dir:
            raise RuntimeError("No analysis session found. Run analysis first.")
        session = self._get_review_session(target_output_dir)
        if not session:
            raise RuntimeError("Analysis session cache not found. Run analysis again.")

        basename = os.path.basename(str(file_name or ""))
        tried = self._candidate_cached_filenames(basename)
        cached = None
        resolved_cache_key = ""
        with session["lock"]:
            for candidate in tried:
                maybe = session.get("files", {}).get(candidate)
                if maybe:
                    resolved_cache_key = candidate
                    cached = maybe
                    break
        if not cached:
            if tried:
                raise FileNotFoundError(f"No cached analysis for file: {basename} (tried: {tried})")
            raise FileNotFoundError(f"No cached analysis for file: {basename}")
        self._touch_review_session(session)
        return os.path.normpath(target_output_dir), session, resolved_cache_key, cached

    def _resolve_autofix_proposal(self, session: Dict, proposal_id: str = "", file_name: str = "") -> Dict:
        autofix = session.get("autofix", {})
        proposals = autofix.get("proposals", {})
        latest_by_file = autofix.get("latest_by_file", {})
        pid = str(proposal_id or "")
        if not pid and file_name:
            pid = str(latest_by_file.get(str(file_name), ""))
        if not pid:
            raise FileNotFoundError("No autofix proposal found")
        proposal = proposals.get(pid) if isinstance(proposals, dict) else None
        if not isinstance(proposal, dict):
            raise FileNotFoundError(f"Autofix proposal not found: {pid}")
        return proposal

    @staticmethod
    def _resolve_toggle(default_enabled: bool, toggle: Optional[bool]) -> bool:
        return default_enabled if toggle is None else bool(toggle)

    def _create_request_reporter(self) -> Reporter:
        reporter = Reporter(config_dir=self.reporter.config_dir)
        reporter.output_base_dir = self.reporter.output_base_dir
        for _ in range(5):
            reporter.start_session()
            try:
                os.makedirs(reporter.output_dir, exist_ok=False)
                return reporter
            except FileExistsError:
                continue

        # Windows clock resolution can repeat the same microsecond-formatted timestamp
        # under concurrent requests; force a unique session suffix instead of sharing dirs.
        for _ in range(10):
            reporter.start_session()
            reporter.timestamp = f"{reporter.timestamp}_{uuid.uuid4().hex[:8]}"
            reporter.output_dir = os.path.join(reporter.output_base_dir, reporter.timestamp)
            try:
                os.makedirs(reporter.output_dir, exist_ok=False)
                return reporter
            except FileExistsError:
                continue

        raise RuntimeError("Failed to allocate unique reporter output directory")

    @staticmethod
    def _public_excel_job_view(job_id: str, job: Dict) -> Dict:
        if not isinstance(job, dict):
            return {"job_id": str(job_id or ""), "status": "unknown"}
        return {
            "job_id": str(job_id or ""),
            "kind": "excel",
            "file": str(job.get("file", "") or ""),
            "output_filename": str(job.get("output_filename", "") or ""),
            "status": str(job.get("status", "unknown") or "unknown"),
            "submitted_at": job.get("submitted_at"),
            "started_at": job.get("started_at"),
            "finished_at": job.get("finished_at"),
            "error": str(job.get("error", "") or ""),
            "generated": bool(job.get("generated", False)),
            "metrics": job.get("metrics", {}),
        }

    def _summarize_excel_jobs(self, session: Dict) -> Dict:
        report_jobs = session.get("report_jobs", {}) if isinstance(session, dict) else {}
        excel_jobs = report_jobs.get("excel", {}) if isinstance(report_jobs, dict) else {}
        if not isinstance(excel_jobs, dict):
            excel_jobs = {}
        jobs = []
        counts = {"pending_count": 0, "running_count": 0, "completed_count": 0, "failed_count": 0}
        for job_id, job in excel_jobs.items():
            view = self._public_excel_job_view(job_id, job)
            jobs.append(view)
            status = str(view.get("status", "") or "").lower()
            if status == "pending":
                counts["pending_count"] += 1
            elif status == "running":
                counts["running_count"] += 1
            elif status == "completed":
                counts["completed_count"] += 1
            elif status == "failed":
                counts["failed_count"] += 1
        return {"excel": {**counts, "jobs": jobs}}

    def _run_deferred_excel_job(
        self,
        output_dir: str,
        reporter_timestamp: str,
        report_data: Dict,
        file_type: str,
        output_filename: str,
    ) -> Dict:
        reporter = Reporter(config_dir=self.reporter.config_dir)
        reporter.output_base_dir = self.reporter.output_base_dir
        reporter.output_dir = output_dir
        reporter.timestamp = reporter_timestamp or os.path.basename(str(output_dir or "").rstrip("\\/"))
        with self._excel_report_semaphore:
            excel_meta = reporter.fill_excel_checklist(report_data, file_type=file_type, output_filename=output_filename) or {}
        output_path = os.path.join(output_dir, output_filename)
        return {
            "output_path": output_path,
            "generated": os.path.isfile(output_path),
            "metrics": excel_meta if isinstance(excel_meta, dict) else {},
        }

    def _schedule_deferred_excel_report(
        self,
        output_dir: str,
        reporter_timestamp: str,
        source_file: str,
        report_data: Dict,
        file_type: str,
        output_filename: str,
    ) -> str:
        session = self._ensure_review_session(output_dir)
        safe_report_data = json.loads(json.dumps(report_data, ensure_ascii=False))
        job_id = uuid.uuid4().hex
        with session["lock"]:
            report_jobs = session.setdefault("report_jobs", {})
            excel_jobs = report_jobs.setdefault("excel", collections.OrderedDict())
            if not isinstance(excel_jobs, collections.OrderedDict):
                excel_jobs = collections.OrderedDict(excel_jobs)
                report_jobs["excel"] = excel_jobs
            excel_jobs[job_id] = {
                "job_id": job_id,
                "kind": "excel",
                "file": str(source_file or ""),
                "output_filename": str(output_filename or ""),
                "status": "pending",
                "submitted_at": self._iso_now(),
                "started_at": None,
                "finished_at": None,
                "error": "",
                "generated": False,
                "future": None,
            }
            self._touch_review_session(session)

        def _task():
            with session["lock"]:
                current = session.get("report_jobs", {}).get("excel", {}).get(job_id)
                if isinstance(current, dict):
                    current["status"] = "running"
                    current["started_at"] = self._iso_now()
                    self._touch_review_session(session)
            return self._run_deferred_excel_job(
                output_dir=output_dir,
                reporter_timestamp=reporter_timestamp,
                report_data=safe_report_data,
                file_type=file_type,
                output_filename=output_filename,
            )

        future = self._excel_report_executor.submit(_task)
        with session["lock"]:
            current = session.get("report_jobs", {}).get("excel", {}).get(job_id)
            if isinstance(current, dict):
                current["future"] = future
                self._touch_review_session(session)

        def _done(done_future):
            status = "completed"
            error = ""
            generated = False
            output_path = ""
            excel_meta = {}
            try:
                result = done_future.result()
                if isinstance(result, dict):
                    generated = bool(result.get("generated", False))
                    output_path = str(result.get("output_path", "") or "")
                    excel_meta = result.get("metrics", {}) if isinstance(result.get("metrics", {}), dict) else {}
            except Exception as exc:
                status = "failed"
                error = str(exc)
            with session["lock"]:
                current = session.get("report_jobs", {}).get("excel", {}).get(job_id)
                if isinstance(current, dict):
                    current["status"] = status
                    current["error"] = error
                    current["generated"] = generated
                    current["output_path"] = output_path
                    current["metrics"] = excel_meta
                    current["finished_at"] = self._iso_now()
                    self._touch_review_session(session)

        future.add_done_callback(_done)
        return job_id

    def flush_deferred_excel_reports(
        self,
        session_id: Optional[str] = None,
        output_dir: Optional[str] = None,
        wait: bool = True,
        timeout_sec: Optional[int] = None,
    ) -> Dict:
        target_output_dir = output_dir or session_id or self._last_output_dir
        if not target_output_dir:
            raise RuntimeError("No analysis session found. Run analysis first.")
        session = self._get_review_session(target_output_dir)
        if not session:
            raise RuntimeError("Analysis session cache not found. Run analysis again.")

        futures = []
        with session["lock"]:
            excel_jobs = session.get("report_jobs", {}).get("excel", {})
            if isinstance(excel_jobs, dict):
                for job in excel_jobs.values():
                    future = job.get("future") if isinstance(job, dict) else None
                    if isinstance(future, concurrent.futures.Future):
                        futures.append(future)
                self._touch_review_session(session)

        if wait and futures:
            timeout = None if timeout_sec is None else max(0, self._safe_int(timeout_sec, 0))
            concurrent.futures.wait(futures, timeout=timeout)

        excel_files = []
        if os.path.isdir(target_output_dir):
            excel_files = [
                name
                for name in os.listdir(target_output_dir)
                if name.lower().endswith(".xlsx")
            ]

        with session["lock"]:
            job_summary = self._summarize_excel_jobs(session)
            counts = job_summary.get("excel", {})
            all_completed = (
                self._safe_int(counts.get("pending_count", 0), 0) == 0
                and self._safe_int(counts.get("running_count", 0), 0) == 0
            )
            self._touch_review_session(session)

        self._last_output_dir = target_output_dir
        return {
            "ok": True,
            "output_dir": target_output_dir,
            "report_paths": {"excel": sorted(excel_files)},
            "report_jobs": job_summary,
            "all_completed": all_completed,
        }

    def list_available_files(self, allow_raw_txt=False):
        files = []

        for ext in ("*.ctl", "*.pnl", "*.xml"):
            for path in glob.glob(os.path.join(self.data_dir, ext)):
                files.append(
                    {
                        "name": os.path.basename(path),
                        "type": os.path.splitext(path)[1].lstrip("."),
                        "selectable": True,
                    }
                )

        for path in glob.glob(os.path.join(self.data_dir, "*.txt")):
            name = os.path.basename(path)
            # Reviewed files are report artifacts and never analysis targets.
            if self._is_reviewed_txt(name):
                continue
            # Raw txt is hidden by default; exposed only when explicitly allowed.
            if self._is_raw_txt(name) and not allow_raw_txt:
                continue
            files.append(
                {
                    "name": name,
                    "type": "txt",
                    "selectable": True,
                }
            )

        return sorted(files, key=lambda item: item["name"].lower())

    def _convert_single_source(self, source: str, converter_fn, suffix: str, metrics: Optional[Dict] = None) -> str:
        source_name = os.path.basename(source)
        target_path = os.path.splitext(source)[0] + suffix
        lock = self._get_conversion_lock(source)
        started = self._perf_now()
        with lock:
            try:
                signature = self._source_signature(source)
                cache_key = os.path.normpath(source)
                with self._conversion_cache_lock:
                    cache_entry = self._conversion_cache.get(cache_key)
                    if (
                        isinstance(cache_entry, dict)
                        and tuple(cache_entry.get("sig", ())) == signature
                        and os.path.isfile(target_path)
                    ):
                        self._metrics_inc_nested(metrics, "convert_cache", "hits", 1)
                        return target_path

                with open(source, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                self._metrics_inc(metrics, "bytes_read", len(content.encode("utf-8", errors="ignore")))
                txt_content = converter_fn(content)
                temp_path = f"{target_path}.tmp.{threading.get_ident()}.{uuid.uuid4().hex[:8]}"
                try:
                    with open(temp_path, "w", encoding="utf-8") as f:
                        f.write(txt_content)
                    os.replace(temp_path, target_path)
                finally:
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except OSError:
                            pass
                with self._conversion_cache_lock:
                    self._conversion_cache[cache_key] = {"sig": signature, "target_path": target_path}
                self._metrics_inc_nested(metrics, "convert_cache", "misses", 1)
                self._metrics_inc(metrics, "bytes_written", len(txt_content.encode("utf-8", errors="ignore")))
                logger.info("Converted: %s -> %s", source_name, os.path.basename(target_path))
                return target_path
            except Exception as e:
                logger.warning("Error converting %s: %s", source, e)
                return ""
            finally:
                self._metrics_add_timing(metrics, "convert", self._elapsed_ms(started))

    def convert_sources(self, selected_files=None, metrics: Optional[Dict] = None):
        selected = set(selected_files or [])
        generated_txt_files = []

        pnl_files = glob.glob(os.path.join(self.data_dir, "*.pnl"))
        xml_files = glob.glob(os.path.join(self.data_dir, "*.xml"))

        for source in pnl_files:
            source_name = os.path.basename(source)
            if selected and source_name not in selected:
                continue
            target_path = self._convert_single_source(
                source,
                converter_fn=self.pnl_parser.convert_to_text,
                suffix="_pnl.txt",
                metrics=metrics,
            )
            if target_path:
                generated_txt_files.append(target_path)

        for source in xml_files:
            source_name = os.path.basename(source)
            if selected and source_name not in selected:
                continue
            target_path = self._convert_single_source(
                source,
                converter_fn=self.xml_parser.parse,
                suffix="_xml.txt",
                metrics=metrics,
            )
            if target_path:
                generated_txt_files.append(target_path)

        return generated_txt_files

    @staticmethod
    def _is_normalized_txt(name):
        return name.endswith("_pnl.txt") or name.endswith("_xml.txt")

    @staticmethod
    def _is_reviewed_txt(name):
        return name.endswith("_REVIEWED.txt")

    @classmethod
    def _is_raw_txt(cls, name):
        return name.endswith(".txt") and not cls._is_normalized_txt(name) and not cls._is_reviewed_txt(name)

    @classmethod
    def _normalized_name_for_source(cls, name: str) -> str:
        if not isinstance(name, str):
            return ""
        lower = name.lower()
        if lower.endswith(".pnl"):
            return name[:-4] + "_pnl.txt"
        if lower.endswith(".xml"):
            return name[:-4] + "_xml.txt"
        return name

    @classmethod
    def _reviewed_name_for_source(cls, name: str) -> str:
        normalized = cls._normalized_name_for_source(name)
        if normalized.lower().endswith(".txt"):
            return normalized[:-4] + "_REVIEWED.txt"
        if normalized.lower().endswith(".ctl"):
            return normalized[:-4] + "_REVIEWED.txt"
        return ""

    @classmethod
    def _candidate_cached_filenames(cls, name: str):
        base = os.path.basename(str(name or ""))
        if not base:
            return []
        candidates = [base]
        normalized = cls._normalized_name_for_source(base)
        if normalized and normalized not in candidates:
            candidates.append(normalized)
        return candidates

    def get_viewer_content(self, name: str, prefer_source: bool = False) -> dict:
        """Return reviewed/normalized/source text for the code viewer."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name is required")
        basename = os.path.basename(name)
        if basename != name:
            raise ValueError("Only basename is allowed")

        reviewed_name = self._reviewed_name_for_source(basename)
        normalized_name = self._normalized_name_for_source(basename)
        source_path = os.path.join(self.data_dir, basename)
        normalized_path = os.path.join(self.data_dir, normalized_name)

        def _read_text(path: str, resolved_name: str, source_kind: str):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return {"file": basename, "resolved_name": resolved_name, "source": source_kind, "content": f.read()}

        if prefer_source and os.path.isfile(source_path):
            return _read_text(source_path, basename, "source")

        if reviewed_name and self._last_output_dir and os.path.isdir(self._last_output_dir):
            reviewed_path = os.path.join(self._last_output_dir, reviewed_name)
            if os.path.isfile(reviewed_path):
                return _read_text(reviewed_path, reviewed_name, "reviewed")

        if normalized_name != basename and os.path.isfile(normalized_path):
            return _read_text(normalized_path, normalized_name, "normalized")

        if os.path.isfile(source_path):
            return _read_text(source_path, basename, "source")

        raise FileNotFoundError(f"File not found: {basename}")

    @staticmethod
    def infer_file_type(filename):
        # Rule split policy: .ctl => Server, .txt (converted/raw) => Client.
        return "Server" if filename.lower().endswith(".ctl") else "Client"

    def collect_targets(self, selected_files=None, allow_raw_txt=False, metrics: Optional[Dict] = None):
        selected = set(selected_files or [])
        generated_txt_files = self.convert_sources(selected_files=selected_files, metrics=metrics)
        targets = []

        for ctl in glob.glob(os.path.join(self.data_dir, "*.ctl")):
            name = os.path.basename(ctl)
            if selected and name not in selected:
                continue
            targets.append(ctl)

        for generated in generated_txt_files:
            generated_name = os.path.basename(generated)
            source_name = generated_name.replace("_pnl.txt", ".pnl").replace("_xml.txt", ".xml")
            if selected and generated_name not in selected and source_name not in selected:
                continue
            targets.append(generated)

        # Explicit normalized txt selection is always allowed for compatibility.
        for item in selected:
            if not self._is_normalized_txt(item):
                continue
            candidate = os.path.join(self.data_dir, item)
            if os.path.exists(candidate) and candidate not in targets:
                targets.append(candidate)

        if allow_raw_txt:
            raw_txt_paths = glob.glob(os.path.join(self.data_dir, "*.txt"))
            for path in raw_txt_paths:
                name = os.path.basename(path)
                if not self._is_raw_txt(name):
                    continue
                if selected and name not in selected:
                    continue
                if path not in targets:
                    targets.append(path)

        return sorted(set(targets))

    def analyze_file(
        self,
        target,
        mode=DEFAULT_MODE,
        enable_ctrlppcheck=None,
        enable_live_ai=None,
        ai_with_context=False,
        context_payload=None,
        reporter=None,
        metrics: Optional[Dict] = None,
        defer_excel_reports: Optional[bool] = None,
    ):
        file_started = self._perf_now()
        active_reporter = reporter or self.reporter
        filename = os.path.basename(target)
        file_type = self.infer_file_type(filename)
        logger.info("Analyzing: %s", filename)

        read_started = self._perf_now()
        with open(target, "r", encoding="utf-8", errors="ignore") as f:
            code_content = f.read()
        read_ms = self._elapsed_ms(read_started)
        self._metrics_inc(metrics, "bytes_read", len(code_content.encode("utf-8", errors="ignore")))

        heuristic_started = self._perf_now()
        # .pnl/.xml are converted to .txt and intentionally reviewed with Client rules.
        internal_violations = self.checker.analyze_raw_code(target, code_content, file_type=file_type)
        heuristic_ms = self._elapsed_ms(heuristic_started)
        self._metrics_add_timing(metrics, "heuristic", heuristic_ms)

        # Attach source basename so frontend can navigate cross-file P1 rows.
        for group in internal_violations or []:
            for violation in (group.get("violations") or []):
                if isinstance(violation, dict):
                    violation.setdefault("file", filename)

        global_violations = []
        use_ctrlpp = False
        if file_type == "Server":
            use_ctrlpp = self._resolve_toggle(self.ctrlpp_enabled_default, enable_ctrlppcheck)
            ctrl_started = self._perf_now()
            with self._ctrlpp_semaphore:
                global_violations = self.ctrl_tool.run_check(
                    target,
                    code_content,
                    enabled=use_ctrlpp,
                )
            self._metrics_add_timing(metrics, "ctrlpp", self._elapsed_ms(ctrl_started))
            if use_ctrlpp:
                self._metrics_inc(metrics, "ctrlpp_calls", 1)

        file_report = {
            "file": filename,
            "internal_violations": internal_violations,
            "global_violations": global_violations,
            "ai_reviews": [],
        }

        if mode in [DEFAULT_MODE, "AI Full"] and internal_violations:
            use_live_ai = self._resolve_toggle(self.live_ai_enabled_default, enable_live_ai)
            if use_live_ai:
                batch_size = max(1, int(getattr(self, "live_ai_batch_groups_per_file", 1) or 1))
                groups = list(internal_violations or [])
                for batch_start in range(0, len(groups), batch_size):
                    batch_groups = groups[batch_start: batch_start + batch_size]
                    if not batch_groups:
                        continue
                    combined_violations = []
                    for group_item in batch_groups:
                        combined_violations.extend(group_item.get("violations") or [])
                    focus_snippet = self._build_focus_snippet(code_content, combined_violations)
                    ai_started = self._perf_now()
                    with self._live_ai_semaphore:
                        review = self.ai_tool.generate_review(
                            code_content,
                            combined_violations,
                            use_context=bool(ai_with_context),
                            context_payload=context_payload,
                            focus_snippet=focus_snippet,
                        )
                    self._metrics_add_timing(metrics, "ai", self._elapsed_ms(ai_started))
                    self._metrics_inc(metrics, "llm_calls", 1)
                    if not review or (isinstance(review, str) and review.startswith("AI live review failed:")):
                        continue
                    review_source = "live-batch" if len(batch_groups) > 1 else "live"
                    for item in batch_groups:
                        parent_issue_id = ""
                        violations = item.get("violations") or []
                        if violations and isinstance(violations[0], dict):
                            parent_issue_id = str(violations[0].get("issue_id", ""))
                        file_report["ai_reviews"].append(
                            {
                                "file": filename,
                                "object": item["object"],
                                "event": item["event"],
                                "review": review,
                                "source": review_source,
                                "status": "Pending",
                                "parent_issue_id": parent_issue_id,
                            }
                        )
            else:
                for item in internal_violations:
                    review = self.ai_tool.get_mock_review(
                        code_content,
                        item["violations"],
                    )
                    if not review:
                        continue
                    parent_issue_id = ""
                    violations = item.get("violations") or []
                    if violations and isinstance(violations[0], dict):
                        parent_issue_id = str(violations[0].get("issue_id", ""))
                    file_report["ai_reviews"].append(
                        {
                            "file": filename,
                            "object": item["object"],
                            "event": item["event"],
                            "review": review,
                            "source": "mock",
                            "status": "Pending",
                            "parent_issue_id": parent_issue_id,
                        }
                    )

        reviewed_name = filename.replace(".txt", "_REVIEWED.txt").replace(".ctl", "_REVIEWED.txt")
        session_key = active_reporter.output_dir
        cache_entry = {
            "file": filename,
            "file_type": file_type,
            "reviewed_name": reviewed_name,
            "source_path": os.path.join(self.data_dir, filename),
            "source_hash": self._sha256_text(code_content),
            "original_content": code_content,
            "report_data": json.loads(json.dumps(file_report, ensure_ascii=False)),
            "updated_at": self._iso_now(),
        }
        self._store_review_cache_file(session_key, filename, cache_entry)

        output_dir = active_reporter.output_dir
        report_started = self._perf_now()
        size_before = 0
        if os.path.isdir(output_dir):
            try:
                size_before = sum(
                    os.path.getsize(os.path.join(output_dir, name))
                    for name in os.listdir(output_dir)
                    if os.path.isfile(os.path.join(output_dir, name))
                )
            except Exception:
                size_before = 0

        with self._reporter_semaphore:
            active_reporter.generate_annotated_txt(code_content, file_report, reviewed_name)
        file_base = os.path.splitext(filename)[0]
        excel_name = f"CodeReview_Submission_{file_base}_{active_reporter.timestamp}.xlsx"
        use_deferred_excel = (
            self.defer_excel_reports_default
            if defer_excel_reports is None
            else bool(defer_excel_reports)
        )
        deferred_excel_job_id = ""
        sync_excel_meta = {}
        if use_deferred_excel:
            deferred_excel_job_id = self._schedule_deferred_excel_report(
                output_dir=active_reporter.output_dir,
                reporter_timestamp=active_reporter.timestamp,
                source_file=filename,
                report_data=file_report,
                file_type=file_type,
                output_filename=excel_name,
            )
        else:
            with self._excel_report_semaphore:
                sync_excel_meta = active_reporter.fill_excel_checklist(
                    file_report,
                    file_type=file_type,
                    output_filename=excel_name,
                ) or {}
            self._metrics_apply_excel_report_meta(metrics, sync_excel_meta if isinstance(sync_excel_meta, dict) else {})

        report_ms = self._elapsed_ms(report_started)
        self._metrics_add_timing(metrics, "report", report_ms)
        if os.path.isdir(output_dir):
            try:
                size_after = sum(
                    os.path.getsize(os.path.join(output_dir, name))
                    for name in os.listdir(output_dir)
                    if os.path.isfile(os.path.join(output_dir, name))
                )
                if size_after > size_before:
                    self._metrics_inc(metrics, "bytes_written", size_after - size_before)
            except Exception:
                pass

        total_ms = self._elapsed_ms(file_started)
        self._metrics_add_per_file(
            metrics,
            {
                "file": filename,
                "timings_ms": {
                    "total": total_ms,
                    "read": read_ms,
                    "heuristic": heuristic_ms,
                    "report": report_ms,
                },
                "p1_groups": len(internal_violations or []),
                "p2_count": len(global_violations or []),
                "p3_count": len(file_report.get("ai_reviews", []) or []),
                "deferred_excel": bool(use_deferred_excel),
                "excel_job_id": deferred_excel_job_id,
                "excel_metrics": sync_excel_meta if isinstance(sync_excel_meta, dict) else {},
            },
        )
        logger.info("Completed analysis for: %s", filename)
        return file_report

    def build_combined_report(self, all_file_results):
        return {
            "file": f"Multiple Files from {os.path.basename(self.data_dir)}",
            "internal_violations": [item for fr in all_file_results for item in fr["internal_violations"]],
            "global_violations": [v for fr in all_file_results for v in fr.get("global_violations", [])],
            "ai_reviews": [item for fr in all_file_results for item in fr["ai_reviews"]],
        }

    def summarize_results(self, all_file_results):
        p1_groups = []
        p2 = []
        p3 = []
        critical = 0
        warning = 0
        info = 0
        total = 0

        for report in all_file_results:
            p1_groups.extend(report["internal_violations"])
            p2.extend(report.get("global_violations", []))
            p3.extend(report.get("ai_reviews", []))
            for group in report["internal_violations"]:
                for violation in group.get("violations", []):
                    total += 1
                    sev = (violation.get("severity") or "").lower()
                    if sev == "critical":
                        critical += 1
                    elif sev in ("warning", "high", "medium"):
                        warning += 1
                    else:
                        info += 1

        score = max(0, 100 - (critical * 15 + warning * 5 + info))
        return {
            "summary": {
                "total": total,
                "critical": critical,
                "warning": warning,
                "info": info,
                "score": score,
                "p1_total": len(p1_groups),
                "p2_total": len(p2),
                "p3_total": len(p3),
            },
            "violations": {"P1": p1_groups, "P2": p2, "P3": p3},
        }

    def run_directory_analysis(
        self,
        mode=DEFAULT_MODE,
        selected_files=None,
        allow_raw_txt=False,
        enable_ctrlppcheck=None,
        enable_live_ai=None,
        ai_with_context=False,
        request_id: Optional[str] = None,
        defer_excel_reports: Optional[bool] = None,
        progress_cb=None,
    ):
        pipeline = DirectoryAnalysisPipeline(self)
        return pipeline.run(
            mode=mode,
            selected_files=selected_files,
            allow_raw_txt=allow_raw_txt,
            enable_ctrlppcheck=enable_ctrlppcheck,
            enable_live_ai=enable_live_ai,
            ai_with_context=ai_with_context,
            request_id=request_id,
            defer_excel_reports=defer_excel_reports,
            progress_cb=progress_cb,
        )

    def _find_matching_ai_review(self, report_data: Dict, object_name: str, event_name: str, review_text: str, issue_id: str = ""):
        target_obj = str(object_name or "")
        target_event = str(event_name or "Global")
        target_review = str(review_text or "")
        target_issue_id = str(issue_id or "")
        ai_reviews = report_data.get("ai_reviews", []) if isinstance(report_data, dict) else []
        for item in ai_reviews if isinstance(ai_reviews, list) else []:
            if not isinstance(item, dict):
                continue
            if target_issue_id and str(item.get("parent_issue_id", "")) == target_issue_id:
                return item
            if (
                str(item.get("object", "")) == target_obj
                and str(item.get("event", "Global")) == target_event
                and str(item.get("review", "")) == target_review
            ):
                return item
        return None

    def _find_violation_for_ai_review(self, report_data: Dict, ai_review: Dict):
        if not isinstance(report_data, dict) or not isinstance(ai_review, dict):
            return None, None
        wanted_issue_id = str(ai_review.get("parent_issue_id", ""))
        wanted_obj = str(ai_review.get("object", ""))
        wanted_event = str(ai_review.get("event", "Global"))
        for group in report_data.get("internal_violations", []) or []:
            if not isinstance(group, dict):
                continue
            if wanted_obj and str(group.get("object", "")) != wanted_obj:
                continue
            if wanted_event and str(group.get("event", "Global")) != wanted_event:
                continue
            for violation in group.get("violations", []) or []:
                if not isinstance(violation, dict):
                    continue
                if wanted_issue_id and str(violation.get("issue_id", "")) != wanted_issue_id:
                    continue
                return group, violation
            if (group.get("violations") or []):
                first = (group.get("violations") or [None])[0]
                if isinstance(first, dict):
                    return group, first
        return None, None

    def _build_autofix_proposal_from_ai_review(
        self,
        session_output_dir: str,
        session: Dict,
        cache_key: str,
        cached: Dict,
        object_name: str,
        event_name: str,
        review_text: str,
        issue_id: str = "",
    ) -> Dict:
        file_name = str(cache_key or cached.get("file") or "")

        report_data = cached.get("report_data")
        if not isinstance(report_data, dict):
            raise RuntimeError("Cached report data is invalid")

        ai_review = self._find_matching_ai_review(report_data, object_name, event_name, review_text, issue_id=issue_id)
        if not ai_review:
            raise FileNotFoundError("Matching AI review was not found in cached session")

        group, violation = self._find_violation_for_ai_review(report_data, ai_review)
        line_no = self._safe_int((violation or {}).get("line", 1), 1)
        source_path = os.path.join(self.data_dir, file_name)
        if not os.path.isfile(source_path):
            raise FileNotFoundError(f"Source file not found: {file_name}")

        with open(source_path, "r", encoding="utf-8", errors="ignore") as f:
            source_content = f.read()
        source_hash = self._sha256_text(source_content)
        source_lines = source_content.splitlines()
        insert_at = max(1, min(len(source_lines) + 1, line_no if line_no > 0 else 1))

        code_block = self._extract_review_code_block(str(ai_review.get("review", "")))
        if not str(code_block).strip():
            raise ValueError("AI review does not contain a code block for autofix")

        reference_line = source_lines[insert_at - 1] if 0 <= (insert_at - 1) < len(source_lines) else ""
        indent = self._line_indent(reference_line)
        summary = self._extract_review_summary(str(ai_review.get("review", "")))
        marker_id = uuid.uuid4().hex[:8]
        inserted_lines = [
            f"{indent}// [AI-AUTOFIX:{marker_id}] {summary}".rstrip(),
            *self._indent_lines(code_block, indent),
            f"{indent}// [/AI-AUTOFIX:{marker_id}]",
        ]

        new_lines = list(source_lines)
        new_lines[insert_at - 1:insert_at - 1] = inserted_lines
        new_content = "\n".join(new_lines)
        if source_content.endswith("\n"):
            new_content += "\n"
        llm_meta = {
            "review_length": len(str(ai_review.get("review", "") or "")),
            "summary_length": len(summary),
            "code_block_length": len(code_block),
            "code_block_present": bool(str(code_block).strip()),
            "parseability": "code_block_extracted" if str(code_block).strip() else "no_code_block",
            "fallback_used": False,
            "snippet_based": True,
            "ai_review_source": str(ai_review.get("source", "") or ""),
        }
        proposal = self._build_autofix_proposal_from_candidate(
            session_output_dir=session_output_dir,
            session=session,
            file_name=file_name,
            source_path=source_path,
            source_content=source_content,
            candidate_content=new_content,
            summary=summary,
            source_tag="live-ai" if str(ai_review.get("source", "")).lower() == "live" else "rule-template",
            generator_type="llm",
            generator_reason="LLM review code block extracted from cached AI review",
            risk_level="medium",
            quality_preview={
                "anchors_match": True,
                "hash_match": True,
                "syntax_check_passed": self._basic_syntax_check(new_content),
                "heuristic_regression_count": 0,
                "ctrlpp_regression_count": 0,
                "errors": [],
            },
            llm_meta=llm_meta,
            extra_private_fields={
                "_object": str(ai_review.get("object", object_name or "")),
                "_event": str(ai_review.get("event", event_name or "Global")),
                "_review": str(ai_review.get("review", review_text or "")),
                "_insert_line": insert_at,
                "_inserted_line_count": len(inserted_lines),
                "_source_hash_at_prepare": source_hash,
            },
        )
        # Preserve insertion-specific hunk shape for anchor checks/backward compatibility.
        proposal["hunks"] = self._build_autofix_hunks_for_insertion(source_lines, new_lines, insert_at, inserted_lines)
        try:
            structured = self._build_structured_instruction_from_hunks(
                proposal=proposal,
                file_name=file_name,
                object_name=str(ai_review.get("object", object_name or "")),
                event_name=str(ai_review.get("event", event_name or "Global")),
            )
            if isinstance(structured, dict):
                proposal["_structured_instruction"] = structured
        except Exception:
            # Fail-soft: keep legacy hunk-only proposal path.
            pass
        return proposal

    def _find_violation_for_rule_autofix(
        self,
        report_data: Dict,
        object_name: str,
        event_name: str,
        issue_id: str = "",
    ) -> Tuple[Optional[Dict], Optional[Dict]]:
        target_obj = str(object_name or "")
        target_event = str(event_name or "Global")
        target_issue_id = str(issue_id or "")
        for group in report_data.get("internal_violations", []) or []:
            if not isinstance(group, dict):
                continue
            if target_obj and str(group.get("object", "")) != target_obj:
                continue
            if target_event and str(group.get("event", "Global")) != target_event:
                continue
            for violation in group.get("violations", []) or []:
                if not isinstance(violation, dict):
                    continue
                if target_issue_id and str(violation.get("issue_id", "")) != target_issue_id:
                    continue
                return group, violation
            if not target_issue_id and (group.get("violations") or []):
                first = (group.get("violations") or [None])[0]
                if isinstance(first, dict):
                    return group, first
        return None, None

    def _build_autofix_proposal_from_rule_template(
        self,
        session_output_dir: str,
        session: Dict,
        cache_key: str,
        cached: Dict,
        object_name: str,
        event_name: str,
        issue_id: str = "",
    ) -> Dict:
        file_name = str(cache_key or cached.get("file") or "")
        if not file_name.lower().endswith(".ctl"):
            raise ValueError("Autofix is supported only for .ctl files")
        report_data = cached.get("report_data")
        if not isinstance(report_data, dict):
            raise RuntimeError("Cached report data is invalid")
        _group, violation = self._find_violation_for_rule_autofix(report_data, object_name, event_name, issue_id=issue_id)
        if not isinstance(violation, dict):
            raise FileNotFoundError("Matching violation for rule autofix was not found in cached session")

        source_path = os.path.join(self.data_dir, file_name)
        if not os.path.isfile(source_path):
            raise FileNotFoundError(f"Source file not found: {file_name}")
        with open(source_path, "r", encoding="utf-8", errors="ignore") as f:
            source_content = f.read()

        normalized_content, normalize_stats = self._rule_autofix_normalize_text(source_content)
        changed = normalized_content != source_content
        rule_id = str(violation.get("rule_id", "") or "")
        rule_item = str(violation.get("rule_item", "") or "")
        line_no = self._safe_int(violation.get("line", 1), 1)
        generator_reason = "rule-first deterministic hygiene normalization"

        candidate_content = normalized_content
        if not changed:
            source_lines = source_content.splitlines()
            insert_at = max(1, min(len(source_lines) + 1, line_no if line_no > 0 else 1))
            ref_line = source_lines[insert_at - 1] if 0 <= (insert_at - 1) < len(source_lines) else ""
            indent = self._line_indent(ref_line)
            marker_id = uuid.uuid4().hex[:8]
            summary = f"Rule template suggestion for {rule_id or 'RULE'}"
            note_lines = [
                f"{indent}// [RULE-AUTOFIX:{marker_id}] {summary} ({rule_item or str(violation.get('message', '') or '').strip()})".rstrip(),
                f"{indent}// TODO: apply deterministic fix pattern or review manually",
                f"{indent}// [/RULE-AUTOFIX:{marker_id}]",
            ]
            new_lines = list(source_lines)
            new_lines[insert_at - 1:insert_at - 1] = note_lines
            candidate_content = "\n".join(new_lines)
            if source_content.endswith("\n"):
                candidate_content += "\n"
            generator_reason = "rule-first fallback annotation template (no deterministic text normalization changes)"
            normalize_stats = {**normalize_stats, "annotation_inserted": 1}
        else:
            summary = "Rule template hygiene normalization (trailing spaces/tabs/blank-runs/EOF newline)"
            normalize_stats = {**normalize_stats, "annotation_inserted": 0}

        proposal = self._build_autofix_proposal_from_candidate(
            session_output_dir=session_output_dir,
            session=session,
            file_name=file_name,
            source_path=source_path,
            source_content=source_content,
            candidate_content=candidate_content,
            summary=summary,
            source_tag="rule-template",
            generator_type="rule",
            generator_reason=generator_reason,
            risk_level="low",
            quality_preview={
                "anchors_match": True,
                "hash_match": True,
                "syntax_check_passed": self._basic_syntax_check(candidate_content),
                "heuristic_regression_count": 0,
                "ctrlpp_regression_count": 0,
                "errors": [],
            },
            extra_private_fields={
                "_object": str(object_name or ""),
                "_event": str(event_name or "Global"),
                "_review": "",
                "_rule_issue_id": str(violation.get("issue_id", "") or ""),
                "_rule_id": rule_id,
                "_rule_item": rule_item,
                "_rule_stats": normalize_stats,
            },
        )
        try:
            structured = self._build_structured_instruction_from_hunks(
                proposal=proposal,
                file_name=file_name,
                object_name=str(object_name or ""),
                event_name=str(event_name or "Global"),
            )
            if isinstance(structured, dict):
                proposal["_structured_instruction"] = structured
        except Exception:
            pass
        return proposal

    def prepare_autofix_for_ai_review(
        self,
        file_name: str,
        object_name: str,
        event_name: str,
        review_text: str,
        output_dir: Optional[str] = None,
        issue_id: str = "",
        generator_preference: Optional[str] = None,
        allow_fallback: Optional[bool] = None,
        prepare_mode: Optional[str] = None,
    ) -> Dict:
        # Preserve legacy behavior for existing clients: if a review text is supplied and no generator was
        # explicitly requested, default to the LLM path instead of forcing auto(rule-first).
        if generator_preference is None and str(review_text or "").strip():
            preferred = "llm"
        else:
            preferred = self._normalize_autofix_generator_preference(generator_preference, self.autofix_prepare_generator_default)
        allow_fallback = self.autofix_allow_fallback_default if allow_fallback is None else bool(allow_fallback)
        normalized_prepare_mode = self._normalize_autofix_prepare_mode(prepare_mode, "single")
        session_output_dir, session, cache_key, cached = self._resolve_review_session_and_file(file_name=file_name, output_dir=output_dir)
        is_ctl_target = str(cache_key or "").lower().endswith(".ctl")
        forced_llm_non_ctl = not is_ctl_target
        if forced_llm_non_ctl:
            preferred = "llm"
        file_lock = self._get_session_file_lock(session, cache_key)
        with file_lock:
            last_error: Optional[Exception] = None
            proposals: List[Dict] = []
            fallback_used_any = False

            if normalized_prepare_mode == "compare":
                if forced_llm_non_ctl:
                    plan_order = ["llm"]
                elif preferred == "auto":
                    plan_order = ["rule", "llm"]
                elif preferred == "rule":
                    plan_order = ["rule", "llm"]
                else:
                    plan_order = ["llm", "rule"]
            else:
                if forced_llm_non_ctl:
                    plan_order = ["llm"]
                elif preferred == "auto":
                    plan_order = ["rule", "llm"]
                else:
                    plan_order = [preferred]

            for idx, generator in enumerate(plan_order):
                try:
                    if generator == "rule":
                        proposal = self._build_autofix_proposal_from_rule_template(
                            session_output_dir=session_output_dir,
                            session=session,
                            cache_key=cache_key,
                            cached=cached,
                            object_name=object_name,
                            event_name=event_name,
                            issue_id=issue_id,
                        )
                    else:
                        if not str(review_text or "").strip():
                            raise ValueError("review must be provided for llm autofix prepare")
                        proposal = self._build_autofix_proposal_from_ai_review(
                            session_output_dir=session_output_dir,
                            session=session,
                            cache_key=cache_key,
                            cached=cached,
                            object_name=object_name,
                            event_name=event_name,
                            review_text=review_text,
                            issue_id=issue_id,
                        )
                    proposal["_prepare_mode"] = normalized_prepare_mode
                    proposal["_requested_preference"] = preferred
                    if forced_llm_non_ctl:
                        proposal["generator_reason"] = (
                            f"{proposal.get('generator_reason', '')}; non-ctl target uses llm-only autofix"
                        ).strip("; ")
                    proposals.append(proposal)
                    if normalized_prepare_mode == "single":
                        if idx > 0:
                            fallback_used_any = True
                            proposal["generator_reason"] = f"{proposal.get('generator_reason', '')}; fallback from {plan_order[0]}"
                            if proposal.get("generator_type") == "llm":
                                llm_meta = proposal.setdefault("llm_meta", {})
                                if isinstance(llm_meta, dict):
                                    llm_meta["fallback_used"] = True
                        break
                except Exception as exc:
                    last_error = exc
                    if normalized_prepare_mode == "single":
                        if idx == (len(plan_order) - 1) or not allow_fallback:
                            raise
                        fallback_used_any = True
                        continue
                    # compare mode is fail-soft per generator
                    continue

            if not proposals:
                if last_error:
                    raise last_error
                raise RuntimeError("Autofix proposal generation failed")

            selection_policy = "rule_first_default"
            if normalized_prepare_mode == "compare":
                selected_proposal, selection_policy = self._select_compare_proposal(proposals, cache_key)
            else:
                selected_proposal = None
                for item in proposals:
                    if str(item.get("generator_type", "")) == "rule":
                        selected_proposal = item
                        break
                if selected_proposal is None:
                    selected_proposal = proposals[0]

            with session["lock"]:
                stats = self._autofix_session_stats(session)
                if normalized_prepare_mode == "compare":
                    stats["prepare_compare_count"] = self._safe_int(stats.get("prepare_compare_count", 0), 0) + 1
                    stats["prepare_compare_generated_candidates_total"] = (
                        self._safe_int(stats.get("prepare_compare_generated_candidates_total", 0), 0) + len(proposals)
                    )
                self._touch_review_session(session)

            selected_view = self._proposal_public_view(selected_proposal)
            if normalized_prepare_mode != "compare":
                return selected_view

            proposal_views = [self._proposal_public_view(item) for item in proposals]
            selected_pid = str(selected_view.get("proposal_id", ""))
            selected_view["proposals"] = proposal_views
            selected_view["selected_proposal_id"] = selected_pid
            selected_view["compare_meta"] = {
                "mode": "compare",
                "requested_generators": list(plan_order),
                "generated_count": len(proposal_views),
                "fallback_used": bool(fallback_used_any),
                "selection_policy": selection_policy,
                "selected_generator_type": str(selected_view.get("generator_type", "") or ""),
                "selected_compare_score": selected_view.get("compare_score", {}),
                "selected_selection_reason": str(selected_view.get("selection_reason", "") or ""),
            }
            return selected_view

    def get_autofix_file_diff(
        self,
        file_name: str = "",
        session_id: Optional[str] = None,
        output_dir: Optional[str] = None,
        proposal_id: str = "",
    ) -> Dict:
        target_output_dir = output_dir or session_id or self._last_output_dir
        if not target_output_dir:
            raise RuntimeError("No analysis session found. Run analysis first.")
        session = self._get_review_session(target_output_dir)
        if not session:
            raise RuntimeError("Analysis session cache not found. Run analysis again.")
        with session["lock"]:
            proposal = self._resolve_autofix_proposal(session, proposal_id=proposal_id, file_name=os.path.basename(str(file_name or "")))
            return self._proposal_public_view(proposal)

    def get_autofix_stats(
        self,
        session_id: Optional[str] = None,
        output_dir: Optional[str] = None,
    ) -> Dict:
        target_output_dir = output_dir or session_id or self._last_output_dir
        if not target_output_dir:
            raise RuntimeError("No analysis session found. Run analysis first.")
        session = self._get_review_session(target_output_dir)
        if not session:
            raise RuntimeError("Analysis session cache not found. Run analysis again.")
        with session["lock"]:
            autofix = session.get("autofix", {}) if isinstance(session, dict) else {}
            proposals = autofix.get("proposals", {}) if isinstance(autofix, dict) else {}
            latest_by_file = autofix.get("latest_by_file", {}) if isinstance(autofix, dict) else {}
            extra_stats = self._autofix_session_stats(session)
            items = list(proposals.values()) if isinstance(proposals, dict) else []

            by_status: Dict[str, int] = {}
            by_generator: Dict[str, int] = {}
            by_generator_status: Dict[str, Dict[str, int]] = {}
            quality_summary = {
                "applied_count": 0,
                "blocked_count": 0,
                "heuristic_regression_blocked_count": 0,
                "ctrlpp_regression_blocked_count": 0,
                "failure_error_codes": {},
            }

            for item in items:
                if not isinstance(item, dict):
                    continue
                status = str(item.get("status", "Prepared") or "Prepared")
                generator = str(item.get("generator_type", "unknown") or "unknown")
                by_status[status] = by_status.get(status, 0) + 1
                by_generator[generator] = by_generator.get(generator, 0) + 1
                gs = by_generator_status.setdefault(generator, {})
                gs[status] = gs.get(status, 0) + 1

                qm = item.get("quality_metrics", {})
                if isinstance(qm, dict):
                    if qm.get("applied"):
                        quality_summary["applied_count"] += 1
                    if str(qm.get("rejected_reason", "")):
                        quality_summary["blocked_count"] += 1
                        reason = str(qm.get("rejected_reason", "")).lower()
                        if "heuristic" in reason:
                            quality_summary["heuristic_regression_blocked_count"] += 1
                        if "ctrlpp" in reason:
                            quality_summary["ctrlpp_regression_blocked_count"] += 1
                    error_code = str(item.get("last_error_code", "") or "")
                    if error_code:
                        failures = quality_summary["failure_error_codes"]
                        failures[error_code] = failures.get(error_code, 0) + 1

            return {
                "ok": True,
                "session_id": os.path.normpath(target_output_dir),
                "output_dir": os.path.normpath(target_output_dir),
                "proposal_count": len([i for i in items if isinstance(i, dict)]),
                "latest_by_file_count": len(latest_by_file) if isinstance(latest_by_file, dict) else 0,
                "by_status": by_status,
                "by_generator": by_generator,
                "by_generator_status": by_generator_status,
                "quality_summary": quality_summary,
                "prepare_compare_count": self._safe_int(extra_stats.get("prepare_compare_count", 0), 0),
                "prepare_compare_generated_candidates_total": self._safe_int(
                    extra_stats.get("prepare_compare_generated_candidates_total", 0),
                    0,
                ),
                "selected_generator_counts": dict(extra_stats.get("selected_generator_counts", {}))
                if isinstance(extra_stats.get("selected_generator_counts", {}), dict)
                else {"rule": 0, "llm": 0},
                "compare_apply_count": self._safe_int(extra_stats.get("compare_apply_count", 0), 0),
                "anchor_mismatch_count": self._safe_int(extra_stats.get("anchor_mismatch_count", 0), 0),
                "token_fallback_attempt_count": self._safe_int(extra_stats.get("token_fallback_attempt_count", 0), 0),
                "token_fallback_success_count": self._safe_int(extra_stats.get("token_fallback_success_count", 0), 0),
                "token_fallback_ambiguous_count": self._safe_int(extra_stats.get("token_fallback_ambiguous_count", 0), 0),
                "apply_engine_structure_success_count": self._safe_int(
                    extra_stats.get("apply_engine_structure_success_count", 0), 0
                ),
                "apply_engine_text_fallback_count": self._safe_int(
                    extra_stats.get("apply_engine_text_fallback_count", 0), 0
                ),
                "multi_hunk_attempt_count": self._safe_int(
                    extra_stats.get("multi_hunk_attempt_count", 0), 0
                ),
                "multi_hunk_success_count": self._safe_int(
                    extra_stats.get("multi_hunk_success_count", 0), 0
                ),
                "multi_hunk_blocked_count": self._safe_int(
                    extra_stats.get("multi_hunk_blocked_count", 0), 0
                ),
                "semantic_guard_checked_count": self._safe_int(
                    extra_stats.get("semantic_guard_checked_count", 0), 0
                ),
                "semantic_guard_blocked_count": self._safe_int(
                    extra_stats.get("semantic_guard_blocked_count", 0), 0
                ),
                "instruction_attempt_count": self._safe_int(
                    extra_stats.get("instruction_attempt_count", 0), 0
                ),
                "instruction_apply_success_count": self._safe_int(
                    extra_stats.get("instruction_apply_success_count", 0), 0
                ),
                "instruction_fallback_to_hunk_count": self._safe_int(
                    extra_stats.get("instruction_fallback_to_hunk_count", 0), 0
                ),
                "instruction_validation_fail_count": self._safe_int(
                    extra_stats.get("instruction_validation_fail_count", 0), 0
                ),
                "instruction_operation_total_count": self._safe_int(
                    extra_stats.get("instruction_operation_total_count", 0), 0
                ),
                "instruction_engine_fail_count": self._safe_int(
                    extra_stats.get("instruction_engine_fail_count", 0), 0
                ),
                "instruction_convert_fail_count": self._safe_int(
                    extra_stats.get("instruction_convert_fail_count", 0), 0
                ),
                "instruction_mode_counts": dict(extra_stats.get("instruction_mode_counts", {}))
                if isinstance(extra_stats.get("instruction_mode_counts", {}), dict)
                else {"off": 0, "attempted": 0, "applied": 0, "fallback_hunks": 0},
                "instruction_validation_fail_by_reason": dict(extra_stats.get("instruction_validation_fail_by_reason", {}))
                if isinstance(extra_stats.get("instruction_validation_fail_by_reason", {}), dict)
                else {},
                "selected_apply_engine_mode": dict(extra_stats.get("selected_apply_engine_mode", {}))
                if isinstance(extra_stats.get("selected_apply_engine_mode", {}), dict)
                else {"structure_apply": 0, "text_fallback": 0},
            }

    def _count_p1_findings(self, internal_groups: List[Dict]) -> int:
        count = 0
        for group in internal_groups or []:
            if not isinstance(group, dict):
                continue
            count += len(group.get("violations", []) or [])
        return count

    def _count_ctrlpp_findings(self, p2_findings: List[Dict]) -> int:
        count = 0
        for item in p2_findings or []:
            if not isinstance(item, dict):
                continue
            rule_id = str(item.get("rule_id", "") or "")
            source = str(item.get("source", "") or "")
            if source and source != "CtrlppCheck":
                continue
            # Fail-soft metadata messages should not block autofix.
            if rule_id == "ctrlppcheck.info":
                continue
            count += 1
        return count

    def _attempt_token_anchor_fallback(
        self,
        current_lines: List[str],
        hunks: List[Dict],
        *,
        min_confidence: float = 0.8,
        min_gap: float = 0.15,
        max_line_drift: Optional[int] = None,
        prefer_nearest_on_tie: bool = False,
        hint_bias: float = 0.0,
        force_pick_nearest_on_ambiguous: bool = False,
    ) -> Dict[str, Any]:
        resolved_hunks: List[Dict] = []
        confidences: List[float] = []
        candidate_counts: List[int] = []
        errors: List[str] = []

        drift_limit = self._safe_int(max_line_drift, 0)
        if drift_limit <= 0:
            drift_limit = max(50, min(300, len(current_lines)))

        for h in hunks or []:
            if not isinstance(h, dict):
                continue
            hint_line = self._safe_int(h.get("start_line", 1), 1)
            locate = locate_anchor_line_by_tokens(
                current_lines,
                before_expected=str(h.get("context_before", "")),
                after_expected=str(h.get("context_after", "")),
                hint_line=hint_line,
                min_confidence=float(min_confidence),
                min_gap=float(min_gap),
                max_line_drift=drift_limit,
                prefer_nearest_on_tie=bool(prefer_nearest_on_tie),
                hint_bias=float(hint_bias or 0.0),
                force_pick_nearest_on_ambiguous=bool(force_pick_nearest_on_ambiguous),
            )
            candidate_counts.append(self._safe_int(locate.get("candidate_count", 0), 0))
            confidences.append(float(locate.get("confidence", 0.0) or 0.0))
            if not bool(locate.get("ok", False)):
                reason = str(locate.get("reason", "no_candidate") or "no_candidate")
                errors.append(f"token fallback failed at line {hint_line}: {reason}")
                continue
            relocated = dict(h)
            relocated["start_line"] = self._safe_int(locate.get("line", hint_line), hint_line)
            resolved_hunks.append(relocated)

        expected_count = len([h for h in (hunks or []) if isinstance(h, dict)])
        success = expected_count > 0 and len(resolved_hunks) == expected_count
        return {
            "success": success,
            "resolved_hunks": resolved_hunks,
            "confidence": max(confidences) if confidences else 0.0,
            "candidate_count": max(candidate_counts) if candidate_counts else 0,
            "errors": errors,
        }

    @staticmethod
    def _hunk_ranges_overlap(hunks: List[Dict]) -> bool:
        ranges: List[Tuple[int, int]] = []
        for h in hunks or []:
            if not isinstance(h, dict):
                continue
            start_line = max(1, CodeInspectorApp._safe_int(h.get("start_line", 1), 1))
            end_line = max(start_line, CodeInspectorApp._safe_int(h.get("end_line", start_line), start_line))
            ranges.append((start_line, end_line))
        ranges.sort(key=lambda item: (item[0], item[1]))
        for idx in range(1, len(ranges)):
            prev_start, prev_end = ranges[idx - 1]
            cur_start, _cur_end = ranges[idx]
            if cur_start <= prev_end:
                return True
        return False

    def _append_autofix_audit_entry(self, output_dir: str, entry: Dict) -> str:
        os.makedirs(output_dir, exist_ok=True)
        audit_path = os.path.join(output_dir, "autofix_audit.jsonl")
        line = json.dumps(entry, ensure_ascii=False)
        with open(audit_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        return audit_path

    def _mark_autofix_proposal_failure(
        self,
        session: Dict,
        proposal: Optional[Dict],
        *,
        error_code: str,
        quality_metrics: Optional[AutoFixQualityMetrics] = None,
    ) -> None:
        if not isinstance(session, dict) or not isinstance(proposal, dict):
            return
        with session["lock"]:
            proposal["status"] = "Rejected"
            proposal["rejected_at"] = self._iso_now()
            proposal["last_error_code"] = str(error_code or "")
            if isinstance(quality_metrics, dict):
                proposal["quality_metrics"] = json.loads(json.dumps(quality_metrics, ensure_ascii=False))
            self._touch_review_session(session)

    def apply_autofix_proposal(
        self,
        proposal_id: str,
        session_id: Optional[str] = None,
        output_dir: Optional[str] = None,
        file_name: str = "",
        expected_base_hash: str = "",
        apply_mode: str = "source_ctl",
        block_on_regression: Optional[bool] = None,
        check_ctrlpp_regression: Optional[bool] = None,
        benchmark_observe_mode: str = "strict_hash",
        benchmark_tuning_min_confidence: Optional[float] = None,
        benchmark_tuning_min_gap: Optional[float] = None,
        benchmark_tuning_max_line_drift: Optional[int] = None,
        benchmark_force_structured_instruction: bool = False,
    ) -> Dict:
        if str(apply_mode or "source_ctl") != "source_ctl":
            raise ValueError("apply_mode must be 'source_ctl'")
        target_output_dir = output_dir or session_id or self._last_output_dir
        if not target_output_dir:
            raise RuntimeError("No analysis session found. Run analysis first.")
        session = self._get_review_session(target_output_dir)
        if not session:
            raise RuntimeError("Analysis session cache not found. Run analysis again.")

        block_on_regression = self.autofix_block_on_regression_default if block_on_regression is None else bool(block_on_regression)
        check_ctrlpp_regression = (
            self.autofix_ctrlpp_regression_check_default
            if check_ctrlpp_regression is None
            else bool(check_ctrlpp_regression)
        )
        normalized_file = os.path.basename(str(file_name or ""))

        with session["lock"]:
            proposal = self._resolve_autofix_proposal(session, proposal_id=str(proposal_id or ""), file_name=normalized_file)
            normalized_file = os.path.basename(str(proposal.get("file", normalized_file)))
        is_ctl_target = normalized_file.lower().endswith(".ctl")

        file_lock = self._get_session_file_lock(session, normalized_file)
        with file_lock:
            with session["lock"]:
                proposal = self._resolve_autofix_proposal(session, proposal_id=str(proposal_id or ""), file_name=normalized_file)
                session_files = session.get("files", {})
                cached = session_files.get(normalized_file)
                if not isinstance(cached, dict):
                    raise RuntimeError("Cached file session not found for autofix apply")

            source_path = os.path.join(self.data_dir, normalized_file)
            if not os.path.isfile(source_path):
                raise FileNotFoundError(f"Source file not found: {normalized_file}")

            with open(source_path, "r", encoding="utf-8", errors="ignore") as f:
                current_content = f.read()
            current_lines = current_content.splitlines()
            current_hash = self._sha256_text(current_content)
            proposal_base_hash = str(proposal.get("base_hash", ""))
            hash_match = current_hash == proposal_base_hash
            if expected_base_hash:
                hash_match = hash_match and (current_hash == str(expected_base_hash))
            normalized_observe_mode = str(benchmark_observe_mode or "strict_hash").strip().lower()
            if normalized_observe_mode not in ("strict_hash", "benchmark_relaxed"):
                normalized_observe_mode = "strict_hash"
            benchmark_observe_enabled = (
                normalized_observe_mode == "benchmark_relaxed"
                and str(os.environ.get("AUTOFIX_BENCHMARK_OBSERVE", "") or "").strip() == "1"
            )
            token_min_confidence_used = 0.8
            token_min_gap_used = 0.15
            token_max_line_drift_used = max(50, min(300, len(current_lines)))
            benchmark_tuning_applied = False
            token_prefer_nearest_tie_used = False
            token_hint_bias_used = 0.0
            token_force_nearest_on_ambiguous_used = False
            benchmark_structured_instruction_forced = False
            instruction_mode = "off"
            instruction_validation_errors: List[str] = []
            instruction_operation = ""
            instruction_operation_count = 0
            instruction_apply_success = False
            instruction_path_reason = "off"
            instruction_failure_stage = "none"
            instruction_candidate_hunk_count = 0
            instruction_applied_hunk_count = 0
            instruction_observability_recorded = False
            instruction_recorded_mode = "off"
            if benchmark_observe_enabled:
                if benchmark_tuning_min_confidence is not None:
                    token_min_confidence_used = float(benchmark_tuning_min_confidence)
                    benchmark_tuning_applied = True
                if benchmark_tuning_min_gap is not None:
                    token_min_gap_used = float(benchmark_tuning_min_gap)
                    benchmark_tuning_applied = True
                if benchmark_tuning_max_line_drift is not None:
                    token_max_line_drift_used = max(10, int(benchmark_tuning_max_line_drift))
                    benchmark_tuning_applied = True
                if benchmark_tuning_applied:
                    token_prefer_nearest_tie_used = True
                    token_hint_bias_used = 0.03
                    token_force_nearest_on_ambiguous_used = True
                benchmark_structured_instruction_forced = bool(benchmark_force_structured_instruction)

            def _with_tuning_metrics(payload: AutoFixQualityMetrics) -> AutoFixQualityMetrics:
                payload["token_min_confidence_used"] = float(token_min_confidence_used)
                payload["token_min_gap_used"] = float(token_min_gap_used)
                payload["token_max_line_drift_used"] = int(token_max_line_drift_used)
                payload["benchmark_tuning_applied"] = bool(benchmark_tuning_applied)
                payload["token_prefer_nearest_tie_used"] = bool(token_prefer_nearest_tie_used)
                payload["token_hint_bias_used"] = float(token_hint_bias_used)
                payload["token_force_nearest_on_ambiguous_used"] = bool(token_force_nearest_on_ambiguous_used)
                payload["benchmark_structured_instruction_forced"] = bool(benchmark_structured_instruction_forced)
                payload["instruction_mode"] = str(instruction_mode or "off")
                payload["instruction_validation_errors"] = list(instruction_validation_errors)
                payload["instruction_operation"] = str(instruction_operation or "")
                payload["instruction_operation_count"] = int(instruction_operation_count or 0)
                payload["instruction_apply_success"] = bool(instruction_apply_success)
                payload["instruction_path_reason"] = str(instruction_path_reason or "off")
                payload["instruction_failure_stage"] = str(instruction_failure_stage or "none")
                payload["instruction_candidate_hunk_count"] = int(instruction_candidate_hunk_count or 0)
                payload["instruction_applied_hunk_count"] = int(instruction_applied_hunk_count or 0)
                return payload

            def _record_instruction_observability(final_mode: Optional[str] = None):
                nonlocal instruction_observability_recorded, instruction_recorded_mode
                if instruction_observability_recorded:
                    return
                mode = str(final_mode or instruction_mode or "off")
                if mode not in ("off", "attempted", "applied", "fallback_hunks"):
                    mode = "off"
                with session["lock"]:
                    stats = self._autofix_session_stats(session)
                    mode_counts = stats.get("instruction_mode_counts", {})
                    if not isinstance(mode_counts, dict):
                        mode_counts = {"off": 0, "attempted": 0, "applied": 0, "fallback_hunks": 0}
                        stats["instruction_mode_counts"] = mode_counts
                    mode_counts[mode] = self._safe_int(mode_counts.get(mode, 0), 0) + 1
                instruction_recorded_mode = mode
                instruction_observability_recorded = True

            hash_gate_bypassed = False
            if not hash_match and not benchmark_observe_enabled:
                quality_metrics = _with_tuning_metrics(self._new_autofix_quality_metrics(
                    proposal_id=str(proposal.get("proposal_id", "")),
                    generator_type=str(proposal.get("generator_type", "unknown")),
                    anchors_match=True,
                    hash_match=False,
                    syntax_check_passed=True,
                    applied=False,
                    rejected_reason="base hash mismatch",
                    validation_errors=[],
                ))
                self._mark_autofix_proposal_failure(session, proposal, error_code="BASE_HASH_MISMATCH", quality_metrics=quality_metrics)
                _record_instruction_observability()
                raise self._autofix_apply_error(
                    "Autofix base hash mismatch. Re-run analysis and prepare a new diff.",
                    error_code="BASE_HASH_MISMATCH",
                    quality_metrics=quality_metrics,
                )
            if not hash_match and benchmark_observe_enabled:
                hash_gate_bypassed = True

            base_hunks = list(proposal.get("hunks", []) or [])
            apply_hunks = list(base_hunks)
            structured_instruction_hunks: List[Dict[str, Any]] = []
            instruction_hunks_active = False
            structured_instruction_raw = proposal.get("_structured_instruction")
            structured_instruction_enabled_for_request = bool(
                self.autofix_structured_instruction_enabled or benchmark_structured_instruction_forced
            )
            if structured_instruction_enabled_for_request and isinstance(structured_instruction_raw, dict):
                instruction_mode = "attempted"
                instruction_path_reason = "attempted"
                instruction_failure_stage = "none"
                with session["lock"]:
                    stats = self._autofix_session_stats(session)
                    stats["instruction_attempt_count"] = self._safe_int(
                        stats.get("instruction_attempt_count", 0), 0
                    ) + 1
                normalized_instruction = normalize_instruction(structured_instruction_raw)
                operations = normalized_instruction.get("operations", []) if isinstance(
                    normalized_instruction.get("operations"), list
                ) else []
                op_names = [
                    str((op or {}).get("operation", "") or "")
                    for op in operations
                    if isinstance(op, dict) and str((op or {}).get("operation", "") or "")
                ]
                instruction_operation = ",".join(sorted(set(op_names))) if op_names else str(
                    normalized_instruction.get("operation", "") or ""
                )
                instruction_operation_count = len(operations)
                if instruction_operation_count > 0:
                    with session["lock"]:
                        stats = self._autofix_session_stats(session)
                        stats["instruction_operation_total_count"] = self._safe_int(
                            stats.get("instruction_operation_total_count", 0), 0
                        ) + instruction_operation_count
                valid_instruction, instruction_validation_errors = validate_instruction(normalized_instruction)
                target_file = str((normalized_instruction.get("target", {}) or {}).get("file", "") or "")
                if target_file and target_file != normalized_file:
                    valid_instruction = False
                    instruction_validation_errors.append("target.file must match proposal file")
                if valid_instruction:
                    try:
                        structured_instruction_hunks = instruction_to_hunks(normalized_instruction)
                        instruction_candidate_hunk_count = len([h for h in structured_instruction_hunks if isinstance(h, dict)])
                        apply_hunks = list(structured_instruction_hunks)
                        instruction_hunks_active = True
                    except Exception as exc:
                        instruction_validation_errors.append(f"instruction_to_hunks failed: {exc}")
                        instruction_mode = "fallback_hunks"
                        instruction_path_reason = "fallback_hunks"
                        instruction_failure_stage = "convert"
                        with session["lock"]:
                            stats = self._autofix_session_stats(session)
                            stats["instruction_fallback_to_hunk_count"] = self._safe_int(
                                stats.get("instruction_fallback_to_hunk_count", 0), 0
                            ) + 1
                            stats["instruction_convert_fail_count"] = self._safe_int(
                                stats.get("instruction_convert_fail_count", 0), 0
                            ) + 1
                        apply_hunks = list(base_hunks)
                        instruction_hunks_active = False
                else:
                    instruction_mode = "fallback_hunks"
                    instruction_path_reason = "validation_failed"
                    instruction_failure_stage = "validate"
                    with session["lock"]:
                        stats = self._autofix_session_stats(session)
                        stats["instruction_validation_fail_count"] = self._safe_int(
                            stats.get("instruction_validation_fail_count", 0), 0
                        ) + 1
                        stats["instruction_fallback_to_hunk_count"] = self._safe_int(
                            stats.get("instruction_fallback_to_hunk_count", 0), 0
                        ) + 1
                        fail_by_reason = stats.get("instruction_validation_fail_by_reason", {})
                        if not isinstance(fail_by_reason, dict):
                            fail_by_reason = {}
                            stats["instruction_validation_fail_by_reason"] = fail_by_reason
                        for err in instruction_validation_errors:
                            reason_key = str(err or "").strip() or "unknown"
                            fail_by_reason[reason_key] = self._safe_int(fail_by_reason.get(reason_key, 0), 0) + 1
                    apply_hunks = list(base_hunks)
                    instruction_hunks_active = False

            anchors_match = True
            normalized_anchor_match = False
            anchor_errors = []
            locator_mode = "anchor_exact"
            token_fallback_attempted = False
            token_fallback_confidence = 0.0
            token_fallback_candidates = 0
            for h in apply_hunks:
                if not isinstance(h, dict):
                    continue
                start_line = self._safe_int(h.get("start_line", 1), 1)
                before_expected = str(h.get("context_before", ""))
                after_expected = str(h.get("context_after", ""))
                before_actual = current_lines[start_line - 2] if start_line >= 2 and (start_line - 2) < len(current_lines) else ""
                after_actual = current_lines[start_line - 1] if (start_line - 1) < len(current_lines) and start_line >= 1 else ""
                if before_expected and before_actual != before_expected:
                    if normalize_anchor_text(before_actual) == normalize_anchor_text(before_expected):
                        normalized_anchor_match = True
                    else:
                        anchors_match = False
                        anchor_errors.append(f"context_before mismatch at line {start_line}")
                if after_expected and after_actual != after_expected:
                    if normalize_anchor_text(after_actual) == normalize_anchor_text(after_expected):
                        normalized_anchor_match = True
                    else:
                        anchors_match = False
                        anchor_errors.append(f"context_after mismatch at line {start_line}")
            if anchors_match and normalized_anchor_match:
                locator_mode = "anchor_normalized"
            if not anchors_match:
                with session["lock"]:
                    stats = self._autofix_session_stats(session)
                    stats["anchor_mismatch_count"] = self._safe_int(stats.get("anchor_mismatch_count", 0), 0) + 1
                token_fallback_attempted = True
                with session["lock"]:
                    stats = self._autofix_session_stats(session)
                    stats["token_fallback_attempt_count"] = self._safe_int(stats.get("token_fallback_attempt_count", 0), 0) + 1
                fallback = self._attempt_token_anchor_fallback(
                    current_lines,
                    [h for h in apply_hunks if isinstance(h, dict)],
                    min_confidence=token_min_confidence_used,
                    min_gap=token_min_gap_used,
                    max_line_drift=token_max_line_drift_used,
                    prefer_nearest_on_tie=token_prefer_nearest_tie_used,
                    hint_bias=token_hint_bias_used,
                    force_pick_nearest_on_ambiguous=token_force_nearest_on_ambiguous_used,
                )
                token_fallback_confidence = float(fallback.get("confidence", 0.0) or 0.0)
                token_fallback_candidates = self._safe_int(fallback.get("candidate_count", 0), 0)
                if bool(fallback.get("success", False)):
                    apply_hunks = list(fallback.get("resolved_hunks", []) or [])
                    anchors_match = True
                    locator_mode = "token_fallback"
                    with session["lock"]:
                        stats = self._autofix_session_stats(session)
                        stats["token_fallback_success_count"] = (
                            self._safe_int(stats.get("token_fallback_success_count", 0), 0) + 1
                        )
                    anchor_errors = []
                else:
                    fallback_reasons = [str(e) for e in (fallback.get("errors", []) or [])]
                    if token_fallback_candidates >= 2 or any("ambiguous_candidates" in e for e in fallback_reasons):
                        with session["lock"]:
                            stats = self._autofix_session_stats(session)
                            stats["token_fallback_ambiguous_count"] = (
                                self._safe_int(stats.get("token_fallback_ambiguous_count", 0), 0) + 1
                            )
                    anchor_errors.extend(fallback_reasons)

            if not anchors_match:
                quality_metrics = _with_tuning_metrics(self._new_autofix_quality_metrics(
                    proposal_id=str(proposal.get("proposal_id", "")),
                    generator_type=str(proposal.get("generator_type", "unknown")),
                    anchors_match=False,
                    hash_match=hash_match,
                    syntax_check_passed=True,
                    applied=False,
                    rejected_reason="anchor mismatch",
                    validation_errors=list(anchor_errors),
                    locator_mode=locator_mode,
                    token_fallback_attempted=token_fallback_attempted,
                    token_fallback_confidence=token_fallback_confidence,
                    token_fallback_candidates=token_fallback_candidates,
                ))
                self._mark_autofix_proposal_failure(session, proposal, error_code="ANCHOR_MISMATCH", quality_metrics=quality_metrics)
                _record_instruction_observability()
                raise self._autofix_apply_error(
                    "Autofix anchor mismatch. Source file changed since diff preparation.",
                    error_code="ANCHOR_MISMATCH",
                    quality_metrics=quality_metrics,
                )

            valid_apply_hunks = [h for h in apply_hunks if isinstance(h, dict)]
            is_multi_hunk_apply = len(valid_apply_hunks) >= 2
            if is_multi_hunk_apply:
                with session["lock"]:
                    stats = self._autofix_session_stats(session)
                    stats["multi_hunk_attempt_count"] = self._safe_int(stats.get("multi_hunk_attempt_count", 0), 0) + 1
            if len(valid_apply_hunks) > 3:
                apply_engine_reason = "too_many_hunks"
                validation_errors = [f"apply engine failed: {apply_engine_reason}"]
                if is_multi_hunk_apply:
                    with session["lock"]:
                        stats = self._autofix_session_stats(session)
                        stats["multi_hunk_blocked_count"] = self._safe_int(stats.get("multi_hunk_blocked_count", 0), 0) + 1
                quality_metrics = _with_tuning_metrics(self._new_autofix_quality_metrics(
                    proposal_id=str(proposal.get("proposal_id", "")),
                    generator_type=str(proposal.get("generator_type", "unknown")),
                    anchors_match=True,
                    hash_match=hash_match,
                    syntax_check_passed=True,
                    applied=False,
                    rejected_reason="apply engine failed",
                    validation_errors=validation_errors,
                    locator_mode=locator_mode,
                    apply_engine_mode="failed",
                    apply_engine_fallback_reason=apply_engine_reason,
                    token_fallback_attempted=token_fallback_attempted,
                    token_fallback_confidence=token_fallback_confidence,
                    token_fallback_candidates=token_fallback_candidates,
                ))
                self._mark_autofix_proposal_failure(
                    session,
                    proposal,
                    error_code="APPLY_ENGINE_FAILED",
                    quality_metrics=quality_metrics,
                )
                _record_instruction_observability()
                raise self._autofix_apply_error(
                    "Autofix apply engine failed: too_many_hunks",
                    error_code="APPLY_ENGINE_FAILED",
                    quality_metrics=quality_metrics,
                )
            if self._hunk_ranges_overlap(valid_apply_hunks):
                apply_engine_reason = "overlapping_hunks"
                validation_errors = [f"apply engine failed: {apply_engine_reason}"]
                if is_multi_hunk_apply:
                    with session["lock"]:
                        stats = self._autofix_session_stats(session)
                        stats["multi_hunk_blocked_count"] = self._safe_int(stats.get("multi_hunk_blocked_count", 0), 0) + 1
                quality_metrics = _with_tuning_metrics(self._new_autofix_quality_metrics(
                    proposal_id=str(proposal.get("proposal_id", "")),
                    generator_type=str(proposal.get("generator_type", "unknown")),
                    anchors_match=True,
                    hash_match=hash_match,
                    syntax_check_passed=True,
                    applied=False,
                    rejected_reason="apply engine failed",
                    validation_errors=validation_errors,
                    locator_mode=locator_mode,
                    apply_engine_mode="failed",
                    apply_engine_fallback_reason=apply_engine_reason,
                    token_fallback_attempted=token_fallback_attempted,
                    token_fallback_confidence=token_fallback_confidence,
                    token_fallback_candidates=token_fallback_candidates,
                ))
                self._mark_autofix_proposal_failure(
                    session,
                    proposal,
                    error_code="APPLY_ENGINE_FAILED",
                    quality_metrics=quality_metrics,
                )
                _record_instruction_observability()
                raise self._autofix_apply_error(
                    "Autofix apply engine failed: overlapping_hunks",
                    error_code="APPLY_ENGINE_FAILED",
                    quality_metrics=quality_metrics,
                )

            candidate_content = str(proposal.get("_candidate_content", ""))
            if not candidate_content:
                _record_instruction_observability()
                raise RuntimeError("Autofix proposal candidate content is missing")

            engine_result = apply_with_engine(
                base_text=current_content,
                hunks=[h for h in apply_hunks if isinstance(h, dict)],
                anchor_line=self._safe_int(
                    (apply_hunks[0] if apply_hunks and isinstance(apply_hunks[0], dict) else {}).get("start_line", 1),
                    1,
                ),
                generator_type=str(proposal.get("generator_type", "unknown")),
                options={
                    "max_line_drift": max(50, min(300, len(current_lines))),
                    "max_hunks_per_apply": 3,
                },
            )
            apply_engine_mode = str(engine_result.get("engine_mode", "failed") or "failed")
            apply_engine_fallback_reason = str(engine_result.get("fallback_reason", "") or "")
            if bool(engine_result.get("ok", False)):
                engine_text = str(engine_result.get("patched_text", ""))
                if engine_text:
                    candidate_content = engine_text
                if instruction_hunks_active:
                    instruction_mode = "applied"
                    instruction_apply_success = True
                    instruction_path_reason = "applied"
                    instruction_failure_stage = "none"
                    instruction_applied_hunk_count = self._safe_int(
                        (engine_result.get("diagnostics", {}) or {}).get("applied_hunk_count", 0),
                        0,
                    )
                    if instruction_applied_hunk_count <= 0:
                        instruction_applied_hunk_count = len([h for h in structured_instruction_hunks if isinstance(h, dict)])
                    with session["lock"]:
                        stats = self._autofix_session_stats(session)
                        stats["instruction_apply_success_count"] = self._safe_int(
                            stats.get("instruction_apply_success_count", 0), 0
                        ) + 1
            else:
                apply_engine_mode = "failed"
                reason = apply_engine_fallback_reason or "apply_failed"
                if instruction_hunks_active:
                    instruction_mode = "fallback_hunks"
                    instruction_apply_success = False
                    instruction_path_reason = "engine_failed"
                    instruction_failure_stage = "apply"
                    instruction_validation_errors.append(f"instruction apply failed: {reason}")
                    with session["lock"]:
                        stats = self._autofix_session_stats(session)
                        stats["instruction_fallback_to_hunk_count"] = self._safe_int(
                            stats.get("instruction_fallback_to_hunk_count", 0), 0
                        ) + 1
                        stats["instruction_engine_fail_count"] = self._safe_int(
                            stats.get("instruction_engine_fail_count", 0), 0
                        ) + 1
                    legacy_engine = apply_with_engine(
                        base_text=current_content,
                        hunks=[h for h in base_hunks if isinstance(h, dict)],
                        anchor_line=self._safe_int(
                            (base_hunks[0] if base_hunks and isinstance(base_hunks[0], dict) else {}).get("start_line", 1),
                            1,
                        ),
                        generator_type=str(proposal.get("generator_type", "unknown")),
                        options={
                            "max_line_drift": max(50, min(300, len(current_lines))),
                            "max_hunks_per_apply": 3,
                        },
                    )
                    if bool(legacy_engine.get("ok", False)):
                        legacy_text = str(legacy_engine.get("patched_text", ""))
                        if legacy_text:
                            candidate_content = legacy_text
                        apply_engine_mode = str(legacy_engine.get("engine_mode", "failed") or "failed")
                        apply_engine_fallback_reason = str(legacy_engine.get("fallback_reason", "") or "")
                        instruction_hunks_active = False
                    else:
                        reason = str(legacy_engine.get("fallback_reason", "") or reason or "apply_failed")
                        apply_engine_mode = "failed"
                        apply_engine_fallback_reason = reason
                if apply_engine_mode == "failed":
                    anchor_errors.append(f"apply engine failed: {reason}")
                if apply_engine_mode == "failed" and is_multi_hunk_apply and reason in (
                    "too_many_hunks",
                    "overlapping_hunks",
                    "hunks_span_multiple_blocks",
                    "anchor_context_not_unique",
                ):
                    with session["lock"]:
                        stats = self._autofix_session_stats(session)
                        stats["multi_hunk_blocked_count"] = self._safe_int(stats.get("multi_hunk_blocked_count", 0), 0) + 1
                if apply_engine_mode == "failed":
                    quality_metrics = _with_tuning_metrics(self._new_autofix_quality_metrics(
                        proposal_id=str(proposal.get("proposal_id", "")),
                        generator_type=str(proposal.get("generator_type", "unknown")),
                        anchors_match=anchors_match,
                        hash_match=hash_match,
                        syntax_check_passed=True,
                        applied=False,
                        rejected_reason="apply engine failed",
                        validation_errors=list(anchor_errors),
                        locator_mode=locator_mode,
                        apply_engine_mode="failed",
                        apply_engine_fallback_reason=reason,
                        token_fallback_attempted=token_fallback_attempted,
                        token_fallback_confidence=token_fallback_confidence,
                        token_fallback_candidates=token_fallback_candidates,
                    ))
                    self._mark_autofix_proposal_failure(
                        session,
                        proposal,
                        error_code="APPLY_ENGINE_FAILED",
                        quality_metrics=quality_metrics,
                    )
                    _record_instruction_observability()
                    raise self._autofix_apply_error(
                        f"Autofix apply engine failed: {reason}",
                        error_code="APPLY_ENGINE_FAILED",
                        quality_metrics=quality_metrics,
                    )

            validation = {
                "anchors_match": anchors_match,
                "hash_match": hash_match,
                "benchmark_observe_mode": normalized_observe_mode,
                "hash_gate_bypassed": hash_gate_bypassed,
                "token_min_confidence_used": float(token_min_confidence_used),
                "token_min_gap_used": float(token_min_gap_used),
                "token_max_line_drift_used": int(token_max_line_drift_used),
                "benchmark_tuning_applied": bool(benchmark_tuning_applied),
                "token_prefer_nearest_tie_used": bool(token_prefer_nearest_tie_used),
                "token_hint_bias_used": float(token_hint_bias_used),
                "token_force_nearest_on_ambiguous_used": bool(token_force_nearest_on_ambiguous_used),
                "benchmark_structured_instruction_forced": bool(benchmark_structured_instruction_forced),
                "syntax_check_passed": self._basic_syntax_check(candidate_content),
                "semantic_check_passed": True,
                "semantic_blocked_reason": "",
                "semantic_violation_count": 0,
                "heuristic_regression_count": 0,
                "ctrlpp_regression_count": 0,
                "errors": list(anchor_errors),
                "locator_mode": locator_mode,
                "apply_engine_mode": apply_engine_mode,
                "apply_engine_fallback_reason": apply_engine_fallback_reason,
                "token_fallback_attempted": token_fallback_attempted,
                "token_fallback_confidence": token_fallback_confidence,
                "token_fallback_candidates": token_fallback_candidates,
                "syntax_check_skipped_reason": "",
                "ctrlpp_regression_skipped_reason": "",
                "instruction_mode": str(instruction_mode or "off"),
                "instruction_validation_errors": list(instruction_validation_errors),
                "instruction_operation": str(instruction_operation or ""),
                "instruction_operation_count": int(instruction_operation_count or 0),
                "instruction_apply_success": bool(instruction_apply_success),
                "instruction_path_reason": str(instruction_path_reason or "off"),
                "instruction_failure_stage": str(instruction_failure_stage or "none"),
                "instruction_candidate_hunk_count": int(instruction_candidate_hunk_count or 0),
                "instruction_applied_hunk_count": int(instruction_applied_hunk_count or 0),
            }
            if not is_ctl_target:
                validation["syntax_check_passed"] = True
                validation["syntax_check_skipped_reason"] = "non_ctl_file"
            if not validation["syntax_check_passed"]:
                quality_metrics = _with_tuning_metrics(self._new_autofix_quality_metrics(
                    proposal_id=str(proposal.get("proposal_id", "")),
                    generator_type=str(proposal.get("generator_type", "unknown")),
                    anchors_match=anchors_match,
                    hash_match=hash_match,
                    syntax_check_passed=False,
                    applied=False,
                    rejected_reason="syntax precheck failed",
                    validation_errors=list(validation["errors"]),
                    locator_mode=locator_mode,
                    apply_engine_mode=apply_engine_mode,
                    apply_engine_fallback_reason=apply_engine_fallback_reason,
                    token_fallback_attempted=token_fallback_attempted,
                    token_fallback_confidence=token_fallback_confidence,
                    token_fallback_candidates=token_fallback_candidates,
                ))
                self._mark_autofix_proposal_failure(
                    session,
                    proposal,
                    error_code="SYNTAX_PRECHECK_FAILED",
                    quality_metrics=quality_metrics,
                )
                _record_instruction_observability()
                raise self._autofix_apply_error(
                    "Autofix syntax precheck failed (brace/parenthesis balance)",
                    error_code="SYNTAX_PRECHECK_FAILED",
                    quality_metrics=quality_metrics,
                )

            generator_type = str(proposal.get("generator_type", "unknown") or "unknown").lower()
            if generator_type == "rule":
                with session["lock"]:
                    stats = self._autofix_session_stats(session)
                    stats["semantic_guard_checked_count"] = (
                        self._safe_int(stats.get("semantic_guard_checked_count", 0), 0) + 1
                    )

                semantic_reference = str(proposal.get("_candidate_content", "") or "")
                if not semantic_reference:
                    semantic_reference = candidate_content
                semantic_result = evaluate_semantic_delta(semantic_reference, candidate_content)
                semantic_blocked = bool(semantic_result.get("blocked", False))
                semantic_reason = str(semantic_result.get("reason", "") or "")
                semantic_violations = [str(v) for v in (semantic_result.get("violations", []) or []) if str(v).strip()]
                semantic_violation_count = len(semantic_violations)
                validation["semantic_check_passed"] = not semantic_blocked
                validation["semantic_blocked_reason"] = semantic_reason
                validation["semantic_violation_count"] = semantic_violation_count

                if semantic_blocked:
                    validation["errors"].append(
                        f"semantic guard blocked ({semantic_reason}): {', '.join(semantic_violations)}"
                    )
                    with session["lock"]:
                        stats = self._autofix_session_stats(session)
                        stats["semantic_guard_blocked_count"] = (
                            self._safe_int(stats.get("semantic_guard_blocked_count", 0), 0) + 1
                        )
                    quality_metrics = _with_tuning_metrics(self._new_autofix_quality_metrics(
                        proposal_id=str(proposal.get("proposal_id", "")),
                        generator_type=str(proposal.get("generator_type", "unknown")),
                        anchors_match=anchors_match,
                        hash_match=hash_match,
                        syntax_check_passed=bool(validation["syntax_check_passed"]),
                        semantic_check_passed=False,
                        semantic_blocked_reason=semantic_reason,
                        semantic_violation_count=semantic_violation_count,
                        applied=False,
                        rejected_reason="semantic guard blocked",
                        validation_errors=list(validation["errors"]),
                        locator_mode=locator_mode,
                        apply_engine_mode=apply_engine_mode,
                        apply_engine_fallback_reason=apply_engine_fallback_reason,
                        token_fallback_attempted=token_fallback_attempted,
                        token_fallback_confidence=token_fallback_confidence,
                        token_fallback_candidates=token_fallback_candidates,
                    ))
                    self._mark_autofix_proposal_failure(
                        session,
                        proposal,
                        error_code="SEMANTIC_GUARD_BLOCKED",
                        quality_metrics=quality_metrics,
                    )
                    _record_instruction_observability()
                    raise self._autofix_apply_error(
                        "Autofix semantic guard blocked high-risk token delta",
                        error_code="SEMANTIC_GUARD_BLOCKED",
                        quality_metrics=quality_metrics,
                    )

            pre_internal = self.checker.analyze_raw_code(source_path, current_content, file_type="Server")
            post_internal = self.checker.analyze_raw_code(source_path, candidate_content, file_type="Server")
            pre_count = self._count_p1_findings(pre_internal)
            post_count = self._count_p1_findings(post_internal)
            regression_count = max(0, post_count - pre_count)
            validation["heuristic_regression_count"] = regression_count

            if check_ctrlpp_regression and not is_ctl_target:
                validation["ctrlpp_regression_skipped_reason"] = "non_ctl_file"
            elif check_ctrlpp_regression:
                tmp_ctrl_fd = None
                tmp_ctrl_path = ""
                try:
                    with self._ctrlpp_semaphore:
                        pre_ctrlpp = self.ctrl_tool.run_check(source_path, current_content, enabled=True)
                    tmp_ctrl_fd, tmp_ctrl_path = tempfile.mkstemp(prefix="autofix_ctrlpp_", suffix=".ctl")
                    with os.fdopen(tmp_ctrl_fd, "w", encoding="utf-8") as tmp_ctrl:
                        tmp_ctrl.write(candidate_content)
                    tmp_ctrl_fd = None
                    with self._ctrlpp_semaphore:
                        post_ctrlpp = self.ctrl_tool.run_check(tmp_ctrl_path, candidate_content, enabled=True)
                    pre_ctrlpp_count = self._count_ctrlpp_findings(pre_ctrlpp or [])
                    post_ctrlpp_count = self._count_ctrlpp_findings(post_ctrlpp or [])
                    validation["ctrlpp_regression_count"] = max(0, post_ctrlpp_count - pre_ctrlpp_count)
                except Exception as exc:
                    validation["errors"].append(f"ctrlpp regression check skipped: {exc}")
                finally:
                    if tmp_ctrl_fd is not None:
                        try:
                            os.close(tmp_ctrl_fd)
                        except OSError:
                            pass
                    if tmp_ctrl_path and os.path.exists(tmp_ctrl_path):
                        try:
                            os.remove(tmp_ctrl_path)
                        except OSError:
                            pass

            if block_on_regression and validation["ctrlpp_regression_count"] > 0:
                validation["errors"].append(
                    f"ctrlpp regression detected (+{validation['ctrlpp_regression_count']})"
                )
                quality_metrics = _with_tuning_metrics(self._new_autofix_quality_metrics(
                    proposal_id=str(proposal.get("proposal_id", "")),
                    generator_type=str(proposal.get("generator_type", "unknown")),
                    anchors_match=anchors_match,
                    hash_match=hash_match,
                    syntax_check_passed=bool(validation["syntax_check_passed"]),
                    semantic_check_passed=bool(validation.get("semantic_check_passed", True)),
                    semantic_blocked_reason=str(validation.get("semantic_blocked_reason", "") or ""),
                    semantic_violation_count=self._safe_int(validation.get("semantic_violation_count", 0), 0),
                    heuristic_regression_count=self._safe_int(validation["heuristic_regression_count"], 0),
                    ctrlpp_regression_count=self._safe_int(validation["ctrlpp_regression_count"], 0),
                    applied=False,
                    rejected_reason="ctrlpp regression blocked",
                    validation_errors=list(validation["errors"]),
                    locator_mode=locator_mode,
                    apply_engine_mode=apply_engine_mode,
                    apply_engine_fallback_reason=apply_engine_fallback_reason,
                    token_fallback_attempted=token_fallback_attempted,
                    token_fallback_confidence=token_fallback_confidence,
                    token_fallback_candidates=token_fallback_candidates,
                ))
                self._mark_autofix_proposal_failure(session, proposal, error_code="REGRESSION_BLOCKED", quality_metrics=quality_metrics)
                _record_instruction_observability()
                raise self._autofix_apply_error(
                    "Autofix validation failed: CtrlppCheck regression detected",
                    error_code="REGRESSION_BLOCKED",
                    quality_metrics=quality_metrics,
                )

            backup_dir = os.path.join(target_output_dir, "autofix_backups")
            os.makedirs(backup_dir, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup_name = f"{normalized_file}.{ts}.{str(proposal.get('proposal_id', ''))[:8]}.bak"
            backup_path = os.path.join(backup_dir, backup_name)
            shutil.copy2(source_path, backup_path)

            tmp_fd, tmp_path = tempfile.mkstemp(prefix="autofix_", suffix=".tmp", dir=os.path.dirname(source_path) or None)
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as tmp:
                    tmp.write(candidate_content)
                os.replace(tmp_path, source_path)
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass

            rolled_back = False
            if block_on_regression and regression_count > 0:
                try:
                    shutil.copy2(backup_path, source_path)
                    rolled_back = True
                finally:
                    validation["errors"].append(
                        f"heuristic regression detected (+{regression_count}); changes rolled back"
                    )
                quality_metrics = _with_tuning_metrics(self._new_autofix_quality_metrics(
                    proposal_id=str(proposal.get("proposal_id", "")),
                    generator_type=str(proposal.get("generator_type", "unknown")),
                    anchors_match=anchors_match,
                    hash_match=hash_match,
                    syntax_check_passed=bool(validation["syntax_check_passed"]),
                    semantic_check_passed=bool(validation.get("semantic_check_passed", True)),
                    semantic_blocked_reason=str(validation.get("semantic_blocked_reason", "") or ""),
                    semantic_violation_count=self._safe_int(validation.get("semantic_violation_count", 0), 0),
                    heuristic_regression_count=self._safe_int(validation["heuristic_regression_count"], 0),
                    ctrlpp_regression_count=self._safe_int(validation["ctrlpp_regression_count"], 0),
                    applied=False,
                    rejected_reason="heuristic regression blocked",
                    validation_errors=list(validation["errors"]),
                    locator_mode=locator_mode,
                    apply_engine_mode=apply_engine_mode,
                    apply_engine_fallback_reason=apply_engine_fallback_reason,
                    token_fallback_attempted=token_fallback_attempted,
                    token_fallback_confidence=token_fallback_confidence,
                    token_fallback_candidates=token_fallback_candidates,
                ))
                self._mark_autofix_proposal_failure(session, proposal, error_code="REGRESSION_BLOCKED", quality_metrics=quality_metrics)
                _record_instruction_observability()
                raise self._autofix_apply_error(
                    "Autofix validation failed: heuristic regression detected",
                    error_code="REGRESSION_BLOCKED",
                    quality_metrics=quality_metrics,
                )

            quality_metrics = _with_tuning_metrics(self._new_autofix_quality_metrics(
                proposal_id=str(proposal.get("proposal_id", "")),
                generator_type=str(proposal.get("generator_type", "unknown")),
                anchors_match=anchors_match,
                hash_match=hash_match,
                syntax_check_passed=bool(validation["syntax_check_passed"]),
                semantic_check_passed=bool(validation.get("semantic_check_passed", True)),
                semantic_blocked_reason=str(validation.get("semantic_blocked_reason", "") or ""),
                semantic_violation_count=self._safe_int(validation.get("semantic_violation_count", 0), 0),
                heuristic_regression_count=self._safe_int(validation["heuristic_regression_count"], 0),
                ctrlpp_regression_count=self._safe_int(validation["ctrlpp_regression_count"], 0),
                applied=True,
                rejected_reason="",
                validation_errors=list(validation["errors"]),
                locator_mode=locator_mode,
                apply_engine_mode=apply_engine_mode,
                apply_engine_fallback_reason=apply_engine_fallback_reason,
                token_fallback_attempted=token_fallback_attempted,
                token_fallback_confidence=token_fallback_confidence,
                token_fallback_candidates=token_fallback_candidates,
            ))

            with session["lock"]:
                cached["original_content"] = candidate_content
                cached["source_hash"] = self._sha256_text(candidate_content)
                cached["updated_at"] = self._iso_now()
                proposal["status"] = "Applied"
                proposal["applied_at"] = self._iso_now()
                proposal["validation"] = dict(validation)
                proposal["quality_metrics"] = dict(quality_metrics)
                stats = self._autofix_session_stats(session)
                if apply_engine_mode == "structure_apply":
                    stats["apply_engine_structure_success_count"] = (
                        self._safe_int(stats.get("apply_engine_structure_success_count", 0), 0) + 1
                    )
                elif apply_engine_mode == "text_fallback":
                    stats["apply_engine_text_fallback_count"] = (
                        self._safe_int(stats.get("apply_engine_text_fallback_count", 0), 0) + 1
                    )
                if str(proposal.get("_prepare_mode", "")) == "compare":
                    stats["compare_apply_count"] = self._safe_int(stats.get("compare_apply_count", 0), 0) + 1
                    selected = stats.setdefault("selected_generator_counts", {"rule": 0, "llm": 0})
                    if isinstance(selected, dict):
                        gen = str(proposal.get("generator_type", "") or "").lower()
                        if gen in ("rule", "llm"):
                            selected[gen] = self._safe_int(selected.get(gen, 0), 0) + 1
                selected_engine = stats.setdefault("selected_apply_engine_mode", {"structure_apply": 0, "text_fallback": 0})
                if isinstance(selected_engine, dict) and apply_engine_mode in ("structure_apply", "text_fallback"):
                    selected_engine[apply_engine_mode] = self._safe_int(selected_engine.get(apply_engine_mode, 0), 0) + 1
                if is_multi_hunk_apply:
                    stats["multi_hunk_success_count"] = self._safe_int(stats.get("multi_hunk_success_count", 0), 0) + 1
                self._touch_review_session(session)

            audit_entry = {
                "applied_by": "api",
                "applied_at": self._iso_now(),
                "proposal_id": proposal.get("proposal_id", ""),
                "file": normalized_file,
                "file_backup_path": backup_path,
                "generator_type": proposal.get("generator_type", "unknown"),
                "validation_summary": {
                    "hash_match": validation["hash_match"],
                    "benchmark_observe_mode": validation.get("benchmark_observe_mode", "strict_hash"),
                    "hash_gate_bypassed": bool(validation.get("hash_gate_bypassed", False)),
                    "anchors_match": validation["anchors_match"],
                    "syntax_check_passed": validation["syntax_check_passed"],
                    "semantic_check_passed": bool(validation.get("semantic_check_passed", True)),
                    "semantic_blocked_reason": str(validation.get("semantic_blocked_reason", "") or ""),
                    "semantic_violation_count": self._safe_int(validation.get("semantic_violation_count", 0), 0),
                    "apply_engine_mode": validation.get("apply_engine_mode", ""),
                    "apply_engine_fallback_reason": validation.get("apply_engine_fallback_reason", ""),
                    "instruction_mode": validation.get("instruction_mode", "off"),
                    "instruction_operation": validation.get("instruction_operation", ""),
                    "instruction_apply_success": bool(validation.get("instruction_apply_success", False)),
                    "instruction_path_reason": validation.get("instruction_path_reason", "off"),
                    "instruction_failure_stage": validation.get("instruction_failure_stage", "none"),
                    "instruction_candidate_hunk_count": self._safe_int(validation.get("instruction_candidate_hunk_count", 0), 0),
                    "instruction_applied_hunk_count": self._safe_int(validation.get("instruction_applied_hunk_count", 0), 0),
                    "heuristic_regression_count": validation["heuristic_regression_count"],
                    "ctrlpp_regression_count": validation["ctrlpp_regression_count"],
                    "errors": validation["errors"],
                },
                "quality_metrics": quality_metrics,
                "rolled_back": rolled_back,
            }
            audit_log_path = self._append_autofix_audit_entry(target_output_dir, audit_entry)
            self._last_output_dir = target_output_dir

            _record_instruction_observability()
            return {
                "ok": True,
                "applied": True,
                "file": normalized_file,
                "proposal_id": proposal.get("proposal_id", ""),
                "output_dir": target_output_dir,
                "backup_path": backup_path,
                "audit_log_path": audit_log_path,
                "validation": validation,
                "quality_metrics": quality_metrics,
                "reanalysis_summary": {
                    "before_p1_total": pre_count,
                    "after_p1_total": post_count,
                    "delta_p1_total": post_count - pre_count,
                    "ctrlpp_regression_count": validation["ctrlpp_regression_count"],
                },
                "viewer_content": self.get_viewer_content(normalized_file, prefer_source=True),
            }

    def apply_ai_review_to_reviewed_file(
        self,
        file_name: str,
        object_name: str,
        event_name: str,
        review_text: str,
        output_dir: Optional[str] = None,
    ) -> dict:
        target_output_dir, session, resolved_cache_key, cached = self._resolve_review_session_and_file(
            file_name=file_name,
            output_dir=output_dir,
        )
        report_data = cached.get("report_data")
        if not isinstance(report_data, dict):
            raise RuntimeError("Cached report data is invalid")

        file_lock = self._get_session_file_lock(session, resolved_cache_key)
        with file_lock:
            target_obj = str(object_name or "")
            target_event = str(event_name or "Global")
            target_review = str(review_text or "")
            matched = False
            for item in report_data.get("ai_reviews", []):
                if (
                    str(item.get("object", "")) == target_obj
                    and str(item.get("event", "Global")) == target_event
                    and str(item.get("review", "")) == target_review
                ):
                    item["status"] = "Accepted"
                    matched = True

            if not matched:
                raise FileNotFoundError("Matching AI review was not found in cached session")

            reporter = Reporter(config_dir=self.reporter.config_dir)
            reporter.output_base_dir = self.reporter.output_base_dir
            reporter.output_dir = target_output_dir
            reporter.timestamp = os.path.basename(target_output_dir.rstrip("/\\"))
            with self._reporter_semaphore:
                reporter.generate_annotated_txt(
                    cached.get("original_content", ""),
                    report_data,
                    cached.get("reviewed_name") or self._reviewed_name_for_source(resolved_cache_key or os.path.basename(str(file_name or ""))),
                )
            cached["updated_at"] = self._iso_now()
            self._touch_review_session(session)

        self._last_output_dir = target_output_dir

        reviewed_file = cached.get("reviewed_name") or self._reviewed_name_for_source(resolved_cache_key or os.path.basename(str(file_name or "")))
        viewer_content = self.get_viewer_content(resolved_cache_key or os.path.basename(str(file_name or "")))
        applied_blocks = 0
        for ai_item in report_data.get("ai_reviews", []):
            if str(ai_item.get("status", "")).lower() == "accepted":
                applied_blocks += 1
        return {
            "ok": True,
            "applied": True,
            "file": resolved_cache_key or os.path.basename(str(file_name or "")),
            "reviewed_file": reviewed_file,
            "output_dir": target_output_dir,
            "applied_blocks": applied_blocks,
            "viewer_content": viewer_content,
        }


def build_arg_parser():
    parser = argparse.ArgumentParser(description="WinCC OA Code Inspector")
    parser.add_argument("--mode", default=DEFAULT_MODE, help="Analysis mode (Static | AI 보조 | AI Full)")
    parser.add_argument("--allow-raw-txt", action="store_true", help="Allow direct analysis of raw .txt files")
    parser.add_argument("--selected-files", nargs="*", default=None, help="Selected basenames to analyze")
    parser.add_argument("--ai-with-context", action="store_true", help="Request contextual AI prompt (reserved)")

    ctrlpp_group = parser.add_mutually_exclusive_group()
    ctrlpp_group.add_argument(
        "--enable-ctrlppcheck",
        action="store_true",
        help="Enable CtrlppCheck validation for .ctl files",
    )
    ctrlpp_group.add_argument(
        "--disable-ctrlppcheck",
        action="store_true",
        help="Disable CtrlppCheck validation for .ctl files",
    )

    ai_group = parser.add_mutually_exclusive_group()
    ai_group.add_argument(
        "--enable-live-ai",
        action="store_true",
        help="Enable live AI review (Ollama provider)",
    )
    ai_group.add_argument(
        "--disable-live-ai",
        action="store_true",
        help="Disable live AI review and use mock review",
    )
    return parser


if __name__ == "__main__":
    app = CodeInspectorApp()
    args = build_arg_parser().parse_args()

    ctrlpp_toggle = None
    if args.enable_ctrlppcheck:
        ctrlpp_toggle = True
    elif args.disable_ctrlppcheck:
        ctrlpp_toggle = False

    live_ai_toggle = None
    if args.enable_live_ai:
        live_ai_toggle = True
    elif args.disable_live_ai:
        live_ai_toggle = False

    try:
        app.run_directory_analysis(
            mode=args.mode,
            selected_files=args.selected_files,
            allow_raw_txt=args.allow_raw_txt,
            enable_ctrlppcheck=ctrlpp_toggle,
            enable_live_ai=live_ai_toggle,
            ai_with_context=args.ai_with_context,
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        print(f"[!] Error during analysis: {e}")
