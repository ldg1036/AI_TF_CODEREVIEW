import hashlib
import json
import os
import re
from collections import Counter
from typing import Any, Callable, Dict, List, Optional

from core.rules.performance_rules import PerformanceRulesMixin
from core.rules.security_rules import SecurityRulesMixin
from core.rules.style_rules import StyleRulesMixin
from core.rules.quality_rules import QualityRulesMixin
from core.rules.config_rules import ConfigRulesMixin


class HeuristicChecker(
    PerformanceRulesMixin,
    SecurityRulesMixin,
    StyleRulesMixin,
    QualityRulesMixin,
    ConfigRulesMixin,
):
    """Static heuristic checker for WinCC OA style rules.

    Rule check methods are organized into Mixin classes under core/rules/:
    - PerformanceRulesMixin: check_while_delay_policy, check_consecutive_dpset, etc.
    - SecurityRulesMixin: check_sql_injection, check_dp_function_exception, etc.
    - StyleRulesMixin: check_style_name_rules, check_coding_standards_advanced, etc.
    - QualityRulesMixin: check_complexity, check_unused_variables, check_dead_code, etc.
    - ConfigRulesMixin: check_config_format_consistency, check_hardcoding_extended, etc.
    """

    def __init__(self, rules_path: str = None):
        if rules_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            rules_path = os.path.join(base_dir, "..", "Config", "parsed_rules.json")

        self.rules_data = self._load_rules(rules_path)
        self.technical_patterns = self._define_technical_patterns()
        self.rule_item_aliases = {
            "loop문내의처리조건": "loop문내에처리조건",
            "명명규칙및코딩스타일준수여부확인": "명명규칙및코딩스타일준수확인",
        }
        self.allowed_rule_items = self._build_allowed_rule_items()
        self.legacy_detector_handlers = self._build_legacy_detector_handlers()
        self.p1_rule_defs = self._load_p1_rule_defs(rules_path)
        self.item_filter_fallback_rule_ids_by_type = self._build_item_filter_fallback_rule_ids_by_type()

    def _load_rules(self, path: str) -> List[Dict]:
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8-sig") as f:
                    return json.load(f)

            alt_path = path.replace("parsed_rules.json", "rules.json")
            if os.path.exists(alt_path):
                with open(alt_path, "r", encoding="utf-8-sig") as f:
                    return json.load(f)
            return []
        except Exception as e:
            print(f"[!] Error loading rules: {e}")
            return []

    def _define_technical_patterns(self) -> Dict:
        return {
            "PERF-01": {
                "pattern": r"(dpConnect|dpQueryConnect)[^\n]{0,200}delay\(",
                "message": "Callback 내부 delay 사용 감지.",
                "severity": "Critical",
                "rule_item": "비동기 처리(dpConnect, dpQueryConnectSingle) 시 Callback 함수 병목 요소 최소화",
            },
            "PERF-02": {
                "pattern": r"dpQuery.*FROM.*[\"'](\*\*|\*\.\*)[\"']",
                "message": "DP Query 전체 범위 조회 패턴 감지.",
                "severity": "Warning",
                "rule_item": "DP Query 최적화 구현",
            },
            "HARD-01": {
                "pattern": r"\b(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b|https?://[^\s\"']+|[\"']config/[^\n\"']+[\"']",
                "message": "IP/URL/설정 경로 하드코딩 감지.",
                "severity": "Medium",
                "rule_item": "하드코딩 지양",
            },
            "DB-01": {
                "pattern": r"sprintf.*(SELECT|INSERT|UPDATE|DELETE)",
                "message": "문자열 SQL 조합 감지.",
                "severity": "Critical",
                "rule_item": "바인딩 쿼리 처리",
            },
            "DB-02": {
                # Line-scoped pattern to avoid catastrophic backtracking on large files.
                "pattern": r"^(?!\s*//)[^\n]*\b(SELECT|INSERT|UPDATE|DELETE)\b",
                "message": "쿼리 주석 누락 가능성 감지.",
                "severity": "Info",
                "rule_item": "쿼리 주석 처리",
            },
        }

    @staticmethod
    def _compact_text(text: str) -> str:
        return re.sub(r"\s+", "", str(text or "")).lower()

    def _normalize_rule_item(self, rule_item: str) -> str:
        compact = self._compact_text(rule_item)
        return self.rule_item_aliases.get(compact, compact)

    def _build_allowed_rule_items(self) -> Dict[str, set]:
        allowed = {"Client": set(), "Server": set()}
        for row in self.rules_data:
            if not isinstance(row, dict):
                continue
            rule_type = row.get("type")
            item = row.get("item")
            if rule_type not in allowed:
                continue
            if not isinstance(item, str):
                continue
            stripped = item.strip()
            if not stripped or stripped.lower() == "nan":
                continue
            allowed[rule_type].add(self._normalize_rule_item(stripped))
        return allowed

    def _is_rule_allowed(self, rule_item: str, file_type: str) -> bool:
        allowed = self.allowed_rule_items.get(file_type)
        if not allowed:
            # If rules were not loaded, avoid dropping findings silently.
            return True
        normalized = self._normalize_rule_item(rule_item)
        return normalized in allowed

    def _build_item_filter_fallback_rule_ids_by_type(self) -> Dict[str, set]:
        allowed = {"Client": set(), "Server": set()}
        for row in self.p1_rule_defs:
            if not isinstance(row, dict):
                continue
            if not row.get("enabled", False):
                continue
            meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
            if not meta.get("allow_item_filter_fallback"):
                continue
            rule_id = row.get("rule_id")
            if not isinstance(rule_id, str) or not rule_id.strip():
                continue
            for file_type in ("Client", "Server"):
                if self._p1_rule_enabled_for_file_type(row, file_type):
                    allowed[file_type].add(rule_id.strip())
        return allowed

    def _filter_violations_by_file_type(self, violations: List[Dict], file_type: str) -> List[Dict]:
        filtered = []
        fallback_rule_ids = self.item_filter_fallback_rule_ids_by_type.get(file_type, set())
        for violation in violations:
            rule_id = violation.get("rule_id")
            rule_item = violation.get("rule_item")
            if rule_id == "INFO" or not rule_item:
                filtered.append(violation)
                continue
            if self._is_rule_allowed(rule_item, file_type):
                filtered.append(violation)
                continue
            # Narrow fallback for known parsed_rules.json extraction gaps/string drift only.
            if isinstance(rule_id, str) and rule_id in fallback_rule_ids:
                filtered.append(violation)
        return filtered

    def _load_p1_rule_defs(self, rules_path: str) -> List[Dict]:
        try:
            cfg_dir = os.path.dirname(os.path.abspath(rules_path))
            defs_path = os.path.join(cfg_dir, "p1_rule_defs.json")
            if not os.path.exists(defs_path):
                return []
            with open(defs_path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            if not isinstance(data, list):
                print("[!] p1_rule_defs.json must be a list. Falling back to legacy P1 engine.")
                return []
            return [row for row in data if isinstance(row, dict)]
        except Exception as e:
            print(f"[!] Error loading p1 rule defs: {e}")
            return []

    def _build_legacy_detector_handlers(self) -> Dict[str, Callable]:
        return {
            "check_sql_injection": self.check_sql_injection,
            "check_complexity": self.check_complexity,
            "check_unused_variables": self.check_unused_variables,
            "check_db_query_error": self.check_db_query_error,
            "check_dp_function_exception": self.check_dp_function_exception,
            "check_config_format_consistency": self.check_config_format_consistency,
            "check_config_error_contract": self.check_config_error_contract,
            "check_while_delay_policy": self.check_while_delay_policy,
            "check_event_exchange_minimization": self.check_event_exchange_minimization,
            "check_dpset_timed_context": self.check_dpset_timed_context,
            "check_dpget_batch_optimization": self.check_dpget_batch_optimization,
            "check_dpset_batch_optimization": self.check_dpset_batch_optimization,
            "check_setvalue_batch_optimization": self.check_setvalue_batch_optimization,
            "check_setmultivalue_adoption": self.check_setmultivalue_adoption,
            "check_getvalue_batch_optimization": self.check_getvalue_batch_optimization,
            "check_try_catch_for_risky_ops": self.check_try_catch_for_risky_ops,
            "check_division_zero_guard": self.check_division_zero_guard,
            "check_manual_aggregation_pattern": self.check_manual_aggregation_pattern,
            "check_consecutive_dpset": self.check_consecutive_dpset,
            "check_memory_leaks_advanced": self.check_memory_leaks_advanced,
            "check_input_validation": self.check_input_validation,
            "check_coding_standards_advanced": self.check_coding_standards_advanced,
            "check_style_name_rules": self.check_style_name_rules,
            "check_style_indent_rules": self.check_style_indent_rules,
            "check_style_header_rules": self.check_style_header_rules,
            "check_magic_index_usage": self.check_magic_index_usage,
            "check_hardcoding_extended": self.check_hardcoding_extended,
            "check_float_literal_hardcoding": self.check_float_literal_hardcoding,
            "check_dead_code": self.check_dead_code,
            "check_duplicate_blocks": self.check_duplicate_blocks,
            "__ui_block_initialize_delay__": self._legacy_ui_block_initialize_delay,
        }

    @staticmethod
    def _p1_rule_enabled_for_file_type(rule_def: Dict[str, Any], file_type: str) -> bool:
        file_types = rule_def.get("file_types")
        if file_types is None:
            return True
        if isinstance(file_types, str):
            file_types = [file_types]
        if not isinstance(file_types, list):
            return True
        normalized = {str(x).strip().lower() for x in file_types if str(x).strip()}
        if not normalized or "all" in normalized or "both" in normalized:
            return True
        return str(file_type or "").strip().lower() in normalized

    @staticmethod
    def _regex_flags_from_rule(flag_names: Any) -> int:
        if isinstance(flag_names, str):
            flag_names = [flag_names]
        flags = 0
        if not isinstance(flag_names, list):
            return flags
        mapping = {
            "IGNORECASE": re.IGNORECASE,
            "MULTILINE": re.MULTILINE,
            "DOTALL": re.DOTALL,
        }
        for name in flag_names:
            key = str(name or "").strip().upper()
            flags |= mapping.get(key, 0)
        return flags

    @staticmethod
    def _normalize_detector_regex(pattern: Any) -> str:
        text = str(pattern or "")
        if not text:
            return ""
        # Some detector entries were serialized with double-escaped regex tokens
        # like "\\\\b", which should behave as "\\b" at runtime.
        try:
            return re.sub(r"\\\\([\\bBsSdDwW\(\)\[\]\{\}\.\+\*\?\^\$\|])", r"\\\1", text)
        except Exception:
            return text

    def _build_p1_issue(
        self,
        rule_id: str,
        rule_item: str,
        severity: str,
        line: int,
        message: str,
        analysis_code: str,
        event_name: str,
    ) -> Dict:
        return {
            "issue_id": self._build_issue_id(rule_id, analysis_code, line, event_name),
            "rule_id": rule_id,
            "rule_item": rule_item,
            "priority_origin": "P1",
            "severity": severity,
            "line": line,
            "message": message,
        }

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
    ) -> List[Dict]:
        detector = rule_def.get("detector", {}) if isinstance(rule_def.get("detector"), dict) else {}
        pattern = detector.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            return []

        event_names = detector.get("event_names")
        if isinstance(event_names, str):
            event_names = [event_names]
        if isinstance(event_names, list) and event_names:
            allowed_events = {str(x) for x in event_names}
            if str(event_name) not in allowed_events:
                return []

        flags = self._regex_flags_from_rule(detector.get("flags", ["DOTALL", "MULTILINE"]))
        try:
            match = re.search(pattern, analysis_code, flags)
        except re.error as e:
            print(f"[!] Invalid regex in p1_rule_defs ({rule_def.get('id', rule_def.get('rule_id'))}): {e}")
            return []
        if not match:
            return []

        rule_id = str(rule_def.get("rule_id", detector.get("rule_id", "")) or "")
        rule_item = str(rule_def.get("item", "") or "")
        finding = rule_def.get("finding", {}) if isinstance(rule_def.get("finding"), dict) else {}
        severity = str(finding.get("severity", rule_def.get("severity", "Info")) or "Info")
        message = str(finding.get("message", rule_def.get("message", "")) or "")
        if not (rule_id and rule_item and message):
            return []

        absolute_line = self._line_from_offset(analysis_code, match.start(), base_line=base_line)
        return [self._build_p1_issue(rule_id, rule_item, severity, absolute_line, message, analysis_code, event_name)]

    def _run_line_repeat_rule(
        self,
        rule_def: Dict[str, Any],
        analysis_code: str,
        event_name: str,
        base_line: int,
    ) -> List[Dict]:
        detector = rule_def.get("detector", {}) if isinstance(rule_def.get("detector"), dict) else {}
        threshold = int(detector.get("threshold", 3) or 3)
        min_len = int(detector.get("min_line_length", 8) or 8)
        ignore_comments = bool(detector.get("ignore_comments", True))
        ignore_braces_only = bool(detector.get("ignore_braces_only", True))
        normalize_ws = bool(detector.get("normalize_whitespace", True))

        normalized_lines = []
        for idx, raw in enumerate(analysis_code.splitlines(), 1):
            line = raw.strip()
            if not line:
                continue
            if ignore_comments and line.startswith("//"):
                continue
            if ignore_braces_only and line in {"{", "}"}:
                continue
            if normalize_ws:
                line = re.sub(r"\s+", " ", line)
            if len(line) < min_len:
                continue
            normalized_lines.append((idx, line))

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
            )

        rule_id = str(rule_def.get("rule_id", "") or "")
        rule_item = str(rule_def.get("item", "") or "")
        finding_meta = rule_def.get("finding", {}) if isinstance(rule_def.get("finding"), dict) else {}
        severity = str(finding_meta.get("severity", "Info") or "Info")
        static_message = str(finding_meta.get("message", "") or "")

        if op == "sql_injection":
            sql_keywords_raw = str(
                detector.get("sql_keywords_pattern", r"\b(SELECT|INSERT|UPDATE|DELETE|FROM|WHERE|JOIN)\b")
            )
            sprintf_pattern_raw = str(detector.get("sprintf_pattern", r"sprintf.*%s"))
            sql_keywords = self._normalize_detector_regex(sql_keywords_raw)
            sprintf_pattern = self._normalize_detector_regex(sprintf_pattern_raw)
            try:
                re.compile(sql_keywords, re.IGNORECASE)
            except re.error:
                sql_keywords = sql_keywords_raw
            try:
                re.compile(sprintf_pattern)
            except re.error:
                sprintf_pattern = sprintf_pattern_raw
            for idx, line in enumerate(analysis_code.splitlines(), 1):
                if re.search(sprintf_pattern, line) and re.search(sql_keywords, line, re.IGNORECASE):
                    absolute_line = base_line + idx - 1
                    return [self._build_p1_issue(rule_id, rule_item, severity, absolute_line, static_message, analysis_code, event_name)]
            return []

        if op == "db_query_error":
            query_pattern_raw = str(detector.get("query_call_pattern", r"\b(dpQuery|dbGet)\b"))
            query_pattern = self._normalize_detector_regex(query_pattern_raw)
            try:
                re.compile(query_pattern)
            except re.error:
                query_pattern = query_pattern_raw
            if not re.search(query_pattern, analysis_code):
                return []
            if re.search(r"\b(writeLog|DebugTN|getLastError)\b", analysis_code):
                return []
            match = re.search(query_pattern, analysis_code)
            absolute_line = self._line_from_offset(analysis_code, match.start(), base_line=base_line) if match else (base_line + anchor_line - 1)
            return [self._build_p1_issue(rule_id, rule_item, severity, absolute_line, static_message, analysis_code, event_name)]

        if op == "dp_function_exception":
            dp_call_pattern_raw = str(detector.get("dp_call_pattern", r"\b(dpSet|dpGet|dpQuery|dpConnect)\s*\([^;]+\)\s*;"))
            dp_call_pattern = self._normalize_detector_regex(dp_call_pattern_raw)
            try:
                re.compile(dp_call_pattern)
            except re.error:
                dp_call_pattern = dp_call_pattern_raw
            first_dp_call = re.search(dp_call_pattern, analysis_code)
            if not first_dp_call:
                return []

            has_try = bool(re.search(r"\btry\b", analysis_code, re.IGNORECASE))
            has_catch = bool(re.search(r"\bcatch\b", analysis_code, re.IGNORECASE))
            has_try_catch = has_try and has_catch
            has_get_last_error = "getLastError" in analysis_code
            has_return_check = bool(
                re.search(
                    r"\b(?:if|switch)\s*\([^\)]*(?:ret|result|err|error|rc|status|iErr|return_value)[^\)]*\)",
                    analysis_code,
                    re.IGNORECASE,
                )
                or re.search(
                    r"\b(?:ret|result|err|error|rc|status|iErr|return_value)\s*=\s*(?:dpSet|dpGet|dpQuery|dpConnect)\b",
                    analysis_code,
                )
            )
            if has_try_catch or has_get_last_error or has_return_check:
                return []

            absolute_line = self._line_from_offset(analysis_code, first_dp_call.start(), base_line=base_line)
            return [self._build_p1_issue(rule_id, rule_item, severity, absolute_line, static_message, analysis_code, event_name)]

        if op == "complexity":
            findings: List[Dict] = []
            max_code_length = int(detector.get("max_code_length", 100000) or 100000)
            if len(analysis_code) > max_code_length:
                return []

            lines = analysis_code.split("\n")
            anchor_local = self._first_function_line(analysis_code)
            max_lines = int(detector.get("max_lines", 500) or 500)
            if len(lines) > max_lines:
                findings.append(
                    self._build_p1_issue(
                        str(detector.get("line_rule_id", "COMP-01")),
                        str(detector.get("line_rule_item", rule_item or "불필요한 코드 지양")),
                        str(detector.get("line_severity", "Medium")),
                        base_line + anchor_local - 1,
                        str(detector.get("line_message_prefix", "함수 길이 과다")) + f" ({len(lines)} lines).",
                        analysis_code,
                        event_name,
                    )
                )

            depth = 0
            max_depth = 0
            max_scan_lines = int(detector.get("max_scan_lines", 2000) or 2000)
            for line in lines[:max_scan_lines]:
                depth += line.count("{")
                depth -= line.count("}")
                max_depth = max(max_depth, depth)

            depth_threshold = int(detector.get("max_depth", 10) or 10)
            if max_depth > depth_threshold:
                findings.append(
                    self._build_p1_issue(
                        str(detector.get("depth_rule_id", "COMP-02")),
                        str(detector.get("depth_rule_item", rule_item or "불필요한 코드 지양")),
                        str(detector.get("depth_severity", "Medium")),
                        base_line + anchor_local - 1,
                        str(detector.get("depth_message_prefix", "제어문 중첩 과다")) + f" (Max depth: {max_depth}).",
                        analysis_code,
                        event_name,
                    )
                )
            return findings

        if op == "unused_variables":
            max_code_length = int(detector.get("max_code_length", 100000) or 100000)
            if len(analysis_code) > max_code_length:
                return []

            clean_code = self._remove_comments(analysis_code)
            all_words = re.findall(r"\b\w+\b", clean_code)
            word_counts = Counter(all_words)

            exception_prefixes = tuple(
                detector.get(
                    "exception_prefixes",
                    ["param_", "cfg_", "g_", "manager_", "query_", "Script", "is_", "thread_", "dp_"],
                )
            )
            exception_vars = set(
                detector.get(
                    "exception_vars",
                    [
                        "return_value",
                        "i",
                        "j",
                        "k",
                        "idx",
                        "cnt",
                        "count",
                        "len",
                        "size",
                        "ret",
                        "result",
                        "success",
                        "ok",
                        "error",
                        "err",
                    ],
                )
            )
            decl_pattern = str(
                detector.get(
                    "declaration_pattern",
                    r"(?<!const\s)\b(int|float|string|bool|dyn_\w+|mapping|time|void|blob|anytype)\s+([a-zA-Z0-9_]+)\s*(=|;)",
                )
            )
            string_usage_pattern_template = str(detector.get("string_usage_template", r'"[^"]*{name}[^"]*"'))
            usage_threshold = int(detector.get("usage_threshold", 1) or 1)
            out_rule_id = str(rule_def.get("rule_id", detector.get("rule_id", "UNUSED-01")) or "UNUSED-01")
            out_item = str(rule_def.get("item", detector.get("rule_item", "불필요한 코드 지양")) or "불필요한 코드 지양")
            out_severity = str(finding_meta.get("severity", detector.get("severity", "Low")) or "Low")
            msg_prefix = str(detector.get("message_prefix", "미사용 변수 감지") or "미사용 변수 감지")

            declarations = re.finditer(decl_pattern, clean_code)
            declared_vars: Dict[str, int] = {}
            findings: List[Dict] = []
            for match in declarations:
                var_name = match.group(2)
                if var_name in declared_vars:
                    continue
                declared_vars[var_name] = self._line_from_offset(clean_code, match.start(), base_line=1)
                if var_name.startswith(exception_prefixes) or var_name in exception_vars:
                    continue
                usage_count = int(word_counts.get(var_name, 0))
                if usage_count <= usage_threshold:
                    string_usage_pattern = string_usage_pattern_template.format(name=re.escape(var_name))
                    if re.search(string_usage_pattern, clean_code):
                        continue
                    findings.append(
                        self._build_p1_issue(
                            out_rule_id,
                            out_item,
                            out_severity,
                            base_line + declared_vars[var_name] - 1,
                            f"{msg_prefix}: '{var_name}'",
                            analysis_code,
                            event_name,
                        )
                    )
            return findings

        if op == "event_exchange_minimization":
            loop_pattern = re.compile(r"\b(?:while|for)\s*\([^\)]*\)\s*\{", re.IGNORECASE)
            func_defs = {}
            func_pattern = re.compile(
                r"\b(?:void|int|float|string|bool|mapping|time|anytype|dyn_[a-zA-Z0-9_]+)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^\)]*\)\s*\{",
                re.IGNORECASE,
            )
            for func_match in func_pattern.finditer(analysis_code):
                name = func_match.group(1)
                brace_idx = analysis_code.find("{", func_match.start())
                if brace_idx < 0:
                    continue
                close_brace = self._find_matching_delimiter(analysis_code, brace_idx, "{", "}")
                if close_brace < 0:
                    continue
                func_defs[name] = analysis_code[brace_idx : close_brace + 1]

            excluded_calls = {
                "if",
                "for",
                "while",
                "switch",
                "return",
                "catch",
                "try",
                "dpSet",
                "dpSetWait",
                "dpSetTimed",
                "dpGet",
                "dpQuery",
                "writeLog",
                "DebugN",
                "dynlen",
                "mappinglen",
            }

            def _body_has_unsafe_dpset(body: str, depth: int, seen: set) -> bool:
                if re.search(r"\bdpSet\s*\(", body):
                    if not re.search(r"\bdpSet(?:Wait|Timed)\s*\(", body) and not re.search(
                        r"\bif\s*\([^\)]*(?:\bchanged\b|\bdelta\b|\bold\b|\bprev\b)[^\)]*\)",
                        body,
                        re.IGNORECASE,
                    ):
                        return True
                if depth <= 0:
                    return False
                called_names = [
                    token
                    for token in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", body)
                    if token not in excluded_calls
                ]
                for called_name in called_names:
                    if called_name in seen:
                        continue
                    callee_body = func_defs.get(called_name, "")
                    if not callee_body:
                        continue
                    if _body_has_unsafe_dpset(callee_body, depth - 1, seen | {called_name}):
                        return True
                return False

            for loop_match in loop_pattern.finditer(analysis_code):
                brace_idx = analysis_code.find("{", loop_match.start())
                if brace_idx < 0:
                    continue
                close_brace = self._find_matching_delimiter(analysis_code, brace_idx, "{", "}")
                if close_brace < 0:
                    continue

                block = analysis_code[brace_idx : close_brace + 1]
                dpset_matches = list(re.finditer(r"\bdpSet\s*\(", block))
                indirect_dpset_call = ""
                if len(dpset_matches) < 1:
                    called_names = [
                        token
                        for token in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", block)
                        if token not in excluded_calls
                    ]
                    for called_name in called_names:
                        callee_body = func_defs.get(called_name, "")
                        if not callee_body:
                            continue
                        if _body_has_unsafe_dpset(callee_body, depth=2, seen={called_name}):
                            indirect_dpset_call = called_name
                            break
                    if not indirect_dpset_call:
                        continue

                if re.search(r"\bdpSet(?:Wait|Timed)\s*\(", block):
                    continue
                if re.search(r"\bif\s*\([^\)]*(?:\bchanged\b|\bdelta\b|\bold\b|\bprev\b)[^\)]*\)", block, re.IGNORECASE):
                    continue

                merged_match = re.search(r"\bdpSet\s*\(\s*\"[^\"]+\"\s*,\s*[^,]+,\s*\"[^\"]+\"\s*,", block)
                if merged_match:
                    continue

                absolute_line = self._line_from_offset(analysis_code, loop_match.start(), base_line=base_line)
                message = (
                    f"루프 내 호출 함수({indirect_dpset_call})에서 dpSet 수행 감지: 변경 가드/배치 처리(dpSetWait, dpSetTimed) 권장."
                    if indirect_dpset_call
                    else (static_message or "루프 내 dpSet 호출 감지: 변경 가드/배치 처리(dpSetWait, dpSetTimed) 권장.")
                )
                return [self._build_p1_issue(rule_id, rule_item, severity, absolute_line, message, analysis_code, event_name)]
            return []

        if op == "coding_standards_advanced":
            lines = analysis_code.splitlines()
            decl_start_pattern = re.compile(r"^\s*(?:int|float|string|bool|dyn_\w+)\s+[a-zA-Z_][a-zA-Z0-9_]*")
            control_pattern = re.compile(r"^\s*(?:if|for|while|switch|return|break|continue|try|catch)\b")

            pending_start_line = 0
            for line_no, line in enumerate(lines, 1):
                stripped = line.strip()
                if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
                    continue

                if pending_start_line:
                    if ";" in stripped:
                        pending_start_line = 0
                        continue
                    if control_pattern.match(stripped) or stripped.endswith("{") or stripped.endswith("}"):
                        absolute_line = base_line + pending_start_line - 1
                        message = f"L{pending_start_line}: 변수 선언 시 세미콜론(;) 누락 가능성."
                        return [self._build_p1_issue(rule_id, rule_item, severity, absolute_line, message, analysis_code, event_name)]
                    continue

                if not decl_start_pattern.match(stripped):
                    continue
                if stripped.endswith(";"):
                    continue
                if "(" in stripped and ")" in stripped:
                    continue
                pending_start_line = line_no

            if pending_start_line:
                absolute_line = base_line + pending_start_line - 1
                message = f"L{pending_start_line}: 변수 선언 시 세미콜론(;) 누락 가능성."
                return [self._build_p1_issue(rule_id, rule_item, severity, absolute_line, message, analysis_code, event_name)]
            return []

        if op == "memory_leaks_advanced":
            decl_pattern = str(detector.get("declaration_pattern", r"\bdyn_\w+\s+[a-zA-Z_][a-zA-Z0-9_]*"))
            cleanup_pattern = str(detector.get("cleanup_pattern", r"\bdyn(?:Clear|Remove)\s*\("))
            loop_dyn_ops_pattern = str(
                detector.get(
                    "loop_dyn_ops_pattern",
                    r"\b(?:while|for)\s*\([^\)]*\)\s*\{[\s\S]{0,1200}\bdyn(?:Append|Insert|MapInsert)\s*\(",
                )
            )
            declarations = [
                (idx, line)
                for idx, line in enumerate(analysis_code.splitlines(), 1)
                if re.search(decl_pattern, line)
            ]
            if not declarations:
                return []
            if re.search(cleanup_pattern, analysis_code):
                return []
            if not re.search(loop_dyn_ops_pattern, analysis_code, re.IGNORECASE):
                return []
            absolute_line = base_line + declarations[0][0] - 1
            return [self._build_p1_issue(rule_id, rule_item, severity, absolute_line, static_message, analysis_code, event_name)]

        if op == "ui_block_initialize_delay":
            event_equals = str(detector.get("event_equals", "Initialize") or "Initialize")
            needle = str(detector.get("contains", "delay(") or "delay(")
            if event_name == event_equals and needle in analysis_code and rule_id and rule_item and static_message:
                ui_line = base_line + anchor_line - 1
                return [self._build_p1_issue(rule_id, rule_item, severity, ui_line, static_message, analysis_code, event_name)]
            return []

        if op == "style_indent_mixed":
            saw_tab_indent = False
            saw_space_indent = False
            mixed_line = 0
            for idx, line in enumerate(analysis_code.splitlines(), 1):
                if not line.strip():
                    continue
                indent_match = re.match(r"^([ \t]+)", line)
                if not indent_match:
                    continue
                indent = indent_match.group(1)
                if "\t" in indent and " " in indent:
                    mixed_line = idx
                    break
                if "\t" in indent:
                    saw_tab_indent = True
                if " " in indent:
                    saw_space_indent = True
            if mixed_line or (saw_tab_indent and saw_space_indent):
                absolute_line = base_line + ((mixed_line or 1) - 1)
                return [self._build_p1_issue(rule_id, rule_item, severity, absolute_line, static_message, analysis_code, event_name)]
            return []

        if op == "magic_index_usage":
            if re.search(r"\bIDX_[A-Z0-9_]+\b", analysis_code):
                return []
            matches = list(
                re.finditer(r"\b(?:parts|data|tokens|fields)\s*\[\s*([2-9]|\d{2,})\s*\]", analysis_code)
            )
            if len(matches) < int(detector.get("min_matches", 3) or 3):
                return []
            absolute_line = self._line_from_offset(analysis_code, matches[0].start(), base_line=base_line)
            return [self._build_p1_issue(rule_id, rule_item, severity, absolute_line, static_message, analysis_code, event_name)]

        if op == "float_literal_hardcoding":
            hit_lines = []
            literals = detector.get("literals", ["0.01", "0.001"])
            if isinstance(literals, str):
                literals = [literals]
            # Build a tolerant regex set while preserving current default behavior.
            literal_patterns = [re.escape(str(x)) for x in literals if str(x)]
            if not literal_patterns:
                literal_patterns = [r"0\.0*1", r"0\.001"]
            pattern = r"\b(?:" + "|".join(literal_patterns) + r")\b"
            for idx, line in enumerate(analysis_code.splitlines(), 1):
                if re.search(r"^\s*const\b", line):
                    continue
                if re.search(pattern, line):
                    hit_lines.append(idx)
            if len(hit_lines) >= int(detector.get("min_hits", 2) or 2):
                absolute_line = base_line + hit_lines[0] - 1
                return [self._build_p1_issue(rule_id, rule_item, severity, absolute_line, static_message, analysis_code, event_name)]
            return []

        if op == "hardcoding_extended":
            lines = analysis_code.splitlines()
            dp_path_hits = []
            dp_path_pattern = str(
                detector.get("dp_path_pattern", r'"([A-Za-z0-9_]+\.[A-Za-z0-9_\.]+)"')
            )
            for idx, line in enumerate(lines, 1):
                if re.search(r"^\s*const\b", line):
                    continue
                for match in re.finditer(dp_path_pattern, line):
                    val = match.group(1)
                    if val.count(".") >= int(detector.get("dp_min_dots", 2) or 2):
                        dp_path_hits.append((idx, val))
            dp_counter = Counter([value for _, value in dp_path_hits])
            repeated_dp = [
                value
                for value, count in dp_counter.items()
                if count >= int(detector.get("dp_repeat_threshold", 2) or 2)
            ]
            if repeated_dp:
                local_line = next((ln for ln, value in dp_path_hits if value == repeated_dp[0]), 1)
                absolute_line = base_line + local_line - 1
                msg = f"고정 DP 경로 문자열 반복 사용 감지: '{repeated_dp[0]}'."
                return [self._build_p1_issue(rule_id, rule_item, severity, absolute_line, msg, analysis_code, event_name)]

            number_hits = []
            ignored_numbers = set(str(x) for x in detector.get("ignore_numbers", ["10", "60", "100"]))
            for idx, line in enumerate(lines, 1):
                if re.search(r"^\s*const\b", line):
                    continue
                for match in re.finditer(r"\b\d{2,}\b", line):
                    value = match.group(0)
                    if value in ignored_numbers:
                        continue
                    number_hits.append((idx, value))
            num_counter = Counter([value for _, value in number_hits])
            repeated_num = [
                value
                for value, count in num_counter.items()
                if count >= int(detector.get("number_repeat_threshold", 3) or 3)
            ]
            if repeated_num:
                local_line = next((ln for ln, value in number_hits if value == repeated_num[0]), 1)
                absolute_line = base_line + local_line - 1
                msg = f"매직 넘버 반복 사용 감지: '{repeated_num[0]}'."
                return [self._build_p1_issue(rule_id, rule_item, severity, absolute_line, msg, analysis_code, event_name)]
            return []

        if op == "dead_code":
            detect_if_false = bool(detector.get("detect_if_false", True))
            detect_after_return = bool(detector.get("detect_after_return", True))

            if detect_if_false:
                false_if = re.search(r"\bif\s*\(\s*false\s*\)", analysis_code, re.IGNORECASE)
                if false_if:
                    absolute_line = self._line_from_offset(analysis_code, false_if.start(), base_line=base_line)
                    msg = static_message or "영구 미실행 분기(if(false)) 감지."
                    return [self._build_p1_issue(rule_id, rule_item, severity, absolute_line, msg, analysis_code, event_name)]

            if not detect_after_return:
                return []

            lines = analysis_code.splitlines()
            line_depths = []
            depth = 0
            for line in lines:
                line_depths.append(depth)
                depth += line.count("{")
                depth -= line.count("}")

            lookahead_limit = int(detector.get("return_lookahead_lines", 20) or 20)
            for idx, line in enumerate(lines, 1):
                if re.search(r"\breturn\b[^;]*;", line):
                    return_depth = line_depths[idx - 1]
                    for look_ahead in range(idx, min(len(lines), idx + lookahead_limit)):
                        if line_depths[look_ahead] < return_depth:
                            break
                        nxt = lines[look_ahead].strip()
                        if not nxt or nxt.startswith("//") or nxt == "}":
                            continue
                        absolute_line = base_line + idx - 1
                        msg = detector.get("return_after_message") or "return 이후 도달 불가능 코드 가능성 감지."
                        return [
                            self._build_p1_issue(
                                rule_id,
                                rule_item,
                                severity,
                                absolute_line,
                                str(msg),
                                analysis_code,
                                event_name,
                            )
                        ]
            return []

        if op == "while_delay_policy":
            for match in re.finditer(r"\bwhile\s*\(", analysis_code):
                open_paren = analysis_code.find("(", match.start())
                if open_paren < 0:
                    continue
                close_paren = self._find_matching_delimiter(analysis_code, open_paren, "(", ")")
                if close_paren < 0:
                    continue
                open_brace = analysis_code.find("{", close_paren)
                if open_brace < 0:
                    continue
                close_brace = self._find_matching_delimiter(analysis_code, open_brace, "{", "}")
                if close_brace < 0:
                    continue
                loop_block = analysis_code[open_brace : close_brace + 1]
                has_delay = bool(re.search(r"\b(?:delay|dpSetWait|dpSetTimed)\s*\(", loop_block))
                if has_delay:
                    continue
                absolute_line = self._line_from_offset(analysis_code, match.start(), base_line=base_line)
                return [self._build_p1_issue(rule_id, rule_item, severity, absolute_line, static_message, analysis_code, event_name)]
            return []

        if op == "while_delay_outside_active":
            active_guard_pattern = str(
                detector.get(
                    "active_guard_pattern",
                    r"\b(?:isActive|isScriptActive|active|enabled?|bActive|runFlag|useFlag)\b",
                )
            )
            delay_pattern = str(detector.get("delay_pattern", r"\b(?:delay|dpSetWait|dpSetTimed)\s*\("))

            for match in re.finditer(r"\bwhile\s*\(", analysis_code, re.IGNORECASE):
                open_paren = analysis_code.find("(", match.start())
                if open_paren < 0:
                    continue
                close_paren = self._find_matching_delimiter(analysis_code, open_paren, "(", ")")
                if close_paren < 0:
                    continue
                open_brace = analysis_code.find("{", close_paren)
                if open_brace < 0:
                    continue
                close_brace = self._find_matching_delimiter(analysis_code, open_brace, "{", "}")
                if close_brace < 0:
                    continue

                loop_block = analysis_code[open_brace : close_brace + 1]
                delay_iter = list(re.finditer(delay_pattern, loop_block, re.IGNORECASE))
                if not delay_iter:
                    continue

                active_if_ranges = []
                for if_match in re.finditer(r"\bif\s*\(", loop_block, re.IGNORECASE):
                    cond_open = loop_block.find("(", if_match.start())
                    if cond_open < 0:
                        continue
                    cond_close = self._find_matching_delimiter(loop_block, cond_open, "(", ")")
                    if cond_close < 0:
                        continue
                    cond_text = loop_block[cond_open + 1 : cond_close]
                    if not re.search(active_guard_pattern, cond_text, re.IGNORECASE):
                        continue
                    body_open = loop_block.find("{", cond_close)
                    if body_open < 0:
                        continue
                    body_close = self._find_matching_delimiter(loop_block, body_open, "{", "}")
                    if body_close < 0:
                        continue
                    active_if_ranges.append((body_open, body_close))

                if not active_if_ranges:
                    continue

                delay_positions = [m.start() for m in delay_iter]
                has_delay_outside_active = False
                for pos in delay_positions:
                    in_active = any(start <= pos <= end for start, end in active_if_ranges)
                    if not in_active:
                        has_delay_outside_active = True
                        break

                if has_delay_outside_active:
                    continue

                first_delay_abs = open_brace + delay_positions[0]
                absolute_line = self._line_from_offset(analysis_code, first_delay_abs, base_line=base_line)
                return [self._build_p1_issue(rule_id, rule_item, severity, absolute_line, static_message, analysis_code, event_name)]
            return []

        if op == "config_format_consistency":
            if not self._has_config_context(analysis_code):
                return []
            if "strsplit" not in analysis_code:
                return []
            delimiters = set(re.findall(r"\bstrsplit\s*\([^,]+,\s*\"([^\"]+)\"\s*\)", analysis_code))
            if len(delimiters) >= int(detector.get("delimiter_mismatch_threshold", 2) or 2):
                pos = analysis_code.find("strsplit")
                absolute_line = self._line_from_offset(analysis_code, pos, base_line=base_line)
                return [self._build_p1_issue(rule_id, rule_item, severity, absolute_line, static_message, analysis_code, event_name)]

            access_match = re.search(r"\b(?:parts|tokens|fields)\s*\[\s*\d+\s*\]", analysis_code)
            has_parts_access = bool(access_match)
            has_len_check = bool(
                re.search(
                    r"\b(?:dynlen|len)\s*\(\s*(?:parts|tokens|fields)\s*\)\s*(?:<|<=|>|>=|==|!=)\s*\d+",
                    analysis_code,
                )
            )
            if has_parts_access and not has_len_check:
                absolute_line = self._line_from_offset(analysis_code, access_match.start(), base_line=base_line)
                return [self._build_p1_issue(rule_id, rule_item, severity, absolute_line, static_message, analysis_code, event_name)]
            return []

        if op == "config_error_contract":
            if not self._has_config_context(analysis_code):
                return []
            has_parse_guard = bool(
                re.search(
                    r"\bif\s*\(\s*(?:dynlen|len)\s*\(\s*(?:parts|tokens|fields)\s*\)\s*(?:<|<=)\s*\d+\s*\)",
                    analysis_code,
                    re.IGNORECASE,
                )
            )
            if not has_parse_guard:
                return []
            has_continue = "continue;" in analysis_code
            has_fail_return = bool(re.search(r"\breturn\s+(?:false|-1)\s*;", analysis_code, re.IGNORECASE))
            if has_continue and not has_fail_return:
                absolute_line = self._line_from_offset(analysis_code, analysis_code.find("continue;"), base_line=base_line)
                return [self._build_p1_issue(rule_id, rule_item, severity, absolute_line, static_message, analysis_code, event_name)]
            return []

        if op == "try_catch_for_risky_ops":
            risky_iter = list(re.finditer(r"\b(dpSet|dpGet|dpQuery|fopen|fileOpen|strsplit)\s*\(", analysis_code))
            if not risky_iter:
                return []
            risky_match = risky_iter[0]
            if re.search(r"\btry\b", analysis_code, re.IGNORECASE) and re.search(r"\bcatch\b", analysis_code, re.IGNORECASE):
                return []
            if re.search(r"\bgetLastError\s*\(", analysis_code, re.IGNORECASE):
                return []
            if re.search(r"\breturn\s+(false|-1)\s*;", analysis_code, re.IGNORECASE):
                return []
            if re.search(r"\b(writeLog|DebugN|DebugTN)\s*\([^)]*(err|error|fail|getLastError)[^)]*\)", analysis_code, re.IGNORECASE):
                return []
            if re.search(r"\bif\s*\([^)]*(err|error|rc|ret|result|status)[^)]*\)", analysis_code, re.IGNORECASE):
                return []
            loop_ranges = self._collect_loop_line_ranges(analysis_code)
            risky_line_local = self._line_from_offset(analysis_code, risky_match.start(), base_line=1)
            in_loop = any(start <= risky_line_local <= end for start, end in loop_ranges)
            has_parse_contract = bool(
                re.search(r"\bdynlen\s*\(\s*(parts|tokens|fields)\s*\)\s*(<|<=)\s*\d+", analysis_code, re.IGNORECASE)
            )
            if not (len(risky_iter) >= 2 or in_loop or has_parse_contract):
                return []
            absolute_line = base_line + risky_line_local - 1
            return [self._build_p1_issue(rule_id, rule_item, severity, absolute_line, static_message, analysis_code, event_name)]

        if op == "division_zero_guard":
            if not self._has_config_context(analysis_code):
                return []
            lines = analysis_code.splitlines()
            for idx, line in enumerate(lines, 1):
                sanitized = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', '""', line)
                if "/" not in sanitized:
                    continue
                if re.search(r"//", sanitized):
                    continue
                if re.search(r"\bmax\s*\(\s*1\s*,", sanitized, re.IGNORECASE):
                    continue
                if re.search(r"\?.*/.*:", sanitized):
                    continue
                for match in re.finditer(r"/\s*([A-Za-z_][A-Za-z0-9_]*|\([^)]+\))", sanitized):
                    denom_expr = match.group(1).strip()
                    if re.fullmatch(r"\d+(?:\.\d+)?", denom_expr):
                        continue
                    if denom_expr.startswith("(") and denom_expr.endswith(")"):
                        inner = denom_expr[1:-1]
                        denom_vars = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", inner)
                    else:
                        denom_vars = [denom_expr]
                    if not denom_vars:
                        continue
                    guard_found = False
                    for lookback in range(max(1, idx - 3), idx + 1):
                        ctx = lines[lookback - 1]
                        for denom in denom_vars:
                            has_non_zero_guard = bool(
                                re.search(rf"\b{re.escape(denom)}\b\s*!=\s*0", ctx)
                                or re.search(rf"\b{re.escape(denom)}\b\s*(>|>=)\s*1", ctx)
                                or re.search(rf"\b{re.escape(denom)}\b\s*(<=|==)\s*0", ctx)
                            )
                            has_if_guard = bool(re.search(rf"\bif\s*\([^)]*\b{re.escape(denom)}\b[^)]*\)", ctx))
                            if has_non_zero_guard and has_if_guard:
                                guard_found = True
                                break
                            if has_if_guard and re.search(
                                r"\b(return|continue|break)\b",
                                "\n".join(lines[lookback - 1 : min(len(lines), lookback + 2)]),
                            ):
                                guard_found = True
                                break
                        if guard_found:
                            break
                    if guard_found:
                        continue
                    absolute_line = base_line + idx - 1
                    return [self._build_p1_issue(rule_id, rule_item, severity, absolute_line, static_message, analysis_code, event_name)]
            return []

        if op == "manual_aggregation_pattern":
            for match in re.finditer(r"\b(?:while|for)\s*\([^\)]*\)\s*\{", analysis_code, re.IGNORECASE):
                open_brace = analysis_code.find("{", match.start())
                if open_brace < 0:
                    continue
                close_brace = self._find_matching_delimiter(analysis_code, open_brace, "{", "}")
                if close_brace < 0:
                    continue
                block = analysis_code[open_brace : close_brace + 1]
                has_manual_agg = bool(
                    re.search(r"\b(sum|total)\s*\+=", block)
                    and re.search(r"\b(count|cnt)\s*(\+\+|\+=\s*1)", block)
                )
                if not has_manual_agg:
                    continue
                if re.search(r"\b(dynSum|dynAvg|avg|average)\s*\(", block):
                    continue
                absolute_line = self._line_from_offset(analysis_code, match.start(), base_line=base_line)
                return [self._build_p1_issue(rule_id, rule_item, severity, absolute_line, static_message, analysis_code, event_name)]
            return []

        if op == "consecutive_dpset":
            lines = analysis_code.splitlines()
            loop_ranges = self._collect_loop_line_ranges(analysis_code)

            def _in_loop(line_no: int) -> bool:
                for start, end in loop_ranges:
                    if start <= line_no <= end:
                        return True
                return False

            dpset_lines = [
                idx for idx, line in enumerate(lines) if re.search(r"\bdpSet\s*\(", line) and not _in_loop(idx + 1)
            ]
            if len(dpset_lines) < 2:
                return []

            max_gap = int(detector.get("max_gap_lines", 4) or 4)
            findings = []
            cluster = [dpset_lines[0]]

            def _emit_cluster(cluster_lines: List[int]) -> None:
                if len(cluster_lines) < 2:
                    return
                start = cluster_lines[0]
                end = cluster_lines[-1]
                window = "\n".join(lines[start : end + 1])
                has_better_pattern = bool(
                    re.search(r"\bdpSet(?:Wait|Timed)\s*\(", window)
                    or re.search(r"\bif\s*\([^\)]*(?:\bchanged\b|\bdelta\b|\bold\b|\bprev\b)[^\)]*\)", window, re.IGNORECASE)
                    or re.search(r"\bdpSetWait\s*\(", analysis_code)
                )
                if has_better_pattern:
                    return
                findings.append(
                    self._build_p1_issue(
                        rule_id, rule_item, severity, base_line + start, static_message, analysis_code, event_name
                    )
                )

            for line_idx in dpset_lines[1:]:
                if line_idx - cluster[-1] <= max_gap:
                    cluster.append(line_idx)
                    continue
                _emit_cluster(cluster)
                cluster = [line_idx]
            _emit_cluster(cluster)
            return findings

        if op == "input_validation":
            anchor_local = self._first_function_line(analysis_code)
            first_input_line = 0
            for idx, line in enumerate(analysis_code.splitlines(), 1):
                if "dpGet" in line or "dpConnect" in line:
                    first_input_line = idx
                    break
            has_input = first_input_line > 0
            has_validation = bool(re.search(r"\b(?:strlen|atoi|atof|isDigit|strIsDigit)\s*\(", analysis_code))
            if has_input and not has_validation:
                absolute_line = base_line + ((first_input_line or anchor_local) - 1)
                return [self._build_p1_issue(rule_id, rule_item, severity, absolute_line, static_message, analysis_code, event_name)]
            return []

        if op == "style_name_rules":
            lines = analysis_code.splitlines()
            function_start = len(lines) + 1
            for idx, line in enumerate(lines, 1):
                stripped = line.strip()
                if re.match(
                    r"^(?:main|void|int|float|string|bool|mapping|time|anytype|dyn_[a-zA-Z0-9_]+)\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\(",
                    stripped,
                ) or re.match(r"^main\s*\(", stripped):
                    function_start = idx
                    break
            decl_pattern = re.compile(
                r"^\s*(const\s+)?(?:int|float|string|bool|mapping|time|anytype|dyn_[a-zA-Z0-9_]+)\s+([a-zA-Z_][a-zA-Z0-9_]*)"
            )
            for idx, line in enumerate(lines, 1):
                stripped = line.strip()
                if not stripped or stripped.startswith("//"):
                    continue
                m = decl_pattern.match(stripped)
                if not m:
                    continue
                is_const = bool(m.group(1))
                name = m.group(2)
                is_global = idx < function_start
                if is_const and not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
                    msg = f"상수 명명 규칙 위반 가능성: '{name}' (UPPER_SNAKE 권장)."
                    return [self._build_p1_issue(rule_id, rule_item, severity, base_line + idx - 1, msg, analysis_code, event_name)]
                if is_global and not is_const and not name.startswith("g_"):
                    msg = f"전역 변수 명명 규칙 위반 가능성: '{name}' (g_ 접두사 권장)."
                    return [self._build_p1_issue(rule_id, rule_item, severity, base_line + idx - 1, msg, analysis_code, event_name)]
                if re.search(r"(cfg|config)", name, re.IGNORECASE) and not name.startswith("cfg_"):
                    msg = f"설정 변수 명명 규칙 위반 가능성: '{name}' (cfg_ 접두사 권장)."
                    return [self._build_p1_issue(rule_id, rule_item, severity, base_line + idx - 1, msg, analysis_code, event_name)]
            return []

        if op == "style_header_rules":
            lines = code.splitlines()
            func_pattern = re.compile(
                r"^\s*(?:void|int|float|string|bool|mapping|time|anytype|dyn_[a-zA-Z0-9_]+)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\("
            )
            for idx, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith("//") or stripped.startswith("/*"):
                    continue
                if not func_pattern.match(stripped) and not re.match(r"^\s*main\s*\(", stripped):
                    continue
                comment_hits = 0
                for back in range(idx - 2, max(-1, idx - 20), -1):
                    prev = lines[back].strip()
                    if not prev:
                        continue
                    if re.match(r"^\s*(//|/\*|\*)", lines[back]):
                        comment_hits += 1
                        continue
                    break
                if comment_hits >= int(detector.get("min_comment_hits", 2) or 2):
                    continue
                return [self._build_p1_issue(rule_id, rule_item, severity, base_line + idx - 1, static_message, analysis_code, event_name)]
            return []

        if op == "dpset_timed_context":
            lines = analysis_code.splitlines()
            for idx, line in enumerate(lines, 1):
                m = re.search(r"\bdpSet\s*\(\s*([^,]+),", line)
                if not m:
                    continue
                first_arg = m.group(1)
                if not re.search(r"(alert|alm|alarm|\.set\b|_set\b|sp_)", first_arg, re.IGNORECASE):
                    continue
                window_start = max(0, idx - 3)
                window_end = min(len(lines), idx + 2)
                window_text = "\n".join(lines[window_start:window_end])
                has_timed = bool(re.search(r"\bdpSet(?:Timed|Wait)\s*\(", window_text))
                has_delta_guard = bool(
                    re.search(
                        r"\bif\s*\([^\)]*(?:!=|\bchanged\b|\bdelta\b|\bold\b|\bprev\b)[^\)]*\)",
                        window_text,
                        re.IGNORECASE,
                    )
                )
                if has_timed or has_delta_guard:
                    continue
                return [self._build_p1_issue(rule_id, rule_item, severity, idx, static_message, analysis_code, event_name)]
            return []

        if op == "dpget_batch_optimization":
            min_count = int(detector.get("min_count", 2) or 2)
            findings = []
            seen_lines = set()
            loop_ranges = self._collect_loop_line_ranges(analysis_code)

            def _in_loop(line_no: int) -> bool:
                for start, end in loop_ranges:
                    if start <= line_no <= end:
                        return True
                return False

            for match in re.finditer(r"\b(?:while|for)\s*\([^\)]*\)\s*\{", analysis_code, re.IGNORECASE):
                open_brace = analysis_code.find("{", match.start())
                if open_brace < 0:
                    continue
                close_brace = self._find_matching_delimiter(analysis_code, open_brace, "{", "}")
                if close_brace < 0:
                    continue
                block = analysis_code[open_brace : close_brace + 1]
                dpget_count = len(re.findall(r"\bdpGet\s*\(", block))
                if dpget_count < min_count:
                    continue
                has_cache = bool(re.search(r"\b(mappingHasKey|cache|memo|lookup)\b", block, re.IGNORECASE))
                if has_cache:
                    continue
                absolute_line = self._line_from_offset(analysis_code, match.start(), base_line=base_line)
                if absolute_line in seen_lines:
                    continue
                seen_lines.add(absolute_line)
                findings.append(
                    self._build_p1_issue(rule_id, rule_item, severity, absolute_line, static_message, analysis_code, event_name)
                )

            # Also catch clustered dpGet calls outside loops (common copy-paste multi-read pattern).
            lines = analysis_code.splitlines()
            dpget_lines = [
                idx
                for idx, line in enumerate(lines, 1)
                if re.search(r"\bdpGet\s*\(", line) and not _in_loop(idx)
            ]
            if len(dpget_lines) < min_count:
                return findings
            max_gap = int(detector.get("max_gap_lines", 8) or 8)

            cluster = [dpget_lines[0]]

            def _emit_cluster(cluster_lines: List[int]) -> None:
                if len(cluster_lines) < min_count:
                    return
                start_line = cluster_lines[0]
                end_line = cluster_lines[-1]
                block = "\n".join(lines[max(0, start_line - 2) : min(len(lines), end_line + 1)])
                if re.search(r"\b(mappingHasKey|cache|memo|lookup)\b", block, re.IGNORECASE):
                    return
                absolute_line = base_line + start_line - 1
                if absolute_line in seen_lines:
                    return
                seen_lines.add(absolute_line)
                findings.append(
                    self._build_p1_issue(rule_id, rule_item, severity, absolute_line, static_message, analysis_code, event_name)
                )

            for line_no in dpget_lines[1:]:
                if line_no - cluster[-1] <= max_gap:
                    cluster.append(line_no)
                    continue
                _emit_cluster(cluster)
                cluster = [line_no]
            _emit_cluster(cluster)
            return findings

        if op == "dpset_batch_optimization":
            findings = []
            seen_lines = set()
            for match in re.finditer(r"\b(?:while|for)\s*\([^\)]*\)\s*\{", analysis_code, re.IGNORECASE):
                open_brace = analysis_code.find("{", match.start())
                if open_brace < 0:
                    continue
                close_brace = self._find_matching_delimiter(analysis_code, open_brace, "{", "}")
                if close_brace < 0:
                    continue
                block = analysis_code[open_brace : close_brace + 1]
                dpset_count = len(re.findall(r"\bdpSet\s*\(", block))
                if dpset_count < int(detector.get("min_count", 2) or 2):
                    continue
                has_batch_hint = bool(re.search(r"\b(dpSetWait|dpSetTimed|batch|group)\b", block, re.IGNORECASE))
                has_guard = bool(re.search(r"(!=|changed|old|prev)", block, re.IGNORECASE))
                if has_batch_hint or has_guard:
                    continue
                absolute_line = self._line_from_offset(analysis_code, match.start(), base_line=base_line)
                if absolute_line in seen_lines:
                    continue
                seen_lines.add(absolute_line)
                findings.append(
                    self._build_p1_issue(rule_id, rule_item, severity, absolute_line, static_message, analysis_code, event_name)
                )
            return findings

        if op == "setvalue_batch_optimization":
            findings = []
            seen_lines = set()
            for match in re.finditer(r"\b(?:while|for)\s*\([^\)]*\)\s*\{", analysis_code, re.IGNORECASE):
                open_brace = analysis_code.find("{", match.start())
                if open_brace < 0:
                    continue
                close_brace = self._find_matching_delimiter(analysis_code, open_brace, "{", "}")
                if close_brace < 0:
                    continue
                block = analysis_code[open_brace : close_brace + 1]
                setvalue_count = len(re.findall(r"\bsetValue\s*\(", block))
                if setvalue_count < int(detector.get("min_count", 2) or 2):
                    continue
                if re.search(r"\bsetMultiValue\s*\(", block, re.IGNORECASE):
                    continue
                absolute_line = self._line_from_offset(analysis_code, match.start(), base_line=base_line)
                if absolute_line in seen_lines:
                    continue
                seen_lines.add(absolute_line)
                findings.append(
                    self._build_p1_issue(rule_id, rule_item, severity, absolute_line, static_message, analysis_code, event_name)
                )
            return findings

        if op == "setmultivalue_adoption":
            lines = analysis_code.splitlines()
            setvalue_lines = [idx for idx, line in enumerate(lines, 1) if re.search(r"\bsetValue\s*\(", line)]
            min_count = int(detector.get("min_count", 2) or 2)
            if len(setvalue_lines) < min_count:
                return []
            max_gap = int(detector.get("max_gap_lines", 6) or 6)
            findings = []
            cluster = [setvalue_lines[0]]

            def _emit_setvalue_cluster(cluster_lines: List[int]) -> None:
                if len(cluster_lines) < min_count:
                    return
                start_line = cluster_lines[0]
                end_line = cluster_lines[-1]
                window_start = max(1, start_line - 1)
                window_end = min(len(lines), end_line + 2)
                block = "\n".join(lines[window_start - 1 : window_end])
                if re.search(r"\bsetMultiValue\s*\(", block, re.IGNORECASE):
                    return
                findings.append(
                    self._build_p1_issue(rule_id, rule_item, severity, base_line + start_line - 1, static_message, analysis_code, event_name)
                )

            for line_no in setvalue_lines[1:]:
                if line_no - cluster[-1] <= max_gap:
                    cluster.append(line_no)
                    continue
                _emit_setvalue_cluster(cluster)
                cluster = [line_no]
            _emit_setvalue_cluster(cluster)
            return findings

        if op == "getmultivalue_adoption":
            lines = analysis_code.splitlines()
            getvalue_lines = [idx for idx, line in enumerate(lines, 1) if re.search(r"\bgetValue\s*\(", line)]
            min_count = int(detector.get("min_count", 2) or 2)
            if len(getvalue_lines) < min_count:
                return []
            max_gap = int(detector.get("max_gap_lines", 6) or 6)
            findings = []
            cluster = [getvalue_lines[0]]

            def _emit_getvalue_cluster(cluster_lines: List[int]) -> None:
                if len(cluster_lines) < min_count:
                    return
                start_line = cluster_lines[0]
                end_line = cluster_lines[-1]
                window_start = max(1, start_line - 1)
                window_end = min(len(lines), end_line + 2)
                block = "\n".join(lines[window_start - 1 : window_end])
                if re.search(r"\bgetMultiValue\s*\(", block, re.IGNORECASE):
                    return
                if re.search(r"\b(cache|mappingHasKey|memo|lookup)\b", block, re.IGNORECASE):
                    return
                findings.append(
                    self._build_p1_issue(rule_id, rule_item, severity, base_line + start_line - 1, static_message, analysis_code, event_name)
                )

            for line_no in getvalue_lines[1:]:
                if line_no - cluster[-1] <= max_gap:
                    cluster.append(line_no)
                    continue
                _emit_getvalue_cluster(cluster)
                cluster = [line_no]
            _emit_getvalue_cluster(cluster)
            return findings

        if op == "getvalue_batch_optimization":
            findings = []
            seen_lines = set()
            for match in re.finditer(r"\b(?:while|for)\s*\([^\)]*\)\s*\{", analysis_code, re.IGNORECASE):
                open_brace = analysis_code.find("{", match.start())
                if open_brace < 0:
                    continue
                close_brace = self._find_matching_delimiter(analysis_code, open_brace, "{", "}")
                if close_brace < 0:
                    continue
                block = analysis_code[open_brace : close_brace + 1]
                getvalue_count = len(re.findall(r"\bgetValue\s*\(", block))
                if getvalue_count < int(detector.get("min_count", 2) or 2):
                    continue
                has_batch_or_cache = bool(
                    re.search(
                        r"\b(getMultiValue|cache|mappingHasKey|memo|lookup|batch)\b",
                        block,
                        re.IGNORECASE,
                    )
                )
                if has_batch_or_cache:
                    continue
                absolute_line = self._line_from_offset(analysis_code, match.start(), base_line=base_line)
                if absolute_line in seen_lines:
                    continue
                seen_lines.add(absolute_line)
                findings.append(
                    self._build_p1_issue(rule_id, rule_item, severity, absolute_line, static_message, analysis_code, event_name)
                )
            return findings

        if op == "debug_logging_presence":
            log_pattern = str(detector.get("log_pattern", r"\b(?:writeLog|DebugN|DebugTN)\s*\("))
            if re.search(log_pattern, analysis_code, re.IGNORECASE):
                return []

            trigger_pattern = str(
                detector.get(
                    "trigger_pattern",
                    r"\b(?:catch|getLastError|err(or)?|fail(ed|ure)?)\b",
                )
            )
            trigger = re.search(trigger_pattern, analysis_code, re.IGNORECASE)
            if not trigger:
                return []

            # Avoid noisy hits for comments-only mentions.
            trigger_line = self._line_from_offset(analysis_code, trigger.start(), base_line=1)
            try:
                line_text = analysis_code.splitlines()[max(0, trigger_line - 1)]
            except Exception:
                line_text = ""
            if line_text.strip().startswith("//"):
                return []

            absolute_line = self._line_from_offset(analysis_code, trigger.start(), base_line=base_line)
            return [self._build_p1_issue(rule_id, rule_item, severity, absolute_line, static_message, analysis_code, event_name)]

        if op == "logging_level_policy":
            trigger_pattern = str(
                detector.get(
                    "trigger_pattern",
                    r"\b(?:catch|getLastError|err(?:or)?|fail(?:ed|ure)?)\b",
                )
            )
            trigger = re.search(trigger_pattern, analysis_code, re.IGNORECASE)
            if not trigger:
                return []

            log_pattern = str(detector.get("log_pattern", r"\b(?:writeLog|DebugN|DebugTN)\s*\("))
            if not re.search(log_pattern, analysis_code, re.IGNORECASE):
                return []

            debug_pattern = str(detector.get("debug_pattern", r"\b(?:DBG1|DBG2|DebugN|DebugTN)\b"))
            if re.search(debug_pattern, analysis_code, re.IGNORECASE):
                return []

            absolute_line = self._line_from_offset(analysis_code, trigger.start(), base_line=base_line)
            return [self._build_p1_issue(rule_id, rule_item, severity, absolute_line, static_message, analysis_code, event_name)]

        if op == "script_active_condition_check":
            mutating_pattern = str(
                detector.get(
                    "mutating_pattern",
                    r"\b(?:dpSet(?:Wait|Timed)?|setValue|setMultiValue)\s*\(",
                )
            )
            mutating_call = re.search(mutating_pattern, analysis_code, re.IGNORECASE)
            if not mutating_call:
                return []

            guard_pattern = str(
                detector.get(
                    "active_guard_pattern",
                    r"\b(?:isActive|active|enabled?|bActive|runFlag|useFlag)\b",
                )
            )
            if re.search(guard_pattern, analysis_code, re.IGNORECASE):
                return []

            absolute_line = self._line_from_offset(analysis_code, mutating_call.start(), base_line=base_line)
            return [self._build_p1_issue(rule_id, rule_item, severity, absolute_line, static_message, analysis_code, event_name)]

        if op == "duplicate_action_handling":
            call_pattern = re.compile(
                str(
                    detector.get(
                        "call_pattern",
                        r"\b(?P<func>dpSet|setValue)\s*\(\s*\"(?P<target>[^\"]+)\"(?:\s*,\s*\"(?P<attr>[^\"]+)\")?",
                    )
                ),
                re.IGNORECASE,
            )
            min_repeat = int(detector.get("min_repeat", 2) or 2)
            max_gap_lines = int(detector.get("max_gap_lines", 10) or 10)
            guard_pattern = str(
                detector.get(
                    "duplicate_guard_pattern",
                    r"\b(?:changed|delta|prev|old|already|once|flag)\b",
                )
            )

            lines = analysis_code.splitlines()
            hits: List[tuple] = []
            for idx, line in enumerate(lines, 1):
                if line.strip().startswith("//"):
                    continue
                m = call_pattern.search(line)
                if m:
                    group_map = m.groupdict() if hasattr(m, "groupdict") else {}
                    func_name = str(group_map.get("func", "") or "").lower()
                    target_name = str(group_map.get("target", "") or "")
                    attr_name = str(group_map.get("attr", "") or "")
                    if not target_name:
                        try:
                            target_name = str(m.group(1) or "")
                        except Exception:
                            target_name = ""
                    if not target_name:
                        continue
                    target_key = target_name
                    if func_name == "setvalue" and attr_name:
                        target_key = f"{target_name}.{attr_name}"
                    hits.append((idx, target_key))
            if len(hits) < min_repeat:
                return []

            by_target: Dict[str, List[int]] = {}
            for line_no, target in hits:
                by_target.setdefault(target, []).append(line_no)

            candidate_findings = []
            for target, line_nos in by_target.items():
                if len(line_nos) < min_repeat:
                    continue
                cluster = [line_nos[0]]

                def _emit_duplicate_cluster(cluster_lines: List[int]) -> None:
                    if len(cluster_lines) < min_repeat:
                        return
                    start_line = cluster_lines[0]
                    end_line = cluster_lines[-1]
                    block = "\n".join(lines[max(0, start_line - 2) : min(len(lines), end_line + 1)])
                    if re.search(guard_pattern, block, re.IGNORECASE):
                        return
                    absolute_line = base_line + start_line - 1
                    message = static_message
                    if "{target}" in message:
                        message = message.format(target=target)
                    candidate_findings.append(
                        self._build_p1_issue(rule_id, rule_item, severity, absolute_line, message, analysis_code, event_name)
                    )

                for line_no in line_nos[1:]:
                    if line_no - cluster[-1] <= max_gap_lines:
                        cluster.append(line_no)
                        continue
                    _emit_duplicate_cluster(cluster)
                    cluster = [line_no]
                _emit_duplicate_cluster(cluster)
            if not candidate_findings:
                return []
            candidate_findings.sort(key=lambda x: int(x.get("line", 0) or 0))
            compressed = [candidate_findings[0]]
            for finding in candidate_findings[1:]:
                prev = compressed[-1]
                prev_line = int(prev.get("line", 0) or 0)
                curr_line = int(finding.get("line", 0) or 0)
                if curr_line - prev_line <= max_gap_lines:
                    continue
                compressed.append(finding)
            return compressed

        print(f"[!] Unsupported composite op in p1_rule_defs: {op}")
        return []

    def _run_configured_p1_rules(
        self,
        code: str,
        analysis_code: str,
        event_name: str,
        base_line: int,
        anchor_line: int,
        file_type: str,
    ) -> List[Dict]:
        violations: List[Dict] = []
        for rule_def in sorted(self.p1_rule_defs, key=lambda r: int(r.get("order", 0) or 0)):
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
                    )
                )
            elif kind == "regex":
                violations.extend(
                    self._run_regex_rule(
                        rule_def,
                        analysis_code=analysis_code,
                        event_name=event_name,
                        base_line=base_line,
                    )
                )
            elif kind == "line_repeat":
                violations.extend(
                    self._run_line_repeat_rule(
                        rule_def,
                        analysis_code=analysis_code,
                        event_name=event_name,
                        base_line=base_line,
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
                    )
                )
            else:
                print(f"[!] Unsupported detector kind in p1_rule_defs: {kind}")
        return violations

    @staticmethod
    def _has_config_context(code: str) -> bool:
        return bool(
            re.search(
                r"\b(config|cfg|ini|json)\b|load_config|config_|cfg_|ini_|json_",
                code,
                re.IGNORECASE,
            )
        )

    def _remove_comments(self, text: str) -> str:
        if not text:
            return text

        chars = list(text)
        i = 0
        n = len(chars)
        in_string = False
        quote_char = ""

        while i < n:
            ch = chars[i]
            nxt = chars[i + 1] if i + 1 < n else ""

            if in_string:
                if ch == "\\" and i + 1 < n:
                    i += 2
                    continue
                if ch == quote_char:
                    in_string = False
                    quote_char = ""
                i += 1
                continue

            if ch in {'"', "'"}:
                in_string = True
                quote_char = ch
                i += 1
                continue

            if ch == "/" and nxt == "/":
                chars[i] = " "
                chars[i + 1] = " "
                i += 2
                while i < n and chars[i] != "\n":
                    chars[i] = " "
                    i += 1
                continue

            if ch == "/" and nxt == "*":
                chars[i] = " "
                chars[i + 1] = " "
                i += 2
                while i + 1 < n:
                    if chars[i] == "*" and chars[i + 1] == "/":
                        chars[i] = " "
                        chars[i + 1] = " "
                        i += 2
                        break
                    if chars[i] != "\n":
                        chars[i] = " "
                    i += 1
                continue

            i += 1

        return "".join(chars)

    def _build_issue_id(self, rule_id: str, code: str, line: int, event_name: str = "") -> str:
        normalized = re.sub(r"\s+", " ", code).strip()
        fingerprint = hashlib.sha1(
            f"{rule_id}|{line}|{event_name}|{normalized}".encode("utf-8", errors="ignore")
        ).hexdigest()[:10]
        return f"P1-{rule_id}-{fingerprint}"

    @staticmethod
    def _line_from_offset(code: str, offset: int, base_line: int = 1) -> int:
        return base_line + code.count("\n", 0, max(0, offset))

    @staticmethod
    def _first_function_line(code: str) -> int:
        lines = code.splitlines()
        for idx, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue
            if re.match(r"^(main)\s*\(", stripped):
                return idx
            if re.match(
                r"^(void|int|float|string|bool|mapping|time|anytype|dyn_[a-zA-Z0-9_]+)\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\(",
                stripped,
            ):
                return idx
        return 1

    # -------------------------------------------------------------------------
    # Legacy check_* methods are now provided by Mixin base classes:
    #   PerformanceRulesMixin, SecurityRulesMixin, StyleRulesMixin,
    #   QualityRulesMixin, ConfigRulesMixin
    # See core/rules/ for the implementations.
    # -------------------------------------------------------------------------

    def check_complexity(self, code: str) -> List[Dict]:
        findings = []
        if len(code) > 100000:
            return findings

        lines = code.split("\n")
        anchor_line = self._first_function_line(code)
        if len(lines) > 500:
            findings.append(
                {
                    "rule_id": "COMP-01",
                    "rule_item": "불필요한 코드 지양",
                    "severity": "Medium",
                    "line": anchor_line,
                    "message": f"함수 길이 과다 ({len(lines)} lines).",
                }
            )

        depth = 0
        max_depth = 0
        for line in lines[:2000]:
            depth += line.count("{")
            depth -= line.count("}")
            max_depth = max(max_depth, depth)

        if max_depth > 10:
            findings.append(
                {
                    "rule_id": "COMP-02",
                    "rule_item": "불필요한 코드 지양",
                    "severity": "Medium",
                    "line": anchor_line,
                    "message": f"제어문 중첩 과다 (Max depth: {max_depth}).",
                }
            )
        return findings

    def check_unused_variables(self, code: str) -> List[Dict]:
        findings = []
        if len(code) > 100000:
            return findings

        clean_code = self._remove_comments(code)
        all_words = re.findall(r"\b\w+\b", clean_code)
        word_counts = Counter(all_words)

        exception_prefixes = ("param_", "cfg_", "g_", "manager_", "query_", "Script", "is_", "thread_", "dp_")
        exception_vars = {
            "return_value",
            "i",
            "j",
            "k",
            "idx",
            "cnt",
            "count",
            "len",
            "size",
            "ret",
            "result",
            "success",
            "ok",
            "error",
            "err",
        }

        declarations = re.finditer(
            r"(?<!const\s)\b(int|float|string|bool|dyn_\w+|mapping|time|void|blob|anytype)\s+([a-zA-Z0-9_]+)\s*(=|;)",
            clean_code,
        )

        declared_vars = {}
        for match in declarations:
            var_name = match.group(2)
            if var_name in declared_vars:
                continue
            declared_vars[var_name] = self._line_from_offset(clean_code, match.start(), base_line=1)

            if var_name.startswith(exception_prefixes) or var_name in exception_vars:
                continue

            usage_count = word_counts[var_name]
            if usage_count <= 1:
                str_usage = re.search(r'"[^"]*' + re.escape(var_name) + r'[^"]*"', clean_code)
                if str_usage:
                    continue
                findings.append(
                    {
                        "rule_id": "UNUSED-01",
                        "rule_item": "불필요한 코드 지양",
                        "severity": "Low",
                        "line": declared_vars[var_name],
                        "message": f"미사용 변수 감지: '{var_name}'",
                    }
                )

        return findings

    def check_db_query_error(self, code: str) -> List[Dict]:
        findings = []
        anchor_line = self._first_function_line(code)
        if "dpQuery" in code or "dbGet" in code:
            if not ("writeLog" in code or "DebugTN" in code or "getLastError" in code):
                match = re.search(r"\b(dpQuery|dbGet)\b", code)
                line_no = self._line_from_offset(code, match.start(), base_line=1) if match else anchor_line
                findings.append(
                    {
                        "rule_id": "DB-ERR-01",
                        "rule_item": "DB Query Error",
                        "severity": "Warning",
                        "line": line_no,
                        "message": "DB Query 실패 로그 기능(writeLog/DebugTN) 누락 가능성.",
                    }
                )
        return findings

    def check_dp_function_exception(self, code: str) -> List[Dict]:
        findings = []
        dp_call_pattern = r"\b(dpSet|dpGet|dpQuery|dpConnect)\s*\([^;]+\)\s*;"
        first_dp_call = re.search(dp_call_pattern, code)
        if not first_dp_call:
            return findings

        has_try_catch = bool(re.search(r"\btry\b[\s\S]{0,2000}\bcatch\b", code, re.IGNORECASE))
        has_get_last_error = "getLastError" in code
        has_return_check = bool(
            re.search(
                r"\b(?:if|switch)\s*\([^\)]*(?:ret|result|err|error|rc|status|iErr|return_value)[^\)]*\)",
                code,
                re.IGNORECASE,
            )
            or re.search(r"\b(?:ret|result|err|error|rc|status|iErr|return_value)\s*=\s*(?:dpSet|dpGet|dpQuery|dpConnect)\b", code)
        )

        if not (has_try_catch or has_get_last_error or has_return_check):
            findings.append(
                {
                    "rule_id": "EXC-DP-01",
                    "rule_item": "DP 함수 예외 처리",
                    "severity": "Warning",
                    "line": self._line_from_offset(code, first_dp_call.start(), base_line=1),
                    "message": "DP 함수 호출 결과에 대한 예외 처리/오류 확인 로직 누락 가능성.",
                }
            )
        return findings

    @staticmethod
    def _find_matching_delimiter(text: str, start_idx: int, left: str, right: str) -> int:
        depth = 0
        for idx in range(start_idx, len(text)):
            ch = text[idx]
            if ch == left:
                depth += 1
            elif ch == right:
                depth -= 1
                if depth == 0:
                    return idx
        return -1

    def _collect_loop_line_ranges(self, code: str) -> List[tuple]:
        ranges = []
        for match in re.finditer(r"\b(?:while|for)\s*\([^\)]*\)\s*\{", code, re.IGNORECASE):
            open_brace = code.find("{", match.start())
            if open_brace < 0:
                continue
            close_brace = self._find_matching_delimiter(code, open_brace, "{", "}")
            if close_brace < 0:
                continue
            start_line = self._line_from_offset(code, match.start(), base_line=1)
            end_line = self._line_from_offset(code, close_brace, base_line=1)
            ranges.append((start_line, end_line))
        return ranges

    def check_while_delay_policy(self, code: str) -> List[Dict]:
        findings = []
        for match in re.finditer(r"\bwhile\s*\(", code):
            open_paren = code.find("(", match.start())
            if open_paren < 0:
                continue
            close_paren = self._find_matching_delimiter(code, open_paren, "(", ")")
            if close_paren < 0:
                continue

            open_brace = code.find("{", close_paren)
            if open_brace < 0:
                continue
            close_brace = self._find_matching_delimiter(code, open_brace, "{", "}")
            if close_brace < 0:
                continue

            loop_block = code[open_brace : close_brace + 1]
            # Loop body should contain periodic yield/wait call to avoid CPU hogging.
            has_delay = bool(re.search(r"\b(?:delay|dpSetWait|dpSetTimed)\s*\(", loop_block))
            if has_delay:
                continue

            findings.append(
                {
                    "rule_id": "PERF-03",
                    "rule_item": "Loop문 내의 처리 조건",
                    "severity": "Critical",
                    "line": self._line_from_offset(code, match.start(), base_line=1),
                    "message": "while 루프 내부 delay 부재 패턴 감지.",
                }
            )
            break

        return findings

    def check_dpset_timed_context(self, code: str) -> List[Dict]:
        findings = []
        lines = code.splitlines()

        for idx, line in enumerate(lines, 1):
            m = re.search(r"\bdpSet\s*\(\s*([^,]+),", line)
            if not m:
                continue

            first_arg = m.group(1)
            # Limit detection to alarm/config-like writes where history churn is a concern.
            if not re.search(r"(alert|alm|alarm|\.set\b|_set\b|sp_)", first_arg, re.IGNORECASE):
                continue

            window_start = max(0, idx - 3)
            window_end = min(len(lines), idx + 2)
            window_text = "\n".join(lines[window_start:window_end])

            has_timed = bool(re.search(r"\bdpSet(?:Timed|Wait)\s*\(", window_text))
            has_delta_guard = bool(
                re.search(r"\bif\s*\([^\)]*(?:!=|\bchanged\b|\bdelta\b|\bold\b|\bprev\b)[^\)]*\)", window_text, re.IGNORECASE)
            )
            if has_timed or has_delta_guard:
                continue

            findings.append(
                {
                    "rule_id": "PERF-05",
                    "rule_item": "Raima DB 증가 방지",
                    "severity": "Warning",
                    "line": idx,
                    "message": "dpSetTimed 대체 가능 패턴 감지.",
                }
            )
            break

        return findings

    def check_consecutive_dpset(self, code: str) -> List[Dict]:
        findings = []
        lines = code.splitlines()
        dpset_lines = [idx for idx, line in enumerate(lines) if re.search(r"\bdpSet\s*\(", line)]
        if len(dpset_lines) < 2:
            return findings
        loop_ranges = self._collect_loop_line_ranges(code)

        def _in_loop(line_no: int) -> bool:
            for start, end in loop_ranges:
                if start <= line_no <= end:
                    return True
            return False

        for idx in range(len(dpset_lines) - 1):
            start = dpset_lines[idx]
            end = dpset_lines[idx + 1]
            if end - start > 4:
                continue
            # PERF-DPSET-CHAIN targets non-loop nearby style issues.
            # Loop-heavy cases are handled by PERF-DPSET-BATCH-01.
            if _in_loop(start + 1) and _in_loop(end + 1):
                continue

            window = "\n".join(lines[start : end + 1])
            has_better_pattern = bool(
                re.search(r"\bdpSet(?:Wait|Timed)\s*\(", window)
                or re.search(r"\bif\s*\([^\)]*(?:\bchanged\b|\bdelta\b|\bold\b|\bprev\b)[^\)]*\)", window, re.IGNORECASE)
                or re.search(r"\bdpSetWait\s*\(", code)
            )
            if has_better_pattern:
                continue

            findings.append(
                {
                    "rule_id": "PERF-DPSET-CHAIN",
                    "rule_item": "Event, Ctrl Manager 이벤트 교환 횟수 최소화",
                    "severity": "Warning",
                    "line": start + 1,
                    "message": "WinCC OA 스타일상 연속 dpSet 호출 지양, 배치/동기/조건부 업데이트 권장.",
                }
            )
            break

        return findings

    def check_event_exchange_minimization(self, code: str) -> List[Dict]:
        findings = []
        loop_pattern = re.compile(r"\b(?:while|for)\s*\([^\)]*\)\s*\{", re.IGNORECASE)
        func_defs = {}
        func_pattern = re.compile(
            r"\b(?:void|int|float|string|bool|mapping|time|anytype|dyn_[a-zA-Z0-9_]+)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^\)]*\)\s*\{",
            re.IGNORECASE,
        )
        for func_match in func_pattern.finditer(code):
            name = func_match.group(1)
            brace_idx = code.find("{", func_match.start())
            if brace_idx < 0:
                continue
            close_brace = self._find_matching_delimiter(code, brace_idx, "{", "}")
            if close_brace < 0:
                continue
            func_defs[name] = code[brace_idx : close_brace + 1]

        excluded_calls = {
            "if",
            "for",
            "while",
            "switch",
            "return",
            "catch",
            "try",
            "dpSet",
            "dpSetWait",
            "dpSetTimed",
            "dpGet",
            "dpQuery",
            "writeLog",
            "DebugN",
            "dynlen",
            "mappinglen",
        }

        def _body_has_unsafe_dpset(body: str, depth: int, seen: set) -> bool:
            if re.search(r"\bdpSet\s*\(", body):
                if not re.search(r"\bdpSet(?:Wait|Timed)\s*\(", body) and not re.search(
                    r"\bif\s*\([^\)]*(?:\bchanged\b|\bdelta\b|\bold\b|\bprev\b)[^\)]*\)",
                    body,
                    re.IGNORECASE,
                ):
                    return True
            if depth <= 0:
                return False
            called_names = [
                token
                for token in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", body)
                if token not in excluded_calls
            ]
            for called_name in called_names:
                if called_name in seen:
                    continue
                callee_body = func_defs.get(called_name, "")
                if not callee_body:
                    continue
                if _body_has_unsafe_dpset(callee_body, depth - 1, seen | {called_name}):
                    return True
            return False
        lines = code.splitlines()
        for loop_match in loop_pattern.finditer(code):
            brace_idx = code.find("{", loop_match.start())
            if brace_idx < 0:
                continue
            close_brace = self._find_matching_delimiter(code, brace_idx, "{", "}")
            if close_brace < 0:
                continue

            block = code[brace_idx : close_brace + 1]
            dpset_matches = list(re.finditer(r"\bdpSet\s*\(", block))
            indirect_dpset_call = ""
            if len(dpset_matches) < 1:
                called_names = [
                    token
                    for token in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", block)
                    if token not in excluded_calls
                ]
                for called_name in called_names:
                    callee_body = func_defs.get(called_name, "")
                    if not callee_body:
                        continue
                    if _body_has_unsafe_dpset(callee_body, depth=2, seen={called_name}):
                        indirect_dpset_call = called_name
                        break
                if not indirect_dpset_call:
                    continue

            if re.search(r"\bdpSet(?:Wait|Timed)\s*\(", block):
                continue
            if re.search(r"\bif\s*\([^\)]*(?:\bchanged\b|\bdelta\b|\bold\b|\bprev\b)[^\)]*\)", block, re.IGNORECASE):
                continue

            merged_match = re.search(r"\bdpSet\s*\(\s*\"[^\"]+\"\s*,\s*[^,]+,\s*\"[^\"]+\"\s*,", block)
            if merged_match:
                continue

            line = self._line_from_offset(code, loop_match.start(), base_line=1)
            findings.append(
                {
                    "rule_id": "PERF-EV-01",
                    "rule_item": "Event, Ctrl Manager 이벤트 교환 횟수 최소화",
                    "severity": "Warning",
                    "line": line,
                    "message": (
                        f"루프 내 호출 함수({indirect_dpset_call})에서 dpSet 수행 감지: "
                        "변경 가드/배치 처리(dpSetWait, dpSetTimed) 권장."
                        if indirect_dpset_call
                        else "루프 내 dpSet 호출 감지: 변경 가드/배치 처리(dpSetWait, dpSetTimed) 권장."
                    ),
                }
            )
            break

        return findings

    def check_memory_leaks_advanced(self, code: str) -> List[Dict]:
        findings = []
        declarations = [
            (idx, line)
            for idx, line in enumerate(code.splitlines(), 1)
            if re.search(r"\bdyn_\w+\s+[a-zA-Z_][a-zA-Z0-9_]*", line)
        ]
        if not declarations:
            return findings

        # Treat explicit dynClear/dynRemove usage as cleanup signals.
        has_cleanup = bool(re.search(r"\bdyn(?:Clear|Remove)\s*\(", code))
        if has_cleanup:
            return findings

        # Warn only when dyn collection APIs are used in iterative contexts.
        loop_dyn_ops = bool(
            re.search(
                r"\b(?:while|for)\s*\([^\)]*\)\s*\{[\s\S]{0,1200}\bdyn(?:Append|Insert|MapInsert)\s*\(",
                code,
                re.IGNORECASE,
            )
        )
        if loop_dyn_ops:
            findings.append(
                {
                    "rule_id": "MEM-01",
                    "rule_item": "메모리 누수 체크",
                    "severity": "Warning",
                    "line": declarations[0][0],
                    "message": "반복 구간 dyn 사용 대비 dynClear()/dynRemove() 누락 가능성.",
                }
            )
        return findings

    def check_input_validation(self, code: str) -> List[Dict]:
        findings = []
        anchor_line = self._first_function_line(code)
        first_input_line = 0
        for idx, line in enumerate(code.splitlines(), 1):
            if "dpGet" in line or "dpConnect" in line:
                first_input_line = idx
                break

        has_input = first_input_line > 0
        has_validation = bool(re.search(r"\b(?:strlen|atoi|atof|isDigit|strIsDigit)\s*\(", code))

        if has_input and not has_validation:
            findings.append(
                {
                    "rule_id": "VAL-01",
                    "rule_item": "적절한 DP 처리 함수 사용",
                    "severity": "High",
                    "line": first_input_line or anchor_line,
                    "message": "dpGet/dpConnect 입력값 유효성 검증(strlen/atoi 등) 누락 가능성.",
                }
            )
        return findings

    def check_coding_standards_advanced(self, code: str) -> List[Dict]:
        findings = []
        lines = code.splitlines()
        decl_start_pattern = re.compile(r"^\s*(?:int|float|string|bool|dyn_\w+)\s+[a-zA-Z_][a-zA-Z0-9_]*")
        control_pattern = re.compile(r"^\s*(?:if|for|while|switch|return|break|continue|try|catch)\b")

        pending_start_line = 0
        for line_no, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
                continue

            if pending_start_line:
                if ";" in stripped:
                    pending_start_line = 0
                    continue
                if control_pattern.match(stripped) or stripped.endswith("{") or stripped.endswith("}"):
                    findings.append(
                        {
                            "rule_id": "STD-01",
                            "rule_item": "명명 규칙 및 코딩 스타일 준수 여부 확인",
                            "severity": "Low",
                            "line": pending_start_line,
                            "message": f"L{pending_start_line}: 변수 선언 시 세미콜론(;) 누락 가능성.",
                        }
                    )
                    pending_start_line = 0
                continue

            if not decl_start_pattern.match(stripped):
                continue
            if stripped.endswith(";"):
                continue
            # Ignore function signatures even when "{" is on the next line.
            if "(" in stripped and ")" in stripped:
                continue
            pending_start_line = line_no

        if pending_start_line:
            findings.append(
                {
                    "rule_id": "STD-01",
                    "rule_item": "명명 규칙 및 코딩 스타일 준수 여부 확인",
                    "severity": "Low",
                    "line": pending_start_line,
                    "message": f"L{pending_start_line}: 변수 선언 시 세미콜론(;) 누락 가능성.",
                }
            )
        return findings

    def check_style_name_rules(self, code: str) -> List[Dict]:
        findings = []
        lines = code.splitlines()
        function_start = len(lines) + 1
        for idx, line in enumerate(lines, 1):
            stripped = line.strip()
            if re.match(
                r"^(?:main|void|int|float|string|bool|mapping|time|anytype|dyn_[a-zA-Z0-9_]+)\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\(",
                stripped,
            ) or re.match(r"^main\s*\(", stripped):
                function_start = idx
                break

        decl_pattern = re.compile(
            r"^\s*(const\s+)?(?:int|float|string|bool|mapping|time|anytype|dyn_[a-zA-Z0-9_]+)\s+([a-zA-Z_][a-zA-Z0-9_]*)"
        )

        for idx, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue
            match = decl_pattern.match(stripped)
            if not match:
                continue

            is_const = bool(match.group(1))
            name = match.group(2)
            is_global = idx < function_start

            if is_const and not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
                findings.append(
                    {
                        "rule_id": "STYLE-NAME-01",
                        "rule_item": "명명 규칙 및 코딩 스타일 준수 확인",
                        "severity": "Low",
                        "line": idx,
                        "message": f"상수 명명 규칙 위반 가능성: '{name}' (UPPER_SNAKE 권장).",
                    }
                )
                break

            if is_global and not is_const and not name.startswith("g_"):
                findings.append(
                    {
                        "rule_id": "STYLE-NAME-01",
                        "rule_item": "명명 규칙 및 코딩 스타일 준수 확인",
                        "severity": "Low",
                        "line": idx,
                        "message": f"전역 변수 명명 규칙 위반 가능성: '{name}' (g_ 접두사 권장).",
                    }
                )
                break

            if re.search(r"(cfg|config)", name, re.IGNORECASE) and not name.startswith("cfg_"):
                findings.append(
                    {
                        "rule_id": "STYLE-NAME-01",
                        "rule_item": "명명 규칙 및 코딩 스타일 준수 확인",
                        "severity": "Low",
                        "line": idx,
                        "message": f"설정 변수 명명 규칙 위반 가능성: '{name}' (cfg_ 접두사 권장).",
                    }
                )
                break

        return findings

    def check_style_indent_rules(self, code: str) -> List[Dict]:
        findings = []
        saw_tab_indent = False
        saw_space_indent = False
        mixed_line = 0

        for idx, line in enumerate(code.splitlines(), 1):
            if not line.strip():
                continue
            indent_match = re.match(r"^([ \t]+)", line)
            if not indent_match:
                continue
            indent = indent_match.group(1)
            if "\t" in indent and " " in indent:
                mixed_line = idx
                break
            if "\t" in indent:
                saw_tab_indent = True
            if " " in indent:
                saw_space_indent = True

        if mixed_line or (saw_tab_indent and saw_space_indent):
            findings.append(
                {
                    "rule_id": "STYLE-INDENT-01",
                    "rule_item": "명명 규칙 및 코딩 스타일 준수 확인",
                    "severity": "Low",
                    "line": mixed_line or 1,
                    "message": "들여쓰기 스타일 혼합 감지(탭/스페이스 혼용).",
                }
            )
        return findings

    def check_style_header_rules(self, code: str) -> List[Dict]:
        findings = []
        lines = code.splitlines()
        func_pattern = re.compile(
            r"^\s*(?:void|int|float|string|bool|mapping|time|anytype|dyn_[a-zA-Z0-9_]+)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\("
        )
        for idx, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("/*"):
                continue
            if not func_pattern.match(stripped) and not re.match(r"^\s*main\s*\(", stripped):
                continue

            has_header = False
            # Inspect a wider range above function start and stop at previous code line.
            comment_hits = 0
            for back in range(idx - 2, max(-1, idx - 20), -1):
                prev = lines[back].strip()
                if not prev:
                    continue
                if re.match(r"^\s*(//|/\*|\*)", lines[back]):
                    comment_hits += 1
                    continue
                break
            if comment_hits >= 2:
                has_header = True
            if has_header:
                continue

            findings.append(
                {
                    "rule_id": "STYLE-HEADER-01",
                    "rule_item": "명명 규칙 및 코딩 스타일 준수 확인",
                    "severity": "Low",
                    "line": idx,
                    "message": "함수 헤더 주석(이름/인자/설명) 누락 가능성.",
                }
            )
            break
        return findings

    def check_hardcoding_extended(self, code: str) -> List[Dict]:
        findings = []
        lines = code.splitlines()
        dp_path_hits = []
        for idx, line in enumerate(lines, 1):
            if re.search(r"^\s*const\b", line):
                continue
            for match in re.finditer(r'"([A-Za-z0-9_]+\.[A-Za-z0-9_\.]+)"', line):
                val = match.group(1)
                if val.count(".") >= 2:
                    dp_path_hits.append((idx, val))

        dp_counter = Counter([value for _, value in dp_path_hits])
        repeated_dp = [value for value, count in dp_counter.items() if count >= 2]
        if repeated_dp:
            line = next((ln for ln, value in dp_path_hits if value == repeated_dp[0]), 1)
            findings.append(
                {
                    "rule_id": "HARD-02",
                    "rule_item": "하드코딩 지양",
                    "severity": "Medium",
                    "line": line,
                    "message": f"고정 DP 경로 문자열 반복 사용 감지: '{repeated_dp[0]}'.",
                }
            )
            return findings

        number_hits = []
        for idx, line in enumerate(lines, 1):
            if re.search(r"^\s*const\b", line):
                continue
            for match in re.finditer(r"\b\d{2,}\b", line):
                value = match.group(0)
                if value in {"10", "60", "100"}:
                    continue
                number_hits.append((idx, value))
        num_counter = Counter([value for _, value in number_hits])
        repeated_num = [value for value, count in num_counter.items() if count >= 3]
        if repeated_num:
            line = next((ln for ln, value in number_hits if value == repeated_num[0]), 1)
            findings.append(
                {
                    "rule_id": "HARD-02",
                    "rule_item": "하드코딩 지양",
                    "severity": "Medium",
                    "line": line,
                    "message": f"매직 넘버 반복 사용 감지: '{repeated_num[0]}'.",
                }
            )
        return findings

    def check_dead_code(self, code: str) -> List[Dict]:
        findings = []
        false_if = re.search(r"\bif\s*\(\s*false\s*\)", code, re.IGNORECASE)
        if false_if:
            findings.append(
                {
                    "rule_id": "CLEAN-DEAD-01",
                    "rule_item": "불필요한 코드 지양",
                    "severity": "Medium",
                    "line": self._line_from_offset(code, false_if.start(), base_line=1),
                    "message": "영구 미실행 분기(if(false)) 감지.",
                }
            )
            return findings

        lines = code.splitlines()
        # Track block depth at start of each line to avoid false positives
        # when return is inside a conditional block and following lines are reachable.
        line_depths = []
        depth = 0
        for line in lines:
            line_depths.append(depth)
            depth += line.count("{")
            depth -= line.count("}")

        for idx, line in enumerate(lines, 1):
            if re.search(r"\breturn\b[^;]*;", line):
                return_depth = line_depths[idx - 1]
                for look_ahead in range(idx, min(len(lines), idx + 20)):
                    if line_depths[look_ahead] < return_depth:
                        break
                    nxt = lines[look_ahead].strip()
                    if not nxt or nxt.startswith("//") or nxt == "}":
                        continue
                    findings.append(
                        {
                            "rule_id": "CLEAN-DEAD-01",
                            "rule_item": "불필요한 코드 지양",
                            "severity": "Medium",
                            "line": idx,
                            "message": "return 이후 도달 불가능 코드 가능성 감지.",
                        }
                    )
                    return findings
        return findings

    def check_duplicate_blocks(self, code: str) -> List[Dict]:
        findings = []
        normalized_lines = []
        for idx, raw in enumerate(code.splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("//") or line in {"{", "}"}:
                continue
            line = re.sub(r"\s+", " ", line)
            if len(line) < 8:
                continue
            normalized_lines.append((idx, line))

        counter = Counter([line for _, line in normalized_lines])
        for line_text, count in counter.items():
            if count >= 3:
                line_no = next(idx for idx, value in normalized_lines if value == line_text)
                findings.append(
                    {
                        "rule_id": "CLEAN-DUP-01",
                        "rule_item": "불필요한 코드 지양",
                        "severity": "Low",
                        "line": line_no,
                        "message": "동일 코드 라인 반복(3회 이상) 감지.",
                    }
                )
                break
        return findings

    def check_config_format_consistency(self, code: str) -> List[Dict]:
        findings = []
        if not self._has_config_context(code):
            return findings
        if "strsplit" not in code:
            return findings

        delimiters = set(re.findall(r"\bstrsplit\s*\([^,]+,\s*\"([^\"]+)\"\s*\)", code))
        if len(delimiters) >= 2:
            line = self._line_from_offset(code, code.find("strsplit"), base_line=1)
            findings.append(
                {
                    "rule_id": "CFG-01",
                    "rule_item": "config 항목 정합성 확인",
                    "severity": "Warning",
                    "line": line,
                    "message": "config 파싱 형식 불일치 가능성, delimiter/필드수 검증 권장.",
                }
            )
            return findings

        has_parts_access = bool(re.search(r"\b(?:parts|tokens|fields)\s*\[\s*\d+\s*\]", code))
        has_len_check = bool(
            re.search(r"\b(?:dynlen|len)\s*\(\s*(?:parts|tokens|fields)\s*\)\s*(?:<|<=|>|>=|==|!=)\s*\d+", code)
        )
        if has_parts_access and not has_len_check:
            line = self._line_from_offset(code, re.search(r"\b(?:parts|tokens|fields)\s*\[\s*\d+\s*\]", code).start(), 1)
            findings.append(
                {
                    "rule_id": "CFG-01",
                    "rule_item": "config 항목 정합성 확인",
                    "severity": "Warning",
                    "line": line,
                    "message": "config 파싱 형식 불일치 가능성, delimiter/필드수 검증 권장.",
                }
            )
        return findings

    def check_config_error_contract(self, code: str) -> List[Dict]:
        findings = []
        if not self._has_config_context(code):
            return findings
        has_parse_guard = bool(
            re.search(
                r"\bif\s*\(\s*(?:dynlen|len)\s*\(\s*(?:parts|tokens|fields)\s*\)\s*(?:<|<=)\s*\d+\s*\)",
                code,
                re.IGNORECASE,
            )
        )
        if not has_parse_guard:
            return findings

        has_continue = "continue;" in code
        has_fail_return = bool(re.search(r"\breturn\s+(?:false|-1)\s*;", code, re.IGNORECASE))
        if has_continue and not has_fail_return:
            line = self._line_from_offset(code, code.find("continue;"), base_line=1)
            findings.append(
                {
                    "rule_id": "CFG-ERR-01",
                    "rule_item": "config 항목 정합성 확인",
                    "severity": "Warning",
                    "line": line,
                    "message": "Error 케이스에서 함수 실패 반환/중단 처리 권장.",
                }
            )
        return findings

    def check_dpget_batch_optimization(self, code: str) -> List[Dict]:
        findings = []
        for match in re.finditer(r"\b(?:while|for)\s*\([^\)]*\)\s*\{", code, re.IGNORECASE):
            open_brace = code.find("{", match.start())
            if open_brace < 0:
                continue
            close_brace = self._find_matching_delimiter(code, open_brace, "{", "}")
            if close_brace < 0:
                continue

            block = code[open_brace : close_brace + 1]
            dpget_count = len(re.findall(r"\bdpGet\s*\(", block))
            if dpget_count <= 1:
                continue

            has_cache = bool(re.search(r"\b(mappingHasKey|cache|memo|lookup)\b", block, re.IGNORECASE))
            if has_cache:
                continue

            findings.append(
                {
                    "rule_id": "PERF-DPGET-BATCH-01",
                    "rule_item": "Event, Ctrl Manager 이벤트 교환 횟수 최소화",
                    "severity": "Warning",
                    "line": self._line_from_offset(code, match.start(), base_line=1),
                    "message": "반복 구간 dpGet 일괄/캐시 처리 권장.",
                }
            )
            break
        return findings

    def check_dpset_batch_optimization(self, code: str) -> List[Dict]:
        findings = []
        for match in re.finditer(r"\b(?:while|for)\s*\([^\)]*\)\s*\{", code, re.IGNORECASE):
            open_brace = code.find("{", match.start())
            if open_brace < 0:
                continue
            close_brace = self._find_matching_delimiter(code, open_brace, "{", "}")
            if close_brace < 0:
                continue

            block = code[open_brace : close_brace + 1]
            dpset_count = len(re.findall(r"\bdpSet\s*\(", block))
            if dpset_count < 2:
                continue

            has_batch_hint = bool(
                re.search(r"\b(dpSetWait|dpSetTimed|batch|group)\b", block, re.IGNORECASE)
            )
            has_guard = bool(re.search(r"(!=|changed|old|prev)", block, re.IGNORECASE))
            if has_batch_hint or has_guard:
                continue

            findings.append(
                {
                    "rule_id": "PERF-DPSET-BATCH-01",
                    "rule_item": "Event, Ctrl Manager 이벤트 교환 횟수 최소화",
                    "severity": "Warning",
                    "line": self._line_from_offset(code, match.start(), base_line=1),
                    "message": "반복 구간 dpSet 일괄/배치 처리 권장.",
                }
            )
            break
        return findings

    def check_try_catch_for_risky_ops(self, code: str) -> List[Dict]:
        findings = []
        risky_iter = list(re.finditer(r"\b(dpSet|dpGet|dpQuery|fopen|fileOpen|strsplit)\s*\(", code))
        if not risky_iter:
            return findings
        risky_match = risky_iter[0]

        if re.search(r"\btry\b", code, re.IGNORECASE) and re.search(r"\bcatch\b", code, re.IGNORECASE):
            return findings
        if re.search(r"\bgetLastError\s*\(", code, re.IGNORECASE):
            return findings
        if re.search(r"\breturn\s+(false|-1)\s*;", code, re.IGNORECASE):
            return findings
        if re.search(r"\b(writeLog|DebugN|DebugTN)\s*\([^)]*(err|error|fail|getLastError)[^)]*\)", code, re.IGNORECASE):
            return findings
        if re.search(r"\bif\s*\([^)]*(err|error|rc|ret|result|status)[^)]*\)", code, re.IGNORECASE):
            return findings

        # Narrow trigger scope: only warn when risk context is strong.
        loop_ranges = self._collect_loop_line_ranges(code)
        risky_line = self._line_from_offset(code, risky_match.start(), base_line=1)
        in_loop = any(start <= risky_line <= end for start, end in loop_ranges)
        has_parse_contract = bool(re.search(r"\bdynlen\s*\(\s*(parts|tokens|fields)\s*\)\s*(<|<=)\s*\d+", code, re.IGNORECASE))
        if not (len(risky_iter) >= 2 or in_loop or has_parse_contract):
            return findings

        findings.append(
            {
                "rule_id": "EXC-TRY-01",
                "rule_item": "불필요한 코드 지양",
                "severity": "Warning",
                "line": risky_line,
                "message": "예외 가능 구문에 try/catch 또는 오류 처리 계약 추가 권장.",
            }
        )
        return findings

    def check_division_zero_guard(self, code: str) -> List[Dict]:
        findings = []
        if not self._has_config_context(code):
            return findings
        lines = code.splitlines()
        for idx, line in enumerate(lines, 1):
            # Remove string literals to avoid path like "config/config.json"
            # being treated as division.
            sanitized = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', '""', line)
            if "/" not in sanitized:
                continue
            if re.search(r"//", sanitized):
                continue

            # Skip obvious safe patterns.
            if re.search(r"\bmax\s*\(\s*1\s*,", sanitized, re.IGNORECASE):
                continue
            if re.search(r"\?.*/.*:", sanitized):
                continue

            for match in re.finditer(r"/\s*([A-Za-z_][A-Za-z0-9_]*|\([^)]+\))", sanitized):
                denom_expr = match.group(1).strip()
                if re.fullmatch(r"\d+(?:\.\d+)?", denom_expr):
                    continue
                if denom_expr.startswith("(") and denom_expr.endswith(")"):
                    inner = denom_expr[1:-1]
                    denom_vars = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", inner)
                else:
                    denom_vars = [denom_expr]
                if not denom_vars:
                    continue

                guard_found = False
                for lookback in range(max(1, idx - 3), idx + 1):
                    ctx = lines[lookback - 1]
                    for denom in denom_vars:
                        has_non_zero_guard = bool(
                            re.search(rf"\b{re.escape(denom)}\b\s*!=\s*0", ctx)
                            or re.search(rf"\b{re.escape(denom)}\b\s*(>|>=)\s*1", ctx)
                            or re.search(rf"\b{re.escape(denom)}\b\s*(<=|==)\s*0", ctx)
                        )
                        has_if_guard = bool(re.search(rf"\bif\s*\([^)]*\b{re.escape(denom)}\b[^)]*\)", ctx))
                        if has_non_zero_guard and has_if_guard:
                            guard_found = True
                            break
                        if has_if_guard and re.search(r"\b(return|continue|break)\b", "\n".join(lines[lookback - 1 : min(len(lines), lookback + 2)])):
                            guard_found = True
                            break
                    if guard_found:
                        break

                if guard_found:
                    continue

                findings.append(
                    {
                        "rule_id": "SAFE-DIV-01",
                        "rule_item": "config 항목 정합성 확인",
                        "severity": "Warning",
                        "line": idx,
                        "message": "분모 0 가능성 감지, 나눗셈 전 guard 조건 추가 권장.",
                    }
                )
                return findings
        return findings

    def check_setvalue_batch_optimization(self, code: str) -> List[Dict]:
        findings = []
        for match in re.finditer(r"\b(?:while|for)\s*\([^\)]*\)\s*\{", code, re.IGNORECASE):
            open_brace = code.find("{", match.start())
            if open_brace < 0:
                continue
            close_brace = self._find_matching_delimiter(code, open_brace, "{", "}")
            if close_brace < 0:
                continue

            block = code[open_brace : close_brace + 1]
            setvalue_count = len(re.findall(r"\bsetValue\s*\(", block))
            if setvalue_count < 2:
                continue
            if re.search(r"\bsetMultiValue\s*\(", block, re.IGNORECASE):
                continue

            findings.append(
                {
                    "rule_id": "PERF-SETVALUE-BATCH-01",
                    "rule_item": "Event, Ctrl Manager 이벤트 교환 횟수 최소화",
                    "severity": "Warning",
                    "line": self._line_from_offset(code, match.start(), base_line=1),
                    "message": "setValue 반복 호출 감지, setMultiValue 기반 일괄 처리 권장.",
                }
            )
            break
        return findings

    def check_setmultivalue_adoption(self, code: str) -> List[Dict]:
        findings = []
        lines = code.splitlines()
        setvalue_lines = [idx for idx, line in enumerate(lines, 1) if re.search(r"\bsetValue\s*\(", line)]
        if len(setvalue_lines) < 2:
            return findings

        for i in range(len(setvalue_lines) - 1):
            start_line = setvalue_lines[i]
            end_line = setvalue_lines[i + 1]
            if end_line - start_line > 6:
                continue

            window_start = max(1, start_line - 1)
            window_end = min(len(lines), end_line + 2)
            block = "\n".join(lines[window_start - 1 : window_end])
            if re.search(r"\bsetMultiValue\s*\(", block, re.IGNORECASE):
                continue

            findings.append(
                {
                    "rule_id": "PERF-SETMULTIVALUE-ADOPT-01",
                    "rule_item": "Event, Ctrl Manager 이벤트 교환 횟수 최소화",
                    "severity": "Warning",
                    "line": start_line,
                    "message": "다중 set 업데이트 감지, setMultiValue 구문 적용 권장.",
                }
            )
            break
        return findings

    def check_getvalue_batch_optimization(self, code: str) -> List[Dict]:
        findings = []
        for match in re.finditer(r"\b(?:while|for)\s*\([^\)]*\)\s*\{", code, re.IGNORECASE):
            open_brace = code.find("{", match.start())
            if open_brace < 0:
                continue
            close_brace = self._find_matching_delimiter(code, open_brace, "{", "}")
            if close_brace < 0:
                continue

            block = code[open_brace : close_brace + 1]
            getvalue_count = len(re.findall(r"\bgetValue\s*\(", block))
            if getvalue_count < 2:
                continue
            has_batch_or_cache = bool(
                re.search(
                    r"\b(getMultiValue|cache|mappingHasKey|memo|lookup|batch)\b",
                    block,
                    re.IGNORECASE,
                )
            )
            if has_batch_or_cache:
                continue

            findings.append(
                {
                    "rule_id": "PERF-GETVALUE-BATCH-01",
                    "rule_item": "Event, Ctrl Manager 이벤트 교환 횟수 최소화",
                    "severity": "Warning",
                    "line": self._line_from_offset(code, match.start(), base_line=1),
                    "message": "getValue 반복 호출 감지, 일괄 조회/캐시 처리 권장.",
                }
            )
            break
        return findings

    def check_manual_aggregation_pattern(self, code: str) -> List[Dict]:
        findings = []
        for match in re.finditer(r"\b(?:while|for)\s*\([^\)]*\)\s*\{", code, re.IGNORECASE):
            open_brace = code.find("{", match.start())
            if open_brace < 0:
                continue
            close_brace = self._find_matching_delimiter(code, open_brace, "{", "}")
            if close_brace < 0:
                continue
            block = code[open_brace : close_brace + 1]

            has_manual_agg = bool(re.search(r"\b(sum|total)\s*\+=", block) and re.search(r"\b(count|cnt)\s*(\+\+|\+=\s*1)", block))
            if not has_manual_agg:
                continue
            if re.search(r"\b(dynSum|dynAvg|avg|average)\s*\(", block):
                continue

            findings.append(
                {
                    "rule_id": "PERF-AGG-01",
                    "rule_item": "불필요한 코드 지양",
                    "severity": "Low",
                    "line": self._line_from_offset(code, match.start(), base_line=1),
                    "message": "수동 집계 대신 표준 집계 유틸(dynSum/dynAvg 등) 검토 권장.",
                }
            )
            break
        return findings

    def check_magic_index_usage(self, code: str) -> List[Dict]:
        findings = []
        if re.search(r"\bIDX_[A-Z0-9_]+\b", code):
            return findings

        matches = list(re.finditer(r"\b(?:parts|data|tokens|fields)\s*\[\s*([2-9]|\d{2,})\s*\]", code))
        if len(matches) < 3:
            return findings

        findings.append(
            {
                "rule_id": "STYLE-IDX-01",
                "rule_item": "명명 규칙 및 코딩 스타일 준수 확인",
                "severity": "Low",
                "line": self._line_from_offset(code, matches[0].start(), base_line=1),
                "message": "인덱스 매직넘버 사용 감지, IDX_* 상수화 권장.",
            }
        )
        return findings

    def check_float_literal_hardcoding(self, code: str) -> List[Dict]:
        findings = []
        lines = code.splitlines()
        hit_lines = []
        for idx, line in enumerate(lines, 1):
            if re.search(r"^\s*const\b", line):
                continue
            if re.search(r"\b0\.0*1\b|\b0\.001\b", line):
                hit_lines.append(idx)
        if len(hit_lines) >= 2:
            findings.append(
                {
                    "rule_id": "HARD-03",
                    "rule_item": "하드코딩 지양",
                    "severity": "Medium",
                    "line": hit_lines[0],
                    "message": "임계 소수값 하드코딩 감지, 상수/설정값 치환 권장.",
                }
            )
        return findings

    def check_event(self, event_data: Dict, file_type: str = "Client") -> List[Dict]:
        violations = []
        code = event_data["code"]
        analysis_code = self._remove_comments(code)
        event_name = event_data["event"]
        base_line = int(event_data.get("line_start", 1) or 1)
        anchor_line = self._first_function_line(analysis_code)

        if len(analysis_code) > 300000:
            return [
                {
                    "issue_id": "INFO-SIZE",
                    "rule_id": "INFO",
                    "rule_item": "시스템 보호",
                    "severity": "Info",
                    "line": 0,
                    "message": f"파일 크기가 너무 커서 ({len(analysis_code)} bytes) 정밀 분석을 건너뜁니다.",
                }
            ]

        if self.p1_rule_defs:
            configured = self._run_configured_p1_rules(
                code=code,
                analysis_code=analysis_code,
                event_name=event_name,
                base_line=base_line,
                anchor_line=anchor_line,
                file_type=file_type,
            )
            dedup = {v["issue_id"]: v for v in configured}
            dedup_list = list(dedup.values())
            return self._filter_violations_by_file_type(dedup_list, file_type=file_type)

        for rule_id, info in self.technical_patterns.items():
            match = re.search(info["pattern"], analysis_code, re.DOTALL | re.MULTILINE)
            if match:
                match_line = self._line_from_offset(analysis_code, match.start(), base_line=base_line)
                violations.append(
                    {
                        "issue_id": self._build_issue_id(rule_id, analysis_code, match_line, event_name),
                        "rule_id": rule_id,
                        "rule_item": info["rule_item"],
                        "priority_origin": "P1",
                        "severity": info["severity"],
                        "line": match_line,
                        "message": info["message"],
                    }
                )

        check_funcs = [
            self.check_sql_injection,
            self.check_complexity,
            self.check_unused_variables,
            self.check_db_query_error,
            self.check_dp_function_exception,
            self.check_config_format_consistency,
            self.check_config_error_contract,
            self.check_while_delay_policy,
            self.check_event_exchange_minimization,
            self.check_dpset_timed_context,
            self.check_dpget_batch_optimization,
            self.check_dpset_batch_optimization,
            self.check_setvalue_batch_optimization,
            self.check_setmultivalue_adoption,
            self.check_getvalue_batch_optimization,
            self.check_try_catch_for_risky_ops,
            self.check_division_zero_guard,
            self.check_manual_aggregation_pattern,
            self.check_consecutive_dpset,
            self.check_memory_leaks_advanced,
            self.check_input_validation,
            self.check_coding_standards_advanced,
            self.check_style_name_rules,
            self.check_style_indent_rules,
            self.check_style_header_rules,
            self.check_magic_index_usage,
            self.check_hardcoding_extended,
            self.check_float_literal_hardcoding,
            self.check_dead_code,
            self.check_duplicate_blocks,
        ]

        for check_func in check_funcs:
            use_original = getattr(check_func, "__name__", "") == "check_style_header_rules"
            check_input = code if use_original else analysis_code
            findings = check_func(check_input)
            for finding in findings:
                local_line = int(finding.get("line", 0) or 0)
                if local_line <= 0:
                    local_line = anchor_line
                absolute_line = base_line + local_line - 1
                violations.append(
                    {
                        "issue_id": self._build_issue_id(finding["rule_id"], analysis_code, absolute_line, event_name),
                        "rule_id": finding["rule_id"],
                        "rule_item": finding["rule_item"],
                        "priority_origin": "P1",
                        "severity": finding["severity"],
                        "line": absolute_line,
                        "message": finding["message"],
                    }
                )

        if event_name == "Initialize" and "delay(" in analysis_code:
            rule_id = "UI-BLOCK"
            ui_line = base_line + anchor_line - 1
            violations.append(
                {
                    "issue_id": self._build_issue_id(rule_id, analysis_code, ui_line, event_name),
                    "rule_id": rule_id,
                    "rule_item": "적절한 DP 처리 함수 사용",
                    "priority_origin": "P1",
                    "severity": "Warning",
                    "line": ui_line,
                    "message": "UI 블로킹 위험: Initialize 내 delay 호출.",
                }
            )

        dedup = {v["issue_id"]: v for v in violations}
        dedup_list = list(dedup.values())
        return self._filter_violations_by_file_type(dedup_list, file_type=file_type)

    def analyze_raw_code(self, file_path: str, code: str, file_type: str = "Client") -> List[Dict]:
        analysis_code = code
        if len(code) > 100000:
            analysis_code = code[:100000] + "\n// ... [Code truncated for performance] ..."

        event_data = {"event": "Global", "code": analysis_code, "line_start": 1}
        violations = self.check_event(event_data, file_type=file_type)
        if violations:
            return [{"object": os.path.basename(file_path), "event": "Global", "violations": violations}]
        return []

    def analyze_project(self, parsed_data: List[Dict], file_type: str = "Client") -> List[Dict]:
        all_results = []
        for obj in parsed_data:
            for event in obj["events"]:
                violations = self.check_event(event, file_type=file_type)
                if violations:
                    for v in violations:
                        if v.get("line") == 0:
                            v["line"] = event.get("line_start", 0)
                    all_results.append({"object": obj["name"], "event": event["event"], "violations": violations})
        return all_results
