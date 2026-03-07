import re
from typing import Dict, List


class SecurityRulesMixin:
    """Security-related heuristic checks for WinCC OA code."""

    def check_sql_injection(self, code: str) -> List[Dict]:
        findings = []
        sql_keywords = r"\b(SELECT|INSERT|UPDATE|DELETE|FROM|WHERE|JOIN)\b"
        for line_no, line in enumerate(code.splitlines(), 1):
            if re.search(r"sprintf.*%s", line) and re.search(sql_keywords, line, re.IGNORECASE):
                findings.append(
                    {
                        "rule_id": "SEC-01",
                        "rule_item": "바인딩 쿼리 처리",
                        "severity": "Critical",
                        "line": line_no,
                        "message": "sprintf 기반 동적 SQL 구성 패턴 감지.",
                    }
                )
                break
        return findings

    def check_dp_function_exception(self, code: str) -> List[Dict]:
        findings = []
        dp_call_pattern = r"\b(dpSet|dpGet|dpQuery|dpConnect)\s*\([^;]+\)\s*;"
        first_dp_call = re.search(dp_call_pattern, code)
        if not first_dp_call:
            return findings

        # Safe alternative: check for try/catch presence without catastrophic backtracking.
        has_try = bool(re.search(r"\btry\b", code, re.IGNORECASE))
        has_catch = bool(re.search(r"\bcatch\b", code, re.IGNORECASE))
        has_try_catch = has_try and has_catch
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
