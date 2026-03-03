from __future__ import annotations

from typing import Any, Dict, List, Tuple


_ALLOWED_OPERATIONS = {"replace", "insert"}
_ALLOWED_LOCATOR_KIND = {"anchor_context"}


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def normalize_instruction(raw: dict) -> dict:
    """Normalize a raw instruction payload into schema-friendly shape."""
    payload = raw if isinstance(raw, dict) else {}
    target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
    locator = payload.get("locator") if isinstance(payload.get("locator"), dict) else {}
    body = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    safety = payload.get("safety") if isinstance(payload.get("safety"), dict) else {}

    operation = _safe_str(payload.get("operation")).lower()
    locator_kind = _safe_str(locator.get("kind")).lower()

    try:
        start_line = int(locator.get("start_line", 0) or 0)
    except (TypeError, ValueError):
        start_line = 0

    return {
        "target": {
            "file": _safe_str(target.get("file")),
            "object": _safe_str(target.get("object")),
            "event": _safe_str(target.get("event")) or "Global",
        },
        "operation": operation,
        "locator": {
            "kind": locator_kind,
            "start_line": start_line,
            "context_before": str(locator.get("context_before", "") or ""),
            "context_after": str(locator.get("context_after", "") or ""),
        },
        "payload": {
            "code": str(body.get("code", "") or ""),
        },
        "safety": {
            "requires_hash_match": bool(safety.get("requires_hash_match", True)),
        },
    }


def validate_instruction(instr: dict) -> Tuple[bool, List[str]]:
    """Validate normalized instruction payload."""
    errors: List[str] = []
    data = instr if isinstance(instr, dict) else {}

    target = data.get("target") if isinstance(data.get("target"), dict) else {}
    locator = data.get("locator") if isinstance(data.get("locator"), dict) else {}
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}

    if not _safe_str(target.get("file")):
        errors.append("target.file is required")

    operation = _safe_str(data.get("operation")).lower()
    if operation not in _ALLOWED_OPERATIONS:
        errors.append("operation must be one of: replace, insert")

    locator_kind = _safe_str(locator.get("kind")).lower()
    if locator_kind not in _ALLOWED_LOCATOR_KIND:
        errors.append("locator.kind must be anchor_context")

    try:
        start_line = int(locator.get("start_line", 0) or 0)
    except (TypeError, ValueError):
        start_line = 0
    if start_line <= 0:
        errors.append("locator.start_line must be >= 1")

    if not str(payload.get("code", "") or "").strip():
        errors.append("payload.code must not be empty")

    return (len(errors) == 0, errors)


def instruction_to_hunks(instr: dict) -> List[Dict[str, Any]]:
    """Convert validated instruction to hunk list consumed by apply engine."""
    data = normalize_instruction(instr)
    operation = data["operation"]
    locator = data["locator"]
    start_line = int(locator.get("start_line", 1) or 1)
    code = str((data.get("payload") or {}).get("code", "") or "")

    if operation == "replace":
        return [
            {
                "start_line": start_line,
                "end_line": start_line,
                "context_before": str(locator.get("context_before", "") or ""),
                "context_after": str(locator.get("context_after", "") or ""),
                "replacement_text": code,
            }
        ]

    if operation == "insert":
        return [
            {
                "start_line": start_line,
                "end_line": start_line,
                "context_before": str(locator.get("context_before", "") or ""),
                "context_after": str(locator.get("context_after", "") or ""),
                "replacement_text": code,
            }
        ]

    raise ValueError(f"Unsupported operation: {operation}")
