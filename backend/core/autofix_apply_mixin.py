import datetime
import json
import os
import shutil
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from core.autofix_apply_engine import apply_with_engine as _default_apply_with_engine
from core.autofix_instruction import (
    instruction_to_hunks as _default_instruction_to_hunks,
    normalize_instruction as _default_normalize_instruction,
    validate_instruction as _default_validate_instruction,
)
from core.autofix_semantic_guard import evaluate_semantic_delta
from core.autofix_tokenizer import locate_anchor_line_by_tokens, normalize_anchor_text
from core.reporter import Reporter

AutoFixQualityMetrics = Dict[str, Any]


def _compat_autofix_symbol(name: str, default):
    try:
        import core.autofix_mixin as facade_module

        return getattr(facade_module, name, default)
    except Exception:
        return default


class AutoFixApplyMixin:
    """Host class should provide autofix config, session helpers, and utility methods."""

    @staticmethod
    def _autofix_error_code_from_exception_message(message: str) -> str:
        msg = str(message or "").lower()
        if "base hash mismatch" in msg:
            return "BASE_HASH_MISMATCH"
        if "anchor mismatch" in msg:
            return "ANCHOR_MISMATCH"
        if "semantic guard blocked" in msg:
            return "SEMANTIC_GUARD_BLOCKED"
        if "syntax precheck failed" in msg:
            return "SYNTAX_PRECHECK_FAILED"
        if "apply engine failed" in msg:
            return "APPLY_ENGINE_FAILED"
        if "heuristic regression detected" in msg or "ctrlppcheck regression detected" in msg:
            return "REGRESSION_BLOCKED"
        if "supported only for .ctl" in msg:
            return "UNSUPPORTED_FILE_TYPE"
        if "session cache" in msg or "run analysis first" in msg:
            return "SESSION_NOT_FOUND"
        return "INTERNAL_ERROR"

    @classmethod
    def _new_autofix_quality_metrics(
        cls,
        proposal_id: str = "",
        generator_type: str = "llm",
        *,
        anchors_match: bool = True,
        hash_match: bool = True,
        syntax_check_passed: bool = True,
        heuristic_regression_count: int = 0,
        ctrlpp_regression_count: int = 0,
        applied: bool = False,
        rejected_reason: str = "",
        validation_errors: Optional[List[str]] = None,
        blocking_errors: Optional[List[str]] = None,
        identifier_reuse_confirmed: bool = True,
        locator_mode: str = "anchor",
        apply_engine_mode: str = "",
        apply_engine_fallback_reason: str = "",
        token_fallback_attempted: bool = False,
        token_fallback_confidence: float = 0.0,
        token_fallback_candidates: int = 0,
        semantic_check_passed: bool = True,
        semantic_blocked_reason: str = "",
        semantic_violation_count: int = 0,
        token_min_confidence_used: float = 0.8,
        token_min_gap_used: float = 0.15,
        token_max_line_drift_used: int = 0,
        benchmark_tuning_applied: bool = False,
        token_prefer_nearest_tie_used: bool = False,
        token_hint_bias_used: float = 0.0,
        token_force_nearest_on_ambiguous_used: bool = False,
        instruction_mode: str = "off",
        instruction_validation_errors: Optional[List[str]] = None,
        instruction_operation: str = "",
        instruction_operation_count: int = 0,
        instruction_apply_success: bool = False,
        instruction_path_reason: str = "off",
        instruction_failure_stage: str = "none",
        instruction_candidate_hunk_count: int = 0,
        instruction_applied_hunk_count: int = 0,
    ) -> AutoFixQualityMetrics:
        return {
            "proposal_id": str(proposal_id or ""),
            "generator_type": str(generator_type or "llm"),
            "anchors_match": bool(anchors_match),
            "hash_match": bool(hash_match),
            "syntax_check_passed": bool(syntax_check_passed),
            "heuristic_regression_count": int(heuristic_regression_count or 0),
            "ctrlpp_regression_count": int(ctrlpp_regression_count or 0),
            "applied": bool(applied),
            "rejected_reason": str(rejected_reason or ""),
            "validation_errors": list(validation_errors or []),
            "blocking_errors": list(blocking_errors or []),
            "identifier_reuse_confirmed": bool(identifier_reuse_confirmed),
            "locator_mode": str(locator_mode or "anchor"),
            "apply_engine_mode": str(apply_engine_mode or ""),
            "apply_engine_fallback_reason": str(apply_engine_fallback_reason or ""),
            "token_fallback_attempted": bool(token_fallback_attempted),
            "token_fallback_confidence": float(token_fallback_confidence or 0.0),
            "token_fallback_candidates": int(token_fallback_candidates or 0),
            "semantic_check_passed": bool(semantic_check_passed),
            "semantic_blocked_reason": str(semantic_blocked_reason or ""),
            "semantic_violation_count": int(semantic_violation_count or 0),
            "token_min_confidence_used": float(token_min_confidence_used or 0.8),
            "token_min_gap_used": float(token_min_gap_used or 0.15),
            "token_max_line_drift_used": int(token_max_line_drift_used or 0),
            "benchmark_tuning_applied": bool(benchmark_tuning_applied),
            "token_prefer_nearest_tie_used": bool(token_prefer_nearest_tie_used),
            "token_hint_bias_used": float(token_hint_bias_used or 0.0),
            "token_force_nearest_on_ambiguous_used": bool(token_force_nearest_on_ambiguous_used),
            "instruction_mode": str(instruction_mode or "off"),
            "instruction_validation_errors": list(instruction_validation_errors or []),
            "instruction_operation": str(instruction_operation or ""),
            "instruction_operation_count": int(instruction_operation_count or 0),
            "instruction_apply_success": bool(instruction_apply_success),
            "instruction_path_reason": str(instruction_path_reason or "off"),
            "instruction_failure_stage": str(instruction_failure_stage or "none"),
            "instruction_candidate_hunk_count": int(instruction_candidate_hunk_count or 0),
            "instruction_applied_hunk_count": int(instruction_applied_hunk_count or 0),
        }

    def _autofix_apply_error(
        self,
        message: str,
        *,
        error_code: str = "",
        quality_metrics: Optional[AutoFixQualityMetrics] = None,
    ):
        from main import AutoFixApplyError

        code = str(error_code or self._autofix_error_code_from_exception_message(message))
        return AutoFixApplyError(message, code, quality_metrics=quality_metrics)

    def _count_p1_findings(self, internal_groups: List[Dict]) -> int:
        count = 0
        for group in internal_groups or []:
            if not isinstance(group, dict):
                continue
            count += len(group.get("violations", []) or [])
        return count

    def _count_ctrlpp_findings(self, p2_findings: List[Dict]) -> int:
        count = 0
        for item in p2_findings or []:
            if not isinstance(item, dict):
                continue
            rule_id = str(item.get("rule_id", "") or "")
            source = str(item.get("source", "") or "")
            if source and source != "CtrlppCheck":
                continue
            if rule_id == "ctrlppcheck.info":
                continue
            count += 1
        return count

    def _attempt_token_anchor_fallback(
        self,
        current_lines: List[str],
        hunks: List[Dict],
        *,
        min_confidence: float = 0.8,
        min_gap: float = 0.15,
        max_line_drift: Optional[int] = None,
        prefer_nearest_on_tie: bool = False,
        hint_bias: float = 0.0,
        force_pick_nearest_on_ambiguous: bool = False,
    ) -> Dict[str, Any]:
        resolved_hunks: List[Dict] = []
        confidences: List[float] = []
        candidate_counts: List[int] = []
        errors: List[str] = []

        drift_limit = self._safe_int(max_line_drift, 0)
        if drift_limit <= 0:
            drift_limit = max(50, min(300, len(current_lines)))

        for h in hunks or []:
            if not isinstance(h, dict):
                continue
            hint_line = self._safe_int(h.get("start_line", 1), 1)
            locate = locate_anchor_line_by_tokens(
                current_lines,
                before_expected=str(h.get("context_before", "")),
                after_expected=str(h.get("context_after", "")),
                hint_line=hint_line,
                min_confidence=float(min_confidence),
                min_gap=float(min_gap),
                max_line_drift=drift_limit,
                prefer_nearest_on_tie=bool(prefer_nearest_on_tie),
                hint_bias=float(hint_bias or 0.0),
                force_pick_nearest_on_ambiguous=bool(force_pick_nearest_on_ambiguous),
            )
            candidate_counts.append(self._safe_int(locate.get("candidate_count", 0), 0))
            confidences.append(float(locate.get("confidence", 0.0) or 0.0))
            if not bool(locate.get("ok", False)):
                reason = str(locate.get("reason", "no_candidate") or "no_candidate")
                errors.append(f"token fallback failed at line {hint_line}: {reason}")
                continue
            relocated = dict(h)
            relocated["start_line"] = self._safe_int(locate.get("line", hint_line), hint_line)
            resolved_hunks.append(relocated)

        expected_count = len([h for h in (hunks or []) if isinstance(h, dict)])
        success = expected_count > 0 and len(resolved_hunks) == expected_count
        return {
            "success": success,
            "resolved_hunks": resolved_hunks,
            "confidence": max(confidences) if confidences else 0.0,
            "candidate_count": max(candidate_counts) if candidate_counts else 0,
            "errors": errors,
        }

    @staticmethod
    def _hunk_ranges_overlap(hunks: List[Dict]) -> bool:
        def _si(value, fallback=0):
            try:
                return int(value)
            except (TypeError, ValueError):
                return int(fallback)

        ranges: List[Tuple[int, int]] = []
        for h in hunks or []:
            if not isinstance(h, dict):
                continue
            start_line = max(1, _si(h.get("start_line", 1), 1))
            end_line = max(start_line, _si(h.get("end_line", start_line), start_line))
            ranges.append((start_line, end_line))
        ranges.sort(key=lambda item: (item[0], item[1]))
        for idx in range(1, len(ranges)):
            _prev_start, prev_end = ranges[idx - 1]
            cur_start, _cur_end = ranges[idx]
            if cur_start <= prev_end:
                return True
        return False

    def _append_autofix_audit_entry(self, output_dir: str, entry: Dict) -> str:
        os.makedirs(output_dir, exist_ok=True)
        audit_path = os.path.join(output_dir, "autofix_audit.jsonl")
        line = json.dumps(entry, ensure_ascii=False)
        with open(audit_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        return audit_path

    def _mark_autofix_proposal_failure(
        self,
        session: Dict,
        proposal: Optional[Dict],
        *,
        error_code: str,
        quality_metrics: Optional[AutoFixQualityMetrics] = None,
    ) -> None:
        if not isinstance(session, dict) or not isinstance(proposal, dict):
            return
        with session["lock"]:
            proposal["status"] = "Rejected"
            proposal["rejected_at"] = self._iso_now()
            proposal["last_error_code"] = str(error_code or "")
            if isinstance(quality_metrics, dict):
                proposal["quality_metrics"] = json.loads(json.dumps(quality_metrics, ensure_ascii=False))
            self._touch_review_session(session)

    def apply_autofix_proposal(
        self,
        proposal_id: str,
        session_id: Optional[str] = None,
        output_dir: Optional[str] = None,
        file_name: str = "",
        expected_base_hash: str = "",
        apply_mode: str = "source_ctl",
        block_on_regression: Optional[bool] = None,
        check_ctrlpp_regression: Optional[bool] = None,
        benchmark_observe_mode: str = "strict_hash",
        benchmark_tuning_min_confidence: Optional[float] = None,
        benchmark_tuning_min_gap: Optional[float] = None,
        benchmark_tuning_max_line_drift: Optional[int] = None,
        benchmark_force_structured_instruction: bool = False,
    ) -> Dict:
        if str(apply_mode or "source_ctl") != "source_ctl":
            raise ValueError("apply_mode must be 'source_ctl'")
        target_output_dir = output_dir or session_id or self._last_output_dir
        if not target_output_dir:
            raise RuntimeError("No analysis session found. Run analysis first.")
        session = self._get_review_session(target_output_dir)
        if not session:
            raise RuntimeError("Analysis session cache not found. Run analysis again.")

        block_on_regression = self.autofix_block_on_regression_default if block_on_regression is None else bool(block_on_regression)
        check_ctrlpp_regression = (
            self.autofix_ctrlpp_regression_check_default
            if check_ctrlpp_regression is None
            else bool(check_ctrlpp_regression)
        )
        normalized_file = os.path.basename(str(file_name or ""))

        with session["lock"]:
            proposal = self._resolve_autofix_proposal(session, proposal_id=str(proposal_id or ""), file_name=normalized_file)
            normalized_file = os.path.basename(str(proposal.get("file", normalized_file)))
        is_ctl_target = normalized_file.lower().endswith(".ctl")

        file_lock = self._get_session_file_lock(session, normalized_file)
        with file_lock:
            with session["lock"]:
                proposal = self._resolve_autofix_proposal(session, proposal_id=str(proposal_id or ""), file_name=normalized_file)
                session_files = session.get("files", {})
                cached = session_files.get(normalized_file)
                if not isinstance(cached, dict):
                    raise RuntimeError("Cached file session not found for autofix apply")

            source_path = str(cached.get("source_path", "") or os.path.join(self.data_dir, normalized_file))
            if not os.path.isfile(source_path):
                raise FileNotFoundError(f"Source file not found: {normalized_file}")

            with open(source_path, "r", encoding="utf-8", errors="ignore") as f:
                current_content = f.read()
            current_lines = current_content.splitlines()
            current_hash = self._sha256_text(current_content)
            proposal_base_hash = str(proposal.get("base_hash", ""))
            hash_match = current_hash == proposal_base_hash
            if expected_base_hash:
                hash_match = hash_match and (current_hash == str(expected_base_hash))
            normalized_observe_mode = str(benchmark_observe_mode or "strict_hash").strip().lower()
            if normalized_observe_mode not in ("strict_hash", "benchmark_relaxed"):
                normalized_observe_mode = "strict_hash"
            benchmark_observe_enabled = (
                normalized_observe_mode == "benchmark_relaxed"
                and str(os.environ.get("AUTOFIX_BENCHMARK_OBSERVE", "") or "").strip() == "1"
            )
            token_min_confidence_used = 0.8
            token_min_gap_used = 0.15
            token_max_line_drift_used = max(50, min(300, len(current_lines)))
            benchmark_tuning_applied = False
            token_prefer_nearest_tie_used = False
            token_hint_bias_used = 0.0
            token_force_nearest_on_ambiguous_used = False
            benchmark_structured_instruction_forced = False
            instruction_mode = "off"
            instruction_validation_errors: List[str] = []
            instruction_operation = ""
            instruction_operation_count = 0
            instruction_apply_success = False
            instruction_path_reason = "off"
            instruction_failure_stage = "none"
            instruction_candidate_hunk_count = 0
            instruction_applied_hunk_count = 0
            instruction_observability_recorded = False
            instruction_recorded_mode = "off"
            if benchmark_observe_enabled:
                if benchmark_tuning_min_confidence is not None:
                    token_min_confidence_used = float(benchmark_tuning_min_confidence)
                    benchmark_tuning_applied = True
                if benchmark_tuning_min_gap is not None:
                    token_min_gap_used = float(benchmark_tuning_min_gap)
                    benchmark_tuning_applied = True
                if benchmark_tuning_max_line_drift is not None:
                    token_max_line_drift_used = max(10, int(benchmark_tuning_max_line_drift))
                    benchmark_tuning_applied = True
                if benchmark_tuning_applied:
                    token_prefer_nearest_tie_used = True
                    token_hint_bias_used = 0.03
                    token_force_nearest_on_ambiguous_used = True
                benchmark_structured_instruction_forced = bool(benchmark_force_structured_instruction)

            def _with_tuning_metrics(payload: AutoFixQualityMetrics) -> AutoFixQualityMetrics:
                payload["token_min_confidence_used"] = float(token_min_confidence_used)
                payload["token_min_gap_used"] = float(token_min_gap_used)
                payload["token_max_line_drift_used"] = int(token_max_line_drift_used)
                payload["benchmark_tuning_applied"] = bool(benchmark_tuning_applied)
                payload["token_prefer_nearest_tie_used"] = bool(token_prefer_nearest_tie_used)
                payload["token_hint_bias_used"] = float(token_hint_bias_used)
                payload["token_force_nearest_on_ambiguous_used"] = bool(token_force_nearest_on_ambiguous_used)
                payload["benchmark_structured_instruction_forced"] = bool(benchmark_structured_instruction_forced)
                payload["instruction_mode"] = str(instruction_mode or "off")
                payload["instruction_validation_errors"] = list(instruction_validation_errors)
                payload["instruction_operation"] = str(instruction_operation or "")
                payload["instruction_operation_count"] = int(instruction_operation_count or 0)
                payload["instruction_apply_success"] = bool(instruction_apply_success)
                payload["instruction_path_reason"] = str(instruction_path_reason or "off")
                payload["instruction_failure_stage"] = str(instruction_failure_stage or "none")
                payload["instruction_candidate_hunk_count"] = int(instruction_candidate_hunk_count or 0)
                payload["instruction_applied_hunk_count"] = int(instruction_applied_hunk_count or 0)
                return payload

            def _record_instruction_observability(final_mode: Optional[str] = None):
                nonlocal instruction_observability_recorded, instruction_recorded_mode
                if instruction_observability_recorded:
                    return
                mode = str(final_mode or instruction_mode or "off")
                if mode not in ("off", "attempted", "applied", "fallback_hunks"):
                    mode = "off"
                with session["lock"]:
                    stats = self._autofix_session_stats(session)
                    mode_counts = stats.get("instruction_mode_counts", {})
                    if not isinstance(mode_counts, dict):
                        mode_counts = {"off": 0, "attempted": 0, "applied": 0, "fallback_hunks": 0}
                        stats["instruction_mode_counts"] = mode_counts
                    mode_counts[mode] = self._safe_int(mode_counts.get(mode, 0), 0) + 1
                instruction_recorded_mode = mode
                instruction_observability_recorded = True

            hash_gate_bypassed = False
            if not hash_match and not benchmark_observe_enabled:
                quality_metrics = _with_tuning_metrics(self._new_autofix_quality_metrics(
                    proposal_id=str(proposal.get("proposal_id", "")),
                    generator_type=str(proposal.get("generator_type", "unknown")),
                    anchors_match=True,
                    hash_match=False,
                    syntax_check_passed=True,
                    applied=False,
                    rejected_reason="base hash mismatch",
                    validation_errors=[],
                ))
                self._mark_autofix_proposal_failure(session, proposal, error_code="BASE_HASH_MISMATCH", quality_metrics=quality_metrics)
                _record_instruction_observability()
                raise self._autofix_apply_error(
                    "Autofix base hash mismatch. Re-run analysis and prepare a new diff.",
                    error_code="BASE_HASH_MISMATCH",
                    quality_metrics=quality_metrics,
                )
            if not hash_match and benchmark_observe_enabled:
                hash_gate_bypassed = True

            base_hunks = list(proposal.get("hunks", []) or [])
            apply_hunks = list(base_hunks)
            structured_instruction_hunks: List[Dict[str, Any]] = []
            instruction_hunks_active = False
            structured_instruction_raw = proposal.get("_structured_instruction")
            structured_instruction_enabled_for_request = bool(
                self.autofix_structured_instruction_enabled or benchmark_structured_instruction_forced
            )
            if structured_instruction_enabled_for_request and isinstance(structured_instruction_raw, dict):
                instruction_mode = "attempted"
                instruction_path_reason = "attempted"
                instruction_failure_stage = "none"
                with session["lock"]:
                    stats = self._autofix_session_stats(session)
                    stats["instruction_attempt_count"] = self._safe_int(
                        stats.get("instruction_attempt_count", 0), 0
                    ) + 1
                normalized_instruction = _compat_autofix_symbol(
                    "normalize_instruction",
                    _default_normalize_instruction,
                )(structured_instruction_raw)
                operations = normalized_instruction.get("operations", []) if isinstance(
                    normalized_instruction.get("operations"), list
                ) else []
                op_names = [
                    str((op or {}).get("operation", "") or "")
                    for op in operations
                    if isinstance(op, dict) and str((op or {}).get("operation", "") or "")
                ]
                instruction_operation = ",".join(sorted(set(op_names))) if op_names else str(
                    normalized_instruction.get("operation", "") or ""
                )
                instruction_operation_count = len(operations)
                if instruction_operation_count > 0:
                    with session["lock"]:
                        stats = self._autofix_session_stats(session)
                        stats["instruction_operation_total_count"] = self._safe_int(
                            stats.get("instruction_operation_total_count", 0), 0
                        ) + instruction_operation_count
                valid_instruction, instruction_validation_errors = _compat_autofix_symbol(
                    "validate_instruction",
                    _default_validate_instruction,
                )(normalized_instruction)
                target_file = str((normalized_instruction.get("target", {}) or {}).get("file", "") or "")
                if target_file and target_file != normalized_file:
                    valid_instruction = False
                    instruction_validation_errors.append("target.file must match proposal file")
                if valid_instruction:
                    try:
                        structured_instruction_hunks = _compat_autofix_symbol(
                            "instruction_to_hunks",
                            _default_instruction_to_hunks,
                        )(normalized_instruction)
                        instruction_candidate_hunk_count = len([h for h in structured_instruction_hunks if isinstance(h, dict)])
                        apply_hunks = list(structured_instruction_hunks)
                        instruction_hunks_active = True
                    except Exception as exc:
                        instruction_validation_errors.append(f"instruction_to_hunks failed: {exc}")
                        instruction_mode = "fallback_hunks"
                        instruction_path_reason = "fallback_hunks"
                        instruction_failure_stage = "convert"
                        with session["lock"]:
                            stats = self._autofix_session_stats(session)
                            stats["instruction_fallback_to_hunk_count"] = self._safe_int(
                                stats.get("instruction_fallback_to_hunk_count", 0), 0
                            ) + 1
                            stats["instruction_convert_fail_count"] = self._safe_int(
                                stats.get("instruction_convert_fail_count", 0), 0
                            ) + 1
                        apply_hunks = list(base_hunks)
                        instruction_hunks_active = False
                else:
                    instruction_mode = "fallback_hunks"
                    instruction_path_reason = "validation_failed"
                    instruction_failure_stage = "validate"
                    with session["lock"]:
                        stats = self._autofix_session_stats(session)
                        stats["instruction_validation_fail_count"] = self._safe_int(
                            stats.get("instruction_validation_fail_count", 0), 0
                        ) + 1
                        stats["instruction_fallback_to_hunk_count"] = self._safe_int(
                            stats.get("instruction_fallback_to_hunk_count", 0), 0
                        ) + 1
                        fail_by_reason = stats.get("instruction_validation_fail_by_reason", {})
                        if not isinstance(fail_by_reason, dict):
                            fail_by_reason = {}
                            stats["instruction_validation_fail_by_reason"] = fail_by_reason
                        for err in instruction_validation_errors:
                            reason_key = str(err or "").strip() or "unknown"
                            fail_by_reason[reason_key] = self._safe_int(fail_by_reason.get(reason_key, 0), 0) + 1
                    apply_hunks = list(base_hunks)
                    instruction_hunks_active = False

            anchors_match = True
            normalized_anchor_match = False
            anchor_errors = []
            locator_mode = "anchor_exact"
            token_fallback_attempted = False
            token_fallback_confidence = 0.0
            token_fallback_candidates = 0
            for h in apply_hunks:
                if not isinstance(h, dict):
                    continue
                start_line = self._safe_int(h.get("start_line", 1), 1)
                before_expected = str(h.get("context_before", ""))
                after_expected = str(h.get("context_after", ""))
                before_actual = current_lines[start_line - 2] if start_line >= 2 and (start_line - 2) < len(current_lines) else ""
                after_actual = current_lines[start_line - 1] if (start_line - 1) < len(current_lines) and start_line >= 1 else ""
                if before_expected and before_actual != before_expected:
                    if normalize_anchor_text(before_actual) == normalize_anchor_text(before_expected):
                        normalized_anchor_match = True
                    else:
                        anchors_match = False
                        anchor_errors.append(f"context_before mismatch at line {start_line}")
                if after_expected and after_actual != after_expected:
                    if normalize_anchor_text(after_actual) == normalize_anchor_text(after_expected):
                        normalized_anchor_match = True
                    else:
                        anchors_match = False
                        anchor_errors.append(f"context_after mismatch at line {start_line}")
            if anchors_match and normalized_anchor_match:
                locator_mode = "anchor_normalized"
            if not anchors_match:
                with session["lock"]:
                    stats = self._autofix_session_stats(session)
                    stats["anchor_mismatch_count"] = self._safe_int(stats.get("anchor_mismatch_count", 0), 0) + 1
                token_fallback_attempted = True
                with session["lock"]:
                    stats = self._autofix_session_stats(session)
                    stats["token_fallback_attempt_count"] = self._safe_int(stats.get("token_fallback_attempt_count", 0), 0) + 1
                fallback = self._attempt_token_anchor_fallback(
                    current_lines,
                    [h for h in apply_hunks if isinstance(h, dict)],
                    min_confidence=token_min_confidence_used,
                    min_gap=token_min_gap_used,
                    max_line_drift=token_max_line_drift_used,
                    prefer_nearest_on_tie=token_prefer_nearest_tie_used,
                    hint_bias=token_hint_bias_used,
                    force_pick_nearest_on_ambiguous=token_force_nearest_on_ambiguous_used,
                )
                token_fallback_confidence = float(fallback.get("confidence", 0.0) or 0.0)
                token_fallback_candidates = self._safe_int(fallback.get("candidate_count", 0), 0)
                if bool(fallback.get("success", False)):
                    apply_hunks = list(fallback.get("resolved_hunks", []) or [])
                    anchors_match = True
                    locator_mode = "token_fallback"
                    with session["lock"]:
                        stats = self._autofix_session_stats(session)
                        stats["token_fallback_success_count"] = (
                            self._safe_int(stats.get("token_fallback_success_count", 0), 0) + 1
                        )
                    anchor_errors = []
                else:
                    fallback_reasons = [str(e) for e in (fallback.get("errors", []) or [])]
                    if token_fallback_candidates >= 2 or any("ambiguous_candidates" in e for e in fallback_reasons):
                        with session["lock"]:
                            stats = self._autofix_session_stats(session)
                            stats["token_fallback_ambiguous_count"] = (
                                self._safe_int(stats.get("token_fallback_ambiguous_count", 0), 0) + 1
                            )
                    anchor_errors.extend(fallback_reasons)

            if not anchors_match:
                quality_metrics = _with_tuning_metrics(self._new_autofix_quality_metrics(
                    proposal_id=str(proposal.get("proposal_id", "")),
                    generator_type=str(proposal.get("generator_type", "unknown")),
                    anchors_match=False,
                    hash_match=hash_match,
                    syntax_check_passed=True,
                    applied=False,
                    rejected_reason="anchor mismatch",
                    validation_errors=list(anchor_errors),
                    locator_mode=locator_mode,
                    token_fallback_attempted=token_fallback_attempted,
                    token_fallback_confidence=token_fallback_confidence,
                    token_fallback_candidates=token_fallback_candidates,
                ))
                self._mark_autofix_proposal_failure(session, proposal, error_code="ANCHOR_MISMATCH", quality_metrics=quality_metrics)
                _record_instruction_observability()
                raise self._autofix_apply_error(
                    "Autofix anchor mismatch. Source file changed since diff preparation.",
                    error_code="ANCHOR_MISMATCH",
                    quality_metrics=quality_metrics,
                )

            valid_apply_hunks = [h for h in apply_hunks if isinstance(h, dict)]
            is_multi_hunk_apply = len(valid_apply_hunks) >= 2
            if is_multi_hunk_apply:
                with session["lock"]:
                    stats = self._autofix_session_stats(session)
                    stats["multi_hunk_attempt_count"] = self._safe_int(stats.get("multi_hunk_attempt_count", 0), 0) + 1
            if len(valid_apply_hunks) > 3:
                apply_engine_reason = "too_many_hunks"
                validation_errors = [f"apply engine failed: {apply_engine_reason}"]
                if is_multi_hunk_apply:
                    with session["lock"]:
                        stats = self._autofix_session_stats(session)
                        stats["multi_hunk_blocked_count"] = self._safe_int(stats.get("multi_hunk_blocked_count", 0), 0) + 1
                quality_metrics = _with_tuning_metrics(self._new_autofix_quality_metrics(
                    proposal_id=str(proposal.get("proposal_id", "")),
                    generator_type=str(proposal.get("generator_type", "unknown")),
                    anchors_match=True,
                    hash_match=hash_match,
                    syntax_check_passed=True,
                    applied=False,
                    rejected_reason="apply engine failed",
                    validation_errors=validation_errors,
                    locator_mode=locator_mode,
                    apply_engine_mode="failed",
                    apply_engine_fallback_reason=apply_engine_reason,
                    token_fallback_attempted=token_fallback_attempted,
                    token_fallback_confidence=token_fallback_confidence,
                    token_fallback_candidates=token_fallback_candidates,
                ))
                self._mark_autofix_proposal_failure(
                    session,
                    proposal,
                    error_code="APPLY_ENGINE_FAILED",
                    quality_metrics=quality_metrics,
                )
                _record_instruction_observability()
                raise self._autofix_apply_error(
                    "Autofix apply engine failed: too_many_hunks",
                    error_code="APPLY_ENGINE_FAILED",
                    quality_metrics=quality_metrics,
                )
            if self._hunk_ranges_overlap(valid_apply_hunks):
                apply_engine_reason = "overlapping_hunks"
                validation_errors = [f"apply engine failed: {apply_engine_reason}"]
                if is_multi_hunk_apply:
                    with session["lock"]:
                        stats = self._autofix_session_stats(session)
                        stats["multi_hunk_blocked_count"] = self._safe_int(stats.get("multi_hunk_blocked_count", 0), 0) + 1
                quality_metrics = _with_tuning_metrics(self._new_autofix_quality_metrics(
                    proposal_id=str(proposal.get("proposal_id", "")),
                    generator_type=str(proposal.get("generator_type", "unknown")),
                    anchors_match=True,
                    hash_match=hash_match,
                    syntax_check_passed=True,
                    applied=False,
                    rejected_reason="apply engine failed",
                    validation_errors=validation_errors,
                    locator_mode=locator_mode,
                    apply_engine_mode="failed",
                    apply_engine_fallback_reason=apply_engine_reason,
                    token_fallback_attempted=token_fallback_attempted,
                    token_fallback_confidence=token_fallback_confidence,
                    token_fallback_candidates=token_fallback_candidates,
                ))
                self._mark_autofix_proposal_failure(
                    session,
                    proposal,
                    error_code="APPLY_ENGINE_FAILED",
                    quality_metrics=quality_metrics,
                )
                _record_instruction_observability()
                raise self._autofix_apply_error(
                    "Autofix apply engine failed: overlapping_hunks",
                    error_code="APPLY_ENGINE_FAILED",
                    quality_metrics=quality_metrics,
                )

            candidate_content = str(proposal.get("_candidate_content", ""))
            if not candidate_content:
                _record_instruction_observability()
                raise RuntimeError("Autofix proposal candidate content is missing")

            engine_result = _compat_autofix_symbol(
                "apply_with_engine",
                _default_apply_with_engine,
            )(
                base_text=current_content,
                hunks=[h for h in apply_hunks if isinstance(h, dict)],
                anchor_line=self._safe_int(
                    (apply_hunks[0] if apply_hunks and isinstance(apply_hunks[0], dict) else {}).get("start_line", 1),
                    1,
                ),
                generator_type=str(proposal.get("generator_type", "unknown")),
                options={
                    "max_line_drift": max(50, min(300, len(current_lines))),
                    "max_hunks_per_apply": 3,
                },
            )
            apply_engine_mode = str(engine_result.get("engine_mode", "failed") or "failed")
            apply_engine_fallback_reason = str(engine_result.get("fallback_reason", "") or "")
            if bool(engine_result.get("ok", False)):
                engine_text = str(engine_result.get("patched_text", ""))
                if engine_text:
                    candidate_content = engine_text
                if instruction_hunks_active:
                    instruction_mode = "applied"
                    instruction_apply_success = True
                    instruction_path_reason = "applied"
                    instruction_failure_stage = "none"
                    instruction_applied_hunk_count = self._safe_int(
                        (engine_result.get("diagnostics", {}) or {}).get("applied_hunk_count", 0),
                        0,
                    )
                    if instruction_applied_hunk_count <= 0:
                        instruction_applied_hunk_count = len([h for h in structured_instruction_hunks if isinstance(h, dict)])
                    with session["lock"]:
                        stats = self._autofix_session_stats(session)
                        stats["instruction_apply_success_count"] = self._safe_int(
                            stats.get("instruction_apply_success_count", 0), 0
                        ) + 1
            else:
                apply_engine_mode = "failed"
                reason = apply_engine_fallback_reason or "apply_failed"
                if instruction_hunks_active:
                    instruction_mode = "fallback_hunks"
                    instruction_apply_success = False
                    instruction_path_reason = "engine_failed"
                    instruction_failure_stage = "apply"
                    instruction_validation_errors.append(f"instruction apply failed: {reason}")
                    with session["lock"]:
                        stats = self._autofix_session_stats(session)
                        stats["instruction_fallback_to_hunk_count"] = self._safe_int(
                            stats.get("instruction_fallback_to_hunk_count", 0), 0
                        ) + 1
                        stats["instruction_engine_fail_count"] = self._safe_int(
                            stats.get("instruction_engine_fail_count", 0), 0
                        ) + 1
                    legacy_engine = _compat_autofix_symbol(
                        "apply_with_engine",
                        _default_apply_with_engine,
                    )(
                        base_text=current_content,
                        hunks=[h for h in base_hunks if isinstance(h, dict)],
                        anchor_line=self._safe_int(
                            (base_hunks[0] if base_hunks and isinstance(base_hunks[0], dict) else {}).get("start_line", 1),
                            1,
                        ),
                        generator_type=str(proposal.get("generator_type", "unknown")),
                        options={
                            "max_line_drift": max(50, min(300, len(current_lines))),
                            "max_hunks_per_apply": 3,
                        },
                    )
                    if bool(legacy_engine.get("ok", False)):
                        legacy_text = str(legacy_engine.get("patched_text", ""))
                        if legacy_text:
                            candidate_content = legacy_text
                        apply_engine_mode = str(legacy_engine.get("engine_mode", "failed") or "failed")
                        apply_engine_fallback_reason = str(legacy_engine.get("fallback_reason", "") or "")
                        instruction_hunks_active = False
                    else:
                        reason = str(legacy_engine.get("fallback_reason", "") or reason or "apply_failed")
                        apply_engine_mode = "failed"
                        apply_engine_fallback_reason = reason
                if apply_engine_mode == "failed":
                    anchor_errors.append(f"apply engine failed: {reason}")
                if apply_engine_mode == "failed" and is_multi_hunk_apply and reason in (
                    "too_many_hunks",
                    "overlapping_hunks",
                    "hunks_span_multiple_blocks",
                    "anchor_context_not_unique",
                ):
                    with session["lock"]:
                        stats = self._autofix_session_stats(session)
                        stats["multi_hunk_blocked_count"] = self._safe_int(stats.get("multi_hunk_blocked_count", 0), 0) + 1
                if apply_engine_mode == "failed":
                    quality_metrics = _with_tuning_metrics(self._new_autofix_quality_metrics(
                        proposal_id=str(proposal.get("proposal_id", "")),
                        generator_type=str(proposal.get("generator_type", "unknown")),
                        anchors_match=anchors_match,
                        hash_match=hash_match,
                        syntax_check_passed=True,
                        applied=False,
                        rejected_reason="apply engine failed",
                        validation_errors=list(anchor_errors),
                        locator_mode=locator_mode,
                        apply_engine_mode="failed",
                        apply_engine_fallback_reason=reason,
                        token_fallback_attempted=token_fallback_attempted,
                        token_fallback_confidence=token_fallback_confidence,
                        token_fallback_candidates=token_fallback_candidates,
                    ))
                    self._mark_autofix_proposal_failure(
                        session,
                        proposal,
                        error_code="APPLY_ENGINE_FAILED",
                        quality_metrics=quality_metrics,
                    )
                    _record_instruction_observability()
                    raise self._autofix_apply_error(
                        f"Autofix apply engine failed: {reason}",
                        error_code="APPLY_ENGINE_FAILED",
                        quality_metrics=quality_metrics,
                    )

            validation = {
                "anchors_match": anchors_match,
                "hash_match": hash_match,
                "benchmark_observe_mode": normalized_observe_mode,
                "hash_gate_bypassed": hash_gate_bypassed,
                "token_min_confidence_used": float(token_min_confidence_used),
                "token_min_gap_used": float(token_min_gap_used),
                "token_max_line_drift_used": int(token_max_line_drift_used),
                "benchmark_tuning_applied": bool(benchmark_tuning_applied),
                "token_prefer_nearest_tie_used": bool(token_prefer_nearest_tie_used),
                "token_hint_bias_used": float(token_hint_bias_used),
                "token_force_nearest_on_ambiguous_used": bool(token_force_nearest_on_ambiguous_used),
                "benchmark_structured_instruction_forced": bool(benchmark_structured_instruction_forced),
                "syntax_check_passed": self._basic_syntax_check(candidate_content),
                "semantic_check_passed": True,
                "semantic_blocked_reason": "",
                "semantic_violation_count": 0,
                "heuristic_regression_count": 0,
                "ctrlpp_regression_count": 0,
                "errors": list(anchor_errors),
                "locator_mode": locator_mode,
                "apply_engine_mode": apply_engine_mode,
                "apply_engine_fallback_reason": apply_engine_fallback_reason,
                "token_fallback_attempted": token_fallback_attempted,
                "token_fallback_confidence": token_fallback_confidence,
                "token_fallback_candidates": token_fallback_candidates,
                "syntax_check_skipped_reason": "",
                "ctrlpp_regression_skipped_reason": "",
                "instruction_mode": str(instruction_mode or "off"),
                "instruction_validation_errors": list(instruction_validation_errors),
                "instruction_operation": str(instruction_operation or ""),
                "instruction_operation_count": int(instruction_operation_count or 0),
                "instruction_apply_success": bool(instruction_apply_success),
                "instruction_path_reason": str(instruction_path_reason or "off"),
                "instruction_failure_stage": str(instruction_failure_stage or "none"),
                "instruction_candidate_hunk_count": int(instruction_candidate_hunk_count or 0),
                "instruction_applied_hunk_count": int(instruction_applied_hunk_count or 0),
            }
            if not is_ctl_target:
                validation["syntax_check_passed"] = True
                validation["syntax_check_skipped_reason"] = "non_ctl_file"
            if not validation["syntax_check_passed"]:
                quality_metrics = _with_tuning_metrics(self._new_autofix_quality_metrics(
                    proposal_id=str(proposal.get("proposal_id", "")),
                    generator_type=str(proposal.get("generator_type", "unknown")),
                    anchors_match=anchors_match,
                    hash_match=hash_match,
                    syntax_check_passed=False,
                    applied=False,
                    rejected_reason="syntax precheck failed",
                    validation_errors=list(validation["errors"]),
                    locator_mode=locator_mode,
                    apply_engine_mode=apply_engine_mode,
                    apply_engine_fallback_reason=apply_engine_fallback_reason,
                    token_fallback_attempted=token_fallback_attempted,
                    token_fallback_confidence=token_fallback_confidence,
                    token_fallback_candidates=token_fallback_candidates,
                ))
                self._mark_autofix_proposal_failure(
                    session,
                    proposal,
                    error_code="SYNTAX_PRECHECK_FAILED",
                    quality_metrics=quality_metrics,
                )
                _record_instruction_observability()
                raise self._autofix_apply_error(
                    "Autofix syntax precheck failed (brace/parenthesis balance)",
                    error_code="SYNTAX_PRECHECK_FAILED",
                    quality_metrics=quality_metrics,
                )

            generator_type = str(proposal.get("generator_type", "unknown") or "unknown").lower()
            if generator_type == "rule":
                with session["lock"]:
                    stats = self._autofix_session_stats(session)
                    stats["semantic_guard_checked_count"] = (
                        self._safe_int(stats.get("semantic_guard_checked_count", 0), 0) + 1
                    )

                semantic_reference = str(proposal.get("_candidate_content", "") or "")
                if not semantic_reference:
                    semantic_reference = candidate_content
                semantic_result = evaluate_semantic_delta(semantic_reference, candidate_content)
                semantic_blocked = bool(semantic_result.get("blocked", False))
                semantic_reason = str(semantic_result.get("reason", "") or "")
                semantic_violations = [str(v) for v in (semantic_result.get("violations", []) or []) if str(v).strip()]
                semantic_violation_count = len(semantic_violations)
                validation["semantic_check_passed"] = not semantic_blocked
                validation["semantic_blocked_reason"] = semantic_reason
                validation["semantic_violation_count"] = semantic_violation_count

                if semantic_blocked:
                    validation["errors"].append(
                        f"semantic guard blocked ({semantic_reason}): {', '.join(semantic_violations)}"
                    )
                    with session["lock"]:
                        stats = self._autofix_session_stats(session)
                        stats["semantic_guard_blocked_count"] = (
                            self._safe_int(stats.get("semantic_guard_blocked_count", 0), 0) + 1
                        )
                    quality_metrics = _with_tuning_metrics(self._new_autofix_quality_metrics(
                        proposal_id=str(proposal.get("proposal_id", "")),
                        generator_type=str(proposal.get("generator_type", "unknown")),
                        anchors_match=anchors_match,
                        hash_match=hash_match,
                        syntax_check_passed=bool(validation["syntax_check_passed"]),
                        semantic_check_passed=False,
                        semantic_blocked_reason=semantic_reason,
                        semantic_violation_count=semantic_violation_count,
                        applied=False,
                        rejected_reason="semantic guard blocked",
                        validation_errors=list(validation["errors"]),
                        locator_mode=locator_mode,
                        apply_engine_mode=apply_engine_mode,
                        apply_engine_fallback_reason=apply_engine_fallback_reason,
                        token_fallback_attempted=token_fallback_attempted,
                        token_fallback_confidence=token_fallback_confidence,
                        token_fallback_candidates=token_fallback_candidates,
                    ))
                    self._mark_autofix_proposal_failure(
                        session,
                        proposal,
                        error_code="SEMANTIC_GUARD_BLOCKED",
                        quality_metrics=quality_metrics,
                    )
                    _record_instruction_observability()
                    raise self._autofix_apply_error(
                        "Autofix semantic guard blocked high-risk token delta",
                        error_code="SEMANTIC_GUARD_BLOCKED",
                        quality_metrics=quality_metrics,
                    )

            pre_internal = self.checker.analyze_raw_code(source_path, current_content, file_type="Server")
            post_internal = self.checker.analyze_raw_code(source_path, candidate_content, file_type="Server")
            pre_count = self._count_p1_findings(pre_internal)
            post_count = self._count_p1_findings(post_internal)
            regression_count = max(0, post_count - pre_count)
            validation["heuristic_regression_count"] = regression_count

            if check_ctrlpp_regression and not is_ctl_target:
                validation["ctrlpp_regression_skipped_reason"] = "non_ctl_file"
            elif check_ctrlpp_regression:
                tmp_ctrl_fd = None
                tmp_ctrl_path = ""
                try:
                    with self._ctrlpp_semaphore:
                        pre_ctrlpp = self.ctrl_tool.run_check(source_path, current_content, enabled=True)
                    tmp_ctrl_fd, tmp_ctrl_path = tempfile.mkstemp(prefix="autofix_ctrlpp_", suffix=".ctl")
                    with os.fdopen(tmp_ctrl_fd, "w", encoding="utf-8") as tmp_ctrl:
                        tmp_ctrl.write(candidate_content)
                    tmp_ctrl_fd = None
                    with self._ctrlpp_semaphore:
                        post_ctrlpp = self.ctrl_tool.run_check(tmp_ctrl_path, candidate_content, enabled=True)
                    pre_ctrlpp_count = self._count_ctrlpp_findings(pre_ctrlpp or [])
                    post_ctrlpp_count = self._count_ctrlpp_findings(post_ctrlpp or [])
                    validation["ctrlpp_regression_count"] = max(0, post_ctrlpp_count - pre_ctrlpp_count)
                except Exception as exc:
                    validation["errors"].append(f"ctrlpp regression check skipped: {exc}")
                finally:
                    if tmp_ctrl_fd is not None:
                        try:
                            os.close(tmp_ctrl_fd)
                        except OSError:
                            pass
                    if tmp_ctrl_path and os.path.exists(tmp_ctrl_path):
                        try:
                            os.remove(tmp_ctrl_path)
                        except OSError:
                            pass

            if block_on_regression and validation["ctrlpp_regression_count"] > 0:
                validation["errors"].append(
                    f"ctrlpp regression detected (+{validation['ctrlpp_regression_count']})"
                )
                quality_metrics = _with_tuning_metrics(self._new_autofix_quality_metrics(
                    proposal_id=str(proposal.get("proposal_id", "")),
                    generator_type=str(proposal.get("generator_type", "unknown")),
                    anchors_match=anchors_match,
                    hash_match=hash_match,
                    syntax_check_passed=bool(validation["syntax_check_passed"]),
                    semantic_check_passed=bool(validation.get("semantic_check_passed", True)),
                    semantic_blocked_reason=str(validation.get("semantic_blocked_reason", "") or ""),
                    semantic_violation_count=self._safe_int(validation.get("semantic_violation_count", 0), 0),
                    heuristic_regression_count=self._safe_int(validation["heuristic_regression_count"], 0),
                    ctrlpp_regression_count=self._safe_int(validation["ctrlpp_regression_count"], 0),
                    applied=False,
                    rejected_reason="ctrlpp regression blocked",
                    validation_errors=list(validation["errors"]),
                    locator_mode=locator_mode,
                    apply_engine_mode=apply_engine_mode,
                    apply_engine_fallback_reason=apply_engine_fallback_reason,
                    token_fallback_attempted=token_fallback_attempted,
                    token_fallback_confidence=token_fallback_confidence,
                    token_fallback_candidates=token_fallback_candidates,
                ))
                self._mark_autofix_proposal_failure(session, proposal, error_code="REGRESSION_BLOCKED", quality_metrics=quality_metrics)
                _record_instruction_observability()
                raise self._autofix_apply_error(
                    "Autofix validation failed: CtrlppCheck regression detected",
                    error_code="REGRESSION_BLOCKED",
                    quality_metrics=quality_metrics,
                )

            backup_dir = os.path.join(target_output_dir, "autofix_backups")
            os.makedirs(backup_dir, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup_name = f"{normalized_file}.{ts}.{str(proposal.get('proposal_id', ''))[:8]}.bak"
            backup_path = os.path.join(backup_dir, backup_name)
            shutil.copy2(source_path, backup_path)

            tmp_fd, tmp_path = tempfile.mkstemp(prefix="autofix_", suffix=".tmp", dir=os.path.dirname(source_path) or None)
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as tmp:
                    tmp.write(candidate_content)
                os.replace(tmp_path, source_path)
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass

            rolled_back = False
            if block_on_regression and regression_count > 0:
                try:
                    shutil.copy2(backup_path, source_path)
                    rolled_back = True
                finally:
                    validation["errors"].append(
                        f"heuristic regression detected (+{regression_count}); changes rolled back"
                    )
                quality_metrics = _with_tuning_metrics(self._new_autofix_quality_metrics(
                    proposal_id=str(proposal.get("proposal_id", "")),
                    generator_type=str(proposal.get("generator_type", "unknown")),
                    anchors_match=anchors_match,
                    hash_match=hash_match,
                    syntax_check_passed=bool(validation["syntax_check_passed"]),
                    semantic_check_passed=bool(validation.get("semantic_check_passed", True)),
                    semantic_blocked_reason=str(validation.get("semantic_blocked_reason", "") or ""),
                    semantic_violation_count=self._safe_int(validation.get("semantic_violation_count", 0), 0),
                    heuristic_regression_count=self._safe_int(validation["heuristic_regression_count"], 0),
                    ctrlpp_regression_count=self._safe_int(validation["ctrlpp_regression_count"], 0),
                    applied=False,
                    rejected_reason="heuristic regression blocked",
                    validation_errors=list(validation["errors"]),
                    locator_mode=locator_mode,
                    apply_engine_mode=apply_engine_mode,
                    apply_engine_fallback_reason=apply_engine_fallback_reason,
                    token_fallback_attempted=token_fallback_attempted,
                    token_fallback_confidence=token_fallback_confidence,
                    token_fallback_candidates=token_fallback_candidates,
                ))
                self._mark_autofix_proposal_failure(session, proposal, error_code="REGRESSION_BLOCKED", quality_metrics=quality_metrics)
                _record_instruction_observability()
                raise self._autofix_apply_error(
                    "Autofix validation failed: heuristic regression detected",
                    error_code="REGRESSION_BLOCKED",
                    quality_metrics=quality_metrics,
                )

            quality_metrics = _with_tuning_metrics(self._new_autofix_quality_metrics(
                proposal_id=str(proposal.get("proposal_id", "")),
                generator_type=str(proposal.get("generator_type", "unknown")),
                anchors_match=anchors_match,
                hash_match=hash_match,
                syntax_check_passed=bool(validation["syntax_check_passed"]),
                semantic_check_passed=bool(validation.get("semantic_check_passed", True)),
                semantic_blocked_reason=str(validation.get("semantic_blocked_reason", "") or ""),
                semantic_violation_count=self._safe_int(validation.get("semantic_violation_count", 0), 0),
                heuristic_regression_count=self._safe_int(validation["heuristic_regression_count"], 0),
                ctrlpp_regression_count=self._safe_int(validation["ctrlpp_regression_count"], 0),
                applied=True,
                rejected_reason="",
                validation_errors=list(validation["errors"]),
                locator_mode=locator_mode,
                apply_engine_mode=apply_engine_mode,
                apply_engine_fallback_reason=apply_engine_fallback_reason,
                token_fallback_attempted=token_fallback_attempted,
                token_fallback_confidence=token_fallback_confidence,
                token_fallback_candidates=token_fallback_candidates,
            ))

            with session["lock"]:
                cached["original_content"] = candidate_content
                cached["source_hash"] = self._sha256_text(candidate_content)
                cached["updated_at"] = self._iso_now()
                proposal["status"] = "Applied"
                proposal["applied_at"] = self._iso_now()
                proposal["validation"] = dict(validation)
                proposal["quality_metrics"] = dict(quality_metrics)
                stats = self._autofix_session_stats(session)
                if apply_engine_mode == "structure_apply":
                    stats["apply_engine_structure_success_count"] = (
                        self._safe_int(stats.get("apply_engine_structure_success_count", 0), 0) + 1
                    )
                elif apply_engine_mode == "text_fallback":
                    stats["apply_engine_text_fallback_count"] = (
                        self._safe_int(stats.get("apply_engine_text_fallback_count", 0), 0) + 1
                    )
                if str(proposal.get("_prepare_mode", "")) == "compare":
                    stats["compare_apply_count"] = self._safe_int(stats.get("compare_apply_count", 0), 0) + 1
                    selected = stats.setdefault("selected_generator_counts", {"rule": 0, "llm": 0})
                    if isinstance(selected, dict):
                        gen = str(proposal.get("generator_type", "") or "").lower()
                        if gen in ("rule", "llm"):
                            selected[gen] = self._safe_int(selected.get(gen, 0), 0) + 1
                selected_engine = stats.setdefault("selected_apply_engine_mode", {"structure_apply": 0, "text_fallback": 0})
                if isinstance(selected_engine, dict) and apply_engine_mode in ("structure_apply", "text_fallback"):
                    selected_engine[apply_engine_mode] = self._safe_int(selected_engine.get(apply_engine_mode, 0), 0) + 1
                if is_multi_hunk_apply:
                    stats["multi_hunk_success_count"] = self._safe_int(stats.get("multi_hunk_success_count", 0), 0) + 1
                self._touch_review_session(session)

            audit_entry = {
                "applied_by": "api",
                "applied_at": self._iso_now(),
                "proposal_id": proposal.get("proposal_id", ""),
                "file": normalized_file,
                "file_backup_path": backup_path,
                "generator_type": proposal.get("generator_type", "unknown"),
                "validation_summary": {
                    "hash_match": validation["hash_match"],
                    "benchmark_observe_mode": validation.get("benchmark_observe_mode", "strict_hash"),
                    "hash_gate_bypassed": bool(validation.get("hash_gate_bypassed", False)),
                    "anchors_match": validation["anchors_match"],
                    "syntax_check_passed": validation["syntax_check_passed"],
                    "semantic_check_passed": bool(validation.get("semantic_check_passed", True)),
                    "semantic_blocked_reason": str(validation.get("semantic_blocked_reason", "") or ""),
                    "semantic_violation_count": self._safe_int(validation.get("semantic_violation_count", 0), 0),
                    "apply_engine_mode": validation.get("apply_engine_mode", ""),
                    "apply_engine_fallback_reason": validation.get("apply_engine_fallback_reason", ""),
                    "instruction_mode": validation.get("instruction_mode", "off"),
                    "instruction_operation": validation.get("instruction_operation", ""),
                    "instruction_apply_success": bool(validation.get("instruction_apply_success", False)),
                    "instruction_path_reason": validation.get("instruction_path_reason", "off"),
                    "instruction_failure_stage": validation.get("instruction_failure_stage", "none"),
                    "instruction_candidate_hunk_count": self._safe_int(validation.get("instruction_candidate_hunk_count", 0), 0),
                    "instruction_applied_hunk_count": self._safe_int(validation.get("instruction_applied_hunk_count", 0), 0),
                    "heuristic_regression_count": validation["heuristic_regression_count"],
                    "ctrlpp_regression_count": validation["ctrlpp_regression_count"],
                    "errors": validation["errors"],
                },
                "quality_metrics": quality_metrics,
                "rolled_back": rolled_back,
            }
            audit_log_path = self._append_autofix_audit_entry(target_output_dir, audit_entry)
            self._last_output_dir = target_output_dir

            _record_instruction_observability()
            return {
                "ok": True,
                "applied": True,
                "file": normalized_file,
                "proposal_id": proposal.get("proposal_id", ""),
                "output_dir": target_output_dir,
                "backup_path": backup_path,
                "audit_log_path": audit_log_path,
                "validation": validation,
                "quality_metrics": quality_metrics,
                "reanalysis_summary": {
                    "before_p1_total": pre_count,
                    "after_p1_total": post_count,
                    "delta_p1_total": post_count - pre_count,
                    "ctrlpp_regression_count": validation["ctrlpp_regression_count"],
                },
                "viewer_content": self.get_viewer_content(normalized_file, prefer_source=True),
            }

    def apply_ai_review_to_reviewed_file(
        self,
        file_name: str,
        object_name: str,
        event_name: str,
        review_text: str,
        output_dir: Optional[str] = None,
    ) -> dict:
        target_output_dir, session, resolved_cache_key, cached = self._resolve_review_session_and_file(
            file_name=file_name,
            output_dir=output_dir,
        )
        report_data = cached.get("report_data")
        if not isinstance(report_data, dict):
            raise RuntimeError("Cached report data is invalid")

        file_lock = self._get_session_file_lock(session, resolved_cache_key)
        with file_lock:
            target_obj = str(object_name or "")
            target_event = str(event_name or "Global")
            target_review = str(review_text or "")
            matched = False
            for item in report_data.get("ai_reviews", []):
                if (
                    str(item.get("object", "")) == target_obj
                    and str(item.get("event", "Global")) == target_event
                    and str(item.get("review", "")) == target_review
                ):
                    item["status"] = "Accepted"
                    matched = True

            if not matched:
                raise FileNotFoundError("Matching AI review was not found in cached session")

            reporter = Reporter(config_dir=self.reporter.config_dir)
            reporter.output_base_dir = self.reporter.output_base_dir
            reporter.output_dir = target_output_dir
            reporter.timestamp = os.path.basename(target_output_dir.rstrip("/\\"))
            with self._reporter_semaphore:
                reporter.generate_annotated_txt(
                    cached.get("original_content", ""),
                    report_data,
                    cached.get("reviewed_name") or self._reviewed_name_for_source(resolved_cache_key or os.path.basename(str(file_name or ""))),
                )
            cached["updated_at"] = self._iso_now()
            self._touch_review_session(session)

        self._last_output_dir = target_output_dir

        reviewed_file = cached.get("reviewed_name") or self._reviewed_name_for_source(resolved_cache_key or os.path.basename(str(file_name or "")))
        viewer_content = self.get_viewer_content(resolved_cache_key or os.path.basename(str(file_name or "")))
        applied_blocks = 0
        for ai_item in report_data.get("ai_reviews", []):
            if str(ai_item.get("status", "")).lower() == "accepted":
                applied_blocks += 1
        return {
            "ok": True,
            "applied": True,
            "file": resolved_cache_key or os.path.basename(str(file_name or "")),
            "reviewed_file": reviewed_file,
            "output_dir": target_output_dir,
            "applied_blocks": applied_blocks,
            "viewer_content": viewer_content,
        }
