import re
from typing import Dict, List


_FUNCTION_START_PATTERN = re.compile(
    r"^(?:main|void|int|float|string|bool|mapping|time|anytype|dyn_[a-zA-Z0-9_]+)\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\("
)
_MAIN_FUNCTION_PATTERN = re.compile(r"^main\s*\(")
_DECL_PATTERN = re.compile(
    r"^\s*(const\s+)?(?:int|float|string|bool|mapping|time|anytype|dyn_[a-zA-Z0-9_]+)\s+([a-zA-Z_][a-zA-Z0-9_]*)"
)
_CONFIG_NAME_PATTERN = re.compile(r"(cfg|config)", re.IGNORECASE)
_INDENT_PATTERN = re.compile(r"^([ \t]+)")
_FUNCTION_HEADER_PATTERN = re.compile(
    r"^\s*(?:void|int|float|string|bool|mapping|time|anytype|dyn_[a-zA-Z0-9_]+)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\("
)
_COMMENT_HEADER_PATTERN = re.compile(r"^\s*(//|/\*|\*)")
_DECL_START_PATTERN = re.compile(r"^\s*(?:int|float|string|bool|dyn_\w+)\s+[a-zA-Z_][a-zA-Z0-9_]*")
_CONTROL_PATTERN = re.compile(r"^\s*(?:if|for|while|switch|return|break|continue|try|catch)\b")
_MAGIC_INDEX_PATTERN = re.compile(r"\b(?:parts|data|tokens|fields)\s*\[\s*([2-9]|\d{2,})\s*\]")
_IDX_CONST_PATTERN = re.compile(r"\bIDX_[A-Z0-9_]+\b")


class StyleRulesMixin:
    """Style and coding standards heuristic checks for WinCC OA code."""

    def check_style_name_rules(self, code: str) -> List[Dict]:
        findings = []
        lines = code.splitlines()
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
            match = _DECL_PATTERN.match(stripped)
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

            if _CONFIG_NAME_PATTERN.search(name) and not name.startswith("cfg_"):
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
            indent_match = _INDENT_PATTERN.match(line)
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
        for idx, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("/*"):
                continue
            if not _FUNCTION_HEADER_PATTERN.match(stripped) and not re.match(r"^\s*main\s*\(", stripped):
                continue

            has_header = False
            # Inspect a wider range above function start and stop at previous code line.
            comment_hits = 0
            for back in range(idx - 2, max(-1, idx - 20), -1):
                prev = lines[back].strip()
                if not prev:
                    continue
                if _COMMENT_HEADER_PATTERN.match(lines[back]):
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

    def check_coding_standards_advanced(self, code: str) -> List[Dict]:
        findings = []
        lines = code.splitlines()
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

            if not _DECL_START_PATTERN.match(stripped):
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

    def check_magic_index_usage(self, code: str) -> List[Dict]:
        findings = []
        if _IDX_CONST_PATTERN.search(code):
            return findings

        matches = list(_MAGIC_INDEX_PATTERN.finditer(code))
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
