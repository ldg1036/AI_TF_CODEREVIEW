import hashlib
import json
import os
import re
from bisect import bisect_right
from collections import Counter
from typing import Any, Callable, Dict, List, Optional

from core.rules.performance_rules import PerformanceRulesMixin
from core.rules.security_rules import SecurityRulesMixin
from core.rules.style_rules import StyleRulesMixin
from core.rules.quality_rules import QualityRulesMixin
from core.rules.config_rules import ConfigRulesMixin
from core.rules.composite_rules import CompositeRulesMixin, CompositeRuleContext

_FUNCTION_SIGNATURE_PATTERN = re.compile(
    r"^(void|int|float|string|bool|mapping|time|anytype|dyn_[a-zA-Z0-9_]+)\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\("
)
_FUNCTION_DEF_PATTERN = re.compile(
    r"\b(?:void|int|float|string|bool|mapping|time|anytype|dyn_[a-zA-Z0-9_]+)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^\)]*\)\s*\{",
    re.IGNORECASE,
)
_LOOP_HEADER_PATTERN = re.compile(r"\b(?:while|for)\s*\([^\)]*\)\s*\{", re.IGNORECASE)
_WHILE_HEADER_PATTERN = re.compile(r"\bwhile\s*\(")
_NORMALIZE_WS_PATTERN = re.compile(r"\s+")
_DPSET_LINE_PATTERN = re.compile(r"\bdpSet\s*\(")
_DPGET_LINE_PATTERN = re.compile(r"\bdpGet\s*\(")
_SETVALUE_LINE_PATTERN = re.compile(r"\bsetValue\s*\(")
_GETVALUE_LINE_PATTERN = re.compile(r"\bgetValue\s*\(")
_DPSET_FIRST_ARG_PATTERN = re.compile(r"\bdpSet\s*\(\s*([^,]+),")
_DPSET_TIMED_HINT_PATTERN = re.compile(r"\bdpSet(?:Timed|Wait)\s*\(")
_CHANGE_GUARD_PATTERN = re.compile(r"\bif\s*\([^\)]*(?:!=|\bchanged\b|\bdelta\b|\bold\b|\bprev\b)[^\)]*\)", re.IGNORECASE)
_DYN_DECL_PATTERN = re.compile(r"\bdyn_\w+\s+[a-zA-Z_][a-zA-Z0-9_]*")
_CALL_NAME_PATTERN = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_MERGED_DPSET_PATTERN = re.compile(r"\bdpSet\s*\(\s*\"[^\"]+\"\s*,\s*[^,]+,\s*\"[^\"]+\"\s*,")


