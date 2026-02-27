#!/usr/bin/env python
"""
Collect autofix apply baseline/improved metrics from a running server.

Mode policy:
- improved: use actual apply outcomes from API
- baseline: counterfactual estimate where anchor mismatch would fail without
  token fallback / apply-engine improvements
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_SERVER = "http://127.0.0.1:8765"
MODE_BASELINE = "baseline"
MODE_IMPROVED = "improved"


def _timestamp_compact() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _json_request(
    base_url: str,
    method: str,
    path: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout_sec: int = 120,
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


def _discover_ctl_files(base_url: str, limit: int, timeout_sec: int) -> List[str]:
    status, payload, _ = _json_request(base_url, "GET", "/api/files", timeout_sec=timeout_sec)
    if status != 200:
        raise RuntimeError(f"/api/files failed ({status}): {payload.get('error', payload)}")
    items = payload.get("files", [])
    if not isinstance(items, list):
        raise RuntimeError("Invalid /api/files payload")
    selected: List[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if name.lower().endswith(".ctl"):
            selected.append(name)
        if len(selected) >= max(1, limit):
            break
    if not selected:
        raise RuntimeError("No .ctl files discovered from /api/files")
    return selected


def _extract_first_target(payload: Dict[str, Any]) -> Tuple[str, str, str]:
    p1_groups = ((payload.get("violations", {}) or {}).get("P1", []) or [])
    for group in p1_groups:
        if not isinstance(group, dict):
            continue
        obj = str(group.get("object", "") or "")
        event = str(group.get("event", "Global") or "Global")
        violations = group.get("violations", []) or []
        for v in violations:
            if not isinstance(v, dict):
                continue
            issue_id = str(v.get("issue_id", "") or "")
            if issue_id:
                return obj, event, issue_id
    raise RuntimeError("No P1 violation found for autofix baseline; choose files with at least one P1 finding")


def run_once(base_url: str, selected_files: List[str], timeout_sec: int) -> Dict[str, Any]:
    source_file_path = ""
    source_backup: Optional[bytes] = None
    if selected_files:
        candidate = os.path.abspath(os.path.join("CodeReview_Data", selected_files[0]))
        if os.path.isfile(candidate):
            source_file_path = candidate
            with open(source_file_path, "rb") as f:
                source_backup = f.read()

    analyze_status, analyze_payload, analyze_ms = _json_request(
        base_url,
        "POST",
        "/api/analyze",
        {
            "mode": "Static",
            "selected_files": selected_files,
            "enable_live_ai": False,
            "enable_ctrlppcheck": False,
        },
        timeout_sec=timeout_sec,
    )
    if analyze_status not in (200, 207):
        raise RuntimeError(f"/api/analyze failed ({analyze_status}): {analyze_payload.get('error', analyze_payload)}")

    output_dir = str(analyze_payload.get("output_dir", "") or "")
    target_obj, target_event, issue_id = _extract_first_target(analyze_payload)
    prepare_status, prepare_payload, prepare_ms = _json_request(
        base_url,
        "POST",
        "/api/autofix/prepare",
        {
            "file": selected_files[0],
            "object": target_obj,
            "event": target_event,
            "issue_id": issue_id,
            "session_id": output_dir,
            "generator_preference": "rule",
            "prepare_mode": "single",
        },
        timeout_sec=timeout_sec,
    )
    if prepare_status != 200:
        raise RuntimeError(f"/api/autofix/prepare failed ({prepare_status}): {prepare_payload.get('error', prepare_payload)}")

    try:
        apply_status, apply_payload, apply_ms = _json_request(
            base_url,
            "POST",
            "/api/autofix/apply",
            {
                "proposal_id": prepare_payload.get("proposal_id", ""),
                "session_id": output_dir,
                "file": selected_files[0],
                "expected_base_hash": prepare_payload.get("base_hash", ""),
                "apply_mode": "source_ctl",
                "block_on_regression": False,
                "check_ctrlpp_regression": False,
            },
            timeout_sec=timeout_sec,
        )
        stats_status, stats_payload, stats_ms = _json_request(
            base_url,
            "GET",
            "/api/autofix/stats?" + urllib.parse.urlencode({"session_id": output_dir}),
            timeout_sec=timeout_sec,
        )
    finally:
        if source_file_path and source_backup is not None:
            with open(source_file_path, "wb") as f:
                f.write(source_backup)

    return {
        "analyze": {"status": analyze_status, "wall_ms": analyze_ms, "output_dir": output_dir},
        "prepare": {"status": prepare_status, "wall_ms": prepare_ms, "proposal_id": prepare_payload.get("proposal_id", "")},
        "apply": {
            "status": apply_status,
            "wall_ms": apply_ms,
            "ok": bool((apply_payload or {}).get("ok", False)),
            "error_code": str((apply_payload or {}).get("error_code", "") or ""),
            "validation": (apply_payload or {}).get("validation", {}),
        },
        "stats": {"status": stats_status, "wall_ms": stats_ms, "payload": stats_payload},
    }


def _build_summary(runs: List[Dict[str, Any]], mode: str) -> Dict[str, Any]:
    run_count = len(runs)
    if run_count <= 0:
        return {
            "mode": mode,
            "run_count": 0,
            "apply_attempts": 0,
            "apply_success_count": 0,
            "anchor_mismatch_failure_count": 0,
            "anchor_mismatch_count": 0,
            "token_fallback_attempt_count": 0,
            "token_fallback_success_count": 0,
            "token_fallback_ambiguous_count": 0,
            "apply_engine_structure_success_count": 0,
            "apply_engine_text_fallback_count": 0,
            "apply_success_rate": 0.0,
            "anchor_mismatch_failure_rate": 0.0,
            "token_fallback_success_rate": 0.0,
            "token_fallback_ambiguous_rate": 0.0,
            "kpi_anchor_failure_rate": 0.0,
        }

    apply_attempts = run_count
    apply_success_count = 0
    anchor_mismatch_failure_count = 0
    anchor_mismatch_count = 0
    token_fallback_attempt_count = 0
    token_fallback_success_count = 0
    token_fallback_ambiguous_count = 0
    apply_engine_structure_success_count = 0
    apply_engine_text_fallback_count = 0

    for run in runs:
        apply_payload = run.get("apply", {}) if isinstance(run, dict) else {}
        stats_payload = ((run.get("stats", {}) or {}).get("payload", {})) if isinstance(run, dict) else {}
        if not isinstance(apply_payload, dict):
            apply_payload = {}
        if not isinstance(stats_payload, dict):
            stats_payload = {}

        if bool(apply_payload.get("ok", False)):
            apply_success_count += 1
        if str(apply_payload.get("error_code", "") or "") == "ANCHOR_MISMATCH":
            anchor_mismatch_failure_count += 1

        anchor_mismatch_count += _safe_int(stats_payload.get("anchor_mismatch_count", 0), 0)
        token_fallback_attempt_count += _safe_int(stats_payload.get("token_fallback_attempt_count", 0), 0)
        token_fallback_success_count += _safe_int(stats_payload.get("token_fallback_success_count", 0), 0)
        token_fallback_ambiguous_count += _safe_int(stats_payload.get("token_fallback_ambiguous_count", 0), 0)
        apply_engine_structure_success_count += _safe_int(stats_payload.get("apply_engine_structure_success_count", 0), 0)
        apply_engine_text_fallback_count += _safe_int(stats_payload.get("apply_engine_text_fallback_count", 0), 0)

    apply_success_rate = (apply_success_count / apply_attempts) if apply_attempts else 0.0
    actual_anchor_failure_rate = (anchor_mismatch_failure_count / apply_attempts) if apply_attempts else 0.0
    token_fallback_success_rate = (
        token_fallback_success_count / token_fallback_attempt_count if token_fallback_attempt_count else 0.0
    )
    token_fallback_ambiguous_rate = (
        token_fallback_ambiguous_count / token_fallback_attempt_count if token_fallback_attempt_count else 0.0
    )

    # Baseline mode is a counterfactual estimate:
    # every anchor mismatch would have become a final failure without fallback.
    if mode == MODE_BASELINE:
        kpi_anchor_failure_rate = (anchor_mismatch_count / apply_attempts) if apply_attempts else 0.0
    else:
        kpi_anchor_failure_rate = actual_anchor_failure_rate

    return {
        "mode": mode,
        "run_count": run_count,
        "apply_attempts": apply_attempts,
        "apply_success_count": apply_success_count,
        "anchor_mismatch_failure_count": anchor_mismatch_failure_count,
        "anchor_mismatch_count": anchor_mismatch_count,
        "token_fallback_attempt_count": token_fallback_attempt_count,
        "token_fallback_success_count": token_fallback_success_count,
        "token_fallback_ambiguous_count": token_fallback_ambiguous_count,
        "apply_engine_structure_success_count": apply_engine_structure_success_count,
        "apply_engine_text_fallback_count": apply_engine_text_fallback_count,
        "apply_success_rate": round(apply_success_rate, 6),
        "anchor_mismatch_failure_rate": round(actual_anchor_failure_rate, 6),
        "token_fallback_success_rate": round(token_fallback_success_rate, 6),
        "token_fallback_ambiguous_rate": round(token_fallback_ambiguous_rate, 6),
        "kpi_anchor_failure_rate": round(kpi_anchor_failure_rate, 6),
    }


def _build_comparison_payload(
    baseline_payload: Dict[str, Any],
    improved_payload: Dict[str, Any],
) -> Dict[str, Any]:
    baseline_summary = baseline_payload.get("summary", {}) if isinstance(baseline_payload, dict) else {}
    improved_summary = improved_payload.get("summary", {}) if isinstance(improved_payload, dict) else {}
    baseline_rate = _safe_float(baseline_summary.get("kpi_anchor_failure_rate", 0.0), 0.0)
    improved_rate = _safe_float(improved_summary.get("kpi_anchor_failure_rate", 0.0), 0.0)
    if baseline_rate > 0:
        improvement_percent = ((baseline_rate - improved_rate) / baseline_rate) * 100.0
    else:
        improvement_percent = 0.0

    return {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "baseline_file": str(baseline_payload.get("_meta_output_path", "") or ""),
        "improved_file": str(improved_payload.get("_meta_output_path", "") or ""),
        "baseline_failure_rate": round(baseline_rate, 6),
        "improved_failure_rate": round(improved_rate, 6),
        "improvement_percent": round(improvement_percent, 3),
        "kpi_target_percent": 10.0,
        "kpi_passed": bool(improvement_percent >= 10.0),
    }


def _default_output_path(mode: str) -> str:
    ts = _timestamp_compact()
    if mode == MODE_IMPROVED:
        name = f"autofix_apply_improved_{ts}.json"
    else:
        name = f"autofix_apply_baseline_{ts}.json"
    return os.path.join("docs", "perf_baselines", name)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect autofix apply baseline/improved stats via HTTP API")
    parser.add_argument("--server-url", default=DEFAULT_SERVER, help="Base URL of running backend server")
    parser.add_argument("--mode", choices=[MODE_BASELINE, MODE_IMPROVED], default=MODE_IMPROVED)
    parser.add_argument("--selected-files", nargs="*", default=None, help="Explicit .ctl file names")
    parser.add_argument("--discover-count", type=int, default=1, help="Auto-discover first N .ctl files when selected files omitted")
    parser.add_argument("--iterations", type=int, default=1, help="Run count")
    parser.add_argument("--timeout-sec", type=int, default=120)
    parser.add_argument("--dry-run", action="store_true", help="Print resolved execution plan without calling server APIs")
    parser.add_argument(
        "--output",
        default="",
        help="Output JSON path (default: docs/perf_baselines/autofix_apply_<mode>_<timestamp>.json)",
    )
    parser.add_argument(
        "--compare-with",
        default="",
        help="Path to counterpart JSON (baseline or improved) to produce comparison section/file",
    )
    parser.add_argument(
        "--output-compare",
        default="",
        help="Comparison JSON output path (default: docs/perf_baselines/autofix_apply_comparison_<timestamp>.json)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_files = list(args.selected_files or [])
    if not selected_files and bool(args.dry_run):
        selected_files = ["<auto-discover .ctl files>"]
    elif not selected_files:
        selected_files = _discover_ctl_files(args.server_url, int(args.discover_count), int(args.timeout_sec))

    out_path = str(args.output or "").strip() or _default_output_path(str(args.mode))
    out_abs = os.path.abspath(out_path)

    if bool(args.dry_run):
        plan = {
            "mode": str(args.mode),
            "server_url": str(args.server_url),
            "selected_files": selected_files,
            "iterations": max(1, int(args.iterations)),
            "timeout_sec": int(args.timeout_sec),
            "output": out_abs,
            "compare_with": str(args.compare_with or ""),
            "output_compare": str(args.output_compare or ""),
            "note": "dry-run: no HTTP requests executed",
        }
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    runs: List[Dict[str, Any]] = []
    for _ in range(max(1, int(args.iterations))):
        runs.append(run_once(args.server_url, selected_files, int(args.timeout_sec)))

    payload = {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "server_url": str(args.server_url),
        "mode": str(args.mode),
        "selected_files": selected_files,
        "iterations": len(runs),
        "runs": runs,
        "summary": _build_summary(runs, str(args.mode)),
    }
    payload["_meta_output_path"] = out_abs

    os.makedirs(os.path.dirname(out_abs), exist_ok=True)
    with open(out_abs, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[ok] metrics written: {out_abs}")

    compare_with = str(args.compare_with or "").strip()
    if compare_with:
        compare_abs = os.path.abspath(compare_with)
        if not os.path.isfile(compare_abs):
            raise RuntimeError(f"compare file not found: {compare_abs}")
        with open(compare_abs, "r", encoding="utf-8") as f:
            counterpart = json.load(f)
        if not isinstance(counterpart, dict):
            raise RuntimeError("compare JSON payload is invalid (dict required)")

        baseline_payload: Dict[str, Any]
        improved_payload: Dict[str, Any]
        current_mode = str(payload.get("mode", "") or "")
        other_mode = str(counterpart.get("mode", "") or "")
        if current_mode == MODE_BASELINE and other_mode == MODE_IMPROVED:
            baseline_payload = payload
            improved_payload = counterpart
        elif current_mode == MODE_IMPROVED and other_mode == MODE_BASELINE:
            baseline_payload = counterpart
            improved_payload = payload
        else:
            raise RuntimeError("compare files must include one baseline and one improved payload")

        comparison = _build_comparison_payload(baseline_payload, improved_payload)
        payload["comparison"] = dict(comparison)
        with open(out_abs, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        output_compare = str(args.output_compare or "").strip()
        if not output_compare:
            output_compare = os.path.join("docs", "perf_baselines", f"autofix_apply_comparison_{_timestamp_compact()}.json")
        compare_out_abs = os.path.abspath(output_compare)
        os.makedirs(os.path.dirname(compare_out_abs), exist_ok=True)
        with open(compare_out_abs, "w", encoding="utf-8") as f:
            json.dump(comparison, f, ensure_ascii=False, indent=2)
        print(f"[ok] comparison written: {compare_out_abs}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n[!] interrupted", file=sys.stderr)
        raise SystemExit(130)
