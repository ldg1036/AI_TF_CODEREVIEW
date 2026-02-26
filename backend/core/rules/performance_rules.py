import re
from collections import Counter
from typing import Dict, List


class PerformanceRulesMixin:
    """Performance-related heuristic checks for WinCC OA code."""

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
