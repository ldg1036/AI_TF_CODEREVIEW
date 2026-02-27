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
PERTURB_NONE = "none"
PERTURB_WHITESPACE = "whitespace"
PERTURB_LINE_DRIFT = "line_drift"
OBSERVE_STRICT_HASH = "strict_hash"
OBSERVE_BENCHMARK_RELAXED = "benchmark_relaxed"


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


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _increment(counter: Dict[str, int], key: str) -> None:
    normalized = _safe_str(key) or "<empty>"
    counter[normalized] = _safe_int(counter.get(normalized, 0), 0) + 1


def _decode_text_payload(raw: bytes) -> Tuple[str, str]:
    for enc in ("utf-8", "cp949", "euc-kr"):
        try:
            return raw.decode(enc), enc
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8"


def _extract_anchor_line(prepare_payload: Dict[str, Any]) -> int:
    if not isinstance(prepare_payload, dict):
        return 0
    anchor_line = _safe_int(prepare_payload.get("anchor_line", 0), 0)
    if anchor_line > 0:
        return anchor_line
    hunks = prepare_payload.get("hunks", [])
    if isinstance(hunks, list):
        for h in hunks:
            if isinstance(h, dict):
                start_line = _safe_int(h.get("start_line", 0), 0)
                if start_line > 0:
                    return start_line
    return 0


def _apply_anchor_perturbation(
    source_bytes: bytes,
    mode: str,
    anchor_line: int,
) -> Tuple[bytes, Dict[str, Any]]:
    info: Dict[str, Any] = {
        "mode": mode,
        "changed": False,
        "reason": "",
        "anchor_line": max(0, int(anchor_line)),
    }
    if mode == PERTURB_NONE:
        info["reason"] = "no_perturbation"
        return source_bytes, info

    text, encoding = _decode_text_payload(source_bytes)
    lines = text.splitlines(keepends=True)
    if not lines:
        info["reason"] = "empty_source"
        return source_bytes, info

    if mode == PERTURB_WHITESPACE:
        mutated_lines: List[str] = []
        changed = 0
        for line in lines:
            if line.strip():
                if line.endswith("\r\n"):
                    mutated_lines.append(line[:-2] + "  \r\n")
                elif line.endswith("\n"):
                    mutated_lines.append(line[:-1] + "  \n")
                else:
                    mutated_lines.append(line + "  ")
                changed += 1
            else:
                mutated_lines.append(line)
        mutated_text = "".join(mutated_lines)
        info.update(
            {
                "changed": bool(changed > 0),
                "reason": "whitespace_tails_added" if changed > 0 else "no_non_empty_lines",
                "mutated_lines": changed,
                "encoding": encoding,
            }
        )
        return mutated_text.encode(encoding, errors="replace"), info

    if mode == PERTURB_LINE_DRIFT:
        idx = max(1, int(anchor_line)) - 1
        if idx < 0 or idx >= len(lines):
            idx = 0
        line_at_anchor = lines[idx]
        newline_token = "\r\n" if line_at_anchor.endswith("\r\n") else "\n"
        lines.insert(idx, newline_token)
        mutated_text = "".join(lines)
        info.update(
            {
                "changed": True,
                "reason": "blank_line_inserted_before_anchor",
                "inserted_index_1based": idx + 1,
                "encoding": encoding,
            }
        )
        return mutated_text.encode(encoding, errors="replace"), info

    info["reason"] = "unknown_mode"
    return source_bytes, info


