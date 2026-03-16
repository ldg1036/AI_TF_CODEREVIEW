import re
from collections import Counter
from typing import Any, Dict, List, Optional

from core.rules.composite_rules import CompositeRuleContext


class CheckerDetectorRunnerMixin:
    """Host class should provide configured rule defs and helper methods."""

    def _legacy_ui_block_initialize_delay(self, code: str, event_name: str = "", anchor_line: int = 1) -> List[Dict]:
        if event_name == "Initialize" and "delay(" in code:
            return [
                {
                    "rule_id": "UI-BLOCK",
                    "rule_item": "적절한 DP 처리 함수 사용",
                    "severity": "Warning",
                    "line": max(1, int(anchor_line or 1)),
                    "message": "UI 블로킹 위험: Initialize 내 delay 호출.",
                }
            ]
        return []

    def _run_legacy_handler_rule(
        self,
        rule_def: Dict[str, Any],
        code: str,
        analysis_code: str,
        event_name: str,
        base_line: int,
        anchor_line: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:
        detector = rule_def.get("detector", {}) if isinstance(rule_def.get("detector"), dict) else {}
        handler_name = str(detector.get("handler", "") or "")
        if not handler_name:
            return []
        handler = self.legacy_detector_handlers.get(handler_name)
        if not handler:
            print(f"[!] Unknown legacy handler in p1_rule_defs: {handler_name}")
            return []

        input_source = str(detector.get("input_source", "analysis_code") or "analysis_code").lower()
        check_input = code if input_source == "original_code" else analysis_code

        if handler_name == "__ui_block_initialize_delay__":
            findings = handler(analysis_code, event_name=event_name, anchor_line=anchor_line)
        elif handler_name in self._CONTEXT_AWARE_RULE_NAMES and input_source != "original_code":
            findings = handler(check_input, context=context)
        else:
            findings = handler(check_input)

        violations = []
        for finding in findings or []:
            if not isinstance(finding, dict):
                continue
            local_line = int(finding.get("line", 0) or 0)
            if local_line <= 0:
                local_line = anchor_line
            absolute_line = base_line + local_line - 1
            violations.append(
                self._build_p1_issue(
                    str(finding.get("rule_id", "")),
                    str(finding.get("rule_item", "")),
                    str(finding.get("severity", "Info")),
                    absolute_line,
                    str(finding.get("message", "")),
                    analysis_code,
                    event_name,
                )
            )
        return violations

    def _run_regex_rule(
        self,
        rule_def: Dict[str, Any],
        analysis_code: str,
        event_name: str,
        base_line: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:
        detector = rule_def.get("detector", {}) if isinstance(rule_def.get("detector"), dict) else {}
        pattern = detector.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            return []

        allowed_events = detector.get("_allowed_event_names")
        if isinstance(allowed_events, set) and allowed_events and str(event_name) not in allowed_events:
            return []

        invalid_regex_error = str(detector.get("_invalid_regex_error", "") or "")
        if invalid_regex_error:
            return []

        compiled = detector.get("_compiled_regex")
        if not isinstance(compiled, re.Pattern):
            flags = self._regex_flags_from_rule(detector.get("flags", ["DOTALL", "MULTILINE"]))
            try:
                compiled = re.compile(pattern, flags)
            except re.error:
                return []
        match = compiled.search(analysis_code)
        if not match:
            return []

        rule_id = str(rule_def.get("rule_id", detector.get("rule_id", "")) or "")
        rule_item = str(rule_def.get("item", "") or "")
        finding = rule_def.get("finding", {}) if isinstance(rule_def.get("finding"), dict) else {}
        severity = str(finding.get("severity", rule_def.get("severity", "Info")) or "Info")
        message = str(finding.get("message", rule_def.get("message", "")) or "")
        if not (rule_id and rule_item and message):
            return []

        absolute_line = self._line_from_offset(analysis_code, match.start(), base_line=base_line, context=context)
        return [self._build_p1_issue(rule_id, rule_item, severity, absolute_line, message, analysis_code, event_name)]

    def _run_line_repeat_rule(
        self,
        rule_def: Dict[str, Any],
        analysis_code: str,
        event_name: str,
        base_line: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:
        detector = rule_def.get("detector", {}) if isinstance(rule_def.get("detector"), dict) else {}
        threshold = int(detector.get("threshold", 3) or 3)
        min_len = int(detector.get("min_line_length", 8) or 8)
        ignore_comments = bool(detector.get("ignore_comments", True))
        ignore_braces_only = bool(detector.get("ignore_braces_only", True))
        normalize_ws = bool(detector.get("normalize_whitespace", True))

        normalized_lines = self._get_normalized_lines(
            analysis_code,
            context=context,
            ignore_comments=ignore_comments,
            ignore_braces_only=ignore_braces_only,
            normalize_ws=normalize_ws,
            min_len=min_len,
        )
        counter = Counter([line for _, line in normalized_lines])
        hit_line = None
        for line_text, count in counter.items():
            if count >= threshold:
                hit_line = next(idx for idx, value in normalized_lines if value == line_text)
                break
        if hit_line is None:
            return []

        rule_id = str(rule_def.get("rule_id", detector.get("rule_id", "")) or "")
        rule_item = str(rule_def.get("item", "") or "")
        finding = rule_def.get("finding", {}) if isinstance(rule_def.get("finding"), dict) else {}
        severity = str(finding.get("severity", rule_def.get("severity", "Info")) or "Info")
        message = str(finding.get("message", rule_def.get("message", "")) or "")
        if not (rule_id and rule_item and message):
            return []

        absolute_line = base_line + hit_line - 1
        return [self._build_p1_issue(rule_id, rule_item, severity, absolute_line, message, analysis_code, event_name)]

    def _run_composite_rule(
        self,
        rule_def: Dict[str, Any],
        code: str,
        analysis_code: str,
        event_name: str,
        base_line: int,
        anchor_line: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:
        detector = rule_def.get("detector", {}) if isinstance(rule_def.get("detector"), dict) else {}
        op = str(detector.get("op", "") or "").strip().lower()
        if not op:
            return []

        # Batch 4 migration: keep behavior parity by routing high-complexity rules
        # through the existing legacy implementations while using the Config-driven
        # composite engine path.
        proxy_ops = {
            "memory_leaks_advanced": "check_memory_leaks_advanced",
        }
        if op in proxy_ops:
            legacy_rule_def = dict(rule_def)
            legacy_detector = dict(detector)
            legacy_detector["kind"] = "legacy_handler"
            legacy_detector["handler"] = str(detector.get("proxy_legacy_handler") or proxy_ops[op])
            legacy_detector.setdefault("input_source", "analysis_code")
            legacy_rule_def["detector"] = legacy_detector
            return self._run_legacy_handler_rule(
                legacy_rule_def,
                code=code,
                analysis_code=analysis_code,
                event_name=event_name,
                base_line=base_line,
                anchor_line=anchor_line,
                context=context,
            )

        rule_id = str(rule_def.get("rule_id", "") or "")
        rule_item = str(rule_def.get("item", "") or "")
        finding_meta = rule_def.get("finding", {}) if isinstance(rule_def.get("finding"), dict) else {}
        severity = str(finding_meta.get("severity", "Info") or "Info")
        static_message = str(finding_meta.get("message", "") or "")

        # --- Dispatch to CompositeRulesMixin handler ---
        handler_name = self.COMPOSITE_OP_DISPATCH.get(op)
        if handler_name is None:
            print(f"[!] Unsupported composite op in p1_rule_defs: {op}")
            return []
        ctx = CompositeRuleContext(
            rule_def=rule_def,
            detector=detector,
            code=code,
            analysis_code=analysis_code,
            event_name=event_name,
            base_line=base_line,
            anchor_line=anchor_line,
            rule_id=rule_id,
            rule_item=rule_item,
            severity=severity,
            static_message=static_message,
        )
        return getattr(self, handler_name)(ctx)

    def _run_configured_p1_rules(
        self,
        code: str,
        analysis_code: str,
        event_name: str,
        base_line: int,
        anchor_line: int,
        file_type: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:
        violations: List[Dict] = []
        for rule_def in self.p1_rule_defs:
            if not bool(rule_def.get("enabled", True)):
                continue
            if not self._p1_rule_enabled_for_file_type(rule_def, file_type):
                continue
            detector = rule_def.get("detector")
            if not isinstance(detector, dict):
                continue
            kind = str(detector.get("kind", "") or "").strip().lower()
            if kind == "legacy_handler":
                violations.extend(
                    self._run_legacy_handler_rule(
                        rule_def,
                        code=code,
                        analysis_code=analysis_code,
                        event_name=event_name,
                        base_line=base_line,
                        anchor_line=anchor_line,
                        context=context,
                    )
                )
            elif kind == "regex":
                violations.extend(
                    self._run_regex_rule(
                        rule_def,
                        analysis_code=analysis_code,
                        event_name=event_name,
                        base_line=base_line,
                        context=context,
                    )
                )
            elif kind == "line_repeat":
                violations.extend(
                    self._run_line_repeat_rule(
                        rule_def,
                        analysis_code=analysis_code,
                        event_name=event_name,
                        base_line=base_line,
                        context=context,
                    )
                )
            elif kind == "composite":
                violations.extend(
                    self._run_composite_rule(
                        rule_def,
                        code=code,
                        analysis_code=analysis_code,
                        event_name=event_name,
                        base_line=base_line,
                        anchor_line=anchor_line,
                        context=context,
                    )
                )
            else:
                print(f"[!] Unsupported detector kind in p1_rule_defs: {kind}")
        return violations
