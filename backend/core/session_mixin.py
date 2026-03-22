"""ReviewSessionMixin – session / cache / deferred-Excel logic extracted from main.py."""

import collections
import concurrent.futures
import json
import os
import threading
import uuid
from typing import Any, Dict, List, Optional, Tuple

from core.input_normalization import InputNormalizer
from core.reporter import Reporter


class ReviewSessionMixin:
    """Mixin that provides review-session lifecycle, file-cache, and deferred Excel report helpers.

    Host class must supply (via __init__):
        _review_session_cache          : OrderedDict
        _review_session_cache_lock     : threading.Lock
        review_session_ttl_sec         : int
        review_session_max_entries     : int
        reporter                       : Reporter
        _excel_report_semaphore        : threading.Semaphore
        _excel_report_executor         : concurrent.futures.ThreadPoolExecutor
        _last_output_dir               : str
    And static helpers:
        _now_ts, _iso_now, _safe_int, _touch_review_session,
        _perf_now, _elapsed_ms, _metrics_add_timing, _metrics_inc,
        _metrics_apply_excel_report_meta (delegated here)
    """

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def _new_review_session(self, output_dir: str) -> Dict:
        return {
            "output_dir": os.path.normpath(str(output_dir or "")),
            "created_at": self._now_ts(),
            "last_accessed_at": self._now_ts(),
            "files": {},
            "file_aliases": {},
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
            key = os.path.normpath(str(filename or ""))
            lock = session["file_locks"].get(key)
            if lock is None:
                lock = threading.Lock()
                session["file_locks"][key] = lock
            return lock

    def _store_review_cache_file(self, session_key: str, filename: str, payload: Dict):
        session = self._ensure_review_session(session_key)
        if not isinstance(payload, dict):
            return
        cache_key = os.path.normpath(str(filename or ""))
        aliases = set()
        aliases.add(os.path.basename(cache_key))
        descriptor = payload.get("file_descriptor", {}) if isinstance(payload.get("file_descriptor", {}), dict) else {}
        display_name = str(payload.get("display_name", "") or "")
        if display_name:
            aliases.add(display_name)
        for alias in (
            descriptor.get("requested_name", ""),
            descriptor.get("canonical_name", ""),
            descriptor.get("canonical_file_id", ""),
            descriptor.get("source_name", ""),
            descriptor.get("reviewed_name", ""),
            payload.get("file", ""),
            payload.get("reviewed_name", ""),
        ):
            alias_text = os.path.basename(str(alias or "").strip())
            if alias_text:
                aliases.add(alias_text)
        for alias in InputNormalizer.candidate_names_for(filename):
            alias_text = os.path.basename(str(alias or "").strip())
            if alias_text:
                aliases.add(alias_text)
        with session["lock"]:
            session["files"][cache_key] = payload
            file_aliases = session.setdefault("file_aliases", {})
            if isinstance(file_aliases, dict):
                for alias in aliases:
                    alias_key = str(alias or "").strip()
                    if not alias_key:
                        continue
                    bucket = file_aliases.setdefault(alias_key, [])
                    if isinstance(bucket, list) and cache_key not in bucket:
                        bucket.append(cache_key)
            self._touch_review_session(session)

    # ------------------------------------------------------------------
    # Session + file resolution
    # ------------------------------------------------------------------

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

        raw_name = str(file_name or "").strip()
        normalized_name = os.path.normpath(raw_name) if raw_name else ""
        basename = os.path.basename(raw_name)
        tried = []
        if normalized_name:
            tried.append(normalized_name)
        tried.extend(candidate for candidate in InputNormalizer.candidate_names_for(basename) if candidate not in tried)
        cached = None
        resolved_cache_key = ""
        with session["lock"]:
            for candidate in tried:
                maybe = session.get("files", {}).get(candidate)
                if maybe:
                    resolved_cache_key = candidate
                    cached = maybe
                    break
                aliases = session.get("file_aliases", {})
                if isinstance(aliases, dict):
                    alias_matches = aliases.get(candidate, [])
                    if isinstance(alias_matches, list) and alias_matches:
                        resolved_cache_key = str(alias_matches[0] or "")
                        cached = session.get("files", {}).get(resolved_cache_key)
                        if cached:
                            break
        if not cached:
            if tried:
                raise FileNotFoundError(f"No cached analysis for file: {basename} (tried: {tried})")
            raise FileNotFoundError(f"No cached analysis for file: {basename}")
        self._touch_review_session(session)
        return os.path.normpath(target_output_dir), session, resolved_cache_key, cached

    # ------------------------------------------------------------------
    # Deferred Excel reports
    # ------------------------------------------------------------------

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

    @staticmethod
    def _default_excel_report_meta(reporter: Reporter) -> Dict[str, Any]:
        excel_available = bool(reporter.is_excel_support_available())
        return {
            "verification_level": "CORE+REPORT" if excel_available else "CORE_ONLY",
            "optional_dependencies": {
                "openpyxl": {
                    "available": excel_available,
                    "required_for": ["excel_report", "template_coverage"],
                }
            },
        }

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
            excel_meta = reporter.fill_excel_checklist(
                report_data,
                file_type=file_type,
                output_filename=output_filename,
                report_meta=self._default_excel_report_meta(reporter),
            ) or {}
        output_path = os.path.join(output_dir, output_filename)
        return {
            "output_path": output_path,
            "generated": os.path.isfile(output_path),
            "metrics": excel_meta if isinstance(excel_meta, dict) else {},
        }

    def _write_review_outputs(
        self,
        *,
        reporter: Reporter,
        code_content: str,
        file_report: Dict,
        reviewed_name: str,
        artifact_stem: str,
        file_type: str,
        defer_excel_reports: Optional[bool],
        metrics: Optional[Dict],
    ) -> Dict[str, Any]:
        output_dir = reporter.output_dir
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

        report_text_started = self._perf_now()
        with self._reporter_semaphore:
            reporter.generate_annotated_txt(code_content, file_report, reviewed_name)
        report_text_ms = self._elapsed_ms(report_text_started)
        self._metrics_add_timing(metrics, "report_text", report_text_ms)

        excel_name = f"CodeReview_Submission_{artifact_stem}_{reporter.timestamp}.xlsx"
        use_deferred_excel = (
            self.defer_excel_reports_default
            if defer_excel_reports is None
            else bool(defer_excel_reports)
        )
        deferred_excel_job_id = ""
        sync_excel_meta: Dict[str, Any] = {}
        if use_deferred_excel:
            deferred_excel_job_id = self._schedule_deferred_excel_report(
                output_dir=reporter.output_dir,
                reporter_timestamp=reporter.timestamp,
                source_file=str(file_report.get("file", "") or ""),
                report_data=file_report,
                file_type=file_type,
                output_filename=excel_name,
            )
        else:
            with self._excel_report_semaphore:
                sync_excel_meta = reporter.fill_excel_checklist(
                    file_report,
                    file_type=file_type,
                    output_filename=excel_name,
                    report_meta=self._default_excel_report_meta(reporter),
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

        excel_timings = sync_excel_meta.get("timings_ms", {}) if isinstance(sync_excel_meta, dict) else {}
        excel_total_ms = self._safe_int(excel_timings.get("total", 0), 0) if isinstance(excel_timings, dict) else 0
        return {
            "output_dir": output_dir,
            "report_ms": report_ms,
            "report_text_ms": report_text_ms,
            "excel_name": excel_name,
            "deferred_excel": bool(use_deferred_excel),
            "excel_job_id": deferred_excel_job_id,
            "excel_metrics": sync_excel_meta if isinstance(sync_excel_meta, dict) else {},
            "excel_total_ms": excel_total_ms,
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
