import concurrent.futures
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, TypedDict, cast


logger = logging.getLogger(__name__)


IndexedTarget = Tuple[int, str]
MetricsDict = Dict[str, Any]
FileAnalysisResult = Dict[str, Any]


class AnalysisError(TypedDict):
    file: str
    error: str


class SummaryPayload(TypedDict):
    total: int
    critical: int
    warning: int
    info: int
    score: int
    requested_file_count: int
    successful_file_count: int
    failed_file_count: int
    p1_total: int
    p2_total: int
    p3_total: int


class ReportPathsPayload(TypedDict):
    html: str
    excel: List[str]
    reviewed_txt: List[str]


class ViolationsPayload(TypedDict):
    P1: List[Any]
    P2: List[Any]
    P3: List[Any]


class PayloadDict(TypedDict, total=False):
    summary: SummaryPayload
    violations: ViolationsPayload
    report_paths: ReportPathsPayload
    output_dir: str
    errors: List[AnalysisError]
    metrics: MetricsDict
    report_jobs: Dict[str, Any]


class CtrlppPreflightPayload(TypedDict):
    attempted: bool
    ready: bool
    binary_path: str
    message: str
    error_code: str


@dataclass
class PipelineRequest:
    mode: Any
    selected_files: Optional[Sequence[str]]
    allow_raw_txt: bool
    enable_ctrlppcheck: Optional[bool]
    enable_live_ai: Optional[bool]
    ai_with_context: bool
    request_id: Optional[str]
    defer_excel_reports: Optional[bool]


@dataclass
class PipelineRuntime:
    total_started: float
    metrics: MetricsDict
    request_reporter: Any
    analysis_targets: List[str]
    use_deferred_excel: bool
    use_live_ai: bool
    requested_ctrlpp: bool
    ai_provider: str
    mcp_context: Any
    progress_cb: Optional[Callable[[Dict[str, Any]], None]]
    enable_ctrlppcheck_effective: Optional[bool]
    ctrlpp_preflight: CtrlppPreflightPayload


