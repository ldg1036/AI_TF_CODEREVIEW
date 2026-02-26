import re
from collections import Counter
from typing import Dict, List


class QualityRulesMixin:
    """Code quality heuristic checks for WinCC OA code."""

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
        # Safe alternative: line-based scan instead of catastrophic [\s\S]{0,1200}.
        loop_ranges = self._collect_loop_line_ranges(code)
        if not loop_ranges:
            return findings

        lines = code.splitlines()
        has_loop_dyn_ops = False
        for start, end in loop_ranges:
            loop_text = "\n".join(lines[max(0, start - 1) : min(len(lines), end)])
            if re.search(r"\bdyn(?:Append|Insert|MapInsert)\s*\(", loop_text, re.IGNORECASE):
                has_loop_dyn_ops = True
                break

        if has_loop_dyn_ops:
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
