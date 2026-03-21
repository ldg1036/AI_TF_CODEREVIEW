"""Pure payload builders for health and historical comparison endpoints."""

from typing import Any, Dict, List, Optional


_ZERO_FILE_COUNTS: Dict[str, int] = {
    "p1_total": 0,
    "p2_total": 0,
    "p3_total": 0,
    "critical": 0,
    "warning": 0,
    "info": 0,
    "total": 0,
}

_ANALYSIS_SUMMARY_KEYS = (
    "total",
    "critical",
    "warning",
    "info",
    "p1_total",
    "p2_total",
    "p3_total",
    "requested_file_count",
    "successful_file_count",
    "failed_file_count",
)


def safe_float(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def build_rules_health_payload(
    p1_rule_defs: List[Dict[str, Any]],
    parsed_rules: List[Dict[str, Any]],
    dependencies: Dict[str, Any],
    *,
    p1_config_health: Optional[Dict[str, Any]] = None,
    generated_at_ms: int,
) -> Dict[str, Any]:
    detector_counts: Dict[str, int] = {"regex": 0, "composite": 0, "line_repeat": 0}
    enabled_count = 0
    for rule_def in p1_rule_defs:
        if not isinstance(rule_def, dict):
            continue
        if bool(rule_def.get("enabled", True)):
            enabled_count += 1
        detector = rule_def.get("detector", {}) if isinstance(rule_def.get("detector"), dict) else {}
        kind = str(detector.get("kind", "") or "").strip().lower()
        if kind in detector_counts:
            detector_counts[kind] += 1

    file_type_counts: Dict[str, int] = {"Client": 0, "Server": 0}
    for row in parsed_rules:
        if not isinstance(row, dict):
            continue
        rule_type = str(row.get("type", "") or "").strip()
        if rule_type in file_type_counts:
            file_type_counts[rule_type] += 1

    degraded_reasons: List[str] = []
    for dep_key, dep_label in (
        ("openpyxl", "openpyxl missing"),
        ("ctrlppcheck", "CtrlppCheck missing"),
        ("playwright", "Playwright missing"),
    ):
        dep = dependencies.get(dep_key, {}) if isinstance(dependencies, dict) else {}
        if not bool(dep.get("available", False)):
            degraded_reasons.append(dep_label)
    normalized_p1_config_health = dict(p1_config_health) if isinstance(p1_config_health, dict) else {}
    p1_reason_codes = [
        str(code).strip()
        for code in (normalized_p1_config_health.get("reason_codes", []) or [])
        if str(code).strip()
    ]
    if bool(normalized_p1_config_health.get("degraded", False)):
        degraded_reasons.extend([code for code in p1_reason_codes if code not in degraded_reasons])

    return {
        "available": True,
        "generated_at_ms": int(generated_at_ms),
        "status": "degraded" if degraded_reasons else "ok",
        "message": ", ".join(degraded_reasons),
        "rules": {
            "p1_total": len([row for row in p1_rule_defs if isinstance(row, dict)]),
            "p1_enabled": enabled_count,
            "review_applicability_unknown_rule_id_count": safe_int(
                normalized_p1_config_health.get("unknown_review_rule_id_count", 0)
            ),
            "detector_counts": detector_counts,
            "file_type_counts": file_type_counts,
            "regex_count": int(detector_counts.get("regex", 0)),
            "composite_count": int(detector_counts.get("composite", 0)),
            "line_repeat_count": int(detector_counts.get("line_repeat", 0)),
        },
        "p1_config_health": {
            "mode": str(normalized_p1_config_health.get("mode", "configured") or "configured"),
            "degraded": bool(normalized_p1_config_health.get("degraded", False)),
            "enabled_rule_count": safe_int(normalized_p1_config_health.get("enabled_rule_count", enabled_count)),
            "unknown_review_rule_ids": list(normalized_p1_config_health.get("unknown_review_rule_ids", []) or []),
            "unknown_review_rule_id_count": safe_int(
                normalized_p1_config_health.get("unknown_review_rule_id_count", 0)
            ),
            "unsupported_detector_ops": list(normalized_p1_config_health.get("unsupported_detector_ops", []) or []),
            "reason_codes": p1_reason_codes,
            "reason_text": str(normalized_p1_config_health.get("reason_text", "") or ""),
        },
        "dependencies": {
            "openpyxl": dependencies.get("openpyxl", {}),
            "ctrlppcheck": dependencies.get("ctrlppcheck", {}),
            "playwright": dependencies.get("playwright", {}),
        },
    }


def summarize_ui_benchmark_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}
    analyze_avg = safe_float(((summary.get("analyzeUiMs") or {}).get("avg")))
    table_avg = safe_float(((summary.get("resultTableScrollMs") or {}).get("avg")))
    jump_avg = safe_float(((summary.get("codeJumpMs") or {}).get("avg")))
    scroll_avg = safe_float(((summary.get("codeViewerScrollMs") or {}).get("avg")))
    failures = payload.get("threshold_failures", [])
    return {
        "status": "passed" if isinstance(failures, list) and not failures else "failed",
        "finished_at": str(payload.get("finished_at", "") or payload.get("started_at", "") or ""),
        "analyze_ui_avg_ms": analyze_avg,
        "table_scroll_avg_ms": table_avg,
        "code_jump_avg_ms": jump_avg,
        "code_scroll_avg_ms": scroll_avg,
        "iterations": int(payload.get("config", {}).get("iterations", 0) or 0)
        if isinstance(payload.get("config"), dict)
        else 0,
        "threshold_failure_count": len(failures) if isinstance(failures, list) else 0,
    }


