import collections
import difflib
import json
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple

from core.autofix_instruction import normalize_instruction, validate_instruction


class AutoFixProposalMixin:
    """Host class should provide autofix config, session helpers, and utility methods."""

    def _build_autofix_hunks_for_insertion(
        self,
        original_lines: List[str],
        new_lines: List[str],
        insert_line: int,
        inserted_lines: List[str],
    ) -> List[Dict]:
        line_count = len(original_lines)
        insert_line = max(1, min(max(line_count, 1), int(insert_line or 1)))
        before_line = original_lines[insert_line - 2] if insert_line >= 2 and (insert_line - 2) < line_count else ""
        anchor_line = original_lines[insert_line - 1] if line_count and (insert_line - 1) < line_count else ""
        after_line = original_lines[insert_line] if line_count and insert_line < line_count else ""
        return [
            {
                "start_line": insert_line,
                "end_line": insert_line,
                "context_before": before_line,
                "context_after": anchor_line or after_line,
                "replacement_text": "\n".join(inserted_lines),
            }
        ]

    @staticmethod
    def _build_structured_instruction_from_hunks(
        *,
        proposal: Dict,
        file_name: str,
        object_name: str,
        event_name: str,
    ) -> Optional[Dict]:
        hunks = proposal.get("hunks", []) if isinstance(proposal, dict) else []
        valid_hunks = [h for h in (hunks or []) if isinstance(h, dict)]
        if not valid_hunks:
            return None
        try:
            operations: List[Dict[str, Any]] = []
            for hunk in valid_hunks:
                start_line = max(1, int(hunk.get("start_line", 1) or 1))
                operations.append(
                    {
                        "operation": "replace",
                        "locator": {
                            "kind": "anchor_context",
                            "start_line": start_line,
                            "context_before": str(hunk.get("context_before", "") or ""),
                            "context_after": str(hunk.get("context_after", "") or ""),
                        },
                        "payload": {
                            "code": str(hunk.get("replacement_text", "") or ""),
                        },
                    }
                )
            instruction_raw = {
                "target": {
                    "file": str(file_name or ""),
                    "object": str(object_name or ""),
                    "event": str(event_name or "Global"),
                },
                "operations": operations,
                "safety": {"requires_hash_match": True},
            }
            return normalize_instruction(instruction_raw)
        except Exception:
            return None

    @staticmethod
    def _normalize_autofix_generator_preference(value: Optional[str], fallback: str = "auto") -> str:
        normalized = str(value or fallback or "auto").strip().lower()
        return normalized if normalized in ("auto", "llm", "rule") else str(fallback or "auto")

    @staticmethod
    def _normalize_autofix_prepare_mode(value: Optional[str], fallback: str = "single") -> str:
        normalized = str(value or fallback or "single").strip().lower()
        return normalized if normalized in ("single", "compare") else str(fallback or "single")

    def _build_autofix_proposal_from_candidate(
        self,
        *,
        session_output_dir: str,
        session: Dict,
        file_name: str,
        source_path: str,
        source_content: str,
        candidate_content: str,
        summary: str,
        source_tag: str,
        generator_type: str,
        generator_reason: str,
        risk_level: str,
        quality_preview: Optional[Dict] = None,
        extra_private_fields: Optional[Dict] = None,
        llm_meta: Optional[Dict] = None,
    ) -> Dict:
        source_hash = self._sha256_text(source_content)
        # Use keepends=True so EOF-newline-only changes still produce a visible diff.
        diff_text = "".join(
            difflib.unified_diff(
                source_content.splitlines(keepends=True),
                candidate_content.splitlines(keepends=True),
                fromfile=file_name,
                tofile=f"{file_name} (autofix)",
                n=3,
            )
        )
        if not diff_text and source_content != candidate_content:
            # Fallback for edge cases where the unified diff renderer collapses formatting-only changes.
            diff_text = (
                f"--- {file_name}\n"
                f"+++ {file_name} (autofix)\n"
                "@@ -1 +1 @@\n"
                "-<content differs>\n"
                "+<content differs>\n"
            )

        hunks: List[Dict] = []
        source_lines = source_content.splitlines()
        candidate_lines = candidate_content.splitlines()
        for group in difflib.SequenceMatcher(a=source_lines, b=candidate_lines).get_opcodes():
            tag, i1, i2, j1, j2 = group
            if tag == "equal":
                continue
            start_line = max(1, i1 + 1)
            context_before = source_lines[i1 - 1] if i1 > 0 and (i1 - 1) < len(source_lines) else ""
            context_after = source_lines[i1] if i1 < len(source_lines) else ""
            hunks.append(
                {
                    "start_line": start_line,
                    "end_line": max(start_line, i2),
                    "context_before": context_before,
                    "context_after": context_after,
                    "replacement_text": "\n".join(candidate_lines[j1:j2]),
                }
            )
        if not hunks and source_content != candidate_content:
            hunks = [
                {
                    "start_line": 1,
                    "end_line": max(1, len(source_lines)),
                    "context_before": "",
                    "context_after": source_lines[0] if source_lines else "",
                    "replacement_text": candidate_content,
                }
            ]

        proposal_id = uuid.uuid4().hex
        preview = quality_preview if isinstance(quality_preview, dict) else {}
        preview = {
            "anchors_match": bool(preview.get("anchors_match", True)),
            "hash_match": bool(preview.get("hash_match", True)),
            "syntax_check_passed": bool(preview.get("syntax_check_passed", self._basic_syntax_check(candidate_content))),
            "heuristic_regression_count": self._safe_int(preview.get("heuristic_regression_count", 0), 0),
            "ctrlpp_regression_count": self._safe_int(preview.get("ctrlpp_regression_count", 0), 0),
            "errors": list(preview.get("errors", []) or []),
            "blocking_errors": list(preview.get("blocking_errors", preview.get("errors", [])) or []),
            "identifier_reuse_confirmed": bool(preview.get("identifier_reuse_confirmed", True)),
            "allow_apply": bool(preview.get("allow_apply", False)),
            "blocked_reason_codes": list(preview.get("blocked_reason_codes", []) or []),
            "semantic_verdict": str(preview.get("semantic_verdict", "") or ""),
            "estimated_issue_delta": dict(preview.get("estimated_issue_delta", {}) or {}),
            "identifier_reuse_ok": bool(preview.get("identifier_reuse_ok", preview.get("identifier_reuse_confirmed", True))),
            "placeholder_free": bool(preview.get("placeholder_free", True)),
        }
        quality_preview_payload = self._new_autofix_quality_metrics(
            proposal_id=proposal_id,
            generator_type=generator_type,
            anchors_match=preview.get("anchors_match", True),
            hash_match=preview.get("hash_match", True),
            syntax_check_passed=preview.get("syntax_check_passed", True),
            heuristic_regression_count=preview.get("heuristic_regression_count", 0),
            ctrlpp_regression_count=preview.get("ctrlpp_regression_count", 0),
            applied=False,
            rejected_reason="",
            validation_errors=list(preview.get("errors", []) or []),
            blocking_errors=list(preview.get("blocking_errors", []) or []),
            identifier_reuse_confirmed=bool(preview.get("identifier_reuse_confirmed", True)),
            allow_apply=bool(preview.get("allow_apply", False)),
            blocked_reason_codes=list(preview.get("blocked_reason_codes", []) or []),
            semantic_verdict=str(preview.get("semantic_verdict", "") or ""),
            estimated_issue_delta=dict(preview.get("estimated_issue_delta", {}) or {}),
            identifier_reuse_ok=bool(preview.get("identifier_reuse_ok", preview.get("identifier_reuse_confirmed", True))),
            placeholder_free=bool(preview.get("placeholder_free", True)),
        )
        proposal = {
            "proposal_id": proposal_id,
            "session_id": session_output_dir,
            "output_dir": session_output_dir,
            "file": file_name,
            "source": source_tag,
            "base_hash": source_hash,
            "summary": str(summary or "").strip(),
            "unified_diff": diff_text,
            "hunks": hunks,
            "risk_level": str(risk_level or "medium"),
            "status": "Prepared",
            "validation_preview": preview,  # backward compatible
            "quality_preview": quality_preview_payload,
            "generator_type": str(generator_type or "llm"),
            "generator_reason": str(generator_reason or ""),
            "created_at": self._iso_now(),
            "_candidate_content": candidate_content,
        }
        if isinstance(llm_meta, dict):
            proposal["llm_meta"] = json.loads(json.dumps(llm_meta, ensure_ascii=False))
        if isinstance(extra_private_fields, dict):
            for key, val in extra_private_fields.items():
                proposal[key] = val

        with session["lock"]:
            self._store_autofix_proposal(session, proposal)
            self._touch_review_session(session)
        return proposal

    @staticmethod
    def _rule_autofix_normalize_text(text: str) -> Tuple[str, Dict[str, int]]:
        source = str(text or "")
        lines = source.splitlines()
        stats = {"trailing_whitespace_lines": 0, "tabs_normalized": 0, "blank_line_runs_trimmed": 0, "eof_newline_added": 0}

        normalized_lines: List[str] = []
        blank_run = 0
        for raw in lines:
            line = raw
            if line.rstrip(" \t") != line:
                stats["trailing_whitespace_lines"] += 1
                line = line.rstrip(" \t")
            if "\t" in line:
                tab_count = line.count("\t")
                stats["tabs_normalized"] += tab_count
                line = line.replace("\t", "    ")
            if not line.strip():
                blank_run += 1
                if blank_run > 2:
                    stats["blank_line_runs_trimmed"] += 1
                    continue
            else:
                blank_run = 0
            normalized_lines.append(line)

        new_text = "\n".join(normalized_lines)
        if source.endswith("\n"):
            new_text += "\n"
        elif source:
            stats["eof_newline_added"] = 1
            new_text += "\n"
        return new_text, stats

    def _proposal_apply_gate(self, proposal: Dict) -> Tuple[bool, str]:
        if not isinstance(proposal, dict):
            return False, "proposal_missing"
        preview = proposal.get("instruction_preview", {}) if isinstance(proposal.get("instruction_preview", {}), dict) else {}
        if not preview:
            preview = self._instruction_preview_for_proposal(proposal, str(proposal.get("file", "") or ""))
        quality = proposal.get("quality_preview", {}) if isinstance(proposal.get("quality_preview", {}), dict) else {}
        explicit_allow_apply = quality.get("allow_apply", None)
        blocked_reason_codes = [
            str(item or "").strip()
            for item in (quality.get("blocked_reason_codes", []) or [])
            if str(item or "").strip()
        ]
        if isinstance(explicit_allow_apply, bool):
            if explicit_allow_apply:
                return True, ""
            if blocked_reason_codes:
                return False, blocked_reason_codes[0]
            return False, "apply_blocked"
        validation_errors = [
            str(item or "").strip()
            for item in (quality.get("validation_errors", []) or [])
            if str(item or "").strip()
        ]
        blocking_errors = [
            str(item or "").strip()
            for item in (quality.get("blocking_errors", []) or [])
            if str(item or "").strip()
        ]
        if not bool(preview.get("valid", False)):
            return False, "instruction_validation_failed"
        if not bool(quality.get("syntax_check_passed", True)):
            return False, "syntax_check_failed"
        if blocking_errors:
            return False, blocking_errors[0]
        if validation_errors:
            return False, validation_errors[0]
        if not bool(quality.get("identifier_reuse_confirmed", True)):
            return False, "identifier_reuse_not_confirmed"
        return True, ""

    def _proposal_public_view(self, proposal: Dict) -> Dict:
        if not isinstance(proposal, dict):
            return {}
        instruction_preview = proposal.get("instruction_preview", {}) if isinstance(proposal.get("instruction_preview", {}), dict) else {}
        if not instruction_preview:
            instruction_preview = self._instruction_preview_for_proposal(proposal, str(proposal.get("file", "") or ""))
        can_apply, blocked_reason = self._proposal_apply_gate({**proposal, "instruction_preview": instruction_preview})
        return {
            "proposal_id": proposal.get("proposal_id", ""),
            "session_id": proposal.get("session_id", ""),
            "output_dir": proposal.get("output_dir", ""),
            "file": proposal.get("file", ""),
            "source": proposal.get("source", "live-ai"),
            "base_hash": proposal.get("base_hash", ""),
            "summary": proposal.get("summary", ""),
            "unified_diff": proposal.get("unified_diff", ""),
            "hunks": proposal.get("hunks", []),
            "risk_level": proposal.get("risk_level", "medium"),
            "status": proposal.get("status", "Prepared"),
            "validation_preview": proposal.get("validation_preview", {}),
            "quality_preview": proposal.get("quality_preview", {}),
            "generator_type": proposal.get("generator_type", "llm"),
            "generator_reason": proposal.get("generator_reason", ""),
            "instruction_preview": instruction_preview,
            "compare_score": proposal.get("compare_score", {}),
            "selection_reason": proposal.get("selection_reason", ""),
            "can_apply": bool(can_apply),
            "blocked_reason": str(blocked_reason or ""),
            "llm_meta": proposal.get("llm_meta", {}),
            "created_at": proposal.get("created_at"),
        }

    def _instruction_preview_for_proposal(self, proposal: Dict, expected_file: str) -> Dict[str, Any]:
        raw = proposal.get("_structured_instruction") if isinstance(proposal, dict) else None
        if not isinstance(raw, dict):
            return {"available": False, "valid": False, "operation": "", "errors": ["missing_instruction"]}
        normalized = normalize_instruction(raw)
        valid, errors = validate_instruction(normalized)
        target_file = os.path.basename(str((normalized.get("target", {}) or {}).get("file", "") or ""))
        if target_file and target_file != os.path.basename(str(expected_file or "")):
            valid = False
            errors = list(errors) + ["target.file must match proposal file"]
        return {
            "available": True,
            "valid": bool(valid),
            "operation": str(normalized.get("operation", "") or ""),
            "operation_count": len(normalized.get("operations", []) or []),
            "supported_ops": sorted(
                {
                    str((op or {}).get("operation", "") or "")
                    for op in (normalized.get("operations", []) or [])
                    if isinstance(op, dict)
                }
            ),
            "errors": [str(e) for e in (errors or [])],
        }

    def _select_compare_proposal(self, proposals: List[Dict], file_name: str) -> Tuple[Dict, str]:
        if not proposals:
            return {}, "none"
        for item in proposals:
            if isinstance(item, dict):
                item["instruction_preview"] = self._instruction_preview_for_proposal(item, file_name)

        def _score(item: Dict) -> Tuple[int, int, int, int, int]:
            preview = item.get("instruction_preview", {}) if isinstance(item, dict) else {}
            quality = item.get("quality_preview", {}) if isinstance(item, dict) else {}
            validation_errors = quality.get("validation_errors", []) if isinstance(quality, dict) else []
            artifact_errors = {
                str(err or "")
                for err in (validation_errors if isinstance(validation_errors, list) else [])
                if str(err or "").strip()
            }
            valid_instruction = 1 if bool(preview.get("valid", False)) else 0
            syntax_ok = 1 if bool(quality.get("syntax_check_passed", True)) else 0
            artifact_free = 0 if artifact_errors else 1
            allow_apply = 1 if bool(quality.get("allow_apply", False)) else 0
            prefer_live_llm = 1 if (
                str(item.get("generator_type", "")).lower() == "llm"
                and str(item.get("source", "")).lower() == "live-ai"
            ) else 0
            prefer_rule = 1 if str(item.get("generator_type", "")).lower() == "rule" else 0
            item["compare_score"] = {
                "allow_apply": allow_apply,
                "instruction_valid": valid_instruction,
                "syntax_ok": syntax_ok,
                "artifact_free": artifact_free,
                "prefer_live_llm": prefer_live_llm,
                "prefer_rule": prefer_rule,
                "total": (allow_apply * 1000) + (valid_instruction * 100) + (syntax_ok * 20) + (artifact_free * 5) + (prefer_rule * 3) + prefer_live_llm,
            }
            return (allow_apply, valid_instruction, syntax_ok, artifact_free, prefer_rule, prefer_live_llm)

        selected = max([p for p in proposals if isinstance(p, dict)], key=_score)
        selected["selection_reason"] = "max(score=allow_apply*1000 + instruction_valid*100 + syntax_ok*20 + artifact_free*5 + prefer_rule*3 + prefer_live_llm)"
        return selected, "allow_apply_then_instruction_validity_then_syntax_then_artifact_free_then_rule_then_live_llm"

    def _store_autofix_proposal(self, session: Dict, proposal: Dict):
        autofix = session.setdefault("autofix", {})
        proposals = autofix.setdefault("proposals", collections.OrderedDict())
        latest_by_file = autofix.setdefault("latest_by_file", {})
        if not isinstance(proposals, collections.OrderedDict):
            proposals = collections.OrderedDict(proposals)
            autofix["proposals"] = proposals
        pid = str(proposal.get("proposal_id", ""))
        if not pid:
            raise RuntimeError("Invalid proposal id")
        proposals[pid] = proposal
        proposals.move_to_end(pid, last=True)
        latest_by_file[str(proposal.get("file", ""))] = pid
        while len(proposals) > self.autofix_proposal_limit_per_session:
            old_pid, _ = proposals.popitem(last=False)
            for file_key, val in list(latest_by_file.items()):
                if val == old_pid:
                    latest_by_file.pop(file_key, None)

    def _autofix_session_stats(self, session: Dict) -> Dict:
        autofix = session.setdefault("autofix", {}) if isinstance(session, dict) else {}
        stats = autofix.setdefault("stats", {}) if isinstance(autofix, dict) else {}
        stats.setdefault("prepare_compare_count", 0)
        stats.setdefault("prepare_compare_generated_candidates_total", 0)
        selected = stats.setdefault("selected_generator_counts", {"rule": 0, "llm": 0})
        if not isinstance(selected, dict):
            selected = {"rule": 0, "llm": 0}
            stats["selected_generator_counts"] = selected
        selected.setdefault("rule", 0)
        selected.setdefault("llm", 0)
        stats.setdefault("compare_apply_count", 0)
        stats.setdefault("anchor_mismatch_count", 0)
        stats.setdefault("token_fallback_attempt_count", 0)
        stats.setdefault("token_fallback_success_count", 0)
        stats.setdefault("token_fallback_ambiguous_count", 0)
        stats.setdefault("apply_engine_structure_success_count", 0)
        stats.setdefault("apply_engine_text_fallback_count", 0)
        stats.setdefault("multi_hunk_attempt_count", 0)
        stats.setdefault("multi_hunk_success_count", 0)
        stats.setdefault("multi_hunk_blocked_count", 0)
        stats.setdefault("semantic_guard_checked_count", 0)
        stats.setdefault("semantic_guard_blocked_count", 0)
        stats.setdefault("instruction_attempt_count", 0)
        stats.setdefault("instruction_apply_success_count", 0)
        stats.setdefault("instruction_fallback_to_hunk_count", 0)
        stats.setdefault("instruction_validation_fail_count", 0)
        stats.setdefault("instruction_operation_total_count", 0)
        stats.setdefault("instruction_engine_fail_count", 0)
        stats.setdefault("instruction_convert_fail_count", 0)
        mode_counts = stats.setdefault("instruction_mode_counts", {"off": 0, "attempted": 0, "applied": 0, "fallback_hunks": 0})
        if not isinstance(mode_counts, dict):
            mode_counts = {"off": 0, "attempted": 0, "applied": 0, "fallback_hunks": 0}
            stats["instruction_mode_counts"] = mode_counts
        mode_counts.setdefault("off", 0)
        mode_counts.setdefault("attempted", 0)
        mode_counts.setdefault("applied", 0)
        mode_counts.setdefault("fallback_hunks", 0)
        validation_fail_by_reason = stats.setdefault("instruction_validation_fail_by_reason", {})
        if not isinstance(validation_fail_by_reason, dict):
            validation_fail_by_reason = {}
            stats["instruction_validation_fail_by_reason"] = validation_fail_by_reason
        engine_counts = stats.setdefault("selected_apply_engine_mode", {"structure_apply": 0, "text_fallback": 0})
        if not isinstance(engine_counts, dict):
            engine_counts = {"structure_apply": 0, "text_fallback": 0}
            stats["selected_apply_engine_mode"] = engine_counts
        engine_counts.setdefault("structure_apply", 0)
        engine_counts.setdefault("text_fallback", 0)
        return stats

    def _resolve_autofix_proposal(self, session: Dict, proposal_id: str = "", file_name: str = "") -> Dict:
        autofix = session.get("autofix", {})
        proposals = autofix.get("proposals", {})
        latest_by_file = autofix.get("latest_by_file", {})
        pid = str(proposal_id or "")
        if not pid and file_name:
            pid = str(latest_by_file.get(str(file_name), ""))
        if not pid:
            raise FileNotFoundError("No autofix proposal found")
        proposal = proposals.get(pid) if isinstance(proposals, dict) else None
        if not isinstance(proposal, dict):
            raise FileNotFoundError(f"Autofix proposal not found: {pid}")
        return proposal