def _json_request(
    base_url: str,
    method: str,
    path: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout_sec: int = 120,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Tuple[int, Dict[str, Any], int]:
    url = base_url.rstrip("/") + path
    data: Optional[bytes] = None
    headers = {"Accept": "application/json"}
    if isinstance(extra_headers, dict):
        for k, v in extra_headers.items():
            if str(k).strip() and v is not None:
                headers[str(k)] = str(v)
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


def _extract_targets(payload: Dict[str, Any]) -> List[Tuple[str, str, str]]:
    targets: List[Tuple[str, str, str]] = []
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
                targets.append((obj, event, issue_id))
    return targets


def run_once(
    base_url: str,
    selected_files: List[str],
    timeout_sec: int,
    perturb_mode: str,
    kpi_observe_mode: str,
    tune_min_confidence: Optional[float] = None,
    tune_min_gap: Optional[float] = None,
    tune_max_line_drift: Optional[int] = None,
) -> Dict[str, Any]:
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
    targets = _extract_targets(analyze_payload)
    if not targets:
        raise RuntimeError("No P1 violation found for autofix baseline; choose files with at least one P1 finding")

    prepare_status = 0
    prepare_payload: Dict[str, Any] = {}
    prepare_ms = 0
    apply_status = 0
    apply_payload: Dict[str, Any] = {}
    apply_ms = 0
    stats_status = 0
    stats_payload: Dict[str, Any] = {}
    stats_ms = 0
    perturbation_meta: Dict[str, Any] = {"mode": perturb_mode, "changed": False, "reason": "not_attempted"}
    target_meta: Dict[str, Any] = {"candidate_count": len(targets), "chosen_index_1based": 0}

    semantic_blocked_count = 0
    for idx, (target_obj, target_event, issue_id) in enumerate(targets, start=1):
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
            continue

        try:
            if source_file_path and source_backup is not None:
                anchor_line = _extract_anchor_line(prepare_payload)
                mutated, perturbation_meta = _apply_anchor_perturbation(source_backup, perturb_mode, anchor_line)
                if mutated != source_backup:
                    with open(source_file_path, "wb") as f:
                        f.write(mutated)

            expected_base_hash = prepare_payload.get("base_hash", "")
            if kpi_observe_mode == OBSERVE_BENCHMARK_RELAXED:
                expected_base_hash = ""

            apply_status, apply_payload, apply_ms = _json_request(
                base_url,
                "POST",
                "/api/autofix/apply",
                {
                    "proposal_id": prepare_payload.get("proposal_id", ""),
                    "session_id": output_dir,
                    "file": selected_files[0],
                    "expected_base_hash": expected_base_hash,
                    "apply_mode": "source_ctl",
                    "block_on_regression": False,
                    "check_ctrlpp_regression": False,
                },
                timeout_sec=timeout_sec,
                extra_headers=(
                    {
                        **{"X-Autofix-Benchmark-Observe-Mode": str(kpi_observe_mode)},
                        **(
                            {"X-Autofix-Benchmark-Tuning-Min-Confidence": str(tune_min_confidence)}
                            if tune_min_confidence is not None
                            else {}
                        ),
                        **(
                            {"X-Autofix-Benchmark-Tuning-Min-Gap": str(tune_min_gap)}
                            if tune_min_gap is not None
                            else {}
                        ),
                        **(
                            {"X-Autofix-Benchmark-Tuning-Max-Line-Drift": str(tune_max_line_drift)}
                            if tune_max_line_drift is not None
                            else {}
                        ),
                    }
                    if str(kpi_observe_mode) == OBSERVE_BENCHMARK_RELAXED
                    else None
                ),
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

        error_code = _safe_str((apply_payload or {}).get("error_code", ""))
        if error_code == "SEMANTIC_GUARD_BLOCKED" and idx < len(targets):
            semantic_blocked_count += 1
            continue

        target_meta.update(
            {
                "chosen_index_1based": idx,
                "object": target_obj,
                "event": target_event,
                "issue_id": issue_id,
                "semantic_blocked_candidates_skipped": semantic_blocked_count,
            }
        )
        break

    if target_meta.get("chosen_index_1based", 0) == 0:
        raise RuntimeError(
            f"No applicable target resolved (semantic blocked candidates={semantic_blocked_count}, total={len(targets)})"
        )

    return {
        "analyze": {"status": analyze_status, "wall_ms": analyze_ms, "output_dir": output_dir},
        "prepare": {"status": prepare_status, "wall_ms": prepare_ms, "proposal_id": prepare_payload.get("proposal_id", "")},
        "apply": {
            "status": apply_status,
            "wall_ms": apply_ms,
            "ok": bool((apply_payload or {}).get("ok", False)),
            "error_code": str((apply_payload or {}).get("error_code", "") or ""),
            "validation": (apply_payload or {}).get("validation", {}),
            "quality_metrics": (apply_payload or {}).get("quality_metrics", {}),
        },
        "stats": {"status": stats_status, "wall_ms": stats_ms, "payload": stats_payload},
        "perturbation": perturbation_meta,
        "target": target_meta,
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
    error_code_counts: Dict[str, int] = {}
    locator_mode_counts: Dict[str, int] = {}
    semantic_block_reason_counts: Dict[str, int] = {}
    apply_engine_reason_counts: Dict[str, int] = {}
    validation_error_fragment_counts: Dict[str, int] = {
        "ambiguous_candidates": 0,
        "low_confidence": 0,
        "drift_exceeded": 0,
        "engine_fallback": 0,
    }
    stats_consistency_mismatch_count = 0

    for run in runs:
        apply_payload = run.get("apply", {}) if isinstance(run, dict) else {}
        stats_payload = ((run.get("stats", {}) or {}).get("payload", {})) if isinstance(run, dict) else {}
        if not isinstance(apply_payload, dict):
            apply_payload = {}
        if not isinstance(stats_payload, dict):
            stats_payload = {}

        if bool(apply_payload.get("ok", False)):
            apply_success_count += 1
        error_code = _safe_str(apply_payload.get("error_code", ""))
        if error_code:
            _increment(error_code_counts, error_code)
        if error_code == "ANCHOR_MISMATCH":
            anchor_mismatch_failure_count += 1

        anchor_mismatch_count += _safe_int(stats_payload.get("anchor_mismatch_count", 0), 0)
        token_fallback_attempt_count += _safe_int(stats_payload.get("token_fallback_attempt_count", 0), 0)
        token_fallback_success_count += _safe_int(stats_payload.get("token_fallback_success_count", 0), 0)
        token_fallback_ambiguous_count += _safe_int(stats_payload.get("token_fallback_ambiguous_count", 0), 0)
        apply_engine_structure_success_count += _safe_int(stats_payload.get("apply_engine_structure_success_count", 0), 0)
        apply_engine_text_fallback_count += _safe_int(stats_payload.get("apply_engine_text_fallback_count", 0), 0)

        validation = apply_payload.get("validation", {}) if isinstance(apply_payload, dict) else {}
        quality_metrics = apply_payload.get("quality_metrics", {}) if isinstance(apply_payload, dict) else {}
        if isinstance(validation, dict):
            locator_mode = _safe_str(validation.get("locator_mode", ""))
            if not locator_mode and isinstance(quality_metrics, dict):
                locator_mode = _safe_str(quality_metrics.get("locator_mode", ""))
            if locator_mode:
                _increment(locator_mode_counts, locator_mode)
            semantic_reason = _safe_str(validation.get("semantic_blocked_reason", ""))
            if not semantic_reason and isinstance(quality_metrics, dict):
                semantic_reason = _safe_str(quality_metrics.get("semantic_blocked_reason", ""))
            if semantic_reason:
                _increment(semantic_block_reason_counts, semantic_reason)
            engine_reason = _safe_str(validation.get("apply_engine_fallback_reason", ""))
            if not engine_reason and isinstance(quality_metrics, dict):
                engine_reason = _safe_str(quality_metrics.get("apply_engine_fallback_reason", ""))
            if engine_reason:
                _increment(apply_engine_reason_counts, engine_reason)

            for err in (validation.get("validation_errors", []) or []):
                message = _safe_str(err).lower()
                if not message:
                    continue
                if "ambiguous_candidates" in message:
                    validation_error_fragment_counts["ambiguous_candidates"] += 1
                if "low_confidence" in message:
                    validation_error_fragment_counts["low_confidence"] += 1
                if "drift_exceeded" in message:
                    validation_error_fragment_counts["drift_exceeded"] += 1
                if "apply engine failed" in message:
                    validation_error_fragment_counts["engine_fallback"] += 1

            attempted = bool(validation.get("token_fallback_attempted", False))
            locator_token = locator_mode == "token_fallback"
            if locator_token and not attempted:
                stats_consistency_mismatch_count += 1

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
        kpi_anchor_failure_rate = (min(anchor_mismatch_count, apply_attempts) / apply_attempts) if apply_attempts else 0.0
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
        "error_code_counts": error_code_counts,
        "locator_mode_counts": locator_mode_counts,
        "semantic_block_reason_counts": semantic_block_reason_counts,
        "apply_engine_fallback_reason_counts": apply_engine_reason_counts,
        "validation_error_fragment_counts": validation_error_fragment_counts,
        "stats_consistency_mismatch_count": stats_consistency_mismatch_count,
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


def _write_json(path: str, payload: Dict[str, Any]) -> str:
    out_abs = os.path.abspath(path)
    os.makedirs(os.path.dirname(out_abs), exist_ok=True)
    with open(out_abs, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return out_abs


def _scenario_to_perturb(scenario: str) -> str:
    return PERTURB_LINE_DRIFT if str(scenario or "") == "drift" else PERTURB_NONE


def _build_review_markdown(
    *,
    general_comparison: Optional[Dict[str, Any]],
    drift_comparison: Optional[Dict[str, Any]],
    general_baseline_summary: Optional[Dict[str, Any]],
    general_improved_summary: Optional[Dict[str, Any]],
    drift_baseline_summary: Optional[Dict[str, Any]],
    drift_improved_summary: Optional[Dict[str, Any]],
) -> str:
    lines: List[str] = []
    lines.append("# Autofix KPI Review")
    lines.append("")
    lines.append(f"- generated_at: {_dt.datetime.now().isoformat(timespec='seconds')}")
    lines.append("- scope: general(strict_hash), drift(benchmark_relaxed)")
    lines.append("")
    if general_comparison:
        lines.append("## General (strict_hash)")
        lines.append(f"- baseline_failure_rate: {general_comparison.get('baseline_failure_rate', 0)}")
        lines.append(f"- improved_failure_rate: {general_comparison.get('improved_failure_rate', 0)}")
        lines.append(f"- improvement_percent: {general_comparison.get('improvement_percent', 0)}")
        if isinstance(general_improved_summary, dict):
            lines.append(f"- error_code_counts: {json.dumps(general_improved_summary.get('error_code_counts', {}), ensure_ascii=False)}")
        lines.append("")
    if drift_comparison:
        improve = _safe_float(drift_comparison.get("improvement_percent", 0.0), 0.0)
        observe_ok = False
        if isinstance(drift_improved_summary, dict):
            locator_counts = drift_improved_summary.get("locator_mode_counts", {})
            base_hash_counts = drift_improved_summary.get("error_code_counts", {})
            has_locator = isinstance(locator_counts, dict) and len(locator_counts) > 0
            base_hash_only = (
                isinstance(base_hash_counts, dict)
                and len(base_hash_counts) == 1
                and _safe_int(base_hash_counts.get("BASE_HASH_MISMATCH", 0), 0)
                == _safe_int(drift_improved_summary.get("apply_attempts", 0), 0)
            )
            observe_ok = bool(has_locator and not base_hash_only)
        lines.append("## Drift (benchmark_relaxed)")
        lines.append(f"- baseline_failure_rate: {drift_comparison.get('baseline_failure_rate', 0)}")
        lines.append(f"- improved_failure_rate: {drift_comparison.get('improved_failure_rate', 0)}")
        lines.append(f"- improvement_percent: {improve}")
        lines.append(f"- kpi_observability_pass: {observe_ok}")
        lines.append(f"- kpi_10_percent_pass: {bool(improve >= 10.0)}")
        if isinstance(drift_improved_summary, dict):
            lines.append(f"- locator_mode_counts: {json.dumps(drift_improved_summary.get('locator_mode_counts', {}), ensure_ascii=False)}")
            lines.append(
                f"- validation_error_fragment_counts: {json.dumps(drift_improved_summary.get('validation_error_fragment_counts', {}), ensure_ascii=False)}"
            )
            lines.append(f"- error_code_counts: {json.dumps(drift_improved_summary.get('error_code_counts', {}), ensure_ascii=False)}")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect autofix apply baseline/improved stats via HTTP API")
    parser.add_argument("--server-url", default=DEFAULT_SERVER, help="Base URL of running backend server")
    parser.add_argument("--mode", choices=[MODE_BASELINE, MODE_IMPROVED], default=MODE_IMPROVED)
    parser.add_argument("--selected-files", nargs="*", default=None, help="Explicit .ctl file names")
    parser.add_argument("--discover-count", type=int, default=1, help="Auto-discover first N .ctl files when selected files omitted")
    parser.add_argument("--iterations", type=int, default=1, help="Run count")
    parser.add_argument("--timeout-sec", type=int, default=120)
    parser.add_argument(
        "--perturb-anchor-mode",
        choices=[PERTURB_NONE, PERTURB_WHITESPACE, PERTURB_LINE_DRIFT],
        default=PERTURB_NONE,
        help="Inject deterministic source perturbation between prepare/apply to stress anchor fallback",
    )
    parser.add_argument(
        "--kpi-observe-mode",
        choices=[OBSERVE_STRICT_HASH, OBSERVE_BENCHMARK_RELAXED],
        default=OBSERVE_STRICT_HASH,
        help="strict_hash keeps runtime hash gate, benchmark_relaxed bypasses expected_base_hash only for KPI observation",
    )
    parser.add_argument("--tune-min-confidence", type=float, default=None, help="Benchmark-only token locator min confidence override")
    parser.add_argument("--tune-min-gap", type=float, default=None, help="Benchmark-only token locator min confidence gap override")
    parser.add_argument("--tune-max-line-drift", type=int, default=None, help="Benchmark-only token locator max line drift override")
    parser.add_argument(
        "--scenario",
        choices=["general", "drift", "both"],
        default="both",
        help="Scenario selector for auto matrix mode",
    )
    parser.add_argument("--auto-run-matrix", action="store_true", help="Run general/drift x baseline/improved matrix")
    parser.add_argument("--review-output", default="", help="Optional markdown review output path")
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
            "perturb_anchor_mode": str(args.perturb_anchor_mode),
            "kpi_observe_mode": str(args.kpi_observe_mode),
            "tune_min_confidence": args.tune_min_confidence,
            "tune_min_gap": args.tune_min_gap,
            "tune_max_line_drift": args.tune_max_line_drift,
            "scenario": str(args.scenario),
            "auto_run_matrix": bool(args.auto_run_matrix),
            "output": out_abs,
            "compare_with": str(args.compare_with or ""),
            "output_compare": str(args.output_compare or ""),
            "review_output": str(args.review_output or ""),
            "note": "dry-run: no HTTP requests executed",
        }
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    def _run_payload(mode: str, perturb_mode: str, observe_mode: str, output_path: str) -> Dict[str, Any]:
        runs: List[Dict[str, Any]] = []
        for _ in range(max(1, int(args.iterations))):
            runs.append(
                run_once(
                    args.server_url,
                    selected_files,
                    int(args.timeout_sec),
                    perturb_mode,
                    observe_mode,
                    tune_min_confidence=args.tune_min_confidence,
                    tune_min_gap=args.tune_min_gap,
                    tune_max_line_drift=args.tune_max_line_drift,
                )
            )
        payload = {
            "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
            "server_url": str(args.server_url),
            "mode": str(mode),
            "perturb_anchor_mode": str(perturb_mode),
            "kpi_observe_mode": str(observe_mode),
            "selected_files": selected_files,
            "iterations": len(runs),
            "runs": runs,
            "summary": _build_summary(runs, str(mode)),
        }
        payload["_meta"] = {
            "kpi_observe_mode": str(observe_mode),
            "benchmark_mode_warning": bool(str(observe_mode) == OBSERVE_BENCHMARK_RELAXED),
            "not_for_production": bool(str(observe_mode) == OBSERVE_BENCHMARK_RELAXED),
            "tune_min_confidence": args.tune_min_confidence,
            "tune_min_gap": args.tune_min_gap,
            "tune_max_line_drift": args.tune_max_line_drift,
        }
        written = _write_json(output_path, payload)
        payload["_meta_output_path"] = written
        _write_json(written, payload)
        print(f"[ok] metrics written: {written}")
        return payload

    if bool(args.auto_run_matrix):
        ts = _timestamp_compact()
        output_root = out_abs if os.path.isdir(out_abs) else os.path.dirname(out_abs)
        if not output_root:
            output_root = os.path.join("docs", "perf_baselines")
        os.makedirs(output_root, exist_ok=True)

        run_general = str(args.scenario) in ("general", "both")
        run_drift = str(args.scenario) in ("drift", "both")
        general_baseline = general_improved = drift_baseline = drift_improved = None
        general_comparison = drift_comparison = None

        if run_general:
            general_baseline_path = os.path.join(output_root, f"autofix_apply_baseline_{ts}_general.json")
            general_improved_path = os.path.join(output_root, f"autofix_apply_improved_{ts}_general.json")
            general_baseline = _run_payload(MODE_BASELINE, _scenario_to_perturb("general"), OBSERVE_STRICT_HASH, general_baseline_path)
            general_improved = _run_payload(MODE_IMPROVED, _scenario_to_perturb("general"), OBSERVE_STRICT_HASH, general_improved_path)
            general_comparison = _build_comparison_payload(general_baseline, general_improved)
            comparison_path = os.path.join(output_root, f"autofix_apply_comparison_{ts}_general.json")
            _write_json(comparison_path, general_comparison)
            print(f"[ok] comparison written: {os.path.abspath(comparison_path)}")

        if run_drift:
            drift_baseline_path = os.path.join(output_root, f"autofix_apply_baseline_{ts}_drift.json")
            drift_improved_path = os.path.join(output_root, f"autofix_apply_improved_{ts}_drift.json")
            drift_baseline = _run_payload(MODE_BASELINE, _scenario_to_perturb("drift"), OBSERVE_BENCHMARK_RELAXED, drift_baseline_path)
            drift_improved = _run_payload(MODE_IMPROVED, _scenario_to_perturb("drift"), OBSERVE_BENCHMARK_RELAXED, drift_improved_path)
            drift_comparison = _build_comparison_payload(drift_baseline, drift_improved)
            comparison_path = os.path.join(output_root, f"autofix_apply_comparison_{ts}_drift.json")
            _write_json(comparison_path, drift_comparison)
            print(f"[ok] comparison written: {os.path.abspath(comparison_path)}")

        review_output = str(args.review_output or "").strip()
        if not review_output:
            review_output = os.path.join(output_root, f"autofix_review_{ts}.md")
        review_md = _build_review_markdown(
            general_comparison=general_comparison,
            drift_comparison=drift_comparison,
            general_baseline_summary=(general_baseline or {}).get("summary", {}) if isinstance(general_baseline, dict) else {},
            general_improved_summary=(general_improved or {}).get("summary", {}) if isinstance(general_improved, dict) else {},
            drift_baseline_summary=(drift_baseline or {}).get("summary", {}) if isinstance(drift_baseline, dict) else {},
            drift_improved_summary=(drift_improved or {}).get("summary", {}) if isinstance(drift_improved, dict) else {},
        )
        review_abs = os.path.abspath(review_output)
        os.makedirs(os.path.dirname(review_abs), exist_ok=True)
        with open(review_abs, "w", encoding="utf-8") as f:
            f.write(review_md)
        print(f"[ok] review written: {review_abs}")
        return 0

    payload = _run_payload(
        str(args.mode),
        str(args.perturb_anchor_mode),
        str(args.kpi_observe_mode),
        out_abs,
    )

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
        _write_json(out_abs, payload)
        output_compare = str(args.output_compare or "").strip()
        if not output_compare:
            output_compare = os.path.join("docs", "perf_baselines", f"autofix_apply_comparison_{_timestamp_compact()}.json")
        compare_out_abs = _write_json(output_compare, comparison)
        print(f"[ok] comparison written: {compare_out_abs}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n[!] interrupted", file=sys.stderr)
        raise SystemExit(130)
