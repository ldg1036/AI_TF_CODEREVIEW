"""AnalyzeJobMixin – Async analysis job lifecycle management extracted from server.py."""

import logging
import os
import time
import threading
import uuid
from typing import Any, Dict, Optional, cast

from main import DEFAULT_MODE

logger = logging.getLogger(__name__)


class AnalyzeJobMixin:
    """Manages asynchronous analysis job creation, execution, progress tracking, and cleanup."""

    _analyze_jobs: Dict[str, Any] = {}
    _analyze_jobs_lock = threading.RLock()
    _analyze_job_ttl_sec = 1800
    _analyze_job_max_entries = 64
    _analyze_poll_interval_ms = 500

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
    def _compute_eta_ms(cls, progress: Dict[str, Any], started_at_ms: Optional[int]) -> Optional[int]:
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
    def _refresh_job_timing_locked(cls, job: Dict[str, Any]) -> None:
        started_at = job.get("started_at")
        timing = job.setdefault("timing", {})
        if started_at:
            timing["elapsed_ms"] = max(0, cls._epoch_ms() - int(started_at))
        else:
            timing["elapsed_ms"] = 0
        timing["eta_ms"] = cls._compute_eta_ms(job.get("progress", {}), started_at)

    @classmethod
    def _public_analyze_job_view(cls, job: Dict[str, Any]) -> Dict[str, Any]:
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
                    progress = current.setdefault("progress", {})
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
                    progress = job.setdefault("progress", {})
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
        from http import HTTPStatus
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
            self._analyze_jobs[job_id] = {
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
            }
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

    def _handle_analyze_status(self) -> None:
        from http import HTTPStatus
        from urllib.parse import urlparse, parse_qs
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
