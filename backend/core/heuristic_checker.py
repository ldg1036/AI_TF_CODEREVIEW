import os
import re
from collections import Counter
from typing import Any, Dict, List, Optional

from core.checker_context_mixin import CheckerContextMixin
from core.checker_detector_runner_mixin import CheckerDetectorRunnerMixin
from core.checker_rule_loader_mixin import CheckerRuleLoaderMixin
from core.rules.composite_rules import CompositeRulesMixin
from core.rules.config_rules import ConfigRulesMixin
from core.rules.performance_rules import PerformanceRulesMixin
from core.rules.quality_rules import QualityRulesMixin
from core.rules.security_rules import SecurityRulesMixin
from core.rules.style_rules import StyleRulesMixin

_WHILE_HEADER_PATTERN = re.compile(r"\bwhile\s*\(")
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


class HeuristicChecker(
    CheckerContextMixin,
    CheckerRuleLoaderMixin,
    CheckerDetectorRunnerMixin,
    CompositeRulesMixin,
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
        self.p1_config_health = self._evaluate_p1_config_health(rules_path)
        self.item_filter_fallback_rule_ids_by_type = self._build_item_filter_fallback_rule_ids_by_type()

    @staticmethod
    def _has_config_context(code: str) -> bool:
        return bool(
            re.search(
                r"\b(config|cfg|ini|json)\b|load_config|config_|cfg_|ini_|json_",
                code,
                re.IGNORECASE,
            )
        )

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

        has_function_signature = function_start <= len(lines)
        generic_global_names = {"name", "path", "file", "data", "temp", "value", "result", "ret", "flag", "count", "idx", "list", "map", "buffer"}
        decl_pattern = re.compile(
            r"^\s*(const\s+)?(?:int|float|string|bool|mapping|time|anytype|dyn_[a-zA-Z0-9_]+)\s+([a-zA-Z_][a-zA-Z0-9_]*)"
        )

        for idx, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue
            if re.match(r"^\s*(?:void|int|float|string|bool|mapping|time|anytype|dyn_[a-zA-Z0-9_]+)\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\(", stripped) or re.match(r"^\s*main\s*\(", stripped):
                continue
            match = decl_pattern.match(stripped)
            if not match:
                continue

            is_const = bool(match.group(1))
            name = match.group(2)
            is_global = idx < function_start

            if is_const and not name.startswith("g_") and not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
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

            if (
                has_function_signature
                and is_global
                and not is_const
                and not name.startswith("g_")
                and (len(name) <= 8 or name.lower() in generic_global_names)
            ):
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

            if (
                re.search(r"(cfg|config)", name, re.IGNORECASE)
                and not name.startswith(("cfg_", "g_"))
                and not re.search(r"(?:_file|_filename|_path|_list)$", name, re.IGNORECASE)
                and re.search(r"\b(?:strsplit|paCfgReadValue|paCfgReadValueList|load_config|config_file|raw_config_list)\b", code, re.IGNORECASE)
            ):
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

    def check_config_format_consistency(self, code: str) -> List[Dict]:
        findings = []
        if not self._has_strong_config_context(code):
            return findings
        if "strsplit" not in code:
            return findings

        split_calls = self._collect_strsplit_calls(code)
        delimiters_by_source: Dict[str, set[str]] = {}
        for source, delimiter in split_calls:
            delimiters_by_source.setdefault(source, set()).add(delimiter)
        if any(len(delimiters) >= 2 for delimiters in delimiters_by_source.values()):
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

    def check_division_zero_guard(self, code: str) -> List[Dict]:
        findings = []
        if not self._has_strong_config_context(code):
            return findings
        lines = code.splitlines()
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

            for match in re.finditer(r"/\s*((?:\([^)]+\)\s*)*[A-Za-z_][A-Za-z0-9_]*|\([^)]+\))", sanitized):
                denom_expr = match.group(1).strip()
                if re.fullmatch(r"\d+(?:\.\d+)?", denom_expr):
                    continue
                denom_vars = [
                    token
                    for token in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", denom_expr)
                    if token.lower() not in {"float", "int", "double", "long", "bool", "string", "time", "mapping", "dyn_anytype", "dyn_float", "dyn_int", "dyn_string"}
                ]
                if not denom_vars:
                    continue
                if self._has_nearby_division_guard(lines, idx, denom_vars):
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

    @staticmethod
    def _dedupe_p1_violations(violations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped: Dict[tuple, Dict[str, Any]] = {}
        for violation in violations or []:
            if not isinstance(violation, dict):
                continue
            key = (
                str(violation.get("rule_id", "") or ""),
                int(violation.get("line", 0) or 0),
                str(violation.get("message", "") or ""),
                str(violation.get("file", "") or ""),
            )
            if key not in deduped:
                deduped[key] = violation
        return list(deduped.values())

    def _run_legacy_p1_rules(
        self,
        code: str,
        analysis_code: str,
        event_name: str,
        base_line: int,
        anchor_line: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        violations: List[Dict[str, Any]] = []

        for rule_id, info in self.technical_patterns.items():
            match = re.search(info["pattern"], analysis_code, re.DOTALL | re.MULTILINE)
            if match:
                match_line = self._line_from_offset(analysis_code, match.start(), base_line=base_line, context=context)
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
                findings = check_func(check_input, context=context)
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

        return violations

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
            if not bool((self.p1_config_health or {}).get("degraded", False)):
                dedup_list = self._dedupe_p1_violations(configured)
                return self._filter_violations_by_file_type(dedup_list, file_type=file_type)
            violations.extend(configured)

        violations.extend(
            self._run_legacy_p1_rules(
                code=code,
                analysis_code=analysis_code,
                event_name=event_name,
                base_line=base_line,
                anchor_line=anchor_line,
                context=analysis_context,
            )
        )

        dedup_list = self._dedupe_p1_violations(violations)
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
