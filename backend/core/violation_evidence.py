from typing import Any, Dict, List


def _safe_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(fallback)


def _detector_kind_for_violation(violation: Dict[str, Any]) -> str:
    source = str(violation.get("source", "") or "").strip().lower()
    priority = str(violation.get("priority_origin", "") or "").strip().upper()
    if source == "ctrlppcheck" or priority == "P2":
        return "ctrlppcheck"
    if priority == "P3":
        return "live_ai"
    if source in ("configured_rule", "configured_detector"):
        return source
    return "heuristic"


def build_violation_evidence(
    violation: Dict[str, Any],
    *,
    source_lines: List[str],
    canonical_file_id: str = "",
) -> Dict[str, Any]:
    line_no = _safe_int(violation.get("line", 0), 0)
    matched_line = ""
    if line_no > 0 and (line_no - 1) < len(source_lines):
        matched_line = str(source_lines[line_no - 1]).strip()
    if not matched_line:
        matched_line = str(violation.get("message", "") or "").strip()
    matched_lines = [line_no] if line_no > 0 else []
    detector_kind = _detector_kind_for_violation(violation)
    rule_id = str(violation.get("rule_id", "") or "").strip() or "UNKNOWN"
    source_label = str(violation.get("priority_origin", "") or detector_kind).strip() or detector_kind
    if line_no > 0:
        display_reason = f"{source_label} detector matched {rule_id} near line {line_no}."
    else:
        display_reason = f"{source_label} detector matched {rule_id}."
    return {
        "matched_text": matched_line,
        "matched_lines": matched_lines,
        "detector_kind": detector_kind,
        "canonical_file_id": str(canonical_file_id or violation.get("canonical_file_id", "") or ""),
        "display_reason": display_reason,
    }
