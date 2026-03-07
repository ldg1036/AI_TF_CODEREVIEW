#!/usr/bin/env python
"""
HTTP performance baseline runner for WinCC OA Code Review server.

This script drives /api/analyze (and optional /api/report/excel flush) across a
matrix of feature toggles and stores the resulting metrics JSON to
docs/perf_baselines/.

It uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


DEFAULT_SERVER = "http://127.0.0.1:8765"


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _timestamp_compact() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _bool_values_csv(raw: str) -> List[bool]:
    out: List[bool] = []
    for part in (raw or "").split(","):
        token = part.strip().lower()
        if not token:
            continue
        if token in ("1", "true", "t", "yes", "y", "on"):
            out.append(True)
        elif token in ("0", "false", "f", "no", "n", "off"):
            out.append(False)
        else:
            raise ValueError(f"Invalid boolean token: {part!r}")
    # dedupe while preserving order
    deduped: List[bool] = []
    for item in out:
        if item not in deduped:
            deduped.append(item)
    return deduped or [False]


def _json_request(
    base_url: str,
    method: str,
    path: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout_sec: int = 300,
) -> Tuple[int, Dict[str, Any], int]:
    url = base_url.rstrip("/") + path
    data: Optional[bytes] = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url=url, data=data, headers=headers, method=method.upper())
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            body = resp.read()
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            parsed = json.loads(body.decode("utf-8")) if body else {}
            return int(getattr(resp, "status", 200)), parsed if isinstance(parsed, dict) else {}, elapsed_ms
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        try:
            parsed = json.loads(body.decode("utf-8")) if body else {}
            if not isinstance(parsed, dict):
                parsed = {"error": str(parsed)}
        except Exception:
            parsed = {"error": body.decode("utf-8", errors="ignore") or str(exc)}
        return int(exc.code), parsed, elapsed_ms


def _discover_files(base_url: str, limit: int, allow_raw_txt: bool, timeout_sec: int) -> List[str]:
    qs = urllib.parse.urlencode({"allow_raw_txt": "true" if allow_raw_txt else "false"})
    status, payload, _ = _json_request(base_url, "GET", f"/api/files?{qs}", timeout_sec=timeout_sec)
    if status != 200:
        raise RuntimeError(f"/api/files failed ({status}): {payload.get('error', payload)}")
    items = payload.get("files", [])
    if not isinstance(items, list):
        raise RuntimeError("Invalid /api/files response: files is not a list")
    selected: List[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        if name.lower().endswith(".ctl"):
            selected.append(name)
        if len(selected) >= limit:
            break
    if not selected:
        raise RuntimeError("No .ctl files discovered from /api/files")
    return selected


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _extract_scenario_result(
    combo: Dict[str, Any],
    analyze_status: int,
    analyze_payload: Dict[str, Any],
    analyze_http_ms: int,
    flush_status: Optional[int],
    flush_payload: Optional[Dict[str, Any]],
    flush_http_ms: int,
) -> Dict[str, Any]:
    metrics = analyze_payload.get("metrics", {}) if isinstance(analyze_payload, dict) else {}
    if not isinstance(metrics, dict):
        metrics = {}
    timings = metrics.get("timings_ms", {}) if isinstance(metrics.get("timings_ms"), dict) else {}
    report_jobs = analyze_payload.get("report_jobs", {}) if isinstance(analyze_payload, dict) else {}
    excel_jobs = report_jobs.get("excel", {}) if isinstance(report_jobs, dict) else {}
    if not isinstance(excel_jobs, dict):
        excel_jobs = {}

    result = {
        "combo": dict(combo),
        "status": {
            "analyze_http": analyze_status,
            "flush_http": flush_status,
            "ok": analyze_status in (200, 207) and (flush_status in (None, 200)),
        },
        "request": {
            "output_dir": analyze_payload.get("output_dir", ""),
            "request_id": analyze_payload.get("request_id", ""),
        },
        "wall_ms": {
            "analyze_http": analyze_http_ms,
            "flush_http": flush_http_ms if flush_status is not None else 0,
            "end_to_end_http": analyze_http_ms + (flush_http_ms if flush_status is not None else 0),
        },
        "metrics": {
            "timings_ms": timings,
            "llm_calls": _safe_int(metrics.get("llm_calls", 0), 0),
            "ctrlpp_calls": _safe_int(metrics.get("ctrlpp_calls", 0), 0),
            "bytes_read": _safe_int(metrics.get("bytes_read", 0), 0),
            "bytes_written": _safe_int(metrics.get("bytes_written", 0), 0),
            "convert_cache": metrics.get("convert_cache", {}),
        },
        "summary": analyze_payload.get("summary", {}),
        "pending_excel_jobs": {
            "after_analyze": _safe_int(excel_jobs.get("pending_count", 0), 0),
            "running_after_analyze": _safe_int(excel_jobs.get("running_count", 0), 0),
            "after_flush": _safe_int(
                (((flush_payload or {}).get("excel") or {}).get("pending_count", 0)),
                0,
            ) if isinstance(flush_payload, dict) else 0,
        },
        "errors": {
            "analyze": analyze_payload.get("error", "") if isinstance(analyze_payload, dict) else "",
            "flush": (flush_payload or {}).get("error", "") if isinstance(flush_payload, dict) else "",
        },
    }
    return result


def _collect_numeric(series: Sequence[Dict[str, Any]], path: Sequence[str]) -> List[int]:
    out: List[int] = []
    for item in series:
        cur: Any = item
        for key in path:
            if not isinstance(cur, dict):
                cur = None
                break
            cur = cur.get(key)
        val = _safe_int(cur, -1)
        if val >= 0:
            out.append(val)
    return out


def _series_summary(values: Sequence[int]) -> Dict[str, Optional[int]]:
    if not values:
        return {"count": 0, "min": None, "max": None, "avg": None, "p95": None}
    data = list(values)
    data_sorted = sorted(data)
    idx = max(0, min(len(data_sorted) - 1, int(round((len(data_sorted) - 1) * 0.95))))
    return {
        "count": len(data_sorted),
        "min": int(data_sorted[0]),
        "max": int(data_sorted[-1]),
        "avg": int(round(statistics.mean(data_sorted))),
        "p95": int(data_sorted[idx]),
    }


def _aggregate_by_combo(runs: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    labels: Dict[str, Dict[str, Any]] = {}
    for run in runs:
        combo = run.get("combo", {}) if isinstance(run, dict) else {}
        key = json.dumps(combo, sort_keys=True, ensure_ascii=False)
        buckets.setdefault(key, []).append(run)
        labels[key] = combo if isinstance(combo, dict) else {}

    summaries: List[Dict[str, Any]] = []
    for key, group in buckets.items():
        summaries.append(
            {
                "combo": labels.get(key, {}),
                "run_count": len(group),
                "ok_runs": sum(1 for x in group if bool(((x.get("status") or {}).get("ok")))),
                "analyze_http_ms": _series_summary(_collect_numeric(group, ("wall_ms", "analyze_http"))),
                "end_to_end_http_ms": _series_summary(_collect_numeric(group, ("wall_ms", "end_to_end_http"))),
                "server_total_ms": _series_summary(_collect_numeric(group, ("metrics", "timings_ms", "server_total"))),
                "analyze_stage_ms": _series_summary(_collect_numeric(group, ("metrics", "timings_ms", "analyze"))),
                "report_stage_ms": _series_summary(_collect_numeric(group, ("metrics", "timings_ms", "report"))),
                "ai_stage_ms": _series_summary(_collect_numeric(group, ("metrics", "timings_ms", "ai"))),
                "ctrlpp_stage_ms": _series_summary(_collect_numeric(group, ("metrics", "timings_ms", "ctrlpp"))),
                "llm_calls": _series_summary(_collect_numeric(group, ("metrics", "llm_calls"))),
                "ctrlpp_calls": _series_summary(_collect_numeric(group, ("metrics", "ctrlpp_calls"))),
                "pending_excel_after_analyze": _series_summary(_collect_numeric(group, ("pending_excel_jobs", "after_analyze"))),
            }
        )
    summaries.sort(key=lambda item: json.dumps(item.get("combo", {}), sort_keys=True, ensure_ascii=False))
    return summaries


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run /api/analyze performance baseline matrix and save JSON",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--server-url", default=DEFAULT_SERVER, help="Base URL of running backend server")
    parser.add_argument("--dataset-name", default="local-sample", help="Label stored in output JSON")
    parser.add_argument("--selected-files", nargs="*", default=None, help="Explicit file names to analyze")
    parser.add_argument("--discover-count", type=int, default=1, help="Auto-discover first N .ctl files when --selected-files is omitted")
    parser.add_argument("--allow-raw-txt", action="store_true", help="Pass allow_raw_txt=true to /api/files discovery and /api/analyze")
    parser.add_argument("--iterations", type=int, default=1, help="Runs per combo")
    parser.add_argument("--live-ai", default="off", help="CSV bools (e.g. off,on)")
    parser.add_argument("--ctrlpp", default="off,on", help="CSV bools (e.g. off,on)")
    parser.add_argument("--defer-excel", default="off,on", help="CSV bools (e.g. off,on)")
    parser.add_argument("--flush-excel", action="store_true", help="Flush deferred Excel jobs after analyze")
    parser.add_argument("--flush-timeout-sec", type=int, default=300)
    parser.add_argument("--http-timeout-sec", type=int, default=300)
    parser.add_argument("--stop-on-error", action="store_true", help="Stop matrix when a request fails")
    parser.add_argument(
        "--output",
        default="",
        help="Output JSON path (default: docs/perf_baselines/http_perf_baseline_<dataset>_<ts>.json)",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        live_ai_values = _bool_values_csv(args.live_ai)
        ctrlpp_values = _bool_values_csv(args.ctrlpp)
        defer_excel_values = _bool_values_csv(args.defer_excel)
    except ValueError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2

    selected_files = [str(x) for x in (args.selected_files or []) if str(x).strip()]
    if not selected_files:
        try:
            selected_files = _discover_files(args.server_url, max(1, int(args.discover_count)), bool(args.allow_raw_txt), int(args.http_timeout_sec))
        except Exception as exc:
            print(f"[error] file discovery failed: {exc}", file=sys.stderr)
            return 2

    output_path = args.output.strip()
    if not output_path:
        safe_dataset = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(args.dataset_name or "dataset"))
        output_path = os.path.join("docs", "perf_baselines", f"http_perf_baseline_{safe_dataset}_{_timestamp_compact()}.json")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    print(f"[info] server_url={args.server_url}")
    print(f"[info] selected_files={selected_files}")
    print(f"[info] matrix live_ai={live_ai_values} ctrlpp={ctrlpp_values} defer_excel={defer_excel_values} iterations={args.iterations}")

    runs: List[Dict[str, Any]] = []
    matrix_started = time.perf_counter()
    combo_index = 0
    total_combos = len(live_ai_values) * len(ctrlpp_values) * len(defer_excel_values)
    stop_early = False

    for live_ai in live_ai_values:
        for ctrlpp in ctrlpp_values:
            for defer_excel in defer_excel_values:
                combo_index += 1
                combo = {
                    "live_ai": bool(live_ai),
                    "ctrlpp": bool(ctrlpp),
                    "defer_excel_reports": bool(defer_excel),
                }
                for iteration in range(1, max(1, int(args.iterations)) + 1):
                    print(
                        f"[run] combo {combo_index}/{total_combos} iter {iteration}/{args.iterations} "
                        f"live_ai={live_ai} ctrlpp={ctrlpp} defer_excel={defer_excel}"
                    )
                    analyze_body = {
                        "selected_files": list(selected_files),
                        "allow_raw_txt": bool(args.allow_raw_txt),
                        "enable_live_ai": bool(live_ai),
                        "enable_ctrlppcheck": bool(ctrlpp),
                        "defer_excel_reports": bool(defer_excel),
                    }
                    analyze_status, analyze_payload, analyze_http_ms = _json_request(
                        args.server_url,
                        "POST",
                        "/api/analyze",
                        payload=analyze_body,
                        timeout_sec=int(args.http_timeout_sec),
                    )

                    flush_status = None
                    flush_payload: Optional[Dict[str, Any]] = None
                    flush_http_ms = 0
                    if args.flush_excel and analyze_status in (200, 207):
                        output_dir = str((analyze_payload or {}).get("output_dir", "")).strip()
                        if output_dir:
                            flush_status, flush_payload, flush_http_ms = _json_request(
                                args.server_url,
                                "POST",
                                "/api/report/excel",
                                payload={"session_id": output_dir, "wait": True, "timeout_sec": int(args.flush_timeout_sec)},
                                timeout_sec=max(int(args.http_timeout_sec), int(args.flush_timeout_sec) + 30),
                            )

                    run_entry = _extract_scenario_result(
                        combo={**combo, "iteration": iteration},
                        analyze_status=analyze_status,
                        analyze_payload=analyze_payload,
                        analyze_http_ms=analyze_http_ms,
                        flush_status=flush_status,
                        flush_payload=flush_payload,
                        flush_http_ms=flush_http_ms,
                    )
                    runs.append(run_entry)

                    ok = bool(((run_entry.get("status") or {}).get("ok")))
                    if not ok and args.stop_on_error:
                        stop_early = True
                        break
                if stop_early:
                    break
            if stop_early:
                break
        if stop_early:
            break

    # Collapse "iteration" out of combo summaries.
    runs_for_summary: List[Dict[str, Any]] = []
    for run in runs:
        combo = dict((run.get("combo") or {})) if isinstance(run.get("combo"), dict) else {}
        combo.pop("iteration", None)
        copied = dict(run)
        copied["combo"] = combo
        runs_for_summary.append(copied)

    report: Dict[str, Any] = {
        "generated_at": _now_iso(),
        "server_url": args.server_url,
        "dataset_name": args.dataset_name,
        "selected_files": selected_files,
        "matrix": {
            "live_ai": live_ai_values,
            "ctrlpp": ctrlpp_values,
            "defer_excel_reports": defer_excel_values,
            "iterations": int(args.iterations),
            "flush_excel": bool(args.flush_excel),
        },
        "elapsed_ms": int((time.perf_counter() - matrix_started) * 1000),
        "runs": runs,
        "combo_summaries": _aggregate_by_combo(runs_for_summary),
        "notes": [
            "Values come from /api/analyze metrics + HTTP wall-clock timings.",
            "Use this file as a baseline for local/CI regression comparisons.",
        ],
    }

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    print(f"[done] wrote {output_path}")
    print(f"[done] total runs={len(runs)} elapsed_ms={report['elapsed_ms']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