class HeuristicChecker(CompositeRulesMixin, 
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

    _CONTEXT_AWARE_RULE_NAMES = {
        "check_complexity",
        "check_unused_variables",
        "check_while_delay_policy",
        "check_dpset_timed_context",
        "check_consecutive_dpset",
        "check_event_exchange_minimization",
        "check_memory_leaks_advanced",
        "check_dead_code",
        "check_duplicate_blocks",
        "check_dpget_batch_optimization",
        "check_dpset_batch_optimization",
        "check_setvalue_batch_optimization",
        "check_setmultivalue_adoption",
        "check_getvalue_batch_optimization",
        "check_manual_aggregation_pattern",
    }

    def __init__(self, rules_path: str = None):
        if rules_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            rules_path = os.path.abspath(os.path.join(base_dir, "..", "Config", "parsed_rules.json"))
        else:
            rules_path = os.path.abspath(str(rules_path))
        self.rules_path = rules_path
        self.config_dir = os.path.dirname(rules_path)

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

    def _build_analysis_context(self, code: str) -> Dict[str, Any]:
        lines = code.splitlines()
        line_starts: List[int] = []
        offset = 0
        for raw_line in code.splitlines(True):
            line_starts.append(offset)
            offset += len(raw_line)
        return {
            "code": code,
            "lines": lines,
            "line_count": len(lines),
            "newline_lines": code.split("\n"),
            "line_starts": line_starts or [0],
            "cache": {},
        }

    @staticmethod
    def _context_matches_code(context: Optional[Dict[str, Any]], code: str) -> bool:
        return isinstance(context, dict) and context.get("code") == code

    @staticmethod
    def _safe_int(value: Any, fallback: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    def _get_context_lines(self, code: str, context: Optional[Dict[str, Any]] = None) -> List[str]:
        if self._context_matches_code(context, code):
            return context["lines"]
        return code.splitlines()

    def _get_context_newline_lines(self, code: str, context: Optional[Dict[str, Any]] = None) -> List[str]:
        if self._context_matches_code(context, code):
            return context["newline_lines"]
        return code.split("\n")

    def _get_context_cache(self, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(context, dict):
            return {}
        cache = context.get("cache")
        if not isinstance(cache, dict):
            cache = {}
            context["cache"] = cache
        return cache

    def _get_function_bodies(self, code: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        cache = self._get_context_cache(context)
        cache_key = "function_bodies"
        if cache_key in cache:
            return cache[cache_key]

        func_defs: Dict[str, str] = {}
        for func_match in _FUNCTION_DEF_PATTERN.finditer(code):
            name = func_match.group(1)
            brace_idx = code.find("{", func_match.start())
            if brace_idx < 0:
                continue
            close_brace = self._find_matching_delimiter(code, brace_idx, "{", "}")
            if close_brace < 0:
                continue
            func_defs[name] = code[brace_idx : close_brace + 1]
        cache[cache_key] = func_defs
        return func_defs

    def _get_loop_blocks(self, code: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        cache = self._get_context_cache(context)
        cache_key = "loop_blocks"
        if cache_key in cache:
            return cache[cache_key]

        blocks: List[Dict[str, Any]] = []
        for match in _LOOP_HEADER_PATTERN.finditer(code):
            open_brace = code.find("{", match.start())
            if open_brace < 0:
                continue
            close_brace = self._find_matching_delimiter(code, open_brace, "{", "}")
            if close_brace < 0:
                continue
            blocks.append(
                {
                    "match_start": match.start(),
                    "start_line": self._line_from_offset(code, match.start(), base_line=1, context=context),
                    "end_line": self._line_from_offset(code, close_brace, base_line=1, context=context),
                    "block": code[open_brace : close_brace + 1],
                }
            )
        cache[cache_key] = blocks
        return blocks

    def _get_token_line_numbers(
        self,
        code: str,
        cache_key: str,
        pattern: re.Pattern,
        context: Optional[Dict[str, Any]] = None,
        one_based: bool = True,
    ) -> List[int]:
        cache = self._get_context_cache(context)
        full_cache_key = f"token_lines:{cache_key}:{1 if one_based else 0}"
        if full_cache_key in cache:
            return cache[full_cache_key]

        start = 1 if one_based else 0
        lines = self._get_context_newline_lines(code, context=context)
        matches = [idx for idx, line in enumerate(lines, start) if pattern.search(line)]
        cache[full_cache_key] = matches
        return matches

    def _get_normalized_lines(
        self,
        code: str,
        context: Optional[Dict[str, Any]] = None,
        *,
        ignore_comments: bool = True,
        ignore_braces_only: bool = True,
        normalize_ws: bool = True,
        min_len: int = 8,
    ) -> List[tuple[int, str]]:
        cache = self._get_context_cache(context)
        cache_key = (
            "normalized_lines",
            ignore_comments,
            ignore_braces_only,
            normalize_ws,
            min_len,
        )
        if cache_key in cache:
            return cache[cache_key]

        normalized_lines = []
        for idx, raw in enumerate(self._get_context_lines(code, context=context), 1):
            line = raw.strip()
            if not line:
                continue
            if ignore_comments and line.startswith("//"):
                continue
            if ignore_braces_only and line in {"{", "}"}:
                continue
            if normalize_ws:
                line = _NORMALIZE_WS_PATTERN.sub(" ", line)
            if len(line) < min_len:
                continue
            normalized_lines.append((idx, line))

        cache[cache_key] = normalized_lines
        return normalized_lines

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
            prepared = []
            for row in data:
                if not isinstance(row, dict):
                    continue
                prepared.append(self._prepare_p1_rule_def(row))
            prepared.sort(key=lambda row: self._safe_int(row.get("_sort_order", 0), 0))
            return prepared
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

    def _prepare_p1_rule_def(self, row: Dict[str, Any]) -> Dict[str, Any]:
        prepared = dict(row)
        prepared["_sort_order"] = self._safe_int(prepared.get("order", 0), 0)

        detector = prepared.get("detector", {})
        if not isinstance(detector, dict):
            return prepared

        prepared_detector = dict(detector)
        kind = str(prepared_detector.get("kind", "") or "").strip().lower()
        if kind == "regex":
            raw_pattern = prepared_detector.get("pattern", "")
            normalized_pattern = self._normalize_detector_regex(raw_pattern)
            prepared_detector["pattern"] = normalized_pattern
            flags = self._regex_flags_from_rule(prepared_detector.get("flags", ["DOTALL", "MULTILINE"]))
            prepared_detector["_compiled_flags"] = flags

            event_names = prepared_detector.get("event_names")
            if isinstance(event_names, str):
                event_names = [event_names]
            if isinstance(event_names, list):
                prepared_detector["_allowed_event_names"] = {
                    str(item) for item in event_names if str(item or "").strip()
                }
            else:
                prepared_detector["_allowed_event_names"] = set()

            try:
                prepared_detector["_compiled_regex"] = re.compile(normalized_pattern, flags)
                prepared_detector["_invalid_regex_error"] = ""
            except re.error as exc:
                prepared_detector["_compiled_regex"] = None
                prepared_detector["_invalid_regex_error"] = str(exc)
                print(
                    f"[!] Invalid regex in p1_rule_defs "
                    f"({prepared.get('id', prepared.get('rule_id'))}): {exc}"
                )

        prepared["detector"] = prepared_detector
        return prepared

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

    def _line_from_offset(
        self,
        code: str,
        offset: int,
        base_line: int = 1,
        context: Optional[Dict[str, Any]] = None,
    ) -> int:
        if self._context_matches_code(context, code):
            line_starts = context.get("line_starts") or [0]
            line_index = bisect_right(line_starts, max(0, offset)) - 1
            return base_line + max(0, line_index)
        return base_line + code.count("\n", 0, max(0, offset))

    def _first_function_line(self, code: str, context: Optional[Dict[str, Any]] = None) -> int:
        lines = self._get_context_lines(code, context=context)
        for idx, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue
            if re.match(r"^(main)\s*\(", stripped):
                return idx
            if _FUNCTION_SIGNATURE_PATTERN.match(stripped):
                return idx
        return 1

    # -------------------------------------------------------------------------
    # Legacy check_* methods are now provided by Mixin base classes:
    #   PerformanceRulesMixin, SecurityRulesMixin, StyleRulesMixin,
    #   QualityRulesMixin, ConfigRulesMixin
    # See core/rules/ for the implementations.
    # -------------------------------------------------------------------------

    def check_complexity(self, code: str, context: Optional[Dict[str, Any]] = None) -> List[Dict]:
        findings = []
        if len(code) > 100000:
            return findings

        lines = self._get_context_lines(code, context=context)
        anchor_line = self._first_function_line(code, context=context)
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

    def check_unused_variables(self, code: str, context: Optional[Dict[str, Any]] = None) -> List[Dict]:
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
            declared_vars[var_name] = self._line_from_offset(clean_code, match.start(), base_line=1, context=context)

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

    def _collect_loop_line_ranges(self, code: str, context: Optional[Dict[str, Any]] = None) -> List[tuple]:
        return [(block["start_line"], block["end_line"]) for block in self._get_loop_blocks(code, context=context)]

    def check_while_delay_policy(self, code: str, context: Optional[Dict[str, Any]] = None) -> List[Dict]:
        findings = []
        for match in _WHILE_HEADER_PATTERN.finditer(code):
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
                    "line": self._line_from_offset(code, match.start(), base_line=1, context=context),
                    "message": "while 루프 내부 delay 부재 패턴 감지.",
                }
            )
            break

        return findings

    def check_dpset_timed_context(self, code: str, context: Optional[Dict[str, Any]] = None) -> List[Dict]:
        findings = []
        lines = self._get_context_lines(code, context=context)

        for idx, line in enumerate(lines, 1):
            m = _DPSET_FIRST_ARG_PATTERN.search(line)
            if not m:
                continue

            first_arg = m.group(1)
            # Limit detection to alarm/config-like writes where history churn is a concern.
            if not re.search(r"(alert|alm|alarm|\.set\b|_set\b|sp_)", first_arg, re.IGNORECASE):
                continue

            window_start = max(0, idx - 3)
            window_end = min(len(lines), idx + 2)
            window_text = "\n".join(lines[window_start:window_end])

            has_timed = bool(_DPSET_TIMED_HINT_PATTERN.search(window_text))
            has_delta_guard = bool(_CHANGE_GUARD_PATTERN.search(window_text))
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

    def check_consecutive_dpset(self, code: str, context: Optional[Dict[str, Any]] = None) -> List[Dict]:
        findings = []
        lines = self._get_context_lines(code, context=context)
        dpset_lines = [line_no - 1 for line_no in self._get_token_line_numbers(code, "dpset", _DPSET_LINE_PATTERN, context=context)]
        if len(dpset_lines) < 2:
            return findings
        loop_ranges = self._collect_loop_line_ranges(code, context=context)

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
                _DPSET_TIMED_HINT_PATTERN.search(window)
                or _CHANGE_GUARD_PATTERN.search(window)
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

        return findings

    def check_event_exchange_minimization(self, code: str, context: Optional[Dict[str, Any]] = None) -> List[Dict]:
        findings = []
        func_defs = self._get_function_bodies(code, context=context)

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
            if _DPSET_LINE_PATTERN.search(body):
                if not _DPSET_TIMED_HINT_PATTERN.search(body) and not _CHANGE_GUARD_PATTERN.search(body):
                    return True
            if depth <= 0:
                return False
            called_names = [
                token
                for token in _CALL_NAME_PATTERN.findall(body)
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
        for loop_block in self._get_loop_blocks(code, context=context):
            block = loop_block["block"]
            dpset_matches = list(_DPSET_LINE_PATTERN.finditer(block))
            indirect_dpset_call = ""
            if len(dpset_matches) < 1:
                called_names = [
                    token
                    for token in _CALL_NAME_PATTERN.findall(block)
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

            if _DPSET_TIMED_HINT_PATTERN.search(block):
                continue
            if _CHANGE_GUARD_PATTERN.search(block):
                continue

            merged_match = _MERGED_DPSET_PATTERN.search(block)
            if merged_match:
                continue

            line = loop_block["start_line"]
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

    def check_memory_leaks_advanced(self, code: str, context: Optional[Dict[str, Any]] = None) -> List[Dict]:
        findings = []
        declarations = [
            (idx, line)
            for idx, line in enumerate(self._get_context_lines(code, context=context), 1)
            if _DYN_DECL_PATTERN.search(line)
        ]
        if not declarations:
            return findings

        # Treat explicit dynClear/dynRemove usage as cleanup signals.
        has_cleanup = bool(re.search(r"\bdyn(?:Clear|Remove)\s*\(", code))
        if has_cleanup:
            return findings

        # Warn only when dyn collection APIs are used in iterative contexts.
        for loop_block in self._get_loop_blocks(code, context=context):
            if re.search(r"\bdyn(?:Append|Insert|MapInsert)\s*\(", loop_block["block"], re.IGNORECASE):
                findings.append(
                    {
                        "rule_id": "MEM-01",
                        "rule_item": "메모리 누수 체크",
                        "severity": "Warning",
                        "line": declarations[0][0],
                        "message": "반복 구간 dyn 사용 대비 dynClear()/dynRemove() 누락 가능성.",
                    }
                )
                break
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

    def check_dead_code(self, code: str, context: Optional[Dict[str, Any]] = None) -> List[Dict]:
        findings = []
        false_if = re.search(r"\bif\s*\(\s*false\s*\)", code, re.IGNORECASE)
        if false_if:
            findings.append(
                {
                    "rule_id": "CLEAN-DEAD-01",
                    "rule_item": "불필요한 코드 지양",
                    "severity": "Medium",
                    "line": self._line_from_offset(code, false_if.start(), base_line=1, context=context),
                    "message": "영구 미실행 분기(if(false)) 감지.",
                }
            )
            return findings

        lines = self._get_context_lines(code, context=context)
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

    def check_duplicate_blocks(self, code: str, context: Optional[Dict[str, Any]] = None) -> List[Dict]:
        findings = []
        normalized_lines = self._get_normalized_lines(code, context=context)
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

    def check_dpget_batch_optimization(self, code: str, context: Optional[Dict[str, Any]] = None) -> List[Dict]:
        findings = []
        seen_lines = set()
        max_gap = 4
        min_count = 2

        def _emit(line_no: int) -> None:
            if line_no in seen_lines:
                return
            seen_lines.add(line_no)
            findings.append(
                {
                    "rule_id": "PERF-DPGET-BATCH-01",
                    "rule_item": "Event, Ctrl Manager 이벤트 교환 횟수 최소화",
                    "severity": "Warning",
                    "line": line_no,
                    "message": "반복 구간 dpGet 일괄/캐시 처리 권장.",
                }
            )

        # loop-inside detection
        for loop_block in self._get_loop_blocks(code, context=context):
            block = loop_block["block"]
            dpget_count = len(re.findall(r"\bdpGet\s*\(", block))
            if dpget_count < min_count:
                continue
            if re.search(r"\b(mappingHasKey|cache|memo|lookup)\b", block, re.IGNORECASE):
                continue
            _emit(loop_block["start_line"])

        # outside-loop clustered detection
        lines = self._get_context_lines(code, context=context)
        loop_ranges = self._collect_loop_line_ranges(code, context=context)

        def _in_loop(line_no: int) -> bool:
            return any(start <= line_no <= end for start, end in loop_ranges)

        dpget_lines = [
            idx
            for idx in self._get_token_line_numbers(code, "dpget", _DPGET_LINE_PATTERN, context=context)
            if not _in_loop(idx)
        ]
        if len(dpget_lines) < min_count:
            return findings

        cluster = [dpget_lines[0]]

        def _emit_cluster(cluster_lines: List[int]) -> None:
            if len(cluster_lines) < min_count:
                return
            start_line = cluster_lines[0]
            end_line = cluster_lines[-1]
            window_start = max(1, start_line - 1)
            window_end = min(len(lines), end_line + 2)
            block = "\n".join(lines[window_start - 1 : window_end])
            if re.search(r"\b(mappingHasKey|cache|memo|lookup)\b", block, re.IGNORECASE):
                return
            _emit(start_line)

        for line_no in dpget_lines[1:]:
            if line_no - cluster[-1] <= max_gap:
                cluster.append(line_no)
                continue
            _emit_cluster(cluster)
            cluster = [line_no]
        _emit_cluster(cluster)
        return findings

    def check_dpset_batch_optimization(self, code: str, context: Optional[Dict[str, Any]] = None) -> List[Dict]:
        findings = []
        seen_lines = set()
        max_gap = 4
        min_count = 2

        def _emit(line_no: int) -> None:
            if line_no in seen_lines:
                return
            seen_lines.add(line_no)
            findings.append(
                {
                    "rule_id": "PERF-DPSET-BATCH-01",
                    "rule_item": "Event, Ctrl Manager 이벤트 교환 횟수 최소화",
                    "severity": "Warning",
                    "line": line_no,
                    "message": "반복 구간 dpSet 일괄/배치 처리 권장.",
                }
            )

        # loop-inside detection
        for loop_block in self._get_loop_blocks(code, context=context):
            block = loop_block["block"]
            dpset_count = len(re.findall(r"\bdpSet\s*\(", block))
            if dpset_count < min_count:
                continue

            has_batch_hint = bool(re.search(r"\b(dpSetWait|dpSetTimed|batch|group)\b", block, re.IGNORECASE))
            has_guard = bool(re.search(r"(!=|changed|old|prev)", block, re.IGNORECASE))
            if has_batch_hint or has_guard:
                continue
            _emit(loop_block["start_line"])

        # outside-loop clustered detection
        lines = self._get_context_lines(code, context=context)
        loop_ranges = self._collect_loop_line_ranges(code, context=context)

        def _in_loop(line_no: int) -> bool:
            return any(start <= line_no <= end for start, end in loop_ranges)

        dpset_lines = [
            idx
            for idx in self._get_token_line_numbers(code, "dpset", _DPSET_LINE_PATTERN, context=context)
            if not _in_loop(idx)
        ]
        if len(dpset_lines) < min_count:
            return findings

        cluster = [dpset_lines[0]]

        def _emit_cluster(cluster_lines: List[int]) -> None:
            if len(cluster_lines) < min_count:
                return
            start_line = cluster_lines[0]
            end_line = cluster_lines[-1]
            window_start = max(1, start_line - 1)
            window_end = min(len(lines), end_line + 2)
            block = "\n".join(lines[window_start - 1 : window_end])
            has_batch_hint = bool(re.search(r"\b(dpSetWait|dpSetTimed|batch|group)\b", block, re.IGNORECASE))
            has_guard = bool(re.search(r"(!=|changed|old|prev)", block, re.IGNORECASE))
            if has_batch_hint or has_guard:
                return
            _emit(start_line)

        for line_no in dpset_lines[1:]:
            if line_no - cluster[-1] <= max_gap:
                cluster.append(line_no)
                continue
            _emit_cluster(cluster)
            cluster = [line_no]
        _emit_cluster(cluster)
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

    def check_setvalue_batch_optimization(self, code: str, context: Optional[Dict[str, Any]] = None) -> List[Dict]:
        findings = []
        for loop_block in self._get_loop_blocks(code, context=context):
            block = loop_block["block"]
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
                    "line": loop_block["start_line"],
                    "message": "setValue 반복 호출 감지, setMultiValue 기반 일괄 처리 권장.",
                }
            )
            break
        return findings

    def check_setmultivalue_adoption(self, code: str, context: Optional[Dict[str, Any]] = None) -> List[Dict]:
        findings = []
        lines = self._get_context_lines(code, context=context)
        setvalue_lines = self._get_token_line_numbers(code, "setvalue", _SETVALUE_LINE_PATTERN, context=context)
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

    def check_getvalue_batch_optimization(self, code: str, context: Optional[Dict[str, Any]] = None) -> List[Dict]:
        findings = []
        for loop_block in self._get_loop_blocks(code, context=context):
            block = loop_block["block"]
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
                    "line": loop_block["start_line"],
                    "message": "getValue 반복 호출 감지, 일괄 조회/캐시 처리 권장.",
                }
            )
            break
        return findings

    def check_manual_aggregation_pattern(self, code: str, context: Optional[Dict[str, Any]] = None) -> List[Dict]:
        findings = []
        for loop_block in self._get_loop_blocks(code, context=context):
            block = loop_block["block"]

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
                    "line": loop_block["start_line"],
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
        analysis_context = self._build_analysis_context(analysis_code)
        anchor_line = self._first_function_line(analysis_code, context=analysis_context)

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
                context=analysis_context,
            )
            dedup = {v["issue_id"]: v for v in configured}
            dedup_list = list(dedup.values())
            return self._filter_violations_by_file_type(dedup_list, file_type=file_type)

        for rule_id, info in self.technical_patterns.items():
            match = re.search(info["pattern"], analysis_code, re.DOTALL | re.MULTILINE)
            if match:
                match_line = self._line_from_offset(analysis_code, match.start(), base_line=base_line, context=analysis_context)
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
            self.check_consecutive_dpset,
            self.check_dpget_batch_optimization,
            self.check_dpset_batch_optimization,
            self.check_setvalue_batch_optimization,
            self.check_setmultivalue_adoption,
            self.check_getvalue_batch_optimization,
            self.check_try_catch_for_risky_ops,
            self.check_division_zero_guard,
            self.check_manual_aggregation_pattern,
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
            rule_name = getattr(check_func, "__name__", "")
            check_input = code if use_original else analysis_code
            if not use_original and rule_name in self._CONTEXT_AWARE_RULE_NAMES:
                findings = check_func(check_input, context=analysis_context)
            else:
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
