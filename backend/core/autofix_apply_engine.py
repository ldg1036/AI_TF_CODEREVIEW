from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

try:
    from core.autofix_tokenizer import normalize_anchor_text
except ModuleNotFoundError:  # pragma: no cover - import path depends on entrypoint
    from backend.core.autofix_tokenizer import normalize_anchor_text


@dataclass(frozen=True)
class BlockRange:
    start_line: int
    end_line: int

    def contains(self, start_line: int, end_line: int) -> bool:
        return self.start_line <= start_line <= self.end_line and self.start_line <= end_line <= self.end_line


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _normalize_reason(reason: str) -> str:
    text = str(reason or "").strip().lower()
    if not text:
        return "apply_failed"
    if "anchor context not unique" in text:
        return "anchor_context_not_unique"
    if "line drift exceeds" in text:
        return "drift_exceeded"
    if "hunks span multiple blocks" in text:
        return "hunks_span_multiple_blocks"
    if "overlapping_hunks" in text:
        return "overlapping_hunks"
    if "too_many_hunks" in text:
        return "too_many_hunks"
    if "no enclosing block" in text:
        return "no_enclosing_block"
    if "out of block range" in text:
        return "hunk_out_of_block_range"
    if "out of range" in text:
        return "line_out_of_range"
    if "ambiguous_candidates" in text:
        return "ambiguous_candidates"
    return text.replace(" ", "_")


def _occurrence_count(lines: List[str], before_expected: str, after_expected: str) -> int:
    if not before_expected and not after_expected:
        return 1
    count = 0
    for idx in range(len(lines) + 1):
        before_actual = lines[idx - 1] if idx > 0 and (idx - 1) < len(lines) else ""
        after_actual = lines[idx] if idx < len(lines) else ""
        before_ok = (not before_expected) or (before_actual == before_expected)
        after_ok = (not after_expected) or (after_actual == after_expected)
        if before_ok and after_ok:
            count += 1
    return count


def _occurrence_count_normalized(lines: List[str], before_expected: str, after_expected: str) -> int:
    if not before_expected and not after_expected:
        return 1
    before_expected_n = normalize_anchor_text(before_expected)
    after_expected_n = normalize_anchor_text(after_expected)
    count = 0
    for idx in range(len(lines) + 1):
        before_actual = lines[idx - 1] if idx > 0 and (idx - 1) < len(lines) else ""
        after_actual = lines[idx] if idx < len(lines) else ""
        before_ok = (not before_expected) or (normalize_anchor_text(before_actual) == before_expected_n)
        after_ok = (not after_expected) or (normalize_anchor_text(after_actual) == after_expected_n)
        if before_ok and after_ok:
            count += 1
    return count


def _extract_block_ranges(lines: List[str]) -> List[BlockRange]:
    ranges: List[BlockRange] = []
    stack: List[int] = []
    for idx, line in enumerate(lines, start=1):
        for ch in line:
            if ch == "{":
                stack.append(idx)
            elif ch == "}" and stack:
                start_line = stack.pop()
                if idx >= start_line:
                    ranges.append(BlockRange(start_line=start_line, end_line=idx))
    return ranges


def _find_innermost_block(blocks: List[BlockRange], line_no: int) -> Optional[BlockRange]:
    found: Optional[BlockRange] = None
    for block in blocks:
        if block.start_line <= line_no <= block.end_line:
            if found is None or (block.end_line - block.start_line) < (found.end_line - found.start_line):
                found = block
    return found


def _detect_overlapping_hunks(hunks: List[Dict[str, Any]]) -> bool:
    ranges: List[Tuple[int, int]] = []
    for h in hunks:
        start_line = max(1, _safe_int(h.get("start_line", 1), 1))
        end_line = max(start_line, _safe_int(h.get("end_line", start_line), start_line))
        ranges.append((start_line, end_line))
    ranges.sort(key=lambda item: (item[0], item[1]))
    for idx in range(1, len(ranges)):
        prev = ranges[idx - 1]
        cur = ranges[idx]
        if cur[0] <= prev[1]:
            return True
    return False


def _apply_hunks_text(base_text: str, hunks: List[Dict[str, Any]], *, validate_stepwise: bool = False) -> Dict[str, Any]:
    lines = base_text.splitlines()
    ordered = sorted(
        [h for h in hunks if isinstance(h, dict)],
        key=lambda item: _safe_int(item.get("start_line", 1), 1),
        reverse=True,
    )
    applied_hunk_count = 0
    try:
        for h in ordered:
            start_line = max(1, _safe_int(h.get("start_line", 1), 1))
            end_line = _safe_int(h.get("end_line", start_line), start_line)
            end_line = max(start_line, end_line)
            if start_line > (len(lines) + 1):
                return {"ok": False, "error": f"start_line out of range: {start_line}", "applied_hunk_count": applied_hunk_count}

            if validate_stepwise:
                before_expected = str(h.get("context_before", ""))
                after_expected = str(h.get("context_after", ""))
                occ = _occurrence_count(lines, before_expected, after_expected)
                occ_norm = _occurrence_count_normalized(lines, before_expected, after_expected)
                if occ != 1 and occ_norm != 1:
                    return {"ok": False, "error": "anchor_context_not_unique", "applied_hunk_count": applied_hunk_count}

            replacement_text = str(h.get("replacement_text", ""))
            replacement_lines = replacement_text.splitlines()
            lines[start_line - 1:end_line] = replacement_lines
            applied_hunk_count += 1
    except Exception as exc:
        return {"ok": False, "error": str(exc), "applied_hunk_count": applied_hunk_count}

    patched = "\n".join(lines)
    if base_text.endswith("\n"):
        patched += "\n"
    return {"ok": True, "patched_text": patched, "applied_hunk_count": applied_hunk_count}


