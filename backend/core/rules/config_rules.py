import re
from collections import Counter
from typing import Dict, List


class ConfigRulesMixin:
    """Configuration and data integrity heuristic checks for WinCC OA code."""

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
