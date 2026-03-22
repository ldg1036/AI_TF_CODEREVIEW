from typing import Any, Dict, List


class AutoFixPrepareQualityMixin:
    """Prepare-time quality helpers for conservative autofix apply gating."""

    @staticmethod
    def _autofix_prepare_rule_family(rule_id: Any) -> str:
        text = str(rule_id or "").strip().upper()
        if not text:
            return ""
        parts = [part for part in text.split("-") if part]
        return parts[0] if parts else text

    @staticmethod
    def _autofix_prepare_severity_bucket(severity: Any) -> str:
        text = str(severity or "").strip().lower()
        if text in ("critical", "error", "high"):
            return "critical"
        if text in ("warning", "warn", "medium", "performance", "style", "portability"):
            return "warning"
        return "info"

    def _flatten_prepare_internal_violations(self, groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        flat: List[Dict[str, Any]] = []
        for group in groups or []:
            if not isinstance(group, dict):
                continue
            object_name = str(group.get("object", "") or "")
            event_name = str(group.get("event", "Global") or "Global")
            for violation in group.get("violations", []) or []:
                if not isinstance(violation, dict):
                    continue
                item = dict(violation)
                item.setdefault("object", object_name)
                item.setdefault("event", event_name)
                flat.append(item)
        return flat

    def _summarize_prepare_internal_violations(
        self,
        violations: List[Dict[str, Any]],
        *,
        target_issue_id: str = "",
        target_rule_id: str = "",
    ) -> Dict[str, int]:
        target_issue_id = str(target_issue_id or "").strip()
        target_rule_id = str(target_rule_id or "").strip()
        target_family = self._autofix_prepare_rule_family(target_rule_id)
        summary = {
            "total_count": 0,
            "critical_count": 0,
            "warning_count": 0,
            "target_issue_count": 0,
            "target_rule_family_count": 0,
        }
        for violation in violations or []:
            if not isinstance(violation, dict):
                continue
            summary["total_count"] += 1
            bucket = self._autofix_prepare_severity_bucket(violation.get("severity", ""))
            if bucket == "critical":
                summary["critical_count"] += 1
            elif bucket == "warning":
                summary["warning_count"] += 1
            if target_issue_id and str(violation.get("issue_id", "") or "").strip() == target_issue_id:
                summary["target_issue_count"] += 1
            if target_family and self._autofix_prepare_rule_family(violation.get("rule_id", "")) == target_family:
                summary["target_rule_family_count"] += 1
        return summary

    def _estimate_prepare_issue_delta(
        self,
        *,
        file_name: str,
        source_path: str,
        report_data: Dict[str, Any],
        candidate_content: str,
        target_issue_id: str = "",
        target_rule_id: str = "",
    ) -> Dict[str, Any]:
        baseline_internal = self._flatten_prepare_internal_violations(
            report_data.get("internal_violations", []) if isinstance(report_data, dict) else []
        )
        file_type = "Server"
        try:
            file_type = self.infer_file_type(file_name)
        except Exception:
            file_type = "Server"
        candidate_internal = self._flatten_prepare_internal_violations(
            self.checker.analyze_raw_code(source_path, candidate_content, file_type=file_type)
        )
        before = self._summarize_prepare_internal_violations(
            baseline_internal,
            target_issue_id=target_issue_id,
            target_rule_id=target_rule_id,
        )
        after = self._summarize_prepare_internal_violations(
            candidate_internal,
            target_issue_id=target_issue_id,
            target_rule_id=target_rule_id,
        )
        return {
            "total_before": int(before["total_count"]),
            "total_after": int(after["total_count"]),
            "total_delta": int(after["total_count"] - before["total_count"]),
            "critical_before": int(before["critical_count"]),
            "critical_after": int(after["critical_count"]),
            "critical_delta": int(after["critical_count"] - before["critical_count"]),
            "warning_before": int(before["warning_count"]),
            "warning_after": int(after["warning_count"]),
            "warning_delta": int(after["warning_count"] - before["warning_count"]),
            "target_issue_before": int(before["target_issue_count"]),
            "target_issue_after": int(after["target_issue_count"]),
            "target_issue_delta": int(after["target_issue_count"] - before["target_issue_count"]),
            "target_rule_family_before": int(before["target_rule_family_count"]),
            "target_rule_family_after": int(after["target_rule_family_count"]),
            "target_rule_family_delta": int(after["target_rule_family_count"] - before["target_rule_family_count"]),
            "target_issue_reduced": int(after["target_issue_count"]) < int(before["target_issue_count"]),
        }

    def _quality_preview_with_prepare_verdict(
        self,
        *,
        preview: Dict[str, Any],
        file_name: str,
        source_path: str,
        report_data: Dict[str, Any],
        candidate_content: str,
        target_issue_id: str = "",
        target_rule_id: str = "",
    ) -> Dict[str, Any]:
        payload = dict(preview or {})
        issue_delta = self._estimate_prepare_issue_delta(
            file_name=file_name,
            source_path=source_path,
            report_data=report_data,
            candidate_content=candidate_content,
            target_issue_id=target_issue_id,
            target_rule_id=target_rule_id,
        )
        blocking_errors = [
            str(item or "").strip()
            for item in (payload.get("blocking_errors", []) or [])
            if str(item or "").strip()
        ]
        validation_errors = [
            str(item or "").strip()
            for item in (payload.get("errors", payload.get("validation_errors", [])) or [])
            if str(item or "").strip()
        ]
        placeholder_free = not any(
            code.startswith("contains_placeholder_") or code == "contains_example_arrow"
            for code in blocking_errors
        )
        identifier_reuse_ok = bool(payload.get("identifier_reuse_confirmed", True))
        blocked_reason_codes: List[str] = []
        reason_messages: List[str] = []

        for code in blocking_errors:
            if code not in blocked_reason_codes:
                blocked_reason_codes.append(code)
        if not bool(payload.get("syntax_check_passed", True)):
            blocked_reason_codes.append("syntax_check_failed")
            reason_messages.append("Preview syntax check failed.")
        if issue_delta["target_issue_before"] > 0 and issue_delta["target_issue_after"] >= issue_delta["target_issue_before"]:
            blocked_reason_codes.append("target_issue_not_reduced")
            reason_messages.append("Preview reanalysis did not reduce the target issue.")
        if issue_delta["critical_delta"] > 0:
            blocked_reason_codes.append("new_critical_findings")
            reason_messages.append("Preview reanalysis introduced new critical findings.")
        elif issue_delta["warning_delta"] > 0:
            blocked_reason_codes.append("new_warning_findings")
            reason_messages.append("Preview reanalysis introduced new warning findings.")
        if issue_delta["target_rule_family_before"] > 0 and issue_delta["target_rule_family_after"] > issue_delta["target_rule_family_before"]:
            blocked_reason_codes.append("target_rule_family_not_reduced")
            reason_messages.append("Preview reanalysis expanded the target rule family footprint.")
        if validation_errors:
            blocked_reason_codes.append("validation_errors_present")
            reason_messages.append("Preview validation returned errors.")
        if not identifier_reuse_ok:
            blocked_reason_codes.append("identifier_reuse_not_confirmed")
            reason_messages.append("Candidate did not clearly reuse identifiers from the source snippet.")
        if not placeholder_free:
            blocked_reason_codes.append("placeholder_artifacts_detected")
            reason_messages.append("Candidate still contains placeholder or example markers.")

        semantic_verdict = "allow_apply"
        if blocked_reason_codes:
            semantic_verdict = str(blocked_reason_codes[0])
        payload["validation_errors"] = validation_errors + [
            message for message in reason_messages if message and message not in validation_errors
        ]
        payload["blocking_errors"] = blocking_errors + [
            code for code in blocked_reason_codes if code not in blocking_errors
        ]
        payload["estimated_issue_delta"] = issue_delta
        payload["semantic_verdict"] = semantic_verdict
        payload["blocked_reason_codes"] = blocked_reason_codes
        payload["allow_apply"] = len(blocked_reason_codes) == 0
        payload["identifier_reuse_ok"] = identifier_reuse_ok
        payload["placeholder_free"] = placeholder_free
        return payload