def apply_with_engine(
    base_text: str,
    hunks: List[Dict[str, Any]],
    anchor_line: int,
    generator_type: str,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    opts = dict(options or {})
    lines = base_text.splitlines()
    blocks = _extract_block_ranges(lines)
    max_line_drift = max(0, _safe_int(opts.get("max_line_drift", 120), 120))
    max_hunks_per_apply = max(1, _safe_int(opts.get("max_hunks_per_apply", 3), 3))

    diagnostics: Dict[str, Any] = {
        "block_count": len(blocks),
        "generator_type": str(generator_type or "unknown"),
        "hunk_count": 0,
        "owner_block": {},
        "overlap_detected": False,
        "applied_hunk_count": 0,
    }

    valid_hunks = [h for h in (hunks or []) if isinstance(h, dict)]
    diagnostics["hunk_count"] = len(valid_hunks)
    if not valid_hunks:
        return {
            "ok": False,
            "patched_text": "",
            "engine_mode": "failed",
            "fallback_reason": "no_hunks",
            "diagnostics": diagnostics,
        }

    if len(valid_hunks) > max_hunks_per_apply:
        return {
            "ok": False,
            "patched_text": "",
            "engine_mode": "failed",
            "fallback_reason": "too_many_hunks",
            "diagnostics": diagnostics,
        }

    overlap_detected = _detect_overlapping_hunks(valid_hunks)
    diagnostics["overlap_detected"] = overlap_detected
    if overlap_detected:
        return {
            "ok": False,
            "patched_text": "",
            "engine_mode": "failed",
            "fallback_reason": "overlapping_hunks",
            "diagnostics": diagnostics,
        }

    structure_reason = ""
    owner_block: Optional[BlockRange] = None
    for h in valid_hunks:
        h_start = max(1, _safe_int(h.get("start_line", 1), 1))
        h_end = max(h_start, _safe_int(h.get("end_line", h_start), h_start))
        if abs(h_start - _safe_int(anchor_line, h_start)) > max_line_drift:
            structure_reason = "drift_exceeded"
            break

        before_expected = str(h.get("context_before", ""))
        after_expected = str(h.get("context_after", ""))
        occ = _occurrence_count(lines, before_expected, after_expected)
        occ_norm = _occurrence_count_normalized(lines, before_expected, after_expected)
        if occ != 1 and occ_norm != 1:
            structure_reason = "anchor_context_not_unique"
            break

        block = _find_innermost_block(blocks, h_start)
        if block is None:
            structure_reason = "no_enclosing_block"
            break
        if not block.contains(h_start, h_end):
            structure_reason = "hunk_out_of_block_range"
            break

        if owner_block is None:
            owner_block = block
        elif owner_block != block:
            structure_reason = "hunks_span_multiple_blocks"
            break

    if owner_block is not None:
        diagnostics["owner_block"] = {"start_line": owner_block.start_line, "end_line": owner_block.end_line}

    if not structure_reason:
        structure_result = _apply_hunks_text(base_text, valid_hunks, validate_stepwise=True)
        diagnostics["applied_hunk_count"] = _safe_int(structure_result.get("applied_hunk_count", 0), 0)
        if structure_result.get("ok"):
            return {
                "ok": True,
                "patched_text": str(structure_result.get("patched_text", "")),
                "engine_mode": "structure_apply",
                "fallback_reason": "",
                "diagnostics": diagnostics,
            }
        structure_reason = _normalize_reason(str(structure_result.get("error", "structure apply failed")))

    if structure_reason in ("hunks_span_multiple_blocks", "too_many_hunks", "overlapping_hunks"):
        return {
            "ok": False,
            "patched_text": "",
            "engine_mode": "failed",
            "fallback_reason": structure_reason,
            "diagnostics": diagnostics,
        }
    if len(valid_hunks) >= 2 and structure_reason == "anchor_context_not_unique":
        return {
            "ok": False,
            "patched_text": "",
            "engine_mode": "failed",
            "fallback_reason": structure_reason,
            "diagnostics": diagnostics,
        }

    # Guard against ambiguous fallback application. If the anchor context is
    # not unique (including normalized form), fail-soft instead of patching.
    for h in valid_hunks:
        before_expected = str(h.get("context_before", ""))
        after_expected = str(h.get("context_after", ""))
        occ = _occurrence_count(lines, before_expected, after_expected)
        occ_norm = _occurrence_count_normalized(lines, before_expected, after_expected)
        if occ > 1 or occ_norm > 1:
            return {
                "ok": False,
                "patched_text": "",
                "engine_mode": "failed",
                "fallback_reason": "ambiguous_candidates",
                "diagnostics": diagnostics,
            }

    fallback_result = _apply_hunks_text(base_text, valid_hunks, validate_stepwise=(len(valid_hunks) >= 2))
    diagnostics["applied_hunk_count"] = _safe_int(fallback_result.get("applied_hunk_count", 0), 0)
    if fallback_result.get("ok"):
        return {
            "ok": True,
            "patched_text": str(fallback_result.get("patched_text", "")),
            "engine_mode": "text_fallback",
            "fallback_reason": _normalize_reason(structure_reason),
            "diagnostics": diagnostics,
        }
    return {
        "ok": False,
        "patched_text": "",
        "engine_mode": "failed",
        "fallback_reason": _normalize_reason(str(fallback_result.get("error", structure_reason or "apply failed"))),
        "diagnostics": diagnostics,
    }
