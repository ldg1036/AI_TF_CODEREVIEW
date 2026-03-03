from __future__ import annotations

from typing import Any, Dict, List, Tuple


_ALLOWED_OPERATIONS = {"replace", "insert"}
_ALLOWED_LOCATOR_KIND = {"anchor_context"}


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _normalize_single_operation(raw_op: Any, fallback: Dict[str, Any] | None = None) -> Dict[str, Any]:
    op_src = raw_op if isinstance(raw_op, dict) else {}
    fallback = fallback if isinstance(fallback, dict) else {}

    locator = op_src.get("locator") if isinstance(op_src.get("locator"), dict) else {}
    payload = op_src.get("payload") if isinstance(op_src.get("payload"), dict) else {}
    if not locator and isinstance(fallback.get("locator"), dict):
        locator = dict(fallback.get("locator") or {})
    if not payload and isinstance(fallback.get("payload"), dict):
        payload = dict(fallback.get("payload") or {})

    operation = _safe_str(op_src.get("operation")).lower()
    if not operation:
        operation = _safe_str(fallback.get("operation")).lower()
    locator_kind = _safe_str(locator.get("kind")).lower()
    try:
        start_line = int(locator.get("start_line", 0) or 0)
    except (TypeError, ValueError):
        start_line = 0

    return {
        "operation": operation,
        "locator": {
            "kind": locator_kind,
            "start_line": start_line,
            "context_before": str(locator.get("context_before", "") or ""),
            "context_after": str(locator.get("context_after", "") or ""),
        },
        "payload": {
            "code": str(payload.get("code", "") or ""),
        },
    }


def normalize_instruction(raw: dict) -> dict:
    """Normalize a raw instruction payload into schema-friendly shape."""
    payload = raw if isinstance(raw, dict) else {}
    target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
    safety = payload.get("safety") if isinstance(payload.get("safety"), dict) else {}

    operations_raw = payload.get("operations")
    operations: List[Dict[str, Any]] = []
    if isinstance(operations_raw, list):
        for item in operations_raw:
            operations.append(_normalize_single_operation(item))
    if not operations:
        operations.append(_normalize_single_operation({}, fallback=payload))
    first = operations[0] if operations else _normalize_single_operation({}, fallback=payload)

    return {
        "target": {
            "file": _safe_str(target.get("file")),
            "object": _safe_str(target.get("object")),
            "event": _safe_str(target.get("event")) or "Global",
        },
        # Backward-compatible mirror fields
        "operation": str(first.get("operation", "") or ""),
        "locator": dict(first.get("locator", {}) or {}),
        "payload": dict(first.get("payload", {}) or {}),
        # Primary v1.1 shape
        "operations": operations,
        "safety": {
            "requires_hash_match": bool(safety.get("requires_hash_match", True)),
        },
    }


def validate_instruction(instr: dict) -> Tuple[bool, List[str]]:
    """Validate normalized instruction payload."""
    errors: List[str] = []
    data = instr if isinstance(instr, dict) else {}

    target = data.get("target") if isinstance(data.get("target"), dict) else {}
    if not _safe_str(target.get("file")):
        errors.append("target.file is required")

    operations = data.get("operations") if isinstance(data.get("operations"), list) else []
    if not operations:
        errors.append("operations must contain at least one operation")

    for index, operation_item in enumerate(operations):
        op = operation_item if isinstance(operation_item, dict) else {}
        locator = op.get("locator") if isinstance(op.get("locator"), dict) else {}
        payload = op.get("payload") if isinstance(op.get("payload"), dict) else {}

        operation = _safe_str(op.get("operation")).lower()
        if operation not in _ALLOWED_OPERATIONS:
            errors.append(f"operations[{index}].operation must be one of: replace, insert")

        locator_kind = _safe_str(locator.get("kind")).lower()
        if locator_kind not in _ALLOWED_LOCATOR_KIND:
            errors.append(f"operations[{index}].locator.kind must be anchor_context")

        try:
            start_line = int(locator.get("start_line", 0) or 0)
        except (TypeError, ValueError):
            start_line = 0
        if start_line <= 0:
            errors.append(f"operations[{index}].locator.start_line must be >= 1")

        if not str(payload.get("code", "") or "").strip():
            errors.append(f"operations[{index}].payload.code must not be empty")

    return (len(errors) == 0, errors)


def instruction_to_hunks(instr: dict) -> List[Dict[str, Any]]:
    """Convert validated instruction to hunk list consumed by apply engine."""
    data = normalize_instruction(instr)
    operations = data.get("operations") if isinstance(data.get("operations"), list) else []

    hunks: List[Dict[str, Any]] = []
    for op_item in operations:
        op = op_item if isinstance(op_item, dict) else {}
        operation = str(op.get("operation", "") or "")
        locator = op.get("locator") if isinstance(op.get("locator"), dict) else {}
        start_line = int(locator.get("start_line", 1) or 1)
        code = str((op.get("payload") or {}).get("code", "") or "")

        if operation not in _ALLOWED_OPERATIONS:
            raise ValueError(f"Unsupported operation: {operation}")

        hunks.append(
            {
                "start_line": start_line,
                "end_line": start_line,
                "context_before": str(locator.get("context_before", "") or ""),
                "context_after": str(locator.get("context_after", "") or ""),
                "replacement_text": code,
            }
        )
    return hunks
