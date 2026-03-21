import os
import re
import uuid
from typing import Dict, List, Optional, Tuple


class AutoFixPrepareMixin:
    """Host class should provide session helpers plus proposal helper methods."""

    @staticmethod
    def _ai_review_code_block_quality_errors(source_content: str, code_block: str) -> List[str]:
        text = str(code_block or "")
        if not text.strip():
            return ["missing_code_block"]
        errors: List[str] = []
        if re.search(r"(^|\n)\s*=>\s*", text):
            errors.append("contains_example_arrow")
        source_lower = str(source_content or "").lower()
        placeholder_patterns = (
            ("contains_placeholder_obj_auto_sel", r"\bobj_auto_sel\d+\b"),
            ("contains_placeholder_system_obj", r"\bSystem1:Obj\d+(?:\.[A-Za-z_][\w]*)?\b"),
            ("contains_placeholder_bsel", r"\bbSel\d+\b"),
        )
        for error_code, pattern in placeholder_patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match and match.group(0).lower() not in source_lower:
                errors.append(error_code)
        return errors

    def _find_matching_ai_review(self, report_data: Dict, object_name: str, event_name: str, review_text: str, issue_id: str = ""):
        target_obj = str(object_name or "")
        target_event = str(event_name or "Global")
        target_review = str(review_text or "")
        target_issue_id = str(issue_id or "")
        ai_reviews = report_data.get("ai_reviews", []) if isinstance(report_data, dict) else []
        for item in ai_reviews if isinstance(ai_reviews, list) else []:
            if not isinstance(item, dict):
                continue
            if target_issue_id and str(item.get("parent_issue_id", "")) == target_issue_id:
                return item
            if (
                str(item.get("object", "")) == target_obj
                and str(item.get("event", "Global")) == target_event
                and str(item.get("review", "")) == target_review
            ):
                return item
        return None

    def _find_violation_for_ai_review(self, report_data: Dict, ai_review: Dict):
        if not isinstance(report_data, dict) or not isinstance(ai_review, dict):
            return None, None
        wanted_issue_id = str(ai_review.get("parent_issue_id", ""))
        wanted_obj = str(ai_review.get("object", ""))
        wanted_event = str(ai_review.get("event", "Global"))
        for group in report_data.get("internal_violations", []) or []:
            if not isinstance(group, dict):
                continue
            if wanted_obj and str(group.get("object", "")) != wanted_obj:
                continue
            if wanted_event and str(group.get("event", "Global")) != wanted_event:
                continue
            for violation in group.get("violations", []) or []:
                if not isinstance(violation, dict):
                    continue
                if wanted_issue_id and str(violation.get("issue_id", "")) != wanted_issue_id:
                    continue
                return group, violation
            if (group.get("violations") or []):
                first = (group.get("violations") or [None])[0]
                if isinstance(first, dict):
                    return group, first
        return None, None

    def _build_autofix_proposal_from_ai_review(
        self,
        session_output_dir: str,
        session: Dict,
        cache_key: str,
        cached: Dict,
        object_name: str,
        event_name: str,
        review_text: str,
        issue_id: str = "",
    ) -> Dict:
        file_name = str(cache_key or cached.get("file") or "")

        report_data = cached.get("report_data")
        if not isinstance(report_data, dict):
            raise RuntimeError("Cached report data is invalid")

        ai_review = self._find_matching_ai_review(report_data, object_name, event_name, review_text, issue_id=issue_id)
        if not ai_review:
            raise FileNotFoundError("Matching AI review was not found in cached session")

        group, violation = self._find_violation_for_ai_review(report_data, ai_review)
        line_no = self._safe_int((violation or {}).get("line", 1), 1)
        source_path = str(cached.get("source_path", "") or os.path.join(self.data_dir, file_name))
        if not os.path.isfile(source_path):
            raise FileNotFoundError(f"Source file not found: {file_name}")

        with open(source_path, "r", encoding="utf-8", errors="ignore") as f:
            source_content = f.read()
        source_hash = self._sha256_text(source_content)
        source_lines = source_content.splitlines()
        insert_at = max(1, min(len(source_lines) + 1, line_no if line_no > 0 else 1))

        code_block = self._extract_review_code_block(str(ai_review.get("review", "")))
        if not str(code_block).strip():
            raise ValueError("AI review does not contain a code block for autofix")
        quality_errors = self._ai_review_code_block_quality_errors(source_content, code_block)

        reference_line = source_lines[insert_at - 1] if 0 <= (insert_at - 1) < len(source_lines) else ""
        indent = self._line_indent(reference_line)
        summary = self._extract_review_summary(str(ai_review.get("review", "")))
        marker_id = uuid.uuid4().hex[:8]
        inserted_lines = [
            f"{indent}// [AI-AUTOFIX:{marker_id}] {summary}".rstrip(),
            *self._indent_lines(code_block, indent),
            f"{indent}// [/AI-AUTOFIX:{marker_id}]",
        ]

        new_lines = list(source_lines)
        new_lines[insert_at - 1:insert_at - 1] = inserted_lines
        new_content = "\n".join(new_lines)
        if source_content.endswith("\n"):
            new_content += "\n"
        llm_meta = {
            "review_length": len(str(ai_review.get("review", "") or "")),
            "summary_length": len(summary),
            "code_block_length": len(code_block),
            "code_block_present": bool(str(code_block).strip()),
            "parseability": "code_block_extracted" if str(code_block).strip() else "no_code_block",
            "fallback_used": False,
            "snippet_based": True,
            "ai_review_source": str(ai_review.get("source", "") or ""),
            "quality_error_codes": list(quality_errors),
        }
        proposal = self._build_autofix_proposal_from_candidate(
            session_output_dir=session_output_dir,
            session=session,
            file_name=file_name,
            source_path=source_path,
            source_content=source_content,
            candidate_content=new_content,
            summary=summary,
            source_tag="live-ai" if str(ai_review.get("source", "")).lower() == "live" else "rule-template",
            generator_type="llm",
            generator_reason="LLM review code block extracted from cached AI review",
            risk_level="medium",
            quality_preview={
                "anchors_match": True,
                "hash_match": True,
                "syntax_check_passed": self._basic_syntax_check(new_content),
                "heuristic_regression_count": 0,
                "ctrlpp_regression_count": 0,
                "errors": list(quality_errors),
            },
            llm_meta=llm_meta,
            extra_private_fields={
                "_object": str(ai_review.get("object", object_name or "")),
                "_event": str(ai_review.get("event", event_name or "Global")),
                "_review": str(ai_review.get("review", review_text or "")),
                "_insert_line": insert_at,
                "_inserted_line_count": len(inserted_lines),
                "_source_hash_at_prepare": source_hash,
            },
        )
        # Preserve insertion-specific hunk shape for anchor checks/backward compatibility.
        proposal["hunks"] = self._build_autofix_hunks_for_insertion(source_lines, new_lines, insert_at, inserted_lines)
        try:
            structured = self._build_structured_instruction_from_hunks(
                proposal=proposal,
                file_name=file_name,
                object_name=str(ai_review.get("object", object_name or "")),
                event_name=str(ai_review.get("event", event_name or "Global")),
            )
            if isinstance(structured, dict):
                proposal["_structured_instruction"] = structured
        except Exception:
            # Fail-soft: keep legacy hunk-only proposal path.
            pass
        return proposal

    def _find_violation_for_rule_autofix(
        self,
        report_data: Dict,
        object_name: str,
        event_name: str,
        issue_id: str = "",
    ) -> Tuple[Optional[Dict], Optional[Dict]]:
        target_obj = str(object_name or "")
        target_event = str(event_name or "Global")
        target_issue_id = str(issue_id or "")
        for group in report_data.get("internal_violations", []) or []:
            if not isinstance(group, dict):
                continue
            if target_obj and str(group.get("object", "")) != target_obj:
                continue
            if target_event and str(group.get("event", "Global")) != target_event:
                continue
            for violation in group.get("violations", []) or []:
                if not isinstance(violation, dict):
                    continue
                if target_issue_id and str(violation.get("issue_id", "")) != target_issue_id:
                    continue
                return group, violation
            if not target_issue_id and (group.get("violations") or []):
                first = (group.get("violations") or [None])[0]
                if isinstance(first, dict):
                    return group, first
        return None, None

    def _build_autofix_proposal_from_rule_template(
        self,
        session_output_dir: str,
        session: Dict,
        cache_key: str,
        cached: Dict,
        object_name: str,
        event_name: str,
        issue_id: str = "",
    ) -> Dict:
        file_name = str(cache_key or cached.get("file") or "")
        if not file_name.lower().endswith(".ctl"):
            raise ValueError("Autofix is supported only for .ctl files")
        report_data = cached.get("report_data")
        if not isinstance(report_data, dict):
            raise RuntimeError("Cached report data is invalid")
        _group, violation = self._find_violation_for_rule_autofix(report_data, object_name, event_name, issue_id=issue_id)
        if not isinstance(violation, dict):
            raise FileNotFoundError("Matching violation for rule autofix was not found in cached session")

        source_path = str(cached.get("source_path", "") or os.path.join(self.data_dir, file_name))
        if not os.path.isfile(source_path):
            raise FileNotFoundError(f"Source file not found: {file_name}")
        with open(source_path, "r", encoding="utf-8", errors="ignore") as f:
            source_content = f.read()

        normalized_content, normalize_stats = self._rule_autofix_normalize_text(source_content)
        changed = normalized_content != source_content
        rule_id = str(violation.get("rule_id", "") or "")
        rule_item = str(violation.get("rule_item", "") or "")
        line_no = self._safe_int(violation.get("line", 1), 1)
        generator_reason = "rule-first deterministic hygiene normalization"

        candidate_content = normalized_content
        if not changed:
            source_lines = source_content.splitlines()
            insert_at = max(1, min(len(source_lines) + 1, line_no if line_no > 0 else 1))
            ref_line = source_lines[insert_at - 1] if 0 <= (insert_at - 1) < len(source_lines) else ""
            indent = self._line_indent(ref_line)
            marker_id = uuid.uuid4().hex[:8]
            summary = f"Rule template suggestion for {rule_id or 'RULE'}"
            note_lines = [
                f"{indent}// [RULE-AUTOFIX:{marker_id}] {summary} ({rule_item or str(violation.get('message', '') or '').strip()})".rstrip(),
                f"{indent}// TODO: apply deterministic fix pattern or review manually",
                f"{indent}// [/RULE-AUTOFIX:{marker_id}]",
            ]
            new_lines = list(source_lines)
            new_lines[insert_at - 1:insert_at - 1] = note_lines
            candidate_content = "\n".join(new_lines)
            if source_content.endswith("\n"):
                candidate_content += "\n"
            generator_reason = "rule-first fallback annotation template (no deterministic text normalization changes)"
            normalize_stats = {**normalize_stats, "annotation_inserted": 1}
        else:
            summary = "Rule template hygiene normalization (trailing spaces/tabs/blank-runs/EOF newline)"
            normalize_stats = {**normalize_stats, "annotation_inserted": 0}

        proposal = self._build_autofix_proposal_from_candidate(
            session_output_dir=session_output_dir,
            session=session,
            file_name=file_name,
            source_path=source_path,
            source_content=source_content,
            candidate_content=candidate_content,
            summary=summary,
            source_tag="rule-template",
            generator_type="rule",
            generator_reason=generator_reason,
            risk_level="low",
            quality_preview={
                "anchors_match": True,
                "hash_match": True,
                "syntax_check_passed": self._basic_syntax_check(candidate_content),
                "heuristic_regression_count": 0,
                "ctrlpp_regression_count": 0,
                "errors": [],
            },
            extra_private_fields={
                "_object": str(object_name or ""),
                "_event": str(event_name or "Global"),
                "_review": "",
                "_rule_issue_id": str(violation.get("issue_id", "") or ""),
                "_rule_id": rule_id,
                "_rule_item": rule_item,
                "_rule_stats": normalize_stats,
            },
        )
        try:
            structured = self._build_structured_instruction_from_hunks(
                proposal=proposal,
                file_name=file_name,
                object_name=str(object_name or ""),
                event_name=str(event_name or "Global"),
            )
            if isinstance(structured, dict):
                proposal["_structured_instruction"] = structured
        except Exception:
            pass
        return proposal

    def prepare_autofix_for_ai_review(
        self,
        file_name: str,
        object_name: str,
        event_name: str,
        review_text: str,
        output_dir: Optional[str] = None,
        issue_id: str = "",
        generator_preference: Optional[str] = None,
        allow_fallback: Optional[bool] = None,
        prepare_mode: Optional[str] = None,
    ) -> Dict:
        # Preserve legacy behavior for existing clients: if a review text is supplied and no generator was
        # explicitly requested, default to the LLM path instead of forcing auto(rule-first).
        if generator_preference is None and str(review_text or "").strip():
            preferred = "llm"
        else:
            preferred = self._normalize_autofix_generator_preference(generator_preference, self.autofix_prepare_generator_default)
        allow_fallback = self.autofix_allow_fallback_default if allow_fallback is None else bool(allow_fallback)
        normalized_prepare_mode = self._normalize_autofix_prepare_mode(prepare_mode, "single")
        session_output_dir, session, cache_key, cached = self._resolve_review_session_and_file(file_name=file_name, output_dir=output_dir)
        is_ctl_target = str(cache_key or "").lower().endswith(".ctl")
        forced_llm_non_ctl = not is_ctl_target
        if forced_llm_non_ctl:
            preferred = "llm"
        file_lock = self._get_session_file_lock(session, cache_key)
        with file_lock:
            last_error: Optional[Exception] = None
            proposals: List[Dict] = []
            fallback_used_any = False

            if normalized_prepare_mode == "compare":
                if forced_llm_non_ctl:
                    plan_order = ["llm"]
                elif preferred == "auto":
                    plan_order = ["rule", "llm"]
                elif preferred == "rule":
                    plan_order = ["rule", "llm"]
                else:
                    plan_order = ["llm", "rule"]
            else:
                if forced_llm_non_ctl:
                    plan_order = ["llm"]
                elif preferred == "auto":
                    plan_order = ["rule", "llm"]
                else:
                    plan_order = [preferred]

            for idx, generator in enumerate(plan_order):
                try:
                    if generator == "rule":
                        proposal = self._build_autofix_proposal_from_rule_template(
                            session_output_dir=session_output_dir,
                            session=session,
                            cache_key=cache_key,
                            cached=cached,
                            object_name=object_name,
                            event_name=event_name,
                            issue_id=issue_id,
                        )
                    else:
                        if not str(review_text or "").strip():
                            raise ValueError("review must be provided for llm autofix prepare")
                        proposal = self._build_autofix_proposal_from_ai_review(
                            session_output_dir=session_output_dir,
                            session=session,
                            cache_key=cache_key,
                            cached=cached,
                            object_name=object_name,
                            event_name=event_name,
                            review_text=review_text,
                            issue_id=issue_id,
                        )
                    proposal["_prepare_mode"] = normalized_prepare_mode
                    proposal["_requested_preference"] = preferred
                    if forced_llm_non_ctl:
                        proposal["generator_reason"] = (
                            f"{proposal.get('generator_reason', '')}; non-ctl target uses llm-only autofix"
                        ).strip("; ")
                    proposals.append(proposal)
                    if normalized_prepare_mode == "single":
                        if idx > 0:
                            fallback_used_any = True
                            proposal["generator_reason"] = f"{proposal.get('generator_reason', '')}; fallback from {plan_order[0]}"
                            if proposal.get("generator_type") == "llm":
                                llm_meta = proposal.setdefault("llm_meta", {})
                                if isinstance(llm_meta, dict):
                                    llm_meta["fallback_used"] = True
                        break
                except Exception as exc:
                    last_error = exc
                    if normalized_prepare_mode == "single":
                        if idx == (len(plan_order) - 1) or not allow_fallback:
                            raise
                        fallback_used_any = True
                        continue
                    # compare mode is fail-soft per generator
                    continue

            if not proposals:
                if last_error:
                    raise last_error
                raise RuntimeError("Autofix proposal generation failed")

            selection_policy = "rule_first_default"
            if normalized_prepare_mode == "compare":
                selected_proposal, selection_policy = self._select_compare_proposal(proposals, cache_key)
            else:
                selected_proposal = None
                for item in proposals:
                    if str(item.get("generator_type", "")) == "rule":
                        selected_proposal = item
                        break
                if selected_proposal is None:
                    selected_proposal = proposals[0]

            with session["lock"]:
                stats = self._autofix_session_stats(session)
                if normalized_prepare_mode == "compare":
                    stats["prepare_compare_count"] = self._safe_int(stats.get("prepare_compare_count", 0), 0) + 1
                    stats["prepare_compare_generated_candidates_total"] = (
                        self._safe_int(stats.get("prepare_compare_generated_candidates_total", 0), 0) + len(proposals)
                    )
                self._touch_review_session(session)

            selected_view = self._proposal_public_view(selected_proposal)
            if normalized_prepare_mode != "compare":
                return selected_view

            proposal_views = [self._proposal_public_view(item) for item in proposals]
            selected_pid = str(selected_view.get("proposal_id", ""))
            selected_view["proposals"] = proposal_views
            selected_view["selected_proposal_id"] = selected_pid
            selected_view["compare_meta"] = {
                "mode": "compare",
                "requested_generators": list(plan_order),
                "generated_count": len(proposal_views),
                "fallback_used": bool(fallback_used_any),
                "selection_policy": selection_policy,
                "selected_generator_type": str(selected_view.get("generator_type", "") or ""),
                "selected_compare_score": selected_view.get("compare_score", {}),
                "selected_selection_reason": str(selected_view.get("selection_reason", "") or ""),
            }
            return selected_view

    def get_autofix_file_diff(
        self,
        file_name: str = "",
        session_id: Optional[str] = None,
        output_dir: Optional[str] = None,
        proposal_id: str = "",
    ) -> Dict:
        target_output_dir = output_dir or session_id or self._last_output_dir
        if not target_output_dir:
            raise RuntimeError("No analysis session found. Run analysis first.")
        session = self._get_review_session(target_output_dir)
        if not session:
            raise RuntimeError("Analysis session cache not found. Run analysis again.")
        with session["lock"]:
            proposal = self._resolve_autofix_proposal(session, proposal_id=proposal_id, file_name=os.path.basename(str(file_name or "")))
            return self._proposal_public_view(proposal)

    def get_autofix_stats(
        self,
        session_id: Optional[str] = None,
        output_dir: Optional[str] = None,
    ) -> Dict:
        target_output_dir = output_dir or session_id or self._last_output_dir
        if not target_output_dir:
            raise RuntimeError("No analysis session found. Run analysis first.")
        session = self._get_review_session(target_output_dir)
        if not session:
            raise RuntimeError("Analysis session cache not found. Run analysis again.")
        with session["lock"]:
            autofix = session.get("autofix", {}) if isinstance(session, dict) else {}
            proposals = autofix.get("proposals", {}) if isinstance(autofix, dict) else {}
            latest_by_file = autofix.get("latest_by_file", {}) if isinstance(autofix, dict) else {}
            extra_stats = self._autofix_session_stats(session)
            items = list(proposals.values()) if isinstance(proposals, dict) else []

            by_status: Dict[str, int] = {}
            by_generator: Dict[str, int] = {}
            by_generator_status: Dict[str, Dict[str, int]] = {}
            quality_summary = {
                "applied_count": 0,
                "blocked_count": 0,
                "heuristic_regression_blocked_count": 0,
                "ctrlpp_regression_blocked_count": 0,
                "failure_error_codes": {},
            }

            for item in items:
                if not isinstance(item, dict):
                    continue
                status = str(item.get("status", "Prepared") or "Prepared")
                generator = str(item.get("generator_type", "unknown") or "unknown")
                by_status[status] = by_status.get(status, 0) + 1
                by_generator[generator] = by_generator.get(generator, 0) + 1
                gs = by_generator_status.setdefault(generator, {})
                gs[status] = gs.get(status, 0) + 1

                qm = item.get("quality_metrics", {})
                if isinstance(qm, dict):
                    if qm.get("applied"):
                        quality_summary["applied_count"] += 1
                    if str(qm.get("rejected_reason", "")):
                        quality_summary["blocked_count"] += 1
                        reason = str(qm.get("rejected_reason", "")).lower()
                        if "heuristic" in reason:
                            quality_summary["heuristic_regression_blocked_count"] += 1
                        if "ctrlpp" in reason:
                            quality_summary["ctrlpp_regression_blocked_count"] += 1
                    error_code = str(item.get("last_error_code", "") or "")
                    if error_code:
                        failures = quality_summary["failure_error_codes"]
                        failures[error_code] = failures.get(error_code, 0) + 1

            return {
                "ok": True,
                "session_id": os.path.normpath(target_output_dir),
                "output_dir": os.path.normpath(target_output_dir),
                "proposal_count": len([i for i in items if isinstance(i, dict)]),
                "latest_by_file_count": len(latest_by_file) if isinstance(latest_by_file, dict) else 0,
                "by_status": by_status,
                "by_generator": by_generator,
                "by_generator_status": by_generator_status,
                "quality_summary": quality_summary,
                "prepare_compare_count": self._safe_int(extra_stats.get("prepare_compare_count", 0), 0),
                "prepare_compare_generated_candidates_total": self._safe_int(
                    extra_stats.get("prepare_compare_generated_candidates_total", 0),
                    0,
                ),
                "selected_generator_counts": dict(extra_stats.get("selected_generator_counts", {}))
                if isinstance(extra_stats.get("selected_generator_counts", {}), dict)
                else {"rule": 0, "llm": 0},
                "compare_apply_count": self._safe_int(extra_stats.get("compare_apply_count", 0), 0),
                "anchor_mismatch_count": self._safe_int(extra_stats.get("anchor_mismatch_count", 0), 0),
                "token_fallback_attempt_count": self._safe_int(extra_stats.get("token_fallback_attempt_count", 0), 0),
                "token_fallback_success_count": self._safe_int(extra_stats.get("token_fallback_success_count", 0), 0),
                "token_fallback_ambiguous_count": self._safe_int(extra_stats.get("token_fallback_ambiguous_count", 0), 0),
                "apply_engine_structure_success_count": self._safe_int(
                    extra_stats.get("apply_engine_structure_success_count", 0), 0
                ),
                "apply_engine_text_fallback_count": self._safe_int(
                    extra_stats.get("apply_engine_text_fallback_count", 0), 0
                ),
                "multi_hunk_attempt_count": self._safe_int(
                    extra_stats.get("multi_hunk_attempt_count", 0), 0
                ),
                "multi_hunk_success_count": self._safe_int(
                    extra_stats.get("multi_hunk_success_count", 0), 0
                ),
                "multi_hunk_blocked_count": self._safe_int(
                    extra_stats.get("multi_hunk_blocked_count", 0), 0
                ),
                "semantic_guard_checked_count": self._safe_int(
                    extra_stats.get("semantic_guard_checked_count", 0), 0
                ),
                "semantic_guard_blocked_count": self._safe_int(
                    extra_stats.get("semantic_guard_blocked_count", 0), 0
                ),
                "instruction_attempt_count": self._safe_int(
                    extra_stats.get("instruction_attempt_count", 0), 0
                ),
                "instruction_apply_success_count": self._safe_int(
                    extra_stats.get("instruction_apply_success_count", 0), 0
                ),
                "instruction_fallback_to_hunk_count": self._safe_int(
                    extra_stats.get("instruction_fallback_to_hunk_count", 0), 0
                ),
                "instruction_validation_fail_count": self._safe_int(
                    extra_stats.get("instruction_validation_fail_count", 0), 0
                ),
                "instruction_operation_total_count": self._safe_int(
                    extra_stats.get("instruction_operation_total_count", 0), 0
                ),
                "instruction_engine_fail_count": self._safe_int(
                    extra_stats.get("instruction_engine_fail_count", 0), 0
                ),
                "instruction_convert_fail_count": self._safe_int(
                    extra_stats.get("instruction_convert_fail_count", 0), 0
                ),
                "instruction_mode_counts": dict(extra_stats.get("instruction_mode_counts", {}))
                if isinstance(extra_stats.get("instruction_mode_counts", {}), dict)
                else {"off": 0, "attempted": 0, "applied": 0, "fallback_hunks": 0},
                "instruction_validation_fail_by_reason": dict(extra_stats.get("instruction_validation_fail_by_reason", {}))
                if isinstance(extra_stats.get("instruction_validation_fail_by_reason", {}), dict)
                else {},
                "selected_apply_engine_mode": dict(extra_stats.get("selected_apply_engine_mode", {}))
                if isinstance(extra_stats.get("selected_apply_engine_mode", {}), dict)
                else {"structure_apply": 0, "text_fallback": 0},
            }
