import argparse
import concurrent.futures
import json
import logging
import os
from typing import Any, Dict, List, Optional, TypedDict, cast

from core.analysis_pipeline import DirectoryAnalysisPipeline
from core.app_runtime_mixin import AppRuntimeMixin
from core.autofix_mixin import AutoFixMixin
from core.file_collector_mixin import FileCollectorMixin
from core.heuristic_checker import HeuristicChecker
from core.live_ai_review_mixin import LiveAIReviewMixin
from core.reporter import Reporter
from core.session_mixin import ReviewSessionMixin

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


class CodeInspectorApp(AppRuntimeMixin, LiveAIReviewMixin, ReviewSessionMixin, FileCollectorMixin, AutoFixMixin):
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.data_dir = os.path.join(self.base_dir, "CodeReview_Data")
        self._initialize_runtime_state()

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
        with open(target, "r", encoding="utf-8", errors="ignore") as handle:
            code_content = handle.read()
        read_ms = self._elapsed_ms(read_started)
        self._metrics_inc(metrics, "bytes_read", len(code_content.encode("utf-8", errors="ignore")))

        emit_progress("heuristic_review")
        heuristic_started = self._perf_now()
        internal_violations = self.checker.analyze_raw_code(target, code_content, file_type=file_type)
        heuristic_ms = self._elapsed_ms(heuristic_started)
        self._metrics_add_timing(metrics, "heuristic", heuristic_ms)

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
                global_violations = self.ctrl_tool.run_check(target, code_content, enabled=use_ctrlpp)
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
            if context_key in selected_parent_keys:
                continue
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
            if not isinstance(context_item, dict):
                continue
            context_key = self._live_ai_parent_context_key(context_item)
            context_item["_selected_rank"] = eligible_rank_by_key.get(context_key, 0)
            context_item["_selected_cap"] = selected_parent_cap
            context_item["todo_prompt_context"] = self._build_todo_prompt_context(code_content, context_item)

        use_live_ai = self._resolve_toggle(self.live_ai_enabled_default, enable_live_ai)
        should_generate_ai_reviews = bool(parent_issue_contexts) and (use_live_ai or mode in [DEFAULT_MODE, "AI Full"])
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
        wait_for_direct_excel = (
            metrics is None
            and progress_cb is None
            and defer_excel_reports is None
            and use_deferred_excel
        )
        if wait_for_direct_excel:
            self.flush_deferred_excel_reports(output_dir=active_reporter.output_dir, wait=True, timeout_sec=30)

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
            "global_violations": [violation for fr in all_file_results for violation in fr.get("global_violations", [])],
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
                    severity = (violation.get("severity") or "").lower()
                    if severity == "critical":
                        critical += 1
                    elif severity in ("warning", "high", "medium"):
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
        result = pipeline.run(
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
        wait_for_direct_excel = (
            request_id is None
            and progress_cb is None
            and defer_excel_reports is None
            and isinstance(result, dict)
            and bool((result.get("output_dir") or "").strip())
        )
        if wait_for_direct_excel:
            flush_result = self.flush_deferred_excel_reports(
                output_dir=str(result.get("output_dir") or ""),
                wait=True,
                timeout_sec=30,
            )
            if isinstance(flush_result, dict):
                result["report_paths"] = flush_result.get("report_paths", result.get("report_paths", {}))
                result["report_jobs"] = flush_result.get("report_jobs", result.get("report_jobs", {}))
        return result


def build_arg_parser():
    parser = argparse.ArgumentParser(description="WinCC OA Code Inspector")
    parser.add_argument("--mode", default=DEFAULT_MODE, help="Analysis mode (Static | AI 보조 | AI Full)")
    parser.add_argument("--allow-raw-txt", action="store_true", help="Allow direct analysis of raw .txt files")
    parser.add_argument("--selected-files", nargs="*", default=None, help="Selected basenames to analyze")
    parser.add_argument("--ai-with-context", action="store_true", help="Request contextual AI prompt (reserved)")

    ctrlpp_group = parser.add_mutually_exclusive_group()
    ctrlpp_group.add_argument("--enable-ctrlppcheck", action="store_true", help="Enable CtrlppCheck validation for .ctl files")
    ctrlpp_group.add_argument("--disable-ctrlppcheck", action="store_true", help="Disable CtrlppCheck validation for .ctl files")

    ai_group = parser.add_mutually_exclusive_group()
    ai_group.add_argument("--enable-live-ai", action="store_true", help="Enable live AI review (Ollama provider)")
    ai_group.add_argument("--disable-live-ai", action="store_true", help="Disable live AI review and use mock review")

    excel_group = parser.add_mutually_exclusive_group()
    excel_group.add_argument("--defer-excel-reports", action="store_true", help="Generate Excel reports asynchronously after analyze completes")
    excel_group.add_argument("--sync-excel-reports", action="store_true", help="Generate Excel reports synchronously during analyze")
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
    except Exception as exc:
        import traceback

        traceback.print_exc()
        print(f"[!] Error during analysis: {exc}")
