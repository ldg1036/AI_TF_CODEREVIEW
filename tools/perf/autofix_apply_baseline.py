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
    apply_tuning_headers: bool = False,
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
                            if (apply_tuning_headers and tune_min_confidence is not None)
                            else {}
                        ),
                        **(
                            {"X-Autofix-Benchmark-Tuning-Min-Gap": str(tune_min_gap)}
                            if (apply_tuning_headers and tune_min_gap is not None)
                            else {}
                        ),
                        **(
                            {"X-Autofix-Benchmark-Tuning-Max-Line-Drift": str(tune_max_line_drift)}
                            if (apply_tuning_headers and tune_max_line_drift is not None)
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
        "kpi_observe_mode": str(kpi_observe_mode),
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
            "instruction_apply_rate": 0.0,
            "instruction_fallback_rate": 0.0,
            "instruction_validation_fail_rate": 0.0,
            "instruction_fail_stage_distribution": {},
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
    hash_gate_bypassed_count = 0
    benchmark_observe_mode_counts: Dict[str, int] = {}
    stats_consistency_mismatch_count = 0
    instruction_mode_counts: Dict[str, int] = {}
    instruction_fail_stage_distribution: Dict[str, int] = {}
    instruction_attempt_count = 0
    instruction_apply_success_count = 0
    instruction_fallback_count = 0
    instruction_validation_fail_count = 0

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
        if not isinstance(validation, dict):
            validation = {}
        if not isinstance(quality_metrics, dict):
            quality_metrics = {}
        if isinstance(validation, dict):
            locator_mode = _safe_str(validation.get("locator_mode", ""))
            if not locator_mode:
                locator_mode = _safe_str(quality_metrics.get("locator_mode", ""))
            if locator_mode:
                _increment(locator_mode_counts, locator_mode)
            observe_mode = _safe_str(validation.get("benchmark_observe_mode", ""))
            if not observe_mode:
                observe_mode = _safe_str(quality_metrics.get("benchmark_observe_mode", ""))
            if not observe_mode and isinstance(run, dict):
                observe_mode = _safe_str(run.get("kpi_observe_mode", ""))
            if observe_mode:
                _increment(benchmark_observe_mode_counts, observe_mode)
            hash_gate_bypassed = bool(validation.get("hash_gate_bypassed", False))
            if not hash_gate_bypassed:
                hash_gate_bypassed = bool(quality_metrics.get("hash_gate_bypassed", False))
            # Some failure payloads omit explicit benchmark flags.
            # In relaxed mode, absence of BASE_HASH_MISMATCH implies hash gate was effectively bypassed.
            if (
                not hash_gate_bypassed
                and observe_mode == OBSERVE_BENCHMARK_RELAXED
                and error_code != "BASE_HASH_MISMATCH"
                and bool(error_code)
            ):
                hash_gate_bypassed = True
            if hash_gate_bypassed:
                hash_gate_bypassed_count += 1
            semantic_reason = _safe_str(validation.get("semantic_blocked_reason", ""))
            if not semantic_reason:
                semantic_reason = _safe_str(quality_metrics.get("semantic_blocked_reason", ""))
            if semantic_reason:
                _increment(semantic_block_reason_counts, semantic_reason)
            engine_reason = _safe_str(validation.get("apply_engine_fallback_reason", ""))
            if not engine_reason:
                engine_reason = _safe_str(quality_metrics.get("apply_engine_fallback_reason", ""))
            if engine_reason:
                _increment(apply_engine_reason_counts, engine_reason)

            validation_errors = validation.get("validation_errors", []) or []
            if (not validation_errors) and isinstance(quality_metrics, dict):
                validation_errors = quality_metrics.get("validation_errors", []) or []
            for err in validation_errors:
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

            instruction_mode = _safe_str(validation.get("instruction_mode", ""))
            if not instruction_mode:
                instruction_mode = _safe_str(quality_metrics.get("instruction_mode", "off"))
            if not instruction_mode:
                instruction_mode = "off"
            _increment(instruction_mode_counts, instruction_mode)

            instruction_path_reason = _safe_str(validation.get("instruction_path_reason", ""))
            if not instruction_path_reason:
                instruction_path_reason = _safe_str(quality_metrics.get("instruction_path_reason", "off"))
            if not instruction_path_reason:
                instruction_path_reason = "off"

            instruction_failure_stage = _safe_str(validation.get("instruction_failure_stage", ""))
            if not instruction_failure_stage:
                instruction_failure_stage = _safe_str(quality_metrics.get("instruction_failure_stage", "none"))
            if not instruction_failure_stage:
                instruction_failure_stage = "none"
            _increment(instruction_fail_stage_distribution, instruction_failure_stage)

            if instruction_mode != "off" or instruction_path_reason not in ("", "off"):
                instruction_attempt_count += 1
            if bool(validation.get("instruction_apply_success", False)) or bool(
                quality_metrics.get("instruction_apply_success", False)
            ):
                instruction_apply_success_count += 1
            if instruction_mode == "fallback_hunks" or instruction_path_reason == "fallback_hunks":
                instruction_fallback_count += 1
            if instruction_failure_stage == "validate" or instruction_path_reason == "validation_failed":
                instruction_validation_fail_count += 1

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

    instruction_apply_rate = (
        instruction_apply_success_count / instruction_attempt_count if instruction_attempt_count else 0.0
    )
    instruction_fallback_rate = (
        instruction_fallback_count / instruction_attempt_count if instruction_attempt_count else 0.0
    )
    instruction_validation_fail_rate = (
        instruction_validation_fail_count / instruction_attempt_count if instruction_attempt_count else 0.0
    )

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
        "hash_gate_bypassed_count": hash_gate_bypassed_count,
        "benchmark_observe_mode_counts": benchmark_observe_mode_counts,
        "stats_consistency_mismatch_count": stats_consistency_mismatch_count,
        "instruction_attempt_count": instruction_attempt_count,
        "instruction_apply_success_count": instruction_apply_success_count,
        "instruction_fallback_count": instruction_fallback_count,
        "instruction_validation_fail_count": instruction_validation_fail_count,
        "instruction_apply_rate": round(instruction_apply_rate, 6),
        "instruction_fallback_rate": round(instruction_fallback_rate, 6),
        "instruction_validation_fail_rate": round(instruction_validation_fail_rate, 6),
        "instruction_mode_counts": instruction_mode_counts,
        "instruction_fail_stage_distribution": instruction_fail_stage_distribution,
    }


