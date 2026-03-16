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
import re
import shutil
import tempfile
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, TypedDict, Tuple, cast

from core.ctrl_wrapper import CtrlppWrapper
from core.errors import ReviewerError
from core.heuristic_checker import HeuristicChecker
from core.llm_reviewer import LLMReviewer
from core.mcp_context import MCPContextClient
from core.pnl_parser import PnlParser
from core.reporter import Reporter
from core.analysis_pipeline import DirectoryAnalysisPipeline
from core.session_mixin import ReviewSessionMixin
from core.file_collector_mixin import FileCollectorMixin
from core.autofix_mixin import AutoFixMixin
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
    report_text: int
    heuristic: int
    ctrlpp: int
    ai: int
    excel_total: int
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
    total: int
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


class CodeInspectorApp(ReviewSessionMixin, FileCollectorMixin, AutoFixMixin):
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
        self.ai_prompt_mode = str(ai_cfg.get("prompt_mode", "todo_compact") or "todo_compact").strip().lower()
        if self.ai_prompt_mode not in ("todo_compact", "issue_context"):
            self.ai_prompt_mode = "todo_compact"
        self.live_ai_batch_groups_per_file = max(1, self._safe_int(ai_cfg.get("batch_groups_per_file", 1), 1))
        self.live_ai_min_review_severity = str(ai_cfg.get("min_review_severity", "warning") or "warning").strip().lower()
        self.live_ai_max_parent_reviews_per_file = max(
            1,
            self._safe_int(ai_cfg.get("max_parent_reviews_per_file", 5), 5),
        )
        self.ai_todo_prompt_window_lines = 4
        self.ai_todo_prompt_max_lines = 12
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
        self.defer_excel_reports_default = bool(perf_cfg.get("defer_excel_reports_default", False))
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

    def reload_rule_configuration(self) -> Dict[str, Any]:
        with self._analysis_lock:
            config_dir = str(getattr(self.checker, "config_dir", "") or os.path.join(self.base_dir, "Config"))
            rules_path = os.path.join(config_dir, "parsed_rules.json")
            reporter_output_base_dir = getattr(self.reporter, "output_base_dir", None)
            reporter_timestamp = getattr(self.reporter, "timestamp", "")
            reporter_output_dir = getattr(self.reporter, "output_dir", "")

            self.checker = HeuristicChecker(rules_path)
            self.reporter = Reporter(config_dir=config_dir)
            if reporter_output_base_dir:
                self.reporter.output_base_dir = reporter_output_base_dir
            if reporter_timestamp:
                self.reporter.timestamp = reporter_timestamp
            if reporter_output_dir:
                self.reporter.output_dir = reporter_output_dir

        return {
            "reloaded": True,
            "config_dir": config_dir,
            "p1_total": len(getattr(self.checker, "p1_rule_defs", []) or []),
            "p1_enabled": len([row for row in (getattr(self.checker, "p1_rule_defs", []) or []) if bool((row or {}).get("enabled", True))]),
        }

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
        return (
            datetime.datetime.now(datetime.timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

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
    def _artifact_safe_stem(name: str) -> str:
        stem = os.path.splitext(os.path.basename(str(name or "")))[0]
        safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in stem).strip("_")
        return safe or "review_target"

    def _report_artifact_stem(self, display_name: str, source_path: str) -> str:
        stem = self._artifact_safe_stem(display_name)
        normalized_source = os.path.normcase(os.path.normpath(str(source_path or "")))
        normalized_data_dir = os.path.normcase(os.path.normpath(str(self.data_dir or "")))
        is_builtin = False
        if normalized_source and normalized_data_dir:
            try:
                is_builtin = os.path.commonpath([normalized_source, normalized_data_dir]) == normalized_data_dir
            except ValueError:
                is_builtin = False
        if is_builtin:
            return stem
        suffix = self._sha256_text(normalized_source or display_name)[:8]
        return f"{stem}_{suffix}"

    def build_report_artifact_stems(self, targets: List[str]) -> Dict[str, str]:
        normalized_targets = [os.path.normpath(str(path or "")) for path in (targets or []) if str(path or "").strip()]
        basename_counts: Dict[str, int] = {}
        for path in normalized_targets:
            base = os.path.basename(path)
            basename_counts[base] = basename_counts.get(base, 0) + 1
        artifact_stems: Dict[str, str] = {}
        for path in normalized_targets:
            display_name = os.path.basename(path)
            base_stem = self._artifact_safe_stem(display_name)
            if basename_counts.get(display_name, 0) > 1:
                suffix = self._sha256_text(path)[:8]
                artifact_stems[path] = f"{base_stem}_{suffix}"
            else:
                artifact_stems[path] = base_stem
        return artifact_stems

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
                "report_text": 0,
                "heuristic": 0,
                "ctrlpp": 0,
                "ai": 0,
                "excel_total": 0,
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
            self._metrics_add_timing(metrics, "excel_total", self._safe_int(timings.get("total", 0), 0))
            self._metrics_add_timing(metrics, "excel_copy", self._safe_int(timings.get("copy", 0), 0))
            self._metrics_add_timing(metrics, "excel_load", self._safe_int(timings.get("load", 0), 0))
            self._metrics_add_timing(metrics, "excel_save", self._safe_int(timings.get("save", 0), 0))
        cache_hit = bool(excel_meta.get("template_cache_hit", False))
        self._metrics_inc_nested(metrics, "excel_template_cache", "hits" if cache_hit else "misses", 1)








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

    def _build_todo_prompt_context(self, code_content: str, context_item: Dict[str, Any]) -> Dict[str, Any]:
        issue_context = context_item.get("issue_context", {}) if isinstance(context_item, dict) else {}
        primary = issue_context.get("primary", {}) if isinstance(issue_context, dict) else {}
        primary_violation = primary if isinstance(primary, dict) else {}
        todo_comment = self.reporter.build_todo_comment(primary_violation)
        snippet = self._build_focus_snippet(
            code_content,
            [primary_violation] if primary_violation else [],
            window_lines=self.ai_todo_prompt_window_lines,
            max_lines=self.ai_todo_prompt_max_lines,
        )
        linked_findings = issue_context.get("linked_findings", []) if isinstance(issue_context, dict) else []
        linked_summary = []
        for item in linked_findings[:4]:
            if not isinstance(item, dict):
                continue
            linked_summary.append(
                {
                    "source": str(item.get("source", "") or ""),
                    "rule_id": str(item.get("rule_id", "") or ""),
                    "line": self._safe_int(item.get("line", 0), 0),
                    "message": str(item.get("message", "") or ""),
                }
            )
        return {
            "todo_comment": todo_comment,
            "snippet": snippet,
            "line": self._safe_int(primary_violation.get("line", 0), 0),
            "object": str(primary_violation.get("object", context_item.get("object", "")) or ""),
            "event": str(primary_violation.get("event", context_item.get("event", "")) or ""),
            "linked_findings": linked_summary,
        }

















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







    def list_ai_models(self) -> Dict[str, Any]:
        try:
            models = self.ai_tool.list_models()
            return {
                "provider": str(self.ai_tool.provider or "ollama"),
                "available": bool(models),
                "models": models,
                "default_model": str(self.ai_tool.model_name or ""),
            }
        except ReviewerError as exc:
            return {
                "provider": str(self.ai_tool.provider or "ollama"),
                "available": False,
                "models": [],
                "default_model": str(self.ai_tool.model_name or ""),
                "error": str(exc),
                "error_code": str(exc.error_code or ""),
            }
        except Exception as exc:
            return {
                "provider": str(self.ai_tool.provider or "ollama"),
                "available": False,
                "models": [],
                "default_model": str(self.ai_tool.model_name or ""),
                "error": str(exc),
            }
















    @staticmethod
    def _normalize_issue_text(value: Any) -> str:
        return " ".join(str(value or "").split()).strip().lower()

    @staticmethod
    def _severity_rank(value: Any) -> int:
        normalized = str(value or "").strip().lower()
        if normalized == "critical":
            return 3
        if normalized in ("warning", "warn", "high", "medium", "performance", "style", "information"):
            return 2
        if normalized in ("info", "information", "low"):
            return 1
        return 0

    def _live_ai_parent_context_key(self, context_item: Dict[str, Any]) -> Tuple[str, str, str, int, str]:
        return (
            str(context_item.get("parent_source", "") or ""),
            str(context_item.get("parent_issue_id", "") or ""),
            str(context_item.get("parent_rule_id", "") or ""),
            self._safe_int(context_item.get("parent_line", 0), 0),
            str(context_item.get("parent_file_path", context_item.get("parent_file", "")) or ""),
        )

    def _eligible_live_ai_parent_issue_contexts(self, contexts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not isinstance(contexts, list) or not contexts:
            return []
        minimum_rank = self._severity_rank(self.live_ai_min_review_severity)
        eligible: List[Dict[str, Any]] = []
        for context in contexts:
            if not isinstance(context, dict):
                continue
            severity_rank = self._severity_rank(context.get("severity", ""))
            if severity_rank < minimum_rank:
                continue
            eligible.append(context)

        def sort_key(item: Dict[str, Any]) -> Tuple[int, int, int, str]:
            linked_findings = cast(List[Dict[str, Any]], item.get("issue_context", {}).get("linked_findings", []))
            return (
                -self._severity_rank(item.get("severity", "")),
                -len(linked_findings),
                self._safe_int(item.get("parent_line", 0), 0),
                str(item.get("parent_issue_id", "") or item.get("parent_rule_id", "") or ""),
            )

        eligible.sort(key=sort_key)
        return eligible

    def _select_live_ai_parent_issue_contexts(self, contexts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        eligible = self._eligible_live_ai_parent_issue_contexts(contexts)
        return eligible[: self._recommended_live_ai_parent_review_limit(eligible)]

    @staticmethod
    def _rule_family(rule_id: Any) -> str:
        text = str(rule_id or "").strip().upper()
        if not text:
            return ""
        parts = [part for part in text.split("-") if part]
        return parts[0] if parts else text

    def _recommended_live_ai_parent_review_limit(self, eligible: List[Dict[str, Any]]) -> int:
        if not isinstance(eligible, list) or not eligible:
            return 0
        hard_cap = max(1, int(self.live_ai_max_parent_reviews_per_file))
        if hard_cap == 1 or len(eligible) == 1:
            return 1

        critical_count = 0
        hotspot_keys = set()
        rule_families = set()
        for item in eligible:
            if not isinstance(item, dict):
                continue
            if self._severity_rank(item.get("severity", "")) >= 3:
                critical_count += 1
            hotspot_keys.add(
                (
                    str(item.get("object", "") or item.get("parent_file", "") or ""),
                    str(item.get("event", "") or "Global"),
                )
            )
            family = self._rule_family(item.get("parent_rule_id", "") or item.get("rule_id", ""))
            if family:
                rule_families.add(family)

        recommended = 2 if len(eligible) >= 2 else 1
        if len(eligible) >= 3 and (critical_count >= 1 or len(hotspot_keys) >= 2 or len(rule_families) >= 2):
            recommended = 3
        if len(eligible) >= 4 and (critical_count >= 2 or (critical_count >= 1 and len(rule_families) >= 3)):
            recommended = 4
        if len(eligible) >= 5 and critical_count >= 2 and len(rule_families) >= 4:
            recommended = 5
        return min(hard_cap, recommended)

    def _run_live_ai_review_for_context(
        self,
        code_content: str,
        filename: str,
        context_item: Dict[str, Any],
        *,
        ai_with_context: bool,
        context_payload: Any,
        ai_model_name: Optional[str] = None,
    ) -> Tuple[Optional[Dict[str, Any]], int, Dict[str, Any]]:
        primary = cast(Dict[str, Any], context_item.get("issue_context", {}).get("primary", {}))
        focus_violations = [primary]
        todo_prompt_context = context_item.get("todo_prompt_context", {}) if isinstance(context_item, dict) else {}
        focus_snippet = str((todo_prompt_context or {}).get("snippet", "") or "")
        if not focus_snippet:
            focus_snippet = self._build_focus_snippet(
                code_content,
                focus_violations,
                window_lines=self.ai_todo_prompt_window_lines if self.ai_prompt_mode == "todo_compact" else None,
                max_lines=self.ai_todo_prompt_max_lines if self.ai_prompt_mode == "todo_compact" else None,
            )
        ai_started = self._perf_now()
        with self._live_ai_semaphore:
            review = self.ai_tool.generate_review(
                code_content,
                focus_violations,
                use_context=bool(ai_with_context),
                context_payload=context_payload,
                focus_snippet=focus_snippet,
                issue_context=context_item.get("issue_context", {}),
                todo_prompt_context=todo_prompt_context,
                model_name=ai_model_name,
            )
        elapsed_ms = self._elapsed_ms(ai_started)
        status_meta = self._new_ai_review_status_entry(
            context_item,
            filename=filename,
            status="generated",
            reason="generated",
        )
        if not review:
            status_meta["status"] = "failed"
            status_meta["reason"] = "empty_response"
            return None, elapsed_ms, status_meta
        if isinstance(review, str) and review.startswith("AI live review failed:"):
            status_meta["status"] = "failed"
            status_meta["reason"] = self._classify_ai_review_failure_reason(review)
            status_meta["detail"] = str(review or "")
            return None, elapsed_ms, status_meta
        return (
            {
                "file": str(context_item.get("file", filename) or filename),
                "file_path": str(context_item.get("file_path", context_item.get("file", filename)) or filename),
                "object": str(context_item.get("object", filename) or filename),
                "event": str(context_item.get("event", "Global") or "Global"),
                "review": review,
                "source": "live",
                "status": "Pending",
                "parent_source": str(context_item.get("parent_source", "P1") or "P1"),
                "parent_issue_id": str(context_item.get("parent_issue_id", "") or ""),
                "parent_rule_id": str(context_item.get("parent_rule_id", "") or ""),
                "parent_file": str(context_item.get("parent_file", filename) or filename),
                "parent_file_path": str(context_item.get("parent_file_path", context_item.get("parent_file", filename)) or filename),
                "parent_line": self._safe_int(context_item.get("parent_line", 0), 0),
            },
            elapsed_ms,
            status_meta,
        )

    def _new_ai_review_status_entry(
        self,
        context_item: Dict[str, Any],
        *,
        filename: str,
        status: str,
        reason: str,
        detail: str = "",
        selected_rank: Optional[int] = None,
        selected_cap: Optional[int] = None,
    ) -> Dict[str, Any]:
        selected_rank_value = self._safe_int(
            selected_rank if selected_rank is not None else context_item.get("selected_rank", context_item.get("_selected_rank", 0)),
            0,
        )
        selected_cap_value = self._safe_int(
            selected_cap if selected_cap is not None else context_item.get("selected_cap", context_item.get("_selected_cap", 0)),
            0,
        )
        payload = {
            "status": str(status or "").strip() or "unknown",
            "reason": str(reason or "").strip() or "unknown",
            "detail": str(detail or "").strip(),
            "parent_source": str(context_item.get("parent_source", "P1") or "P1"),
            "parent_issue_id": str(context_item.get("parent_issue_id", "") or ""),
            "parent_rule_id": str(context_item.get("parent_rule_id", "") or ""),
            "parent_file": str(context_item.get("parent_file", filename) or filename),
            "parent_file_path": str(context_item.get("parent_file_path", context_item.get("parent_file", filename)) or filename),
            "parent_line": self._safe_int(context_item.get("parent_line", 0), 0),
            "file": str(context_item.get("file", filename) or filename),
            "file_path": str(context_item.get("file_path", context_item.get("file", filename)) or filename),
            "object": str(context_item.get("object", filename) or filename),
            "event": str(context_item.get("event", "Global") or "Global"),
            "severity": str(context_item.get("severity", "") or ""),
            "message": str(context_item.get("message", "") or ""),
        }
        if selected_rank_value > 0:
            payload["selected_rank"] = selected_rank_value
        if selected_cap_value > 0:
            payload["selected_cap"] = selected_cap_value
        return payload

    @staticmethod
    def _classify_ai_review_failure_reason(review_text: Any) -> str:
        text = str(review_text or "").strip().lower()
        if "timed out" in text or "timeout" in text:
            return "timeout"
        if "invalid ai response payload" in text or "normalize review" in text or "json" in text:
            return "response_parse_failed"
        return "fail_soft_skip"

    @staticmethod
    def _rule_requires_domain_hint(parent_rule_id: Any) -> bool:
        rule = str(parent_rule_id or "").strip().upper()
        if not rule:
            return False
        return rule in {
            "PERF-SETMULTIVALUE-ADOPT-01",
            "PERF-GETMULTIVALUE-ADOPT-01",
            "PERF-DPSET-BATCH-01",
            "PERF-DPGET-BATCH-01",
        }

    @staticmethod
    def _domain_hint_instruction(parent_rule_id: Any) -> str:
        rule = str(parent_rule_id or "").strip().upper()
        if rule == "PERF-SETMULTIVALUE-ADOPT-01":
            return (
                "반복 setValue 호출은 하나의 setMultiValue 호출로 묶어 제안하세요. "
                "반드시 WinCC OA CONTROL fenced code block을 포함하고, before/after 중 after 예시는 "
                "setMultiValue(\"obj_auto_sel1\", \"enabled\", false,\n"
                "              \"obj_auto_sel2\", \"enabled\", false); "
                "형태처럼 여러 호출을 하나로 합친 실제 코드를 보여주세요."
            )
        if rule == "PERF-GETMULTIVALUE-ADOPT-01":
            return (
                "반복 getValue 호출은 하나의 getMultiValue 호출로 묶어 제안하세요. "
                "반드시 WinCC OA CONTROL fenced code block을 포함하고, 여러 getValue 호출이 "
                "getMultiValue(...) 하나로 합쳐진 실제 코드를 보여주세요."
            )
        if rule == "PERF-DPSET-BATCH-01":
            return (
                "반복 dpSet 호출은 dpSetWait 또는 동등한 배치 묶음 처리로 제안하세요. "
                "반드시 WinCC OA CONTROL fenced code block을 포함하고, 여러 dpSet 호출을 한 번에 처리하는 "
                "실제 예시를 보여주세요."
            )
        if rule == "PERF-DPGET-BATCH-01":
            return (
                "반복 dpGet 호출은 dpGetAll 또는 동등한 배치 묶음 처리로 제안하세요. "
                "반드시 WinCC OA CONTROL fenced code block을 포함하고, 여러 dpGet 호출을 한 번에 처리하는 "
                "실제 예시를 보여주세요."
            )
        return ""

    @staticmethod
    def _extract_review_code_blocks(review_text: Any) -> List[str]:
        text = str(review_text or "")
        if not text:
            return []
        blocks = re.findall(r"```(?:[\w#+.-]+)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
        return [str(block or "").strip() for block in blocks if str(block or "").strip()]

    @staticmethod
    def _domain_hint_instruction(parent_rule_id: Any) -> str:
        rule = str(parent_rule_id or "").strip().upper()
        if rule == "PERF-SETMULTIVALUE-ADOPT-01":
            return (
                "반복 setValue 호출은 하나의 setMultiValue 호출로 묶어 제안하세요. "
                "반드시 WinCC OA CONTROL fenced code block을 포함하고, 가능하면 before/after를 함께 보여주세요. "
                "after 예시는 다음 형태를 우선 사용하세요:\n"
                "setValue(\"obj_auto_sel1\", \"enabled\", false);\n"
                "setValue(\"obj_auto_sel2\", \"enabled\", false);\n"
                "=>\n"
                "setMultiValue(\"obj_auto_sel1\", \"enabled\", false,\n"
                "              \"obj_auto_sel2\", \"enabled\", false);"
            )
        if rule == "PERF-GETMULTIVALUE-ADOPT-01":
            return (
                "반복 getValue 호출은 하나의 getMultiValue 호출로 묶어 제안하세요. "
                "반드시 WinCC OA CONTROL fenced code block을 포함하고, 가능하면 before/after를 함께 보여주세요. "
                "여러 getValue 호출이 getMultiValue(...) 하나로 합쳐진 실제 코드를 보여주세요."
            )
        if rule == "PERF-DPSET-BATCH-01":
            return (
                "반복 dpSet 호출은 dpSetWait 또는 동등한 배치 묶음 처리로 제안하세요. "
                "반드시 WinCC OA CONTROL fenced code block을 포함하고, 가능하면 before/after를 함께 보여주세요. "
                "여러 dpSet 호출을 한 번에 처리하는 실제 예시를 보여주세요."
            )
        if rule == "PERF-DPGET-BATCH-01":
            return (
                "반복 dpGet 호출은 dpGetAll 또는 동등한 배치 묶음 처리로 제안하세요. "
                "반드시 WinCC OA CONTROL fenced code block을 포함하고, 가능하면 before/after를 함께 보여주세요. "
                "여러 dpGet 호출을 한 번에 처리하는 실제 예시를 보여주세요."
            )
        return ""

    @staticmethod
    def _has_grouped_dp_call(block_text: Any, function_name: str) -> bool:
        block = str(block_text or "")
        func = str(function_name or "").strip()
        if not block or not func:
            return False
        pattern = rf"{re.escape(func)}\s*\(([\s\S]*?)\);"
        for match in re.finditer(pattern, block, flags=re.IGNORECASE):
            args = str(match.group(1) or "")
            if args.count(",") >= 3:
                return True
        return False

    @staticmethod
    def _review_has_multi_call_example(parent_rule_id: Any, review_text: Any) -> bool:
        text = str(review_text or "")
        rule = str(parent_rule_id or "").strip().upper()
        if not text or not rule:
            return False
        blocks = CodeInspectorApp._extract_review_code_blocks(text)
        lowered = [block.lower() for block in blocks]
        if rule == "PERF-SETMULTIVALUE-ADOPT-01":
            return any("setmultivalue(" in block for block in lowered)
        if rule == "PERF-GETMULTIVALUE-ADOPT-01":
            return any("getmultivalue(" in block for block in lowered)
        if rule == "PERF-DPSET-BATCH-01":
            return any(CodeInspectorApp._has_grouped_dp_call(block, "dpSet") for block in blocks)
        if rule == "PERF-DPGET-BATCH-01":
            return any(CodeInspectorApp._has_grouped_dp_call(block, "dpGet") for block in blocks)
        return True

    def _review_has_domain_hint(self, parent_rule_id: Any, review_text: Any) -> bool:
        text = str(review_text or "").strip().lower()
        rule = str(parent_rule_id or "").strip().upper()
        if not text or not rule:
            return False
        if rule == "PERF-SETMULTIVALUE-ADOPT-01":
            return ("setmultivalue" in text) and self._review_has_multi_call_example(rule, review_text)
        if rule == "PERF-GETMULTIVALUE-ADOPT-01":
            return ("getmultivalue" in text) and self._review_has_multi_call_example(rule, review_text)
        if rule == "PERF-DPSET-BATCH-01":
            return ("dpset" in text) and self._review_has_multi_call_example(rule, review_text)
        if rule == "PERF-DPGET-BATCH-01":
            return ("dpget" in text) and self._review_has_multi_call_example(rule, review_text)
        return True

    @staticmethod
    def _domain_hint_instruction(parent_rule_id: Any) -> str:
        rule = str(parent_rule_id or "").strip().upper()
        if rule == "PERF-SETMULTIVALUE-ADOPT-01":
            return (
                "반복 setValue 호출은 하나의 setMultiValue 호출로 묶어 제안하세요. "
                "반드시 WinCC OA CONTROL fenced code block을 포함하고 before/after 예시를 보여주세요.\n"
                "setValue(\"obj_auto_sel1\", \"enabled\", false);\n"
                "setValue(\"obj_auto_sel2\", \"enabled\", false);\n"
                "=>\n"
                "setMultiValue(\"obj_auto_sel1\", \"enabled\", false,\n"
                "              \"obj_auto_sel2\", \"enabled\", false);"
            )
        if rule == "PERF-GETMULTIVALUE-ADOPT-01":
            return (
                "반복 getValue 호출은 하나의 getMultiValue 호출로 묶어 제안하세요. "
                "반드시 WinCC OA CONTROL fenced code block을 포함하고 before/after 예시를 보여주세요.\n"
                "getValue(\"obj_auto_sel1\", \"enabled\", bSel1);\n"
                "getValue(\"obj_auto_sel2\", \"enabled\", bSel2);\n"
                "=>\n"
                "getMultiValue(\"obj_auto_sel1\", \"enabled\", bSel1,\n"
                "              \"obj_auto_sel2\", \"enabled\", bSel2);"
            )
        if rule == "PERF-DPSET-BATCH-01":
            return (
                "반복 dpSet 호출은 하나의 grouped dpSet 호출로 묶어 제안하세요. "
                "dpSetWait 같은 다른 함수로 바꾸지 말고, 여러 DPE/value 쌍을 한 번의 dpSet 호출에 넣는 WinCC OA CONTROL 예시를 보여주세요.\n"
                "dpSet(\"System1:Obj1.enabled\", false);\n"
                "dpSet(\"System1:Obj2.enabled\", false);\n"
                "=>\n"
                "dpSet(\"System1:Obj1.enabled\", false,\n"
                "      \"System1:Obj2.enabled\", false);"
            )
        if rule == "PERF-DPGET-BATCH-01":
            return (
                "반복 dpGet 호출은 하나의 grouped dpGet 호출로 묶어 제안하세요. "
                "dpGetAll 같은 다른 함수로 바꾸지 말고, 여러 DPE/target 쌍을 한 번의 dpGet 호출에 넣는 WinCC OA CONTROL 예시를 보여주세요.\n"
                "dpGet(\"System1:Obj1.enabled\", bObj1);\n"
                "dpGet(\"System1:Obj2.enabled\", bObj2);\n"
                "=>\n"
                "dpGet(\"System1:Obj1.enabled\", bObj1,\n"
                "      \"System1:Obj2.enabled\", bObj2);"
            )
        return ""

    def _resolve_violation_target_path(self, violation: Dict[str, Any]) -> str:
        file_path = str((violation or {}).get("file_path", "") or "").strip()
        file_name = str((violation or {}).get("file", "") or "").strip()
        candidates = []
        if file_path:
            candidates.append(file_path)
        if file_name:
            candidates.append(file_name)
            candidates.append(os.path.join(self.data_dir, os.path.basename(file_name)))
        normalized = []
        for candidate in candidates:
            if not candidate:
                continue
            normalized.append(os.path.normpath(candidate))
        for candidate in normalized:
            if os.path.isfile(candidate):
                return candidate
        raise FileNotFoundError(f"Input file not found for violation: {file_path or file_name or '(unknown)'}")

    def _build_single_violation_context(self, target_path: str, violation: Dict[str, Any]) -> Dict[str, Any]:
        source = str((violation or {}).get("source", (violation or {}).get("priority_origin", "P1")) or "P1").strip().upper()
        if source not in ("P1", "P2"):
            source = "P1"
        basename = os.path.basename(str((violation or {}).get("file", "") or target_path))
        parent_issue_id = str((violation or {}).get("issue_id", "") or "").strip()
        parent_rule_id = str((violation or {}).get("rule_id", "") or "").strip()
        parent_line = self._safe_int((violation or {}).get("line", 0), 0)
        message = str((violation or {}).get("message", "") or "").strip()
        object_name = str((violation or {}).get("object", "") or basename).strip() or basename
        event_name = str((violation or {}).get("event", "Global") or "Global").strip() or "Global"
        severity = str((violation or {}).get("severity", "") or "").strip()
        if not parent_issue_id:
            parent_issue_id = f"{source}-{parent_rule_id or 'UNKNOWN'}-{self._sha256_text(f'{basename}:{parent_line}:{message}')[:10]}"
        return {
            "parent_source": source,
            "parent_issue_id": parent_issue_id,
            "parent_rule_id": parent_rule_id,
            "parent_file": basename,
            "parent_file_path": os.path.normpath(str(target_path)),
            "parent_line": parent_line,
            "file": basename,
            "file_path": os.path.normpath(str(target_path)),
            "object": object_name,
            "event": event_name,
            "severity": severity,
            "message": message,
            "issue_context": {
                "primary": {
                    "source": source,
                    "issue_id": parent_issue_id,
                    "rule_id": parent_rule_id,
                    "line": parent_line,
                    "file": basename,
                    "file_path": os.path.normpath(str(target_path)),
                    "object": object_name,
                    "event": event_name,
                    "severity": severity,
                    "message": message,
                },
                "linked_findings": [],
            },
        }

    def generate_ai_review_for_violation(
        self,
        violation: Dict[str, Any],
        *,
        enable_live_ai: Optional[bool] = None,
        ai_model_name: Optional[str] = None,
        ai_with_context: bool = False,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not isinstance(violation, dict):
            raise ValueError("violation must be an object")
        target_path = self._resolve_violation_target_path(violation)
        with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
            code_content = f.read()
        context_item = self._build_single_violation_context(target_path, violation)
        context_item["todo_prompt_context"] = self._build_todo_prompt_context(code_content, context_item)
        use_live_ai = self._resolve_toggle(self.live_ai_enabled_default, enable_live_ai)

        review_item: Optional[Dict[str, Any]] = None
        status_meta: Dict[str, Any]
        domain_warning = ""

        if use_live_ai:
            review_item, _elapsed_ms, status_meta = self._run_live_ai_review_for_context(
                code_content,
                os.path.basename(target_path),
                context_item,
                ai_with_context=bool(ai_with_context),
                context_payload=None,
                ai_model_name=ai_model_name,
            )
            parent_rule_id = context_item.get("parent_rule_id", "")
            needs_hint = self._rule_requires_domain_hint(parent_rule_id)
            has_hint = self._review_has_domain_hint(parent_rule_id, (review_item or {}).get("review", ""))
            if review_item and needs_hint and not has_hint:
                reinforced = dict(context_item)
                reinforced_todo = dict((context_item.get("todo_prompt_context") or {}))
                hint_text = self._domain_hint_instruction(parent_rule_id)
                todo_comment = str(reinforced_todo.get("todo_comment", "") or "").strip()
                snippet = str(reinforced_todo.get("snippet", "") or "").strip()
                if hint_text:
                    if hint_text not in todo_comment:
                        reinforced_todo["todo_comment"] = (f"{todo_comment}\n{hint_text}" if todo_comment else hint_text).strip()
                    if hint_text not in snippet:
                        reinforced_todo["snippet"] = (f"{snippet}\n// Domain hint: {hint_text}" if snippet else f"// Domain hint: {hint_text}").strip()
                reinforced["todo_prompt_context"] = reinforced_todo
                retried_review_item, _elapsed_ms_retry, retried_status_meta = self._run_live_ai_review_for_context(
                    code_content,
                    os.path.basename(target_path),
                    reinforced,
                    ai_with_context=bool(ai_with_context),
                    context_payload=None,
                    ai_model_name=ai_model_name,
                )
                if retried_review_item:
                    review_item = retried_review_item
                    status_meta = retried_status_meta
                if not self._review_has_domain_hint(parent_rule_id, (review_item or {}).get("review", "")):
                    domain_warning = (
                        "도메인 가이드 검증 경고: 멀티 API 변환 키워드 또는 묶음 처리 코드 예시(setMultiValue/getMultiValue, dpSetWait/dpGetAll)가 부족합니다."
                    )
            if domain_warning and ("dpSetWait/dpGetAll" in str(domain_warning) or "setMultiValue/getMultiValue" in str(domain_warning)):
                domain_warning = (
                    "도메인 가이드 검증 경고: 멀티 API 변환 키워드 또는 묶음 처리 코드 예시(setMultiValue/getMultiValue, grouped dpSet/dpGet)가 부족합니다."
                )
            if domain_warning:
                status_meta["detail"] = (
                    f"{status_meta.get('detail', '').strip()} {domain_warning}".strip()
                    if str(status_meta.get("detail", "")).strip()
                    else domain_warning
                )
        else:
            primary = cast(Dict[str, Any], context_item.get("issue_context", {}).get("primary", {}))
            review = self.ai_tool.get_mock_review(
                code_content,
                [primary],
                issue_context=context_item.get("issue_context", {}),
                todo_prompt_context=context_item.get("todo_prompt_context", {}),
            )
            status_meta = self._new_ai_review_status_entry(
                context_item,
                filename=os.path.basename(target_path),
                status="generated" if review else "failed",
                reason="mock_generated" if review else "empty_response",
            )
            if review:
                review_item = {
                    "file": str(context_item.get("file", os.path.basename(target_path)) or os.path.basename(target_path)),
                    "file_path": str(context_item.get("file_path", target_path) or target_path),
                    "object": str(context_item.get("object", os.path.basename(target_path)) or os.path.basename(target_path)),
                    "event": str(context_item.get("event", "Global") or "Global"),
                    "review": review,
                    "source": "mock",
                    "status": "Pending",
                    "parent_source": str(context_item.get("parent_source", "P1") or "P1"),
                    "parent_issue_id": str(context_item.get("parent_issue_id", "") or ""),
                    "parent_rule_id": str(context_item.get("parent_rule_id", "") or ""),
                    "parent_file": str(context_item.get("parent_file", os.path.basename(target_path)) or os.path.basename(target_path)),
                    "parent_file_path": str(context_item.get("parent_file_path", target_path) or target_path),
                    "parent_line": self._safe_int(context_item.get("parent_line", 0), 0),
                }

        result = {
            "request_id": str(request_id or uuid.uuid4().hex),
            "available": bool(review_item),
            "message": "P3 review generated" if review_item else str(status_meta.get("detail", "") or "P3 review unavailable"),
            "review_item": review_item,
            "status_item": status_meta,
        }
        return result

    def _build_parent_issue_contexts(self, filename: str, source_path: str, internal_violations: List[Dict], global_violations: List[Dict]) -> List[Dict]:
        contexts: List[Dict] = []
        by_issue_id: Dict[str, Dict[str, Any]] = {}

        for group in internal_violations or []:
            if not isinstance(group, dict):
                continue
            object_name = str(group.get("object", filename) or filename)
            event_name = str(group.get("event", "Global") or "Global")
            for violation in group.get("violations", []) or []:
                if not isinstance(violation, dict):
                    continue
                issue_id = str(violation.get("issue_id", "") or "").strip()
                rule_id = str(violation.get("rule_id", "") or "").strip()
                line_no = self._safe_int(violation.get("line", 0), 0)
                message = str(violation.get("message", "") or "").strip()
                context = {
                    "parent_source": "P1",
                    "parent_issue_id": issue_id,
                    "parent_rule_id": rule_id,
                    "parent_file": filename,
                    "parent_file_path": source_path,
                    "parent_line": line_no,
                    "file": filename,
                    "file_path": source_path,
                    "object": object_name,
                    "event": event_name,
                    "severity": str(violation.get("severity", "") or ""),
                    "message": message,
                    "issue_context": {
                        "primary": {
                            "source": "P1",
                            "issue_id": issue_id,
                            "rule_id": rule_id,
                            "line": line_no,
                            "file": filename,
                            "file_path": source_path,
                            "object": object_name,
                            "event": event_name,
                            "severity": str(violation.get("severity", "") or ""),
                            "message": message,
                        },
                        "linked_findings": [],
                    },
                }
                contexts.append(context)
                if issue_id:
                    by_issue_id[issue_id] = context

        matched_p2_indexes = set()
        for idx, violation in enumerate(global_violations or []):
            if not isinstance(violation, dict):
                continue
            file_name = os.path.basename(str(violation.get("file", "") or filename)) or filename
            file_path = str(violation.get("file_path", "") or violation.get("file", "") or source_path)
            line_no = self._safe_int(violation.get("line", 0), 0)
            rule_id = str(violation.get("rule_id", "") or "").strip()
            message = str(violation.get("message", "") or "").strip()
            target_issue_id = str(violation.get("issue_id", "") or "").strip()
            normalized_message = self._normalize_issue_text(message)

            best_context = None
            best_score = -1
            for context in contexts:
                primary = context.get("issue_context", {}).get("primary", {})
                score = 0
                if os.path.basename(str(primary.get("file", "") or filename)) == file_name:
                    score += 4
                if target_issue_id and target_issue_id == str(primary.get("issue_id", "") or ""):
                    score += 10
                primary_line = self._safe_int(primary.get("line", 0), 0)
                if line_no > 0 and primary_line > 0:
                    delta = abs(line_no - primary_line)
                    if delta == 0:
                        score += 5
                    elif delta <= 3:
                        score += 4
                    elif delta <= 10:
                        score += 3
                    elif delta <= 25:
                        score += 1
                primary_rule = str(primary.get("rule_id", "") or "").strip()
                if rule_id and primary_rule:
                    if rule_id == primary_rule:
                        score += 4
                    elif rule_id.split("-", 1)[0] == primary_rule.split("-", 1)[0]:
                        score += 2
                primary_message = self._normalize_issue_text(primary.get("message", ""))
                if normalized_message and primary_message:
                    if normalized_message == primary_message:
                        score += 3
                    elif normalized_message in primary_message or primary_message in normalized_message:
                        score += 1
                if score > best_score:
                    best_score = score
                    best_context = context

            if best_context and best_score >= 6:
                linked = {
                    "source": "P2",
                    "issue_id": target_issue_id,
                    "rule_id": rule_id,
                    "line": line_no,
                    "file": file_name,
                    "file_path": file_path,
                    "object": str(violation.get("object", file_name) or file_name),
                    "event": str(violation.get("event", "Global") or "Global"),
                    "severity": str(violation.get("severity", violation.get("type", "")) or ""),
                    "message": message,
                }
                cast(Dict[str, Any], best_context["issue_context"]).setdefault("linked_findings", []).append(linked)
                matched_p2_indexes.add(idx)

        for idx, violation in enumerate(global_violations or []):
            if idx in matched_p2_indexes or not isinstance(violation, dict):
                continue
            file_name = os.path.basename(str(violation.get("file", "") or filename)) or filename
            rule_id = str(violation.get("rule_id", "") or "").strip()
            line_no = self._safe_int(violation.get("line", 0), 0)
            issue_id = str(violation.get("issue_id", "") or f"P2::{file_name}:{rule_id}:{line_no}") or f"P2::{file_name}:{rule_id}:{line_no}"
            message = str(violation.get("message", "") or "").strip()
            object_name = str(violation.get("object", file_name) or file_name)
            event_name = str(violation.get("event", "Global") or "Global")
            contexts.append(
                {
                    "parent_source": "P2",
                    "parent_issue_id": issue_id,
                    "parent_rule_id": rule_id,
                    "parent_file": file_name,
                    "parent_file_path": file_path,
                    "parent_line": line_no,
                    "file": file_name,
                    "file_path": file_path,
                    "object": object_name,
                    "event": event_name,
                    "severity": str(violation.get("severity", violation.get("type", "")) or ""),
                    "message": message,
                    "issue_context": {
                        "primary": {
                            "source": "P2",
                            "issue_id": issue_id,
                            "rule_id": rule_id,
                            "line": line_no,
                            "file": file_name,
                            "file_path": file_path,
                            "object": object_name,
                            "event": event_name,
                            "severity": str(violation.get("severity", violation.get("type", "")) or ""),
                            "message": message,
                        },
                        "linked_findings": [],
                    },
                }
            )
        return contexts

    def analyze_file(
        self,
        target,
        mode=DEFAULT_MODE,
        enable_ctrlppcheck=None,
        enable_live_ai=None,
        ai_with_context=False,
        ai_model_name: Optional[str] = None,
        artifact_stem: str = "",
        context_payload=None,
        reporter=None,
        metrics: Optional[Dict] = None,
        defer_excel_reports: Optional[bool] = None,
        progress_cb=None,
    ):
        file_started = self._perf_now()
        active_reporter = reporter or self.reporter
        filename = os.path.basename(target)
        file_type = self.infer_file_type(filename)
        logger.info("Analyzing: %s", filename)

        def emit_progress(phase: str):
            if not callable(progress_cb):
                return
            try:
                progress_cb({"phase": phase, "file": filename})
            except Exception:
                logger.exception("Per-file analysis progress callback error")

        emit_progress("read_source")

        read_started = self._perf_now()
        with open(target, "r", encoding="utf-8", errors="ignore") as f:
            code_content = f.read()
        read_ms = self._elapsed_ms(read_started)
        self._metrics_inc(metrics, "bytes_read", len(code_content.encode("utf-8", errors="ignore")))

        emit_progress("heuristic_review")
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
                    violation.setdefault("file_path", os.path.normpath(str(target)))

        global_violations = []
        use_ctrlpp = False
        if file_type == "Server":
            use_ctrlpp = self._resolve_toggle(self.ctrlpp_enabled_default, enable_ctrlppcheck)
            ctrl_started = self._perf_now()
            if use_ctrlpp:
                emit_progress("ctrlpp_check")
            with self._ctrlpp_semaphore:
                global_violations = self.ctrl_tool.run_check(
                    target,
                    code_content,
                    enabled=use_ctrlpp,
                )
            for violation in global_violations or []:
                if isinstance(violation, dict):
                    violation.setdefault("file", filename)
                    violation.setdefault("file_path", os.path.normpath(str(target)))
            self._metrics_add_timing(metrics, "ctrlpp", self._elapsed_ms(ctrl_started))
            if use_ctrlpp:
                self._metrics_inc(metrics, "ctrlpp_calls", 1)

        file_report = {
            "file": filename,
            "source_code": code_content,
            "internal_violations": internal_violations,
            "global_violations": global_violations,
            "ai_reviews": [],
            "ai_review_statuses": [],
        }

        all_parent_issue_contexts = self._build_parent_issue_contexts(
            filename,
            os.path.normpath(str(target)),
            internal_violations,
            global_violations,
        )
        eligible_parent_issue_contexts = self._eligible_live_ai_parent_issue_contexts(all_parent_issue_contexts)
        selected_parent_cap = self._recommended_live_ai_parent_review_limit(eligible_parent_issue_contexts)
        parent_issue_contexts = eligible_parent_issue_contexts[:selected_parent_cap]
        eligible_rank_by_key = {
            self._live_ai_parent_context_key(item): idx + 1
            for idx, item in enumerate(eligible_parent_issue_contexts)
            if isinstance(item, dict)
        }
        selected_parent_keys = {
            self._live_ai_parent_context_key(item)
            for item in parent_issue_contexts
            if isinstance(item, dict)
        }
        minimum_rank = self._severity_rank(self.live_ai_min_review_severity)
        for context_item in all_parent_issue_contexts:
            if not isinstance(context_item, dict):
                continue
            context_key = self._live_ai_parent_context_key(context_item)
            if context_key not in selected_parent_keys:
                skipped_reason = "severity_filtered"
                detail = ""
                selected_rank = None
                if self._severity_rank(context_item.get("severity", "")) >= minimum_rank:
                    skipped_reason = "priority_limited"
                    selected_rank = eligible_rank_by_key.get(context_key, 0) or None
                    detail = (
                        "현재 파일의 상위 우선 parent 개수 제한으로 제외되었습니다."
                        if selected_parent_cap > 0
                        else "현재 파일의 우선순위 제한으로 제외되었습니다."
                    )
                file_report["ai_review_statuses"].append(
                    self._new_ai_review_status_entry(
                        context_item,
                        filename=filename,
                        status="skipped",
                        reason=skipped_reason,
                        detail=detail,
                        selected_rank=selected_rank,
                        selected_cap=selected_parent_cap if skipped_reason == "priority_limited" else None,
                    )
                )
        for context_item in parent_issue_contexts:
            if isinstance(context_item, dict):
                context_key = self._live_ai_parent_context_key(context_item)
                context_item["_selected_rank"] = eligible_rank_by_key.get(context_key, 0)
                context_item["_selected_cap"] = selected_parent_cap
                context_item["todo_prompt_context"] = self._build_todo_prompt_context(code_content, context_item)

        use_live_ai = self._resolve_toggle(self.live_ai_enabled_default, enable_live_ai)
        should_generate_ai_reviews = bool(parent_issue_contexts) and (
            use_live_ai or mode in [DEFAULT_MODE, "AI Full"]
        )
        if should_generate_ai_reviews:
            if use_live_ai:
                emit_progress("live_ai_review")
                live_ai_workers = max(1, min(self.live_ai_max_workers, len(parent_issue_contexts)))
                with concurrent.futures.ThreadPoolExecutor(max_workers=live_ai_workers) as pool:
                    futures = [
                        pool.submit(
                            self._run_live_ai_review_for_context,
                            code_content,
                            filename,
                            context_item,
                            ai_with_context=bool(ai_with_context),
                            context_payload=context_payload,
                            ai_model_name=ai_model_name,
                        )
                        for context_item in parent_issue_contexts
                    ]
                    for future in concurrent.futures.as_completed(futures):
                        review_item, elapsed_ms, status_meta = future.result()
                        self._metrics_add_timing(metrics, "ai", elapsed_ms)
                        self._metrics_inc(metrics, "llm_calls", 1)
                        if isinstance(status_meta, dict):
                            file_report["ai_review_statuses"].append(status_meta)
                        if review_item:
                            file_report["ai_reviews"].append(review_item)
            else:
                for context_item in parent_issue_contexts:
                    primary = cast(Dict[str, Any], context_item.get("issue_context", {}).get("primary", {}))
                    review = self.ai_tool.get_mock_review(
                        code_content,
                        [primary],
                        issue_context=context_item.get("issue_context", {}),
                        todo_prompt_context=context_item.get("todo_prompt_context", {}),
                    )
                    if not review:
                        continue
                    file_report["ai_reviews"].append(
                        {
                            "file": str(context_item.get("file", filename) or filename),
                            "object": str(context_item.get("object", filename) or filename),
                            "event": str(context_item.get("event", "Global") or "Global"),
                            "review": review,
                            "source": "mock",
                            "status": "Pending",
                            "parent_source": str(context_item.get("parent_source", "P1") or "P1"),
                            "parent_issue_id": str(context_item.get("parent_issue_id", "") or ""),
                            "parent_rule_id": str(context_item.get("parent_rule_id", "") or ""),
                            "parent_file": str(context_item.get("parent_file", filename) or filename),
                            "parent_line": self._safe_int(context_item.get("parent_line", 0), 0),
                        }
                    )
                    file_report["ai_review_statuses"].append(
                        self._new_ai_review_status_entry(
                            context_item,
                            filename=filename,
                            status="generated",
                            reason="mock_generated",
                        )
                    )

        artifact_stem = str(artifact_stem or "").strip() or self._report_artifact_stem(filename, str(target))
        reviewed_name = f"{artifact_stem}_REVIEWED.txt"
        session_key = active_reporter.output_dir
        cache_entry = {
            "file": filename,
            "display_name": filename,
            "artifact_stem": artifact_stem,
            "file_type": file_type,
            "reviewed_name": reviewed_name,
            "source_path": os.path.normpath(str(target)),
            "source_hash": self._sha256_text(code_content),
            "original_content": code_content,
            "report_data": json.loads(json.dumps(file_report, ensure_ascii=False)),
            "updated_at": self._iso_now(),
        }
        self._store_review_cache_file(session_key, filename, cache_entry)

        emit_progress("write_reports")
        output_meta = self._write_review_outputs(
            reporter=active_reporter,
            code_content=code_content,
            file_report=file_report,
            reviewed_name=reviewed_name,
            artifact_stem=artifact_stem,
            file_type=file_type,
            defer_excel_reports=defer_excel_reports,
            metrics=metrics,
        )
        report_ms = self._safe_int(output_meta.get("report_ms", 0), 0)
        report_text_ms = self._safe_int(output_meta.get("report_text_ms", 0), 0)
        use_deferred_excel = bool(output_meta.get("deferred_excel", False))
        deferred_excel_job_id = str(output_meta.get("excel_job_id", "") or "")
        sync_excel_meta = output_meta.get("excel_metrics", {}) if isinstance(output_meta.get("excel_metrics", {}), dict) else {}
        excel_total_ms = self._safe_int(output_meta.get("excel_total_ms", 0), 0)

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
                    "report_text": report_text_ms,
                    "excel_total": excel_total_ms,
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
            "ai_review_statuses": [item for fr in all_file_results for item in fr.get("ai_review_statuses", [])],
        }

    def summarize_results(self, all_file_results):
        p1_groups = []
        p2 = []
        p3 = []
        ai_review_statuses = []
        critical = 0
        warning = 0
        info = 0
        total = 0

        for report in all_file_results:
            p1_groups.extend(report["internal_violations"])
            p2.extend(report.get("global_violations", []))
            p3.extend(report.get("ai_reviews", []))
            ai_review_statuses.extend(report.get("ai_review_statuses", []))
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
            "ai_review_statuses": ai_review_statuses,
        }

    def run_directory_analysis(
        self,
        mode=DEFAULT_MODE,
        selected_files=None,
        input_sources=None,
        allow_raw_txt=False,
        enable_ctrlppcheck=None,
        enable_live_ai=None,
        ai_model_name: Optional[str] = None,
        ai_with_context=False,
        request_id: Optional[str] = None,
        defer_excel_reports: Optional[bool] = None,
        progress_cb=None,
    ):
        pipeline = DirectoryAnalysisPipeline(self)
        return pipeline.run(
            mode=mode,
            selected_files=selected_files,
            input_sources=input_sources,
            allow_raw_txt=allow_raw_txt,
            enable_ctrlppcheck=enable_ctrlppcheck,
            enable_live_ai=enable_live_ai,
            ai_model_name=ai_model_name,
            ai_with_context=ai_with_context,
            request_id=request_id,
            defer_excel_reports=defer_excel_reports,
            progress_cb=progress_cb,
        )


















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

    excel_group = parser.add_mutually_exclusive_group()
    excel_group.add_argument(
        "--defer-excel-reports",
        action="store_true",
        help="Generate Excel reports asynchronously after analyze completes",
    )
    excel_group.add_argument(
        "--sync-excel-reports",
        action="store_true",
        help="Generate Excel reports synchronously during analyze",
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

    defer_excel_toggle = None
    if args.defer_excel_reports:
        defer_excel_toggle = True
    elif args.sync_excel_reports:
        defer_excel_toggle = False

    try:
        app.run_directory_analysis(
            mode=args.mode,
            selected_files=args.selected_files,
            allow_raw_txt=args.allow_raw_txt,
            enable_ctrlppcheck=ctrlpp_toggle,
            enable_live_ai=live_ai_toggle,
            ai_with_context=args.ai_with_context,
            defer_excel_reports=defer_excel_toggle,
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        print(f"[!] Error during analysis: {e}")