def summarize_ui_real_smoke_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    run = payload.get("run", {}) if isinstance(payload.get("run"), dict) else {}
    after_run = run.get("afterRun", {}) if isinstance(run.get("afterRun"), dict) else {}
    rows = after_run.get("rows", None)
    if rows in (None, ""):
        rows = after_run.get("result_row_count", None)
    if rows in (None, ""):
        rows = after_run.get("review_target_count", 0)
    return {
        "status": "passed" if bool(payload.get("ok", False)) else "failed",
        "finished_at": str(payload.get("finished_at", "") or payload.get("started_at", "") or ""),
        "elapsed_ms": safe_float(run.get("elapsed_ms")),
        "rows": int(rows or 0),
        "total_issues": str(after_run.get("totalIssues", "") or ""),
        "selected_file": str(((payload.get("backend") or {}).get("selected_target_file", "")) or ""),
    }


def summarize_ctrlpp_integration_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    direct = payload.get("direct_smoke", {}) if isinstance(payload.get("direct_smoke"), dict) else {}
    binary = payload.get("binary", {}) if isinstance(payload.get("binary"), dict) else {}
    return {
        "status": str(payload.get("status", "unknown") or "unknown"),
        "finished_at": str(payload.get("finished_at", "") or payload.get("started_at", "") or ""),
        "elapsed_ms": safe_float(direct.get("elapsed_ms")),
        "finding_count": int(direct.get("finding_count", 0) or 0),
        "binary_exists": bool(binary.get("exists", False)),
        "infra_error": bool(direct.get("infra_error", False)),
    }


def compute_operational_delta(category: str, latest: Dict[str, Any], previous: Dict[str, Any]) -> Dict[str, Any]:
    delta: Dict[str, Any] = {}
    if category == "ui_benchmark":
        for key in ("analyze_ui_avg_ms", "table_scroll_avg_ms", "code_jump_avg_ms", "code_scroll_avg_ms"):
            latest_value = safe_float(latest.get(key))
            previous_value = safe_float(previous.get(key))
            if latest_value is not None and previous_value is not None:
                delta[key] = round(latest_value - previous_value, 2)
        return delta
    for key in ("elapsed_ms", "rows", "finding_count"):
        latest_value = safe_float(latest.get(key))
        previous_value = safe_float(previous.get(key))
        if latest_value is not None and previous_value is not None:
            delta[key] = round(latest_value - previous_value, 2)
    return delta


def build_analysis_run_collection(
    runs: List[Dict[str, Any]],
    invalid_runs: List[str],
    base_message: str = "",
) -> Dict[str, Any]:
    warnings = list(invalid_runs)
    message = str(base_message or "")
    if warnings:
        summary = f"skipped {len(warnings)} invalid run(s): {warnings[0]}"
        message = f"{message} ({summary})" if message else summary
    return {
        "runs": runs,
        "invalid_runs": invalid_runs,
        "warnings": warnings,
        "invalid_run_count": len(warnings),
        "message": message,
    }


def normalize_file_summary(item: Dict[str, Any]) -> Dict[str, int]:
    return {
        "p1_total": safe_int(item.get("p1_total", 0)),
        "p2_total": safe_int(item.get("p2_total", 0)),
        "p3_total": safe_int(item.get("p3_total", 0)),
        "critical": safe_int(item.get("critical", 0)),
        "warning": safe_int(item.get("warning", 0)),
        "info": safe_int(item.get("info", 0)),
        "total": safe_int(item.get("total", 0)),
    }