def _evaluate_observability(summary: Dict[str, Any], min_sample: int = 3) -> Dict[str, Any]:
    apply_attempts = _safe_int(summary.get("apply_attempts", 0), 0)
    locator_mode_counts = summary.get("locator_mode_counts", {})
    error_code_counts = summary.get("error_code_counts", {})
    hash_gate_bypassed_count = _safe_int(summary.get("hash_gate_bypassed_count", 0), 0)
    validation_error_fragment_counts = summary.get("validation_error_fragment_counts", {})

    has_locator = isinstance(locator_mode_counts, dict) and len(locator_mode_counts) > 0
    base_hash_only = (
        isinstance(error_code_counts, dict)
        and len(error_code_counts) == 1
        and _safe_int(error_code_counts.get("BASE_HASH_MISMATCH", 0), 0) == apply_attempts
        and apply_attempts > 0
    )
    bypass_seen = hash_gate_bypassed_count >= 1

    observability_pass = bool(has_locator and not base_hash_only and bypass_seen)
    reason = "PASS"
    if not observability_pass:
        if apply_attempts < max(1, min_sample):
            reason = "HOLD_LOW_SAMPLE"
        elif (not bypass_seen) and base_hash_only:
            reason = "BLOCKED_ENV_GATE"
        elif has_locator and isinstance(validation_error_fragment_counts, dict):
            ambiguous = _safe_int(validation_error_fragment_counts.get("ambiguous_candidates", 0), 0)
            if ambiguous > 0:
                reason = "BLOCKED_AMBIGUOUS"
            else:
                reason = "HOLD_LOW_SAMPLE"
        else:
            reason = "HOLD_LOW_SAMPLE"

    return {
        "kpi_observability_pass": observability_pass,
        "kpi_observability_reason": reason,
        "has_locator_mode_counts": has_locator,
        "base_hash_mismatch_only": base_hash_only,
        "hash_gate_bypassed_seen": bypass_seen,
        "apply_attempts": apply_attempts,
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
    observability = _evaluate_observability(improved_summary if isinstance(improved_summary, dict) else {})
    improved_instruction_apply_rate = _safe_float(improved_summary.get("instruction_apply_rate", 0.0), 0.0)
    improved_instruction_validation_fail_rate = _safe_float(
        improved_summary.get("instruction_validation_fail_rate", 0.0), 0.0
    )
    improved_regression_blocked = 0
    if isinstance(improved_summary, dict):
        err_counts = improved_summary.get("error_code_counts", {})
        if isinstance(err_counts, dict):
            improved_regression_blocked = _safe_int(err_counts.get("REGRESSION_BLOCKED", 0), 0)
    rollout_criteria = {
        "instruction_apply_rate_min": 0.70,
        "instruction_validation_fail_rate_max": 0.20,
        "safety_gate_regression_max": 0,
    }
    rollout_checks = {
        "instruction_apply_rate_ok": bool(improved_instruction_apply_rate >= rollout_criteria["instruction_apply_rate_min"]),
        "instruction_validation_fail_rate_ok": bool(
            improved_instruction_validation_fail_rate <= rollout_criteria["instruction_validation_fail_rate_max"]
        ),
        "safety_gate_regression_ok": bool(improved_regression_blocked <= rollout_criteria["safety_gate_regression_max"]),
    }
    rollout_ready = bool(
        rollout_checks["instruction_apply_rate_ok"]
        and rollout_checks["instruction_validation_fail_rate_ok"]
        and rollout_checks["safety_gate_regression_ok"]
    )

    return {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "baseline_file": str(baseline_payload.get("_meta_output_path", "") or ""),
        "improved_file": str(improved_payload.get("_meta_output_path", "") or ""),
        "baseline_failure_rate": round(baseline_rate, 6),
        "improved_failure_rate": round(improved_rate, 6),
        "improvement_percent": round(improvement_percent, 3),
        "kpi_target_percent": 10.0,
        "kpi_passed": bool(improvement_percent >= 10.0),
        "kpi_observability_pass": bool(observability.get("kpi_observability_pass", False)),
        "kpi_observability_reason": str(observability.get("kpi_observability_reason", "HOLD_LOW_SAMPLE")),
        "instruction_apply_rate": round(improved_instruction_apply_rate, 6),
        "instruction_validation_fail_rate": round(improved_instruction_validation_fail_rate, 6),
        "instruction_fail_stage_distribution": (
            dict(improved_summary.get("instruction_fail_stage_distribution", {}))
            if isinstance(improved_summary.get("instruction_fail_stage_distribution", {}), dict)
            else {}
        ),
        "rollout_criteria": rollout_criteria,
        "rollout_checks": rollout_checks,
        "rollout_ready": rollout_ready,
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


def _parse_float_list(text: str) -> List[float]:
    raw = [part.strip() for part in str(text or "").split(",")]
    out: List[float] = []
    for item in raw:
        if not item:
            continue
        out.append(float(item))
    return out


def _parse_int_list(text: str) -> List[int]:
    raw = [part.strip() for part in str(text or "").split(",")]
    out: List[int] = []
    for item in raw:
        if not item:
            continue
        out.append(int(item))
    return out


def _read_json_file(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid json payload (dict required): {path}")
    return payload


def _derive_primary_block_reason(summary: Dict[str, Any]) -> str:
    if not isinstance(summary, dict):
        return "HOLD_LOW_SAMPLE"
    frag = summary.get("validation_error_fragment_counts", {})
    if isinstance(frag, dict):
        ambiguous = _safe_int(frag.get("ambiguous_candidates", 0), 0)
        low_conf = _safe_int(frag.get("low_confidence", 0), 0)
        drift_exceeded = _safe_int(frag.get("drift_exceeded", 0), 0)
        if max(ambiguous, low_conf, drift_exceeded) > 0:
            if ambiguous >= low_conf and ambiguous >= drift_exceeded:
                return "BLOCKED_AMBIGUOUS"
            if low_conf >= drift_exceeded:
                return "BLOCKED_LOW_CONFIDENCE"
            return "BLOCKED_DRIFT_EXCEEDED"
    err = summary.get("error_code_counts", {})
    if isinstance(err, dict):
        if _safe_int(err.get("ANCHOR_MISMATCH", 0), 0) > 0:
            return "BLOCKED_ANCHOR_MISMATCH_ONLY"
        if _safe_int(err.get("BASE_HASH_MISMATCH", 0), 0) > 0:
            return "BLOCKED_ENV_GATE"
        if _safe_int(err.get("APPLY_ENGINE_FAILED", 0), 0) > 0:
            return "BLOCKED_APPLY_ENGINE"
    return "HOLD_LOW_SAMPLE"


def _build_sweep_root_cause_payload(sweep_payload: Dict[str, Any]) -> Dict[str, Any]:
    rows = sweep_payload.get("rows", []) if isinstance(sweep_payload, dict) else []
    if not isinstance(rows, list):
        rows = []
    aggregate_reason_counts: Dict[str, int] = {}
    aggregate_fragment_counts = {
        "ambiguous_candidates": 0,
        "low_confidence": 0,
        "drift_exceeded": 0,
    }
    analyzed_rows: List[Dict[str, Any]] = []

    for row in rows:
        if not isinstance(row, dict):
            continue
        comparison = row.get("comparison", {})
        if not isinstance(comparison, dict):
            comparison = {}
        improved_file = _safe_str(comparison.get("improved_file", ""))
        improved_payload: Dict[str, Any] = {}
        improved_summary: Dict[str, Any] = {}
        if improved_file and os.path.isfile(improved_file):
            improved_payload = _read_json_file(improved_file)
            improved_summary = (improved_payload.get("summary", {}) or {})
            if not isinstance(improved_summary, dict):
                improved_summary = {}

        frag = improved_summary.get("validation_error_fragment_counts", {})
        if not isinstance(frag, dict):
            frag = {}
        if (
            _safe_int(frag.get("ambiguous_candidates", 0), 0) == 0
            and _safe_int(frag.get("low_confidence", 0), 0) == 0
            and _safe_int(frag.get("drift_exceeded", 0), 0) == 0
            and isinstance(improved_payload, dict)
        ):
            recomputed = {"ambiguous_candidates": 0, "low_confidence": 0, "drift_exceeded": 0}
            runs = improved_payload.get("runs", [])
            if isinstance(runs, list):
                for run in runs:
                    if not isinstance(run, dict):
                        continue
                    apply_payload = run.get("apply", {})
                    if not isinstance(apply_payload, dict):
                        continue
                    validation = apply_payload.get("validation", {})
                    quality_metrics = apply_payload.get("quality_metrics", {})
                    if not isinstance(validation, dict):
                        validation = {}
                    if not isinstance(quality_metrics, dict):
                        quality_metrics = {}
                    errors = validation.get("validation_errors", []) or quality_metrics.get("validation_errors", []) or []
                    for err in errors:
                        message = _safe_str(err).lower()
                        if "ambiguous_candidates" in message:
                            recomputed["ambiguous_candidates"] += 1
                        if "low_confidence" in message:
                            recomputed["low_confidence"] += 1
                        if "drift_exceeded" in message:
                            recomputed["drift_exceeded"] += 1
            frag = recomputed
        aggregate_fragment_counts["ambiguous_candidates"] += _safe_int(frag.get("ambiguous_candidates", 0), 0)
        aggregate_fragment_counts["low_confidence"] += _safe_int(frag.get("low_confidence", 0), 0)
        aggregate_fragment_counts["drift_exceeded"] += _safe_int(frag.get("drift_exceeded", 0), 0)

        observe_pass = bool(comparison.get("kpi_observability_pass", False))
        improve_pass = bool(comparison.get("kpi_passed", False))
        if improve_pass:
            reason = "PASS_10_PERCENT"
        elif observe_pass:
            ambiguous = _safe_int(frag.get("ambiguous_candidates", 0), 0)
            low_conf = _safe_int(frag.get("low_confidence", 0), 0)
            drift_exceeded = _safe_int(frag.get("drift_exceeded", 0), 0)
            if ambiguous > 0:
                reason = "BLOCKED_AMBIGUOUS"
            elif low_conf > 0:
                reason = "BLOCKED_LOW_CONFIDENCE"
            elif drift_exceeded > 0:
                reason = "BLOCKED_DRIFT_EXCEEDED"
            else:
                reason = _derive_primary_block_reason(improved_summary)
        else:
            reason = _safe_str(comparison.get("kpi_observability_reason", "")) or "HOLD_LOW_SAMPLE"
        _increment(aggregate_reason_counts, reason)

        analyzed_rows.append(
            {
                "tuning": row.get("tuning", {}),
                "improvement_percent": _safe_float(comparison.get("improvement_percent", 0.0), 0.0),
                "kpi_observability_pass": observe_pass,
                "kpi_10_percent_pass": improve_pass,
                "reason": reason,
                "fragment_counts": {
                    "ambiguous_candidates": _safe_int(frag.get("ambiguous_candidates", 0), 0),
                    "low_confidence": _safe_int(frag.get("low_confidence", 0), 0),
                    "drift_exceeded": _safe_int(frag.get("drift_exceeded", 0), 0),
                },
                "error_code_counts": improved_summary.get("error_code_counts", {}),
            }
        )

    return {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "mode": "drift_tuning_sweep_root_cause",
        "source_sweep_file": _safe_str(sweep_payload.get("_meta_source_file", "")),
        "row_count": len(analyzed_rows),
        "aggregate_reason_counts": aggregate_reason_counts,
        "aggregate_fragment_counts": aggregate_fragment_counts,
        "rows": analyzed_rows,
    }


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
        observe_result = _evaluate_observability(drift_improved_summary or {})
        observe_ok = bool(observe_result.get("kpi_observability_pass", False))
        lines.append("## Drift (benchmark_relaxed)")
        lines.append(f"- baseline_failure_rate: {drift_comparison.get('baseline_failure_rate', 0)}")
        lines.append(f"- improved_failure_rate: {drift_comparison.get('improved_failure_rate', 0)}")
        lines.append(f"- improvement_percent: {improve}")
        lines.append(f"- kpi_observability_pass: {observe_ok}")
        lines.append(f"- kpi_observability_reason: {observe_result.get('kpi_observability_reason', 'HOLD_LOW_SAMPLE')}")
        lines.append(f"- kpi_10_percent_pass: {bool(improve >= 10.0)}")
        lines.append(f"- instruction_apply_rate: {drift_comparison.get('instruction_apply_rate', 0)}")
        lines.append(f"- instruction_validation_fail_rate: {drift_comparison.get('instruction_validation_fail_rate', 0)}")
        lines.append(
            f"- instruction_fail_stage_distribution: {json.dumps(drift_comparison.get('instruction_fail_stage_distribution', {}), ensure_ascii=False)}"
        )
        lines.append(f"- rollout_ready: {bool(drift_comparison.get('rollout_ready', False))}")
        lines.append(
            f"- rollout_checks: {json.dumps(drift_comparison.get('rollout_checks', {}), ensure_ascii=False)}"
        )
        if isinstance(drift_improved_summary, dict):
            lines.append(
                f"- hash_gate_bypassed_count: {_safe_int(drift_improved_summary.get('hash_gate_bypassed_count', 0), 0)}"
            )
            lines.append(
                f"- benchmark_observe_mode_counts: {json.dumps(drift_improved_summary.get('benchmark_observe_mode_counts', {}), ensure_ascii=False)}"
            )
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
    parser.add_argument(
        "--auto-tune-drift",
        action="store_true",
        help="Run drift-only tuning sweep (baseline/improved) and emit best candidate summary",
    )
    parser.add_argument(
        "--sweep-min-confidence",
        default="0.55,0.65,0.8",
        help="Comma-separated min-confidence values for --auto-tune-drift",
    )
    parser.add_argument(
        "--sweep-min-gap",
        default="0.05,0.1,0.15",
        help="Comma-separated min-gap values for --auto-tune-drift",
    )
    parser.add_argument(
        "--sweep-max-line-drift",
        default="300,600,900",
        help="Comma-separated max-line-drift values for --auto-tune-drift",
    )
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
    parser.add_argument(
        "--analyze-sweep-json",
        default="",
        help="Analyze an existing drift sweep JSON and generate root-cause summary without re-running API calls",
    )
    parser.add_argument(
        "--analyze-sweep-output",
        default="",
        help="Root-cause output JSON path for --analyze-sweep-json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    analyze_sweep_json = _safe_str(getattr(args, "analyze_sweep_json", ""))
    if analyze_sweep_json:
        src_abs = os.path.abspath(analyze_sweep_json)
        if not os.path.isfile(src_abs):
            raise RuntimeError(f"sweep json not found: {src_abs}")
        sweep_payload = _read_json_file(src_abs)
        sweep_payload["_meta_source_file"] = src_abs
        result = _build_sweep_root_cause_payload(sweep_payload)
        ts = _timestamp_compact()
        out_path = _safe_str(getattr(args, "analyze_sweep_output", ""))
        if not out_path:
            out_path = os.path.join("docs", "perf_baselines", f"autofix_apply_root_cause_{ts}.json")
        out_abs = _write_json(out_path, result)
        print(f"[ok] root-cause written: {out_abs}")

        review_output = _safe_str(getattr(args, "review_output", ""))
        if not review_output:
            review_output = os.path.join("docs", "perf_baselines", f"autofix_root_cause_review_{ts}.md")
        review_lines: List[str] = []
        review_lines.append("# Autofix KPI Root Cause Review")
        review_lines.append("")
        review_lines.append(f"- source_sweep_file: `{src_abs}`")
        review_lines.append(f"- row_count: {result.get('row_count', 0)}")
        review_lines.append(f"- aggregate_reason_counts: `{json.dumps(result.get('aggregate_reason_counts', {}), ensure_ascii=False)}`")
        review_lines.append(
            f"- aggregate_fragment_counts: `{json.dumps(result.get('aggregate_fragment_counts', {}), ensure_ascii=False)}`"
        )
        review_lines.append("")
        review_lines.append("## Rows")
        for row in result.get("rows", []):
            if not isinstance(row, dict):
                continue
            tuning = row.get("tuning", {})
            review_lines.append(
                f"- c={tuning.get('min_confidence')} g={tuning.get('min_gap')} d={tuning.get('max_line_drift')}: "
                f"reason={row.get('reason')}, improve={row.get('improvement_percent')}%"
            )
        review_abs = os.path.abspath(review_output)
        os.makedirs(os.path.dirname(review_abs), exist_ok=True)
        with open(review_abs, "w", encoding="utf-8") as f:
            f.write("\n".join(review_lines) + "\n")
        print(f"[ok] root-cause review written: {review_abs}")
        return 0

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
        return _run_payload_with_tuning(
            mode,
            perturb_mode,
            observe_mode,
            output_path,
            tune_min_confidence=args.tune_min_confidence,
            tune_min_gap=args.tune_min_gap,
            tune_max_line_drift=args.tune_max_line_drift,
        )

    def _run_payload_with_tuning(
        mode: str,
        perturb_mode: str,
        observe_mode: str,
        output_path: str,
        *,
        tune_min_confidence: Optional[float],
        tune_min_gap: Optional[float],
        tune_max_line_drift: Optional[int],
    ) -> Dict[str, Any]:
        runs: List[Dict[str, Any]] = []
        for _ in range(max(1, int(args.iterations))):
            runs.append(
                run_once(
                    args.server_url,
                    selected_files,
                    int(args.timeout_sec),
                    perturb_mode,
                    observe_mode,
                    apply_tuning_headers=(str(mode) == MODE_IMPROVED),
                    tune_min_confidence=tune_min_confidence,
                    tune_min_gap=tune_min_gap,
                    tune_max_line_drift=tune_max_line_drift,
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
            "tune_min_confidence": tune_min_confidence,
            "tune_min_gap": tune_min_gap,
            "tune_max_line_drift": tune_max_line_drift,
        }
        written = _write_json(output_path, payload)
        payload["_meta_output_path"] = written
        _write_json(written, payload)
        print(f"[ok] metrics written: {written}")
        return payload

    if bool(args.auto_tune_drift):
        ts = _timestamp_compact()
        output_root = out_abs if os.path.isdir(out_abs) else os.path.dirname(out_abs)
        if not output_root:
            output_root = os.path.join("docs", "perf_baselines")
        os.makedirs(output_root, exist_ok=True)

        min_conf_values = _parse_float_list(args.sweep_min_confidence)
        min_gap_values = _parse_float_list(args.sweep_min_gap)
        max_drift_values = _parse_int_list(args.sweep_max_line_drift)
        if not min_conf_values or not min_gap_values or not max_drift_values:
            raise RuntimeError("auto-tune-drift sweep values must not be empty")

        sweep_rows: List[Dict[str, Any]] = []
        best_row: Optional[Dict[str, Any]] = None
        combo_index = 0

        for min_conf in min_conf_values:
            for min_gap in min_gap_values:
                for max_drift in max_drift_values:
                    combo_index += 1
                    suffix = f"drift_tune_{combo_index:02d}_c{str(min_conf).replace('.', '_')}_g{str(min_gap).replace('.', '_')}_d{max_drift}"
                    base_path = os.path.join(output_root, f"autofix_apply_baseline_{ts}_{suffix}.json")
                    imp_path = os.path.join(output_root, f"autofix_apply_improved_{ts}_{suffix}.json")
                    baseline_payload = _run_payload_with_tuning(
                        MODE_BASELINE,
                        _scenario_to_perturb("drift"),
                        OBSERVE_BENCHMARK_RELAXED,
                        base_path,
                        tune_min_confidence=min_conf,
                        tune_min_gap=min_gap,
                        tune_max_line_drift=max_drift,
                    )
                    improved_payload = _run_payload_with_tuning(
                        MODE_IMPROVED,
                        _scenario_to_perturb("drift"),
                        OBSERVE_BENCHMARK_RELAXED,
                        imp_path,
                        tune_min_confidence=min_conf,
                        tune_min_gap=min_gap,
                        tune_max_line_drift=max_drift,
                    )
                    comparison = _build_comparison_payload(baseline_payload, improved_payload)
                    comp_path = os.path.join(output_root, f"autofix_apply_comparison_{ts}_{suffix}.json")
                    _write_json(comp_path, comparison)
                    print(f"[ok] comparison written: {os.path.abspath(comp_path)}")

                    row = {
                        "tuning": {
                            "min_confidence": min_conf,
                            "min_gap": min_gap,
                            "max_line_drift": max_drift,
                        },
                        "comparison_file": os.path.abspath(comp_path),
                        "comparison": comparison,
                    }
                    sweep_rows.append(row)

                    if best_row is None:
                        best_row = row
                    else:
                        cur_obs = bool(row["comparison"].get("kpi_observability_pass", False))
                        best_obs = bool(best_row["comparison"].get("kpi_observability_pass", False))
                        cur_imp = _safe_float(row["comparison"].get("improvement_percent", 0.0), 0.0)
                        best_imp = _safe_float(best_row["comparison"].get("improvement_percent", 0.0), 0.0)
                        if (cur_obs and not best_obs) or (cur_obs == best_obs and cur_imp > best_imp):
                            best_row = row

        sweep_payload = {
            "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
            "server_url": str(args.server_url),
            "mode": "drift_tuning_sweep",
            "iterations": max(1, int(args.iterations)),
            "selected_files": selected_files,
            "sweep_values": {
                "min_confidence": min_conf_values,
                "min_gap": min_gap_values,
                "max_line_drift": max_drift_values,
            },
            "row_count": len(sweep_rows),
            "rows": sweep_rows,
            "best": best_row or {},
        }
        sweep_path = os.path.join(output_root, f"autofix_apply_sweep_{ts}_drift.json")
        sweep_abs = _write_json(sweep_path, sweep_payload)
        print(f"[ok] sweep written: {sweep_abs}")
        sweep_payload["_meta_source_file"] = sweep_abs
        root_cause_payload = _build_sweep_root_cause_payload(sweep_payload)
        root_cause_path = os.path.join(output_root, f"autofix_apply_root_cause_{ts}_drift.json")
        root_cause_abs = _write_json(root_cause_path, root_cause_payload)
        print(f"[ok] root-cause written: {root_cause_abs}")

        review_output = str(args.review_output or "").strip()
        if not review_output:
            review_output = os.path.join(output_root, f"autofix_review_{ts}.md")
        lines: List[str] = []
        lines.append("# Autofix KPI Drift Tuning Sweep")
        lines.append("")
        lines.append(f"- generated_at: {_dt.datetime.now().isoformat(timespec='seconds')}")
        lines.append(f"- row_count: {len(sweep_rows)}")
        if best_row:
            bcmp = best_row.get("comparison", {})
            bt = best_row.get("tuning", {})
            lines.append("- best_candidate:")
            lines.append(f"  - min_confidence: {bt.get('min_confidence')}")
            lines.append(f"  - min_gap: {bt.get('min_gap')}")
            lines.append(f"  - max_line_drift: {bt.get('max_line_drift')}")
            lines.append(f"  - kpi_observability_pass: {bcmp.get('kpi_observability_pass')}")
            lines.append(f"  - kpi_observability_reason: {bcmp.get('kpi_observability_reason')}")
            lines.append(f"  - improvement_percent: {bcmp.get('improvement_percent')}")
            lines.append(f"  - kpi_10_percent_pass: {bcmp.get('kpi_passed')}")
        lines.append("")
        lines.append("## Sweep Rows")
        for row in sweep_rows:
            t = row.get("tuning", {})
            c = row.get("comparison", {})
            lines.append(
                f"- c={t.get('min_confidence')} g={t.get('min_gap')} d={t.get('max_line_drift')}: "
                f"obs={c.get('kpi_observability_pass')}/{c.get('kpi_observability_reason')}, "
                f"improve={c.get('improvement_percent')}%"
            )
        lines.append("")
        lines.append("## Root Cause Aggregate")
        lines.append(
            f"- aggregate_reason_counts: {json.dumps(root_cause_payload.get('aggregate_reason_counts', {}), ensure_ascii=False)}"
        )
        lines.append(
            f"- aggregate_fragment_counts: {json.dumps(root_cause_payload.get('aggregate_fragment_counts', {}), ensure_ascii=False)}"
        )
        review_abs = os.path.abspath(review_output)
        os.makedirs(os.path.dirname(review_abs), exist_ok=True)
        with open(review_abs, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"[ok] review written: {review_abs}")
        return 0

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
