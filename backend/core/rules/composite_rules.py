"""Composite rule operation handlers extracted from HeuristicChecker._run_composite_rule.

Each ``_composite_*`` method implements one ``op`` value from p1_rule_defs.json
composite detector entries.  The dispatch table ``COMPOSITE_OP_DISPATCH`` maps
op names to method names so the caller can replace the long if/elif chain with
a single dictionary lookup.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, List, Optional

from core.regex_guard import safe_search, safe_finditer, safe_findall


@lru_cache(maxsize=128)
def _compile_cached(pattern: str, flags: int = 0) -> re.Pattern:
    return re.compile(pattern, flags)


_LOOP_BLOCK_PATTERN = re.compile(r"\b(?:while|for)\s*\([^\)]*\)\s*\{", re.IGNORECASE)
_FUNCTION_DEF_PATTERN = re.compile(
    r"\b(?:void|int|float|string|bool|mapping|time|anytype|dyn_[a-zA-Z0-9_]+)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^\)]*\)\s*\{",
    re.IGNORECASE,
)
_FUNCTION_START_PATTERN = re.compile(
    r"^(?:main|void|int|float|string|bool|mapping|time|anytype|dyn_[a-zA-Z0-9_]+)\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\("
)
_DECL_START_PATTERN = re.compile(r"^\s*(?:int|float|string|bool|dyn_\w+)\s+[a-zA-Z_][a-zA-Z0-9_]*")
_CONTROL_PATTERN = re.compile(r"^\s*(?:if|for|while|switch|return|break|continue|try|catch)\b")
_STYLE_DECL_PATTERN = re.compile(
    r"^\s*(const\s+)?(?:int|float|string|bool|mapping|time|anytype|dyn_[a-zA-Z0-9_]+)\s+([a-zA-Z_][a-zA-Z0-9_]*)"
)
_STYLE_FUNCTION_PATTERN = re.compile(
    r"^\s*(?:void|int|float|string|bool|mapping|time|anytype|dyn_[a-zA-Z0-9_]+)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\("
)
_MAIN_FUNCTION_PATTERN = re.compile(r"^\s*main\s*\(")


@dataclass
class CompositeRuleContext:
    """Shared context passed to every composite-op handler."""
    rule_def: Dict[str, Any]
    detector: Dict[str, Any]
    code: str
    analysis_code: str
    event_name: str
    base_line: int
    anchor_line: int
    rule_id: str = ""
    rule_item: str = ""
    severity: str = "Info"
    static_message: str = ""


class CompositeRulesMixin:
    """Mixin contributing composite-rule op handlers to HeuristicChecker."""

    COMPOSITE_OP_DISPATCH: Dict[str, str] = {
        "sql_injection": "_composite_sql_injection",
        "db_query_error": "_composite_db_query_error",
        "dp_function_exception": "_composite_dp_function_exception",
        "complexity": "_composite_complexity",
        "unused_variables": "_composite_unused_variables",
        "event_exchange_minimization": "_composite_event_exchange_minimization",
        "coding_standards_advanced": "_composite_coding_standards_advanced",
        "memory_leaks_advanced": "_composite_memory_leaks_advanced",
        "ui_block_initialize_delay": "_composite_ui_block_initialize_delay",
        "style_indent_mixed": "_composite_style_indent_mixed",
        "magic_index_usage": "_composite_magic_index_usage",
        "float_literal_hardcoding": "_composite_float_literal_hardcoding",
        "hardcoding_extended": "_composite_hardcoding_extended",
        "dead_code": "_composite_dead_code",
        "while_delay_policy": "_composite_while_delay_policy",
        "while_delay_outside_active": "_composite_while_delay_outside_active",
        "config_format_consistency": "_composite_config_format_consistency",
        "config_error_contract": "_composite_config_error_contract",
        "try_catch_for_risky_ops": "_composite_try_catch_for_risky_ops",
        "division_zero_guard": "_composite_division_zero_guard",
        "manual_aggregation_pattern": "_composite_manual_aggregation_pattern",
        "consecutive_dpset": "_composite_consecutive_dpset",
        "input_validation": "_composite_input_validation",
        "style_name_rules": "_composite_style_name_rules",
        "style_header_rules": "_composite_style_header_rules",
        "dpset_timed_context": "_composite_dpset_timed_context",
        "dpget_batch_optimization": "_composite_dpget_batch_optimization",
        "dpset_batch_optimization": "_composite_dpset_batch_optimization",
        "setvalue_batch_optimization": "_composite_setvalue_batch_optimization",
        "setmultivalue_adoption": "_composite_setmultivalue_adoption",
        "getmultivalue_adoption": "_composite_getmultivalue_adoption",
        "getvalue_batch_optimization": "_composite_getvalue_batch_optimization",
        "debug_logging_presence": "_composite_debug_logging_presence",
        "logging_level_policy": "_composite_logging_level_policy",
        "script_active_condition_check": "_composite_script_active_condition_check",
        "duplicate_action_handling": "_composite_duplicate_action_handling",
    }

    # -- helpers (delegated to HeuristicChecker via self) ---------------------

    def _composite_sql_injection(self, ctx: CompositeRuleContext) -> List[Dict]:
        sql_keywords_raw = str(ctx.detector.get("sql_keywords_pattern", r"\b(SELECT|INSERT|UPDATE|DELETE|FROM|WHERE|JOIN)\b"))
        sprintf_pattern_raw = str(ctx.detector.get("sprintf_pattern", r"sprintf.*%s"))
        sql_keywords = self._normalize_detector_regex(sql_keywords_raw)
        sprintf_pattern = self._normalize_detector_regex(sprintf_pattern_raw)
        try:
            sql_keywords_re = _compile_cached(sql_keywords, re.IGNORECASE)
        except re.error:
            sql_keywords_re = _compile_cached(sql_keywords_raw, re.IGNORECASE)
        try:
            sprintf_re = _compile_cached(sprintf_pattern)
        except re.error:
            sprintf_re = _compile_cached(sprintf_pattern_raw)
        for idx, line in enumerate(ctx.analysis_code.splitlines(), 1):
            if sprintf_re.search(line) and sql_keywords_re.search(line):
                absolute_line = ctx.base_line + idx - 1
                return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, ctx.static_message, ctx.analysis_code, ctx.event_name)]
        return []

    def _composite_db_query_error(self, ctx: CompositeRuleContext) -> List[Dict]:
        query_pattern_raw = str(ctx.detector.get("query_call_pattern", r"\b(dpQuery|dbGet)\b"))
        query_pattern = self._normalize_detector_regex(query_pattern_raw)
        try:
            query_re = _compile_cached(query_pattern)
        except re.error:
            query_re = _compile_cached(query_pattern_raw)
        if not query_re.search(ctx.analysis_code):
            return []
        if re.search(r"\b(writeLog|DebugTN|getLastError)\b", ctx.analysis_code):
            return []
        match = query_re.search(ctx.analysis_code)
        absolute_line = self._line_from_offset(ctx.analysis_code, match.start(), base_line=ctx.base_line) if match else (ctx.base_line + ctx.anchor_line - 1)
        return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, ctx.static_message, ctx.analysis_code, ctx.event_name)]

    def _composite_dp_function_exception(self, ctx: CompositeRuleContext) -> List[Dict]:
        dp_call_pattern_raw = str(ctx.detector.get("dp_call_pattern", r"\b(dpSet|dpGet|dpQuery|dpConnect)\s*\([^;]+\)\s*;"))
        dp_call_pattern = self._normalize_detector_regex(dp_call_pattern_raw)
        try:
            dp_call_re = _compile_cached(dp_call_pattern)
        except re.error:
            dp_call_re = _compile_cached(dp_call_pattern_raw)
        first_dp_call = dp_call_re.search(ctx.analysis_code)
        if not first_dp_call:
            return []
        has_try = bool(re.search(r"\btry\b", ctx.analysis_code, re.IGNORECASE))
        has_catch = bool(re.search(r"\bcatch\b", ctx.analysis_code, re.IGNORECASE))
        has_try_catch = has_try and has_catch
        has_get_last_error = "getLastError" in ctx.analysis_code
        has_return_check = bool(
            re.search(r"\b(?:if|switch)\s*\([^\)]*(?:ret|result|err|error|rc|status|iErr|return_value)[^\)]*\)", ctx.analysis_code, re.IGNORECASE)
            or re.search(r"\b(?:ret|result|err|error|rc|status|iErr|return_value)\s*=\s*(?:dpSet|dpGet|dpQuery|dpConnect)\b", ctx.analysis_code)
        )
        if has_try_catch or has_get_last_error or has_return_check:
            return []
        absolute_line = self._line_from_offset(ctx.analysis_code, first_dp_call.start(), base_line=ctx.base_line)
        return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, ctx.static_message, ctx.analysis_code, ctx.event_name)]

    def _composite_complexity(self, ctx: CompositeRuleContext) -> List[Dict]:
        findings: List[Dict] = []
        max_code_length = int(ctx.detector.get("max_code_length", 100000) or 100000)
        if len(ctx.analysis_code) > max_code_length:
            return []
        lines = ctx.analysis_code.split("\n")
        anchor_local = self._first_function_line(ctx.analysis_code)
        max_lines = int(ctx.detector.get("max_lines", 500) or 500)
        if len(lines) > max_lines:
            findings.append(self._build_p1_issue(
                str(ctx.detector.get("line_rule_id", "COMP-01")),
                str(ctx.detector.get("line_rule_item", ctx.rule_item or "불필요한 코드 지양")),
                str(ctx.detector.get("line_severity", "Medium")),
                ctx.base_line + anchor_local - 1,
                str(ctx.detector.get("line_message_prefix", "함수 길이 과다")) + f" ({len(lines)} lines).",
                ctx.analysis_code, ctx.event_name,
            ))
        depth = 0
        max_depth = 0
        max_scan_lines = int(ctx.detector.get("max_scan_lines", 2000) or 2000)
        for line in lines[:max_scan_lines]:
            depth += line.count("{")
            depth -= line.count("}")
            max_depth = max(max_depth, depth)
        depth_threshold = int(ctx.detector.get("max_depth", 10) or 10)
        if max_depth > depth_threshold:
            findings.append(self._build_p1_issue(
                str(ctx.detector.get("depth_rule_id", "COMP-02")),
                str(ctx.detector.get("depth_rule_item", ctx.rule_item or "불필요한 코드 지양")),
                str(ctx.detector.get("depth_severity", "Medium")),
                ctx.base_line + anchor_local - 1,
                str(ctx.detector.get("depth_message_prefix", "제어문 중첩 과다")) + f" (Max depth: {max_depth}).",
                ctx.analysis_code, ctx.event_name,
            ))
        return findings

    def _composite_unused_variables(self, ctx: CompositeRuleContext) -> List[Dict]:
        max_code_length = int(ctx.detector.get("max_code_length", 100000) or 100000)
        if len(ctx.analysis_code) > max_code_length:
            return []
        clean_code = self._remove_comments(ctx.analysis_code)
        all_words = re.findall(r"\b\w+\b", clean_code)
        word_counts = Counter(all_words)
        exception_prefixes = tuple(ctx.detector.get("exception_prefixes", ["param_", "cfg_", "g_", "manager_", "query_", "Script", "is_", "thread_", "dp_"]))
        exception_vars = set(ctx.detector.get("exception_vars", ["return_value", "i", "j", "k", "idx", "cnt", "count", "len", "size", "ret", "result", "success", "ok", "error", "err"]))
        decl_pattern = str(ctx.detector.get("declaration_pattern", r"(?<!const\s)\b(int|float|string|bool|dyn_\w+|mapping|time|void|blob|anytype)\s+([a-zA-Z0-9_]+)\s*(=|;)"))
        string_usage_pattern_template = str(ctx.detector.get("string_usage_template", r'"[^"]*{name}[^"]*"'))
        usage_threshold = int(ctx.detector.get("usage_threshold", 1) or 1)
        out_rule_id = str(ctx.rule_def.get("rule_id", ctx.detector.get("rule_id", "UNUSED-01")) or "UNUSED-01")
        out_item = str(ctx.rule_def.get("item", ctx.detector.get("rule_item", "불필요한 코드 지양")) or "불필요한 코드 지양")
        out_severity = str(ctx.detector.get("severity", "Low") or "Low")
        msg_prefix = str(ctx.detector.get("message_prefix", "미사용 변수 감지") or "미사용 변수 감지")
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
                findings.append(self._build_p1_issue(out_rule_id, out_item, out_severity, ctx.base_line + declared_vars[var_name] - 1, f"{msg_prefix}: '{var_name}'", ctx.analysis_code, ctx.event_name))
        return findings

    def _composite_event_exchange_minimization(self, ctx: CompositeRuleContext) -> List[Dict]:
        func_defs = {}
        for func_match in _FUNCTION_DEF_PATTERN.finditer(ctx.analysis_code):
            name = func_match.group(1)
            brace_idx = ctx.analysis_code.find("{", func_match.start())
            if brace_idx < 0:
                continue
            close_brace = self._find_matching_delimiter(ctx.analysis_code, brace_idx, "{", "}")
            if close_brace < 0:
                continue
            func_defs[name] = ctx.analysis_code[brace_idx:close_brace + 1]
        excluded_calls = {"if", "for", "while", "switch", "return", "catch", "try", "dpSet", "dpSetWait", "dpSetTimed", "dpGet", "dpQuery", "writeLog", "DebugN", "dynlen", "mappinglen"}

        def _body_has_unsafe_dpset(body: str, depth: int, seen: set) -> bool:
            if re.search(r"\bdpSet\s*\(", body):
                if not re.search(r"\bdpSet(?:Wait|Timed)\s*\(", body) and not re.search(r"\bif\s*\([^\)]*(?:\bchanged\b|\bdelta\b|\bold\b|\bprev\b)[^\)]*\)", body, re.IGNORECASE):
                    return True
            if depth <= 0:
                return False
            called_names = [token for token in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", body) if token not in excluded_calls]
            for called_name in called_names:
                if called_name in seen:
                    continue
                callee_body = func_defs.get(called_name, "")
                if not callee_body:
                    continue
                if _body_has_unsafe_dpset(callee_body, depth - 1, seen | {called_name}):
                    return True
            return False

        for loop_match in _LOOP_BLOCK_PATTERN.finditer(ctx.analysis_code):
            brace_idx = ctx.analysis_code.find("{", loop_match.start())
            if brace_idx < 0:
                continue
            close_brace = self._find_matching_delimiter(ctx.analysis_code, brace_idx, "{", "}")
            if close_brace < 0:
                continue
            block = ctx.analysis_code[brace_idx:close_brace + 1]
            dpset_matches = list(re.finditer(r"\bdpSet\s*\(", block))
            indirect_dpset_call = ""
            if len(dpset_matches) < 1:
                called_names = [token for token in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", block) if token not in excluded_calls]
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
            merged_match = re.search(r'\bdpSet\s*\(\s*\"[^\"]+\"\s*,\s*[^,]+,\s*\"[^\"]+\"\s*,', block)
            if merged_match:
                continue
            absolute_line = self._line_from_offset(ctx.analysis_code, loop_match.start(), base_line=ctx.base_line)
            message = (
                f"루프 내 호출 함수({indirect_dpset_call})에서 dpSet 수행 감지: 변경 가드/배치 처리(dpSetWait, dpSetTimed) 권장."
                if indirect_dpset_call
                else (ctx.static_message or "루프 내 dpSet 호출 감지: 변경 가드/배치 처리(dpSetWait, dpSetTimed) 권장.")
            )
            return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, message, ctx.analysis_code, ctx.event_name)]
        return []

    def _composite_coding_standards_advanced(self, ctx: CompositeRuleContext) -> List[Dict]:
        lines = ctx.analysis_code.splitlines()
        pending_start_line = 0
        for line_no, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
                continue
            if pending_start_line:
                if ";" in stripped:
                    pending_start_line = 0
                    continue
                if _CONTROL_PATTERN.match(stripped) or stripped.endswith("{") or stripped.endswith("}"):
                    absolute_line = ctx.base_line + pending_start_line - 1
                    message = f"L{pending_start_line}: 변수 선언 시 세미콜론(;) 누락 가능성."
                    return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, message, ctx.analysis_code, ctx.event_name)]
                continue
            if not _DECL_START_PATTERN.match(stripped):
                continue
            if stripped.endswith(";"):
                continue
            if "(" in stripped and ")" in stripped:
                continue
            pending_start_line = line_no
        if pending_start_line:
            absolute_line = ctx.base_line + pending_start_line - 1
            message = f"L{pending_start_line}: 변수 선언 시 세미콜론(;) 누락 가능성."
            return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, message, ctx.analysis_code, ctx.event_name)]
        return []

    def _composite_memory_leaks_advanced(self, ctx: CompositeRuleContext) -> List[Dict]:
        decl_pattern = str(ctx.detector.get("declaration_pattern", r"\bdyn_\w+\s+[a-zA-Z_][a-zA-Z0-9_]*"))
        cleanup_pattern = str(ctx.detector.get("cleanup_pattern", r"\bdyn(?:Clear|Remove)\s*\("))
        loop_dyn_ops_pattern = str(ctx.detector.get("loop_dyn_ops_pattern", r"\b(?:while|for)\s*\([^\)]*\)\s*\{[\s\S]{0,1200}\bdyn(?:Append|Insert|MapInsert)\s*\("))
        declarations = [(idx, line) for idx, line in enumerate(ctx.analysis_code.splitlines(), 1) if re.search(decl_pattern, line)]
        if not declarations:
            return []
        if re.search(cleanup_pattern, ctx.analysis_code):
            return []
        if not re.search(loop_dyn_ops_pattern, ctx.analysis_code, re.IGNORECASE):
            return []
        absolute_line = ctx.base_line + declarations[0][0] - 1
        return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, ctx.static_message, ctx.analysis_code, ctx.event_name)]

    def _composite_ui_block_initialize_delay(self, ctx: CompositeRuleContext) -> List[Dict]:
        event_equals = str(ctx.detector.get("event_equals", "Initialize") or "Initialize")
        needle = str(ctx.detector.get("contains", "delay(") or "delay(")
        if ctx.event_name == event_equals and needle in ctx.analysis_code and ctx.rule_id and ctx.rule_item and ctx.static_message:
            ui_line = ctx.base_line + ctx.anchor_line - 1
            return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, ui_line, ctx.static_message, ctx.analysis_code, ctx.event_name)]
        return []

    def _composite_style_indent_mixed(self, ctx: CompositeRuleContext) -> List[Dict]:
        saw_tab_indent = False
        saw_space_indent = False
        mixed_line = 0
        for idx, line in enumerate(ctx.analysis_code.splitlines(), 1):
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
            absolute_line = ctx.base_line + ((mixed_line or 1) - 1)
            return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, ctx.static_message, ctx.analysis_code, ctx.event_name)]
        return []

    def _composite_magic_index_usage(self, ctx: CompositeRuleContext) -> List[Dict]:
        if re.search(r"\bIDX_[A-Z0-9_]+\b", ctx.analysis_code):
            return []
        matches = list(re.finditer(r"\b(?:parts|data|tokens|fields)\s*\[\s*([2-9]|\d{2,})\s*\]", ctx.analysis_code))
        if len(matches) < int(ctx.detector.get("min_matches", 3) or 3):
            return []
        absolute_line = self._line_from_offset(ctx.analysis_code, matches[0].start(), base_line=ctx.base_line)
        return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, ctx.static_message, ctx.analysis_code, ctx.event_name)]

    def _composite_float_literal_hardcoding(self, ctx: CompositeRuleContext) -> List[Dict]:
        hit_lines = []
        literals = ctx.detector.get("literals", ["0.01", "0.001"])
        if isinstance(literals, str):
            literals = [literals]
        literal_patterns = [re.escape(str(x)) for x in literals if str(x)]
        if not literal_patterns:
            literal_patterns = [r"0\.0*1", r"0\.001"]
        pattern = r"\b(?:" + "|".join(literal_patterns) + r")\b"
        for idx, line in enumerate(ctx.analysis_code.splitlines(), 1):
            if re.search(r"^\s*const\b", line):
                continue
            if re.search(pattern, line):
                hit_lines.append(idx)
        if len(hit_lines) >= int(ctx.detector.get("min_hits", 2) or 2):
            absolute_line = ctx.base_line + hit_lines[0] - 1
            return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, ctx.static_message, ctx.analysis_code, ctx.event_name)]
        return []

    def _composite_hardcoding_extended(self, ctx: CompositeRuleContext) -> List[Dict]:
        lines = ctx.analysis_code.splitlines()
        dp_path_hits = []
        dp_path_pattern = str(ctx.detector.get("dp_path_pattern", r'"([A-Za-z0-9_]+\.[A-Za-z0-9_\.]+)"'))
        for idx, line in enumerate(lines, 1):
            if re.search(r"^\s*const\b", line):
                continue
            for match in re.finditer(dp_path_pattern, line):
                val = match.group(1)
                if val.count(".") >= int(ctx.detector.get("dp_min_dots", 2) or 2):
                    dp_path_hits.append((idx, val))
        dp_counter = Counter([value for _, value in dp_path_hits])
        repeated_dp = [value for value, count in dp_counter.items() if count >= int(ctx.detector.get("dp_repeat_threshold", 2) or 2)]
        if repeated_dp:
            local_line = next((ln for ln, value in dp_path_hits if value == repeated_dp[0]), 1)
            absolute_line = ctx.base_line + local_line - 1
            msg = f"고정 DP 경로 문자열 반복 사용 감지: '{repeated_dp[0]}'."
            return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, msg, ctx.analysis_code, ctx.event_name)]
        number_hits = []
        ignored_numbers = set(str(x) for x in ctx.detector.get("ignore_numbers", ["10", "60", "100"]))
        for idx, line in enumerate(lines, 1):
            if re.search(r"^\s*const\b", line):
                continue
            for match in re.finditer(r"\b\d{2,}\b", line):
                value = match.group(0)
                if value in ignored_numbers:
                    continue
                number_hits.append((idx, value))
        num_counter = Counter([value for _, value in number_hits])
        repeated_num = [value for value, count in num_counter.items() if count >= int(ctx.detector.get("number_repeat_threshold", 3) or 3)]
        if repeated_num:
            local_line = next((ln for ln, value in number_hits if value == repeated_num[0]), 1)
            absolute_line = ctx.base_line + local_line - 1
            msg = f"매직 넘버 반복 사용 감지: '{repeated_num[0]}'."
            return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, msg, ctx.analysis_code, ctx.event_name)]
        return []

    def _composite_dead_code(self, ctx: CompositeRuleContext) -> List[Dict]:
        detect_if_false = bool(ctx.detector.get("detect_if_false", True))
        detect_after_return = bool(ctx.detector.get("detect_after_return", True))
        if detect_if_false:
            false_if = re.search(r"\bif\s*\(\s*false\s*\)", ctx.analysis_code, re.IGNORECASE)
            if false_if:
                absolute_line = self._line_from_offset(ctx.analysis_code, false_if.start(), base_line=ctx.base_line)
                msg = ctx.static_message or "영구 미실행 분기(if(false)) 감지."
                return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, msg, ctx.analysis_code, ctx.event_name)]
        if not detect_after_return:
            return []
        lines = ctx.analysis_code.splitlines()
        line_depths = []
        depth = 0
        for line in lines:
            line_depths.append(depth)
            depth += line.count("{")
            depth -= line.count("}")
        lookahead_limit = int(ctx.detector.get("return_lookahead_lines", 20) or 20)
        for idx, line in enumerate(lines, 1):
            if re.search(r"\breturn\b[^;]*;", line):
                return_depth = line_depths[idx - 1]
                for look_ahead in range(idx, min(len(lines), idx + lookahead_limit)):
                    if line_depths[look_ahead] < return_depth:
                        break
                    nxt = lines[look_ahead].strip()
                    if not nxt or nxt.startswith("//") or nxt == "}":
                        continue
                    absolute_line = ctx.base_line + idx - 1
                    msg = ctx.detector.get("return_after_message") or "return 이후 도달 불가능 코드 가능성 감지."
                    return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, str(msg), ctx.analysis_code, ctx.event_name)]
        return []

    def _composite_while_delay_policy(self, ctx: CompositeRuleContext) -> List[Dict]:
        for match in re.finditer(r"\bwhile\s*\(", ctx.analysis_code):
            open_paren = ctx.analysis_code.find("(", match.start())
            if open_paren < 0:
                continue
            close_paren = self._find_matching_delimiter(ctx.analysis_code, open_paren, "(", ")")
            if close_paren < 0:
                continue
            open_brace = ctx.analysis_code.find("{", close_paren)
            if open_brace < 0:
                continue
            close_brace = self._find_matching_delimiter(ctx.analysis_code, open_brace, "{", "}")
            if close_brace < 0:
                continue
            loop_block = ctx.analysis_code[open_brace:close_brace + 1]
            has_delay = bool(re.search(r"\b(?:delay|dpSetWait|dpSetTimed)\s*\(", loop_block))
            if has_delay:
                continue
            absolute_line = self._line_from_offset(ctx.analysis_code, match.start(), base_line=ctx.base_line)
            return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, ctx.static_message, ctx.analysis_code, ctx.event_name)]
        return []

    def _composite_while_delay_outside_active(self, ctx: CompositeRuleContext) -> List[Dict]:
        active_guard_pattern = str(ctx.detector.get("active_guard_pattern", r"\b(?:isActive|isScriptActive|active|enabled?|bActive|runFlag|useFlag)\b"))
        delay_pattern = str(ctx.detector.get("delay_pattern", r"\b(?:delay|dpSetWait|dpSetTimed)\s*\("))
        for match in re.finditer(r"\bwhile\s*\(", ctx.analysis_code, re.IGNORECASE):
            open_paren = ctx.analysis_code.find("(", match.start())
            if open_paren < 0:
                continue
            close_paren = self._find_matching_delimiter(ctx.analysis_code, open_paren, "(", ")")
            if close_paren < 0:
                continue
            open_brace = ctx.analysis_code.find("{", close_paren)
            if open_brace < 0:
                continue
            close_brace = self._find_matching_delimiter(ctx.analysis_code, open_brace, "{", "}")
            if close_brace < 0:
                continue
            loop_block = ctx.analysis_code[open_brace:close_brace + 1]
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
                cond_text = loop_block[cond_open + 1:cond_close]
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
            absolute_line = self._line_from_offset(ctx.analysis_code, first_delay_abs, base_line=ctx.base_line)
            return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, ctx.static_message, ctx.analysis_code, ctx.event_name)]
        return []

    def _composite_config_format_consistency(self, ctx: CompositeRuleContext) -> List[Dict]:
        if not self._has_config_context(ctx.analysis_code):
            return []
        if "strsplit" not in ctx.analysis_code:
            return []
        delimiters = set(re.findall(r'\bstrsplit\s*\([^,]+,\s*\"([^\"]+)\"\s*\)', ctx.analysis_code))
        if len(delimiters) >= int(ctx.detector.get("delimiter_mismatch_threshold", 2) or 2):
            pos = ctx.analysis_code.find("strsplit")
            absolute_line = self._line_from_offset(ctx.analysis_code, pos, base_line=ctx.base_line)
            return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, ctx.static_message, ctx.analysis_code, ctx.event_name)]
        access_match = re.search(r"\b(?:parts|tokens|fields)\s*\[\s*\d+\s*\]", ctx.analysis_code)
        has_parts_access = bool(access_match)
        has_len_check = bool(re.search(r"\b(?:dynlen|len)\s*\(\s*(?:parts|tokens|fields)\s*\)\s*(?:<|<=|>|>=|==|!=)\s*\d+", ctx.analysis_code))
        if has_parts_access and not has_len_check:
            absolute_line = self._line_from_offset(ctx.analysis_code, access_match.start(), base_line=ctx.base_line)
            return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, ctx.static_message, ctx.analysis_code, ctx.event_name)]
        return []

    def _composite_config_error_contract(self, ctx: CompositeRuleContext) -> List[Dict]:
        if not self._has_config_context(ctx.analysis_code):
            return []
        has_parse_guard = bool(re.search(r"\bif\s*\(\s*(?:dynlen|len)\s*\(\s*(?:parts|tokens|fields)\s*\)\s*(?:<|<=)\s*\d+\s*\)", ctx.analysis_code, re.IGNORECASE))
        if not has_parse_guard:
            return []
        has_continue = "continue;" in ctx.analysis_code
        has_fail_return = bool(re.search(r"\breturn\s+(?:false|-1)\s*;", ctx.analysis_code, re.IGNORECASE))
        if has_continue and not has_fail_return:
            absolute_line = self._line_from_offset(ctx.analysis_code, ctx.analysis_code.find("continue;"), base_line=ctx.base_line)
            return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, ctx.static_message, ctx.analysis_code, ctx.event_name)]
        return []

    def _composite_try_catch_for_risky_ops(self, ctx: CompositeRuleContext) -> List[Dict]:
        risky_iter = list(re.finditer(r"\b(dpSet|dpGet|dpQuery|fopen|fileOpen|strsplit)\s*\(", ctx.analysis_code))
        if not risky_iter:
            return []
        risky_match = risky_iter[0]
        if re.search(r"\btry\b", ctx.analysis_code, re.IGNORECASE) and re.search(r"\bcatch\b", ctx.analysis_code, re.IGNORECASE):
            return []
        if re.search(r"\bgetLastError\s*\(", ctx.analysis_code, re.IGNORECASE):
            return []
        if re.search(r"\breturn\s+(false|-1)\s*;", ctx.analysis_code, re.IGNORECASE):
            return []
        if re.search(r"\b(writeLog|DebugN|DebugTN)\s*\([^)]*(err|error|fail|getLastError)[^)]*\)", ctx.analysis_code, re.IGNORECASE):
            return []
        if re.search(r"\bif\s*\([^)]*(err|error|rc|ret|result|status)[^)]*\)", ctx.analysis_code, re.IGNORECASE):
            return []
        loop_ranges = self._collect_loop_line_ranges(ctx.analysis_code)
        risky_line_local = self._line_from_offset(ctx.analysis_code, risky_match.start(), base_line=1)
        in_loop = any(start <= risky_line_local <= end for start, end in loop_ranges)
        has_parse_contract = bool(re.search(r"\bdynlen\s*\(\s*(parts|tokens|fields)\s*\)\s*(<|<=)\s*\d+", ctx.analysis_code, re.IGNORECASE))
        if not (len(risky_iter) >= 2 or in_loop or has_parse_contract):
            return []
        absolute_line = ctx.base_line + risky_line_local - 1
        return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, ctx.static_message, ctx.analysis_code, ctx.event_name)]

    def _composite_division_zero_guard(self, ctx: CompositeRuleContext) -> List[Dict]:
        if not self._has_config_context(ctx.analysis_code):
            return []
        lines = ctx.analysis_code.splitlines()
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
                    ctx_line = lines[lookback - 1]
                    for denom in denom_vars:
                        has_non_zero_guard = bool(
                            re.search(rf"\b{re.escape(denom)}\b\s*!=\s*0", ctx_line)
                            or re.search(rf"\b{re.escape(denom)}\b\s*(>|>=)\s*1", ctx_line)
                            or re.search(rf"\b{re.escape(denom)}\b\s*(<=|==)\s*0", ctx_line)
                        )
                        has_if_guard = bool(re.search(rf"\bif\s*\([^)]*\b{re.escape(denom)}\b[^)]*\)", ctx_line))
                        if has_non_zero_guard and has_if_guard:
                            guard_found = True
                            break
                        if has_if_guard and re.search(r"\b(return|continue|break)\b", "\n".join(lines[lookback - 1:min(len(lines), lookback + 2)])):
                            guard_found = True
                            break
                    if guard_found:
                        break
                if guard_found:
                    continue
                absolute_line = ctx.base_line + idx - 1
                return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, ctx.static_message, ctx.analysis_code, ctx.event_name)]
        return []

    def _composite_manual_aggregation_pattern(self, ctx: CompositeRuleContext) -> List[Dict]:
        for match in re.finditer(r"\b(?:while|for)\s*\([^\)]*\)\s*\{", ctx.analysis_code, re.IGNORECASE):
            open_brace = ctx.analysis_code.find("{", match.start())
            if open_brace < 0:
                continue
            close_brace = self._find_matching_delimiter(ctx.analysis_code, open_brace, "{", "}")
            if close_brace < 0:
                continue
            block = ctx.analysis_code[open_brace:close_brace + 1]
            has_manual_agg = bool(re.search(r"\b(sum|total)\s*\+=", block) and re.search(r"\b(count|cnt)\s*(\+\+|\+=\s*1)", block))
            if not has_manual_agg:
                continue
            if re.search(r"\b(dynSum|dynAvg|avg|average)\s*\(", block):
                continue
            absolute_line = self._line_from_offset(ctx.analysis_code, match.start(), base_line=ctx.base_line)
            return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, ctx.static_message, ctx.analysis_code, ctx.event_name)]
        return []

    def _composite_consecutive_dpset(self, ctx: CompositeRuleContext) -> List[Dict]:
        lines = ctx.analysis_code.splitlines()
        loop_ranges = self._collect_loop_line_ranges(ctx.analysis_code)

        def _in_loop(line_no: int) -> bool:
            for start, end in loop_ranges:
                if start <= line_no <= end:
                    return True
            return False

        dpset_lines = [idx for idx, line in enumerate(lines) if re.search(r"\bdpSet\s*\(", line) and not _in_loop(idx + 1)]
        if len(dpset_lines) < 2:
            return []
        max_gap = int(ctx.detector.get("max_gap_lines", 4) or 4)
        findings = []
        cluster = [dpset_lines[0]]

        def _emit_cluster(cluster_lines: List[int]) -> None:
            if len(cluster_lines) < 2:
                return
            start = cluster_lines[0]
            end = cluster_lines[-1]
            window = "\n".join(lines[start:end + 1])
            has_better_pattern = bool(
                re.search(r"\bdpSet(?:Wait|Timed)\s*\(", window)
                or re.search(r"\bif\s*\([^\)]*(?:\bchanged\b|\bdelta\b|\bold\b|\bprev\b)[^\)]*\)", window, re.IGNORECASE)
                or re.search(r"\bdpSetWait\s*\(", ctx.analysis_code)
            )
            if has_better_pattern:
                return
            findings.append(self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, ctx.base_line + start, ctx.static_message, ctx.analysis_code, ctx.event_name))

        for line_idx in dpset_lines[1:]:
            if line_idx - cluster[-1] <= max_gap:
                cluster.append(line_idx)
                continue
            _emit_cluster(cluster)
            cluster = [line_idx]
        _emit_cluster(cluster)
        return findings

    def _composite_input_validation(self, ctx: CompositeRuleContext) -> List[Dict]:
        anchor_local = self._first_function_line(ctx.analysis_code)
        first_input_line = 0
        for idx, line in enumerate(ctx.analysis_code.splitlines(), 1):
            if "dpGet" in line or "dpConnect" in line:
                first_input_line = idx
                break
        has_input = first_input_line > 0
        has_validation = bool(re.search(r"\b(?:strlen|atoi|atof|isDigit|strIsDigit)\s*\(", ctx.analysis_code))
        if has_input and not has_validation:
            absolute_line = ctx.base_line + ((first_input_line or anchor_local) - 1)
            return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, ctx.static_message, ctx.analysis_code, ctx.event_name)]
        return []

    def _composite_style_name_rules(self, ctx: CompositeRuleContext) -> List[Dict]:
        lines = ctx.analysis_code.splitlines()
        function_start = len(lines) + 1
        for idx, line in enumerate(lines, 1):
            stripped = line.strip()
            if _FUNCTION_START_PATTERN.match(stripped) or _MAIN_FUNCTION_PATTERN.match(stripped):
                function_start = idx
                break
        for idx, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue
            m = _STYLE_DECL_PATTERN.match(stripped)
            if not m:
                continue
            is_const = bool(m.group(1))
            name = m.group(2)
            is_global = idx < function_start
            if is_const and not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
                msg = f"상수 명명 규칙 위반 가능성: '{name}' (UPPER_SNAKE 권장)."
                return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, ctx.base_line + idx - 1, msg, ctx.analysis_code, ctx.event_name)]
            if is_global and not is_const and not name.startswith("g_"):
                msg = f"전역 변수 명명 규칙 위반 가능성: '{name}' (g_ 접두사 권장)."
                return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, ctx.base_line + idx - 1, msg, ctx.analysis_code, ctx.event_name)]
            if re.search(r"(cfg|config)", name, re.IGNORECASE) and not name.startswith("cfg_"):
                msg = f"설정 변수 명명 규칙 위반 가능성: '{name}' (cfg_ 접두사 권장)."
                return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, ctx.base_line + idx - 1, msg, ctx.analysis_code, ctx.event_name)]
        return []

    def _composite_style_header_rules(self, ctx: CompositeRuleContext) -> List[Dict]:
        lines = ctx.code.splitlines()
        for idx, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("/*"):
                continue
            if not _STYLE_FUNCTION_PATTERN.match(stripped) and not _MAIN_FUNCTION_PATTERN.match(stripped):
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
            if comment_hits >= int(ctx.detector.get("min_comment_hits", 2) or 2):
                continue
            return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, ctx.base_line + idx - 1, ctx.static_message, ctx.analysis_code, ctx.event_name)]
        return []

    def _composite_dpset_timed_context(self, ctx: CompositeRuleContext) -> List[Dict]:
        lines = ctx.analysis_code.splitlines()
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
            has_delta_guard = bool(re.search(r"\bif\s*\([^\)]*(?:!=|\bchanged\b|\bdelta\b|\bold\b|\bprev\b)[^\)]*\)", window_text, re.IGNORECASE))
            if has_timed or has_delta_guard:
                continue
            return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, idx, ctx.static_message, ctx.analysis_code, ctx.event_name)]
        return []

    def _composite_dpget_batch_optimization(self, ctx: CompositeRuleContext) -> List[Dict]:
        min_count = int(ctx.detector.get("min_count", 2) or 2)
        findings = []
        seen_lines = set()
        loop_ranges = self._collect_loop_line_ranges(ctx.analysis_code)

        def _in_loop(line_no: int) -> bool:
            for start, end in loop_ranges:
                if start <= line_no <= end:
                    return True
            return False

        for match in re.finditer(r"\b(?:while|for)\s*\([^\)]*\)\s*\{", ctx.analysis_code, re.IGNORECASE):
            open_brace = ctx.analysis_code.find("{", match.start())
            if open_brace < 0:
                continue
            close_brace = self._find_matching_delimiter(ctx.analysis_code, open_brace, "{", "}")
            if close_brace < 0:
                continue
            block = ctx.analysis_code[open_brace:close_brace + 1]
            dpget_count = len(re.findall(r"\bdpGet\s*\(", block))
            if dpget_count < min_count:
                continue
            has_cache = bool(re.search(r"\b(mappingHasKey|cache|memo|lookup)\b", block, re.IGNORECASE))
            if has_cache:
                continue
            absolute_line = self._line_from_offset(ctx.analysis_code, match.start(), base_line=ctx.base_line)
            if absolute_line in seen_lines:
                continue
            seen_lines.add(absolute_line)
            findings.append(self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, ctx.static_message, ctx.analysis_code, ctx.event_name))

        lines = ctx.analysis_code.splitlines()
        dpget_lines = [idx for idx, line in enumerate(lines, 1) if re.search(r"\bdpGet\s*\(", line) and not _in_loop(idx)]
        if len(dpget_lines) < min_count:
            return findings
        max_gap = int(ctx.detector.get("max_gap_lines", 8) or 8)
        cluster = [dpget_lines[0]]

        def _emit_cluster(cluster_lines: List[int]) -> None:
            if len(cluster_lines) < min_count:
                return
            start_line = cluster_lines[0]
            end_line = cluster_lines[-1]
            block = "\n".join(lines[max(0, start_line - 2):min(len(lines), end_line + 1)])
            if re.search(r"\b(mappingHasKey|cache|memo|lookup)\b", block, re.IGNORECASE):
                return
            absolute_line = ctx.base_line + start_line - 1
            if absolute_line in seen_lines:
                return
            seen_lines.add(absolute_line)
            findings.append(self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, ctx.static_message, ctx.analysis_code, ctx.event_name))

        for line_no in dpget_lines[1:]:
            if line_no - cluster[-1] <= max_gap:
                cluster.append(line_no)
                continue
            _emit_cluster(cluster)
            cluster = [line_no]
        _emit_cluster(cluster)
        return findings

    def _composite_dpset_batch_optimization(self, ctx: CompositeRuleContext) -> List[Dict]:
        findings = []
        seen_lines = set()
        for match in re.finditer(r"\b(?:while|for)\s*\([^\)]*\)\s*\{", ctx.analysis_code, re.IGNORECASE):
            open_brace = ctx.analysis_code.find("{", match.start())
            if open_brace < 0:
                continue
            close_brace = self._find_matching_delimiter(ctx.analysis_code, open_brace, "{", "}")
            if close_brace < 0:
                continue
            block = ctx.analysis_code[open_brace:close_brace + 1]
            dpset_count = len(re.findall(r"\bdpSet\s*\(", block))
            if dpset_count < int(ctx.detector.get("min_count", 2) or 2):
                continue
            has_batch_hint = bool(re.search(r"\b(dpSetWait|dpSetTimed|batch|group)\b", block, re.IGNORECASE))
            has_guard = bool(re.search(r"(!=|changed|old|prev)", block, re.IGNORECASE))
            if has_batch_hint or has_guard:
                continue
            absolute_line = self._line_from_offset(ctx.analysis_code, match.start(), base_line=ctx.base_line)
            if absolute_line in seen_lines:
                continue
            seen_lines.add(absolute_line)
            findings.append(self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, ctx.static_message, ctx.analysis_code, ctx.event_name))
        return findings

    def _composite_setvalue_batch_optimization(self, ctx: CompositeRuleContext) -> List[Dict]:
        findings = []
        seen_lines = set()
        for match in re.finditer(r"\b(?:while|for)\s*\([^\)]*\)\s*\{", ctx.analysis_code, re.IGNORECASE):
            open_brace = ctx.analysis_code.find("{", match.start())
            if open_brace < 0:
                continue
            close_brace = self._find_matching_delimiter(ctx.analysis_code, open_brace, "{", "}")
            if close_brace < 0:
                continue
            block = ctx.analysis_code[open_brace:close_brace + 1]
            setvalue_count = len(re.findall(r"\bsetValue\s*\(", block))
            if setvalue_count < int(ctx.detector.get("min_count", 2) or 2):
                continue
            if re.search(r"\bsetMultiValue\s*\(", block, re.IGNORECASE):
                continue
            absolute_line = self._line_from_offset(ctx.analysis_code, match.start(), base_line=ctx.base_line)
            if absolute_line in seen_lines:
                continue
            seen_lines.add(absolute_line)
            findings.append(self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, ctx.static_message, ctx.analysis_code, ctx.event_name))
        return findings

    def _composite_setmultivalue_adoption(self, ctx: CompositeRuleContext) -> List[Dict]:
        lines = ctx.analysis_code.splitlines()
        setvalue_lines = [idx for idx, line in enumerate(lines, 1) if re.search(r"\bsetValue\s*\(", line)]
        min_count = int(ctx.detector.get("min_count", 2) or 2)
        if len(setvalue_lines) < min_count:
            return []
        max_gap = int(ctx.detector.get("max_gap_lines", 6) or 6)
        findings = []
        cluster = [setvalue_lines[0]]

        def _emit_setvalue_cluster(cluster_lines: List[int]) -> None:
            if len(cluster_lines) < min_count:
                return
            start_line = cluster_lines[0]
            end_line = cluster_lines[-1]
            window_start = max(1, start_line - 1)
            window_end = min(len(lines), end_line + 2)
            block = "\n".join(lines[window_start - 1:window_end])
            if re.search(r"\bsetMultiValue\s*\(", block, re.IGNORECASE):
                return
            findings.append(self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, ctx.base_line + start_line - 1, ctx.static_message, ctx.analysis_code, ctx.event_name))

        for line_no in setvalue_lines[1:]:
            if line_no - cluster[-1] <= max_gap:
                cluster.append(line_no)
                continue
            _emit_setvalue_cluster(cluster)
            cluster = [line_no]
        _emit_setvalue_cluster(cluster)
        return findings

    def _composite_getmultivalue_adoption(self, ctx: CompositeRuleContext) -> List[Dict]:
        lines = ctx.analysis_code.splitlines()
        getvalue_lines = [idx for idx, line in enumerate(lines, 1) if re.search(r"\bgetValue\s*\(", line)]
        min_count = int(ctx.detector.get("min_count", 2) or 2)
        if len(getvalue_lines) < min_count:
            return []
        max_gap = int(ctx.detector.get("max_gap_lines", 6) or 6)
        findings = []
        cluster = [getvalue_lines[0]]

        def _emit_getvalue_cluster(cluster_lines: List[int]) -> None:
            if len(cluster_lines) < min_count:
                return
            start_line = cluster_lines[0]
            end_line = cluster_lines[-1]
            window_start = max(1, start_line - 1)
            window_end = min(len(lines), end_line + 2)
            block = "\n".join(lines[window_start - 1:window_end])
            if re.search(r"\bgetMultiValue\s*\(", block, re.IGNORECASE):
                return
            if re.search(r"\b(cache|mappingHasKey|memo|lookup)\b", block, re.IGNORECASE):
                return
            findings.append(self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, ctx.base_line + start_line - 1, ctx.static_message, ctx.analysis_code, ctx.event_name))

        for line_no in getvalue_lines[1:]:
            if line_no - cluster[-1] <= max_gap:
                cluster.append(line_no)
                continue
            _emit_getvalue_cluster(cluster)
            cluster = [line_no]
        _emit_getvalue_cluster(cluster)
        return findings

    def _composite_getvalue_batch_optimization(self, ctx: CompositeRuleContext) -> List[Dict]:
        findings = []
        seen_lines = set()
        for match in re.finditer(r"\b(?:while|for)\s*\([^\)]*\)\s*\{", ctx.analysis_code, re.IGNORECASE):
            open_brace = ctx.analysis_code.find("{", match.start())
            if open_brace < 0:
                continue
            close_brace = self._find_matching_delimiter(ctx.analysis_code, open_brace, "{", "}")
            if close_brace < 0:
                continue
            block = ctx.analysis_code[open_brace:close_brace + 1]
            getvalue_count = len(re.findall(r"\bgetValue\s*\(", block))
            if getvalue_count < int(ctx.detector.get("min_count", 2) or 2):
                continue
            has_batch_or_cache = bool(re.search(r"\b(getMultiValue|cache|mappingHasKey|memo|lookup|batch)\b", block, re.IGNORECASE))
            if has_batch_or_cache:
                continue
            absolute_line = self._line_from_offset(ctx.analysis_code, match.start(), base_line=ctx.base_line)
            if absolute_line in seen_lines:
                continue
            seen_lines.add(absolute_line)
            findings.append(self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, ctx.static_message, ctx.analysis_code, ctx.event_name))
        return findings

    def _composite_debug_logging_presence(self, ctx: CompositeRuleContext) -> List[Dict]:
        log_pattern = str(ctx.detector.get("log_pattern", r"\b(?:writeLog|DebugN|DebugTN)\s*\("))
        if re.search(log_pattern, ctx.analysis_code, re.IGNORECASE):
            return []
        trigger_pattern = str(ctx.detector.get("trigger_pattern", r"\b(?:catch|getLastError|err(or)?|fail(ed|ure)?)\b"))
        trigger = re.search(trigger_pattern, ctx.analysis_code, re.IGNORECASE)
        if not trigger:
            return []
        trigger_line = self._line_from_offset(ctx.analysis_code, trigger.start(), base_line=1)
        try:
            line_text = ctx.analysis_code.splitlines()[max(0, trigger_line - 1)]
        except Exception:
            line_text = ""
        if line_text.strip().startswith("//"):
            return []
        absolute_line = self._line_from_offset(ctx.analysis_code, trigger.start(), base_line=ctx.base_line)
        return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, ctx.static_message, ctx.analysis_code, ctx.event_name)]

    def _composite_logging_level_policy(self, ctx: CompositeRuleContext) -> List[Dict]:
        trigger_pattern = str(ctx.detector.get("trigger_pattern", r"\b(?:catch|getLastError|err(?:or)?|fail(?:ed|ure)?)\b"))
        trigger = re.search(trigger_pattern, ctx.analysis_code, re.IGNORECASE)
        if not trigger:
            return []
        log_pattern = str(ctx.detector.get("log_pattern", r"\b(?:writeLog|DebugN|DebugTN)\s*\("))
        if not re.search(log_pattern, ctx.analysis_code, re.IGNORECASE):
            return []
        debug_pattern = str(ctx.detector.get("debug_pattern", r"\b(?:DBG1|DBG2|DebugN|DebugTN)\b"))
        if re.search(debug_pattern, ctx.analysis_code, re.IGNORECASE):
            return []
        absolute_line = self._line_from_offset(ctx.analysis_code, trigger.start(), base_line=ctx.base_line)
        return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, ctx.static_message, ctx.analysis_code, ctx.event_name)]

    def _composite_script_active_condition_check(self, ctx: CompositeRuleContext) -> List[Dict]:
        mutating_pattern = str(ctx.detector.get("mutating_pattern", r"\b(?:dpSet(?:Wait|Timed)?|setValue|setMultiValue)\s*\("))
        mutating_call = re.search(mutating_pattern, ctx.analysis_code, re.IGNORECASE)
        if not mutating_call:
            return []
        guard_pattern = str(ctx.detector.get("active_guard_pattern", r"\b(?:isActive|active|enabled?|bActive|runFlag|useFlag)\b"))
        if re.search(guard_pattern, ctx.analysis_code, re.IGNORECASE):
            return []
        absolute_line = self._line_from_offset(ctx.analysis_code, mutating_call.start(), base_line=ctx.base_line)
        return [self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, ctx.static_message, ctx.analysis_code, ctx.event_name)]

    def _composite_duplicate_action_handling(self, ctx: CompositeRuleContext) -> List[Dict]:
        call_pattern = _compile_cached(
            str(ctx.detector.get("call_pattern", r'\b(?P<func>dpSet|setValue)\s*\(\s*\"(?P<target>[^\"]+)\"(?:\s*,\s*\"(?P<attr>[^\"]+)\")?')),
            re.IGNORECASE,
        )
        min_repeat = int(ctx.detector.get("min_repeat", 2) or 2)
        max_gap_lines = int(ctx.detector.get("max_gap_lines", 10) or 10)
        guard_pattern = str(ctx.detector.get("duplicate_guard_pattern", r"\b(?:changed|delta|prev|old|already|once|flag)\b"))
        lines = ctx.analysis_code.splitlines()
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
                block = "\n".join(lines[max(0, start_line - 2):min(len(lines), end_line + 1)])
                if re.search(guard_pattern, block, re.IGNORECASE):
                    return
                absolute_line = ctx.base_line + start_line - 1
                message = ctx.static_message
                if "{target}" in message:
                    message = message.format(target=target)
                candidate_findings.append(self._build_p1_issue(ctx.rule_id, ctx.rule_item, ctx.severity, absolute_line, message, ctx.analysis_code, ctx.event_name))

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