class DirectoryAnalysisPipeline:
    """Request-scope directory analysis orchestration extracted from main.py."""

    def __init__(self, app: Any):
        self.app = app

    def run(
        self,
        mode,
        selected_files=None,
        allow_raw_txt=False,
        enable_ctrlppcheck=None,
        enable_live_ai=None,
        ai_with_context=False,
        request_id: Optional[str] = None,
        defer_excel_reports: Optional[bool] = None,
        progress_cb: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> PayloadDict:
        request = PipelineRequest(
            mode=mode,
            selected_files=selected_files,
            allow_raw_txt=bool(allow_raw_txt),
            enable_ctrlppcheck=enable_ctrlppcheck,
            enable_live_ai=enable_live_ai,
            ai_with_context=bool(ai_with_context),
            request_id=request_id,
            defer_excel_reports=defer_excel_reports,
        )
        runtime = self._prepare_runtime(request, progress_cb=progress_cb)

        if not runtime.analysis_targets:
            logger.info("No analysis targets found. Skipping report generation.")
            return self._empty_payload(runtime.total_started, runtime.metrics)

        file_results, analysis_errors = self._run_all_file_analyses(request, runtime)
        self._strip_ai_reviews_if_disabled(file_results, runtime.use_live_ai)
        self._generate_combined_html(file_results, runtime)
        payload = self._build_payload(file_results, analysis_errors, runtime)
        self._store_session_snapshot(payload, runtime)
        runtime.metrics["timings_ms"]["total"] = self.app._elapsed_ms(runtime.total_started)
        payload["metrics"] = runtime.metrics
        return payload

    def _prepare_runtime(
        self,
        request: PipelineRequest,
        progress_cb: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> PipelineRuntime:
        total_started = self.app._perf_now()
        metrics = self.app._new_metrics(request_id=request.request_id)
        logger.info("Starting Directory Analysis: %s", self.app.data_dir)

        request_reporter = self.app._create_request_reporter()
        self.app._ensure_review_session(request_reporter.output_dir)

        analysis_targets = self._collect_targets(request, metrics)
        metrics["file_count"] = len(analysis_targets)
        requested_ctrlpp = self.app._resolve_toggle(self.app.ctrlpp_enabled_default, request.enable_ctrlppcheck)
        ctrlpp_preflight = cast(
            CtrlppPreflightPayload,
            {
                "attempted": False,
                "ready": False,
                "binary_path": "",
                "message": "",
                "error_code": "",
            },
        )
        effective_enable_ctrlppcheck: Optional[bool] = bool(requested_ctrlpp)
        if requested_ctrlpp:
            ctl_targets = [path for path in analysis_targets if str(path).lower().endswith(".ctl")]
            if ctl_targets:
                raw_preflight = self.app.ctrl_tool.prepare_for_analysis(True, ctl_targets)
                ctrlpp_preflight = cast(
                    CtrlppPreflightPayload,
                    {
                        "attempted": bool(raw_preflight.get("attempted", False)),
                        "ready": bool(raw_preflight.get("ready", False)),
                        "binary_path": str(raw_preflight.get("binary_path", "") or ""),
                        "message": str(raw_preflight.get("message", "") or ""),
                        "error_code": str(raw_preflight.get("error_code", "") or ""),
                    },
                )
                # Fail-soft: keep analysis alive but skip per-file Ctrlpp when preflight failed.
                if not ctrlpp_preflight["ready"]:
                    effective_enable_ctrlppcheck = False
                    metrics["ctrlpp_preflight_failed"] = 1

        use_deferred_excel = (
            self.app.defer_excel_reports_default
            if request.defer_excel_reports is None
            else bool(request.defer_excel_reports)
        )
        use_live_ai = self.app._resolve_toggle(self.app.live_ai_enabled_default, request.enable_live_ai)
        mcp_context = self._prefetch_mcp_context_if_needed(request, use_live_ai, metrics)

        return PipelineRuntime(
            total_started=total_started,
            metrics=metrics,
            request_reporter=request_reporter,
            analysis_targets=analysis_targets,
            use_deferred_excel=use_deferred_excel,
            use_live_ai=use_live_ai,
            requested_ctrlpp=bool(requested_ctrlpp),
            ai_provider=str(getattr(self.app.ai_tool, "provider", "") or "").strip().lower(),
            mcp_context=mcp_context,
            progress_cb=progress_cb,
            enable_ctrlppcheck_effective=effective_enable_ctrlppcheck,
            ctrlpp_preflight=ctrlpp_preflight,
        )

    def _collect_targets(self, request: PipelineRequest, metrics: MetricsDict) -> List[str]:
        collect_started = self.app._perf_now()
        targets = self.app.collect_targets(
            selected_files=request.selected_files,
            allow_raw_txt=request.allow_raw_txt,
            metrics=metrics,
        )
        self.app._metrics_add_timing(metrics, "collect", self.app._elapsed_ms(collect_started))
        return list(targets or [])

    def _prefetch_mcp_context_if_needed(
        self,
        request: PipelineRequest,
        use_live_ai: bool,
        metrics: MetricsDict,
    ) -> Any:
        if not (use_live_ai and request.ai_with_context):
            return None
        mcp_started = self.app._perf_now()
        context = self.app.mcp_tool.fetch_context()
        self.app._metrics_add_timing(metrics, "mcp_context", self.app._elapsed_ms(mcp_started))
        return context

    def _run_all_file_analyses(
        self,
        request: PipelineRequest,
        runtime: PipelineRuntime,
    ) -> Tuple[List[FileAnalysisResult], List[AnalysisError]]:
        analyze_started = self.app._perf_now()
        indexed_targets: List[IndexedTarget] = list(enumerate(runtime.analysis_targets))
        ordered_results, ordered_errors = self._execute_indexed_analyses(indexed_targets, request, runtime)

        all_file_results: List[FileAnalysisResult] = []
        analysis_errors: List[AnalysisError] = []
        for idx in range(len(indexed_targets)):
            if idx in ordered_results:
                all_file_results.append(ordered_results[idx])
            if idx in ordered_errors:
                analysis_errors.append(ordered_errors[idx])

        self.app._metrics_add_timing(runtime.metrics, "analyze", self.app._elapsed_ms(analyze_started))
        return all_file_results, analysis_errors

    def _execute_indexed_analyses(
        self,
        indexed_targets: List[IndexedTarget],
        request: PipelineRequest,
        runtime: PipelineRuntime,
    ) -> Tuple[Dict[int, FileAnalysisResult], Dict[int, AnalysisError]]:
        ordered_results: Dict[int, FileAnalysisResult] = {}
        ordered_errors: Dict[int, AnalysisError] = {}
        max_workers = max(1, min(self.app.analysis_max_workers, len(indexed_targets)))
        total_files = len(indexed_targets)
        completed_files = 0
        failed_files = 0

        if max_workers > 1 and len(indexed_targets) > 1:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
                future_map = {
                    pool.submit(self._analyze_one, item, request, runtime): item
                    for item in indexed_targets
                }
                for future in concurrent.futures.as_completed(future_map):
                    idx, target = future_map[future]
                    ok = self._collect_future_result(future, idx, target, ordered_results, ordered_errors)
                    if ok:
                        completed_files += 1
                    else:
                        failed_files += 1
                    self._emit_progress_event(
                        runtime,
                        phase="analyze_file_done" if ok else "analyze_file_failed",
                        file_name=os.path.basename(str(target)),
                        total_files=total_files,
                        completed_files=completed_files,
                        failed_files=failed_files,
                    )
            return ordered_results, ordered_errors

        for idx, target in indexed_targets:
            try:
                _, result = self._analyze_one((idx, target), request, runtime)
                ordered_results[idx] = result
                completed_files += 1
                self._emit_progress_event(
                    runtime,
                    phase="analyze_file_done",
                    file_name=os.path.basename(str(target)),
                    total_files=total_files,
                    completed_files=completed_files,
                    failed_files=failed_files,
                )
            except Exception as exc:  # pragma: no cover - exercised via API tests
                self._record_analysis_error(idx, target, exc, ordered_errors)
                failed_files += 1
                self._emit_progress_event(
                    runtime,
                    phase="analyze_file_failed",
                    file_name=os.path.basename(str(target)),
                    total_files=total_files,
                    completed_files=completed_files,
                    failed_files=failed_files,
                )
        return ordered_results, ordered_errors

    def _collect_future_result(
        self,
        future: "concurrent.futures.Future[Tuple[int, FileAnalysisResult]]",
        idx: int,
        target: str,
        ordered_results: Dict[int, FileAnalysisResult],
        ordered_errors: Dict[int, AnalysisError],
    ) -> bool:
        try:
            result_idx, result = future.result()
            ordered_results[result_idx] = result
            return True
        except Exception as exc:  # pragma: no cover - exercised via API tests
            self._record_analysis_error(idx, target, exc, ordered_errors)
            return False

    def _record_analysis_error(
        self,
        idx: int,
        target: str,
        exc: Exception,
        ordered_errors: Dict[int, AnalysisError],
    ) -> None:
        logger.exception("Error during analysis of %s: %s", target, exc)
        ordered_errors[idx] = {
            "file": os.path.basename(str(target)),
            "error": str(exc),
        }

    @staticmethod
    def _emit_progress_event(
        runtime: PipelineRuntime,
        *,
        phase: str,
        file_name: str,
        total_files: int,
        completed_files: int,
        failed_files: int,
    ) -> None:
        cb = runtime.progress_cb
        if not callable(cb):
            return
        try:
            cb(
                {
                    "phase": phase,
                    "file": str(file_name or ""),
                    "total_files": max(0, int(total_files or 0)),
                    "completed_files": max(0, int(completed_files or 0)),
                    "failed_files": max(0, int(failed_files or 0)),
                }
            )
        except Exception:
            logger.exception("Analysis progress callback error")

    def _analyze_one(
        self,
        index_target: IndexedTarget,
        request: PipelineRequest,
        runtime: PipelineRuntime,
    ) -> Tuple[int, FileAnalysisResult]:
        idx, target = index_target
        result = self.app.analyze_file(
            target,
            mode=request.mode,
            enable_ctrlppcheck=runtime.enable_ctrlppcheck_effective,
            enable_live_ai=request.enable_live_ai,
            ai_with_context=request.ai_with_context,
            context_payload=runtime.mcp_context,
            reporter=runtime.request_reporter,
            metrics=runtime.metrics,
            defer_excel_reports=runtime.use_deferred_excel,
        )
        return idx, result

    @staticmethod
    def _strip_ai_reviews_if_disabled(all_file_results: List[FileAnalysisResult], use_live_ai: bool) -> None:
        if use_live_ai:
            return
        for file_result in all_file_results:
            file_result["ai_reviews"] = []

    def _generate_combined_html(self, all_file_results: List[FileAnalysisResult], runtime: PipelineRuntime) -> None:
        logger.info("Generating combined HTML report for %d files...", len(all_file_results))
        html_report_started = self.app._perf_now()
        combined_report = self.app.build_combined_report(all_file_results)
        excel_support = bool(runtime.request_reporter.is_excel_support_available())
        report_meta = {
            "verification_level": "CORE+REPORT" if excel_support else "CORE_ONLY",
            "optional_dependencies": {
                "openpyxl": {"available": excel_support, "required_for": ["excel_report", "template_coverage"]}
            },
        }
        with self.app._reporter_semaphore:
            runtime.request_reporter.generate_html_report(combined_report, "combined_analysis_report.html", report_meta=report_meta)
        self.app._metrics_add_timing(runtime.metrics, "report", self.app._elapsed_ms(html_report_started))
        logger.info("Analysis Completed. Results saved in: %s", runtime.request_reporter.output_dir)

    def _build_payload(
        self,
        all_file_results: List[FileAnalysisResult],
        analysis_errors: List[AnalysisError],
        runtime: PipelineRuntime,
    ) -> PayloadDict:
        payload = self.app.summarize_results(all_file_results)
        self._inject_ctrlpp_preflight_warning(payload, runtime.ctrlpp_preflight)
        payload["summary"]["requested_file_count"] = len(runtime.analysis_targets)
        payload["summary"]["successful_file_count"] = len(all_file_results)
        payload["summary"]["failed_file_count"] = len(analysis_errors)
        payload["summary"]["ctrlpp_preflight_attempted"] = bool(runtime.ctrlpp_preflight.get("attempted", False))
        payload["summary"]["ctrlpp_preflight_ready"] = bool(runtime.ctrlpp_preflight.get("ready", False))
        payload["summary"]["ctrlpp_preflight_message"] = str(runtime.ctrlpp_preflight.get("message", "") or "")

        excel_support = bool(runtime.request_reporter.is_excel_support_available())
        payload["summary"]["verification_level"] = "CORE+REPORT" if excel_support else "CORE_ONLY"
        llm_calls = self.app._safe_int(runtime.metrics.get("llm_calls", 0), 0)
        ctrlpp_calls = self.app._safe_int(runtime.metrics.get("ctrlpp_calls", 0), 0)
        ai_provider = str(runtime.ai_provider or "").lower()
        runtime.metrics["optional_dependencies"] = {
            "openpyxl": {
                "available": excel_support,
                "enabled_by_request": True,
                "used_in_run": bool(excel_support),
                "required_for": ["excel_report", "template_coverage"],
            },
            "ollama": {
                "available": ai_provider == "ollama",
                "enabled_by_request": bool(runtime.use_live_ai),
                "used_in_run": bool(llm_calls > 0),
                "provider": ai_provider or "unknown",
                "required_for": ["p3_live_ai"],
            },
            "ctrlppcheck": {
                "available": bool(runtime.ctrlpp_preflight.get("ready", False)),
                "enabled_by_request": bool(runtime.requested_ctrlpp),
                "used_in_run": bool(ctrlpp_calls > 0),
                "preflight_attempted": bool(runtime.ctrlpp_preflight.get("attempted", False)),
                "required_for": ["p2_ctrlpp"],
            },
        }

        excel_files, reviewed_txt = self._scan_report_artifacts(runtime.request_reporter.output_dir)
        payload["report_paths"] = {
            "html": "combined_analysis_report.html",
            "excel": sorted(excel_files),
            "reviewed_txt": sorted(reviewed_txt),
        }
        payload["output_dir"] = runtime.request_reporter.output_dir
        payload["errors"] = analysis_errors
        self.app._last_output_dir = runtime.request_reporter.output_dir
        return payload

    @staticmethod
    def _inject_ctrlpp_preflight_warning(payload: PayloadDict, preflight: CtrlppPreflightPayload) -> None:
        if bool(preflight.get("ready", False)):
            return
        message = str(preflight.get("message", "") or "").strip()
        if not message:
            return
        p2_list = payload.setdefault("violations", {}).setdefault("P2", [])
        if any(str(item.get("message", "") or "").strip() == message for item in p2_list if isinstance(item, dict)):
            return
        p2_list.append(
            {
                "type": "warning",
                "severity": "warning",
                "rule_id": "ctrlppcheck.info",
                "line": 0,
                "message": f"CtrlppCheck preflight install failed: {message}",
                "verbose": "",
                "file": "",
                "source": "CtrlppCheck",
                "priority_origin": "P2",
            }
        )
        summary = payload.get("summary", {})
        if isinstance(summary, dict):
            summary["p2_total"] = len(p2_list)

    @staticmethod
    def _scan_report_artifacts(output_dir: str) -> Tuple[List[str], List[str]]:
        excel_files: List[str] = []
        reviewed_txt: List[str] = []
        if os.path.isdir(output_dir):
            excel_files = [name for name in os.listdir(output_dir) if name.lower().endswith(".xlsx")]
            reviewed_txt = [name for name in os.listdir(output_dir) if name.endswith("_REVIEWED.txt")]
        return excel_files, reviewed_txt

    def _store_session_snapshot(self, payload: PayloadDict, runtime: PipelineRuntime) -> None:
        session = self.app._ensure_review_session(runtime.request_reporter.output_dir)
        with session["lock"]:
            payload["report_jobs"] = self.app._summarize_excel_jobs(session)
            session["summary"] = self._json_clone(payload.get("summary", {}))
            session["report_paths"] = dict(payload.get("report_paths", {}))
            session["report_jobs_public"] = self._json_clone(payload.get("report_jobs", {}))
            session["metrics"] = self._json_clone(runtime.metrics)
            self.app._touch_review_session(session)

    def _empty_payload(self, total_started: float, metrics: MetricsDict) -> PayloadDict:
        payload = {
            "summary": {
                "total": 0,
                "critical": 0,
                "warning": 0,
                "info": 0,
                "score": 100,
                "requested_file_count": 0,
                "successful_file_count": 0,
                "failed_file_count": 0,
                "p1_total": 0,
                "p2_total": 0,
                "p3_total": 0,
                "verification_level": "CORE_ONLY",
            },
            "violations": {"P1": [], "P2": [], "P3": []},
            "report_paths": {"html": "", "excel": [], "reviewed_txt": []},
            "output_dir": "",
            "errors": [],
        }
        metrics["timings_ms"]["total"] = self.app._elapsed_ms(total_started)
        metrics["optional_dependencies"] = {
            "openpyxl": {
                "available": False,
                "enabled_by_request": True,
                "used_in_run": False,
                "required_for": ["excel_report", "template_coverage"],
            },
            "ollama": {
                "available": False,
                "enabled_by_request": False,
                "used_in_run": False,
                "provider": "unknown",
                "required_for": ["p3_live_ai"],
            },
            "ctrlppcheck": {
                "available": False,
                "enabled_by_request": False,
                "used_in_run": False,
                "preflight_attempted": False,
                "required_for": ["p2_ctrlpp"],
            },
        }
        payload["metrics"] = metrics
        return payload

    @staticmethod
    def _json_clone(value: Any) -> Any:
        return json.loads(json.dumps(value, ensure_ascii=False))
