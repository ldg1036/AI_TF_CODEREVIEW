import collections
import concurrent.futures
import datetime
import hashlib
import json
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from core.ctrl_wrapper import CtrlppWrapper
from core.heuristic_checker import HeuristicChecker
from core.input_normalization import InputNormalizer
from core.llm_reviewer import LLMReviewer
from core.mcp_context import MCPContextClient
from core.pnl_parser import PnlParser
from core.reporter import Reporter
from core.xml_parser import XmlParser


class AppRuntimeMixin:
    """Host class should provide base_dir and data_dir before initialization."""

    def _initialize_runtime_state(self) -> None:
        self.app_config = self._load_app_config()

        self.pnl_parser = PnlParser()
        self.xml_parser = XmlParser()
        self.input_normalizer = InputNormalizer()
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
        self.autofix_structured_instruction_enabled = bool(engine_cfg.get("structured_instruction_enabled", False))

        self._last_output_dir = ""
        self._review_session_cache = collections.OrderedDict()
        self._review_session_cache_lock = threading.Lock()

    def _load_app_config(self) -> Dict[str, Any]:
        config_path = os.path.join(self.base_dir, "Config", "config.json")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _safe_int(value: Any, fallback: int = 0) -> int:
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
                artifact_stems[path] = f"{base_stem}_{self._sha256_text(path)[:8]}"
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

    def _new_metrics(self, request_id: Optional[str] = None) -> Dict[str, Any]:
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

    def _metrics_add_timing(self, metrics: Optional[Dict[str, Any]], key: str, ms: int) -> None:
        if not isinstance(metrics, dict):
            return
        with self._metrics_lock:
            timings = metrics.setdefault("timings_ms", {})
            timings[key] = self._safe_int(timings.get(key, 0), 0) + self._safe_int(ms, 0)

    def _metrics_inc(self, metrics: Optional[Dict[str, Any]], key: str, amount: int = 1) -> None:
        if not isinstance(metrics, dict):
            return
        with self._metrics_lock:
            metrics[key] = self._safe_int(metrics.get(key, 0), 0) + self._safe_int(amount, 0)

    def _metrics_inc_nested(self, metrics: Optional[Dict[str, Any]], parent: str, key: str, amount: int = 1) -> None:
        if not isinstance(metrics, dict):
            return
        with self._metrics_lock:
            target = metrics.setdefault(parent, {})
            if not isinstance(target, dict):
                target = {}
                metrics[parent] = target
            target[key] = self._safe_int(target.get(key, 0), 0) + self._safe_int(amount, 0)

    def _metrics_add_per_file(self, metrics: Optional[Dict[str, Any]], payload: Dict[str, Any]) -> None:
        if not isinstance(metrics, dict) or not isinstance(payload, dict):
            return
        with self._metrics_lock:
            per_file = metrics.setdefault("per_file", [])
            if isinstance(per_file, list):
                per_file.append(payload)

    def _metrics_apply_excel_report_meta(self, metrics: Optional[Dict[str, Any]], excel_meta: Optional[Dict[str, Any]]) -> None:
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
            stripped = str(review_text or "").strip()
            return stripped.splitlines()[0] if stripped else ""

    @staticmethod
    def _indent_lines(code_block: str, indent: str) -> List[str]:
        result = []
        for line in str(code_block or "").splitlines():
            result.append(f"{indent}{line}" if line.strip() else "")
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
        violations: List[Dict[str, Any]],
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
            if start <= prev_end + 1:
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
            budget -= take_end - start + 1
            if take_end < end:
                rendered.append("// ...")
        return "\n".join(rendered)

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