def compute_analysis_summary_delta(latest: Dict[str, Any], previous: Dict[str, Any]) -> Dict[str, int]:
    latest_summary = latest.get("summary", {}) if isinstance(latest.get("summary"), dict) else {}
    previous_summary = previous.get("summary", {}) if isinstance(previous.get("summary"), dict) else {}
    return {key: safe_int(latest_summary.get(key, 0)) - safe_int(previous_summary.get(key, 0)) for key in _ANALYSIS_SUMMARY_KEYS}


def compute_analysis_file_diffs(latest: Dict[str, Any], previous: Dict[str, Any]) -> List[Dict[str, Any]]:
    latest_map = {
        str((item or {}).get("file", "") or "(unknown)"): normalize_file_summary(item)
        for item in latest.get("file_summaries", []) or []
        if isinstance(item, dict)
    }
    previous_map = {
        str((item or {}).get("file", "") or "(unknown)"): normalize_file_summary(item)
        for item in previous.get("file_summaries", []) or []
        if isinstance(item, dict)
    }
    file_diffs: List[Dict[str, Any]] = []
    all_files = sorted(set(latest_map.keys()) | set(previous_map.keys()), key=lambda value: value.lower())
    for file_name in all_files:
        current_counts = dict(latest_map.get(file_name, _ZERO_FILE_COUNTS))
        previous_counts = dict(previous_map.get(file_name, _ZERO_FILE_COUNTS))
        delta_counts = {key: current_counts[key] - previous_counts[key] for key in current_counts.keys()}
        if file_name not in previous_map:
            status = "added"
        elif file_name not in latest_map:
            status = "removed"
        elif any(delta_counts.values()):
            status = "changed"
        else:
            status = "unchanged"
        file_diffs.append(
            {
                "file": file_name,
                "status": status,
                "current_counts": current_counts,
                "previous_counts": previous_counts,
                "delta_counts": delta_counts,
            }
        )
    file_diffs.sort(
        key=lambda item: (
            0 if str(item.get("status", "")) != "unchanged" else 1,
            -abs(safe_int(item.get("delta_counts", {}).get("p1_total", 0))),
            -abs(safe_int(item.get("delta_counts", {}).get("total", 0))),
            str(item.get("file", "")).lower(),
        )
    )
    return file_diffs


def merge_analysis_diff_message(primary: str, secondary: str) -> str:
    normalized_primary = str(primary or "").strip()
    normalized_secondary = str(secondary or "").strip()
    if normalized_primary and normalized_secondary:
        return f"{normalized_primary} ({normalized_secondary})"
    return normalized_primary or normalized_secondary


def public_analysis_run(run: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "output_dir": str(run.get("output_dir", "") or ""),
        "timestamp": str(run.get("timestamp", "") or ""),
        "request_id": str(run.get("request_id", "") or ""),
        "summary": run.get("summary", {}) if isinstance(run.get("summary"), dict) else {},
        "report_paths": run.get("report_paths", {}) if isinstance(run.get("report_paths"), dict) else {},
    }


def build_analysis_diff_payload(
    latest: Dict[str, Any],
    previous: Dict[str, Any],
    warnings: Optional[List[str]] = None,
    invalid_run_count: int = 0,
) -> Dict[str, Any]:
    warning_list = list(warnings or [])
    return {
        "available": True,
        "message": str((warning_list or [""])[0] or ""),
        "latest": public_analysis_run(latest),
        "previous": public_analysis_run(previous),
        "delta": {"summary": compute_analysis_summary_delta(latest, previous)},
        "file_diffs": compute_analysis_file_diffs(latest, previous),
        "warnings": warning_list,
        "invalid_run_count": safe_int(invalid_run_count),
    }


def build_analysis_diff_unavailable_payload(
    *,
    latest: Optional[Dict[str, Any]] = None,
    base_message: str = "비교 가능한 최근 2회 분석 결과가 없음",
    secondary_message: str = "",
    warnings: Optional[List[str]] = None,
    invalid_run_count: int = 0,
) -> Dict[str, Any]:
    return {
        "available": False,
        "message": merge_analysis_diff_message(base_message, secondary_message),
        "latest": public_analysis_run(latest) if isinstance(latest, dict) else None,
        "previous": None,
        "delta": {"summary": {}},
        "file_diffs": [],
        "warnings": list(warnings or []),
        "invalid_run_count": safe_int(invalid_run_count),
    }


def build_verification_latest_unavailable_payload(message: str) -> Dict[str, Any]:
    return {
        "available": False,
        "message": str(message or ""),
        "summary": {},
        "source_file": "",
        "source_path": "",
    }
