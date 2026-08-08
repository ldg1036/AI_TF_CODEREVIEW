"""
AST 기반 심층 제어 흐름 분석(Control Flow Analysis) 체커 (03_정적분석_룰카탈로그.md §13).

주요 검증 대상:
1. ctl.ast.dp_callback_resolve: dpConnect 호출 시 콜백 함수의 실제 정의 여부 검사
2. ctl.ast.callback_signature: 콜백 함수 매개변수 시그니처 (2개 이상 인자) 규격 검증
3. ctl.ast.loop_reachability: while(true) 등 무한 루프 내 탈출 구문(break/return) 도달 가능성 검사
"""

from __future__ import annotations

import logging
import re

from app.core.models import ParseStatusType, SeverityLevel, Violation, ViolationStatus
from app.core.parser.base_parser import ParsedFile

logger = logging.getLogger(__name__)


class ASTControlFlowChecker:
    """WinCC OA 스크립트 심층 제어 흐름 및 콜백 그래프 분석 체커."""

    RULE_ID_RESOLVE = "CTL-AST-CFA-001"
    RULE_ID_SIGNATURE = "CTL-AST-CFA-002"
    RULE_ID_REACHABILITY = "CTL-AST-CFA-003"

    @classmethod
    def _extract_function_definitions(cls, content: str) -> dict[str, str]:
        """
        소스 코드에서 함수 선언문과 파라미터 시그니처를 추출합니다.

        Returns:
            { "함수명": "파라미터_시그니처_문자열" }
        """
        funcs: dict[str, str] = {}
        # 예: void cb_func(string dp, anytype val) { ...
        # 또는 int myFunc(int a)
        pattern = r"\b(?:void|int|bool|string|float|dyn_string|dyn_anytype|dyn_int|dyn_float|anytype)\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)"
        matches = re.findall(pattern, content)
        for name, params in matches:
            funcs[name] = params.strip()
        return funcs

    @classmethod
    def _check_dp_callback_resolve(cls, parsed: ParsedFile, funcs: dict[str, str]) -> list[Violation]:
        """dpConnect 콜백 함수의 정의 여부 및 심볼 존재 여부를 검사합니다."""
        violations: list[Violation] = []
        lines = parsed.content.splitlines()

        # dpConnect("cb_name", ... 또는 dpConnect(cb_name, ...
        pattern = r"\bdpConnect\s*\(\s*(?:\"([a-zA-Z0-9_]+)\"|([a-zA-Z0-9_]+))"
        has_uses = any(line.strip().startswith("#uses") for line in lines)

        for idx, line in enumerate(lines, start=1):
            l_strip = line.strip()
            if l_strip.startswith("//") or l_strip.startswith("/*"):
                continue
            match = re.search(pattern, line)
            if match:
                cb_name = match.group(1) or match.group(2)
                if cb_name and cb_name not in funcs:
                    severity = SeverityLevel.INFO if has_uses else SeverityLevel.HIGH
                    msg_suffix = " (외부 #uses 라이브러리 참조 가능성 있음)" if has_uses else " (심볼 확인 불가)"
                    violations.append(
                        Violation(
                            violation_id=f"V-{cls.RULE_ID_RESOLVE}-{idx}",
                            file_id=str(parsed.file_path),
                            rule_id=cls.RULE_ID_RESOLVE,
                            severity=severity,
                            status=ViolationStatus.FAIL,
                            line_start=idx,
                            line_end=idx,
                            message=f"dpConnect 콜백 함수 '{cb_name}'가 현재 모듈 내에 선언되어 있지 않습니다{msg_suffix}.",
                            snippet=l_strip,
                        )
                    )
        return violations


    @classmethod
    def _check_callback_signature(cls, parsed: ParsedFile, funcs: dict[str, str]) -> list[Violation]:
        """콜백 함수가 최소 2개 이상의 매개변수를 규격으로 갖추고 있는지 검증합니다."""
        violations: list[Violation] = []
        lines = parsed.content.splitlines()

        # dpConnect에 등록된 콜백 함수명들을 수집
        pattern = r"\bdpConnect\s*\(\s*(?:\"([a-zA-Z0-9_]+)\"|([a-zA-Z0-9_]+))"
        called_cbs: set[str] = set()
        for line in lines:
            m = re.search(pattern, line)
            if m:
                cb = m.group(1) or m.group(2)
                if cb:
                    called_cbs.add(cb)

        for cb_name in called_cbs:
            if cb_name in funcs:
                params = funcs[cb_name]
                # 매개변수를 쉼표로 분리
                param_list = [p.strip() for p in params.split(",") if p.strip()]
                if len(param_list) < 2:
                    # 콜백 함수 정의된 라인을 검색
                    line_no = 1
                    for idx, line in enumerate(lines, start=1):
                        if cb_name in line and "(" in line:
                            line_no = idx
                            break
                    violations.append(
                        Violation(
                            violation_id=f"V-{cls.RULE_ID_SIGNATURE}-{line_no}",
                            file_id=str(parsed.file_path),
                            rule_id=cls.RULE_ID_SIGNATURE,
                            severity=SeverityLevel.MEDIUM,
                            status=ViolationStatus.FAIL,
                            line_start=line_no,
                            line_end=line_no,
                            message=f"dpConnect 콜백 함수 '{cb_name}'의 매개변수가 {len(param_list)}개입니다 (요구 규격: string dp, anytype val 등 2개 이상).",
                            snippet=f"{cb_name}({params})",
                        )
                    )
        return violations

    @classmethod
    def _check_loop_reachability(cls, parsed: ParsedFile) -> list[Violation]:
        """while(true), while(1), for(;;) 등 무한 루프 블록의 break/return 탈출 가능성을 검사합니다."""
        violations: list[Violation] = []
        lines = parsed.content.splitlines()

        inf_loop_pattern = r"(?:while\s*\(\s*(?:true|1)\s*\)|for\s*\(\s*;\s*;\s*\))"

        i = 0
        while i < len(lines):
            line = lines[i]
            l_strip = line.strip()
            if not l_strip.startswith("//") and re.search(inf_loop_pattern, line, re.IGNORECASE):
                start_line = i + 1
                # 중괄호 블록 내부를 간단히 탐색하여 break나 return 구문이 있는지 확인
                has_exit = False
                brace_count = 0
                found_open = False

                for j in range(i, min(i + 50, len(lines))):
                    curr_line = lines[j]
                    curr_strip = curr_line.strip()
                    if curr_strip.startswith("//") or curr_strip.startswith("/*"):
                        continue
                    if "{" in curr_line:
                        brace_count += curr_line.count("{")
                        found_open = True
                    if "}" in curr_line:
                        brace_count -= curr_line.count("}")

                    if re.search(r"\b(break|return|exit)\b", curr_line):
                        has_exit = True
                        break

                    if found_open and brace_count <= 0 and j > i:
                        break

                if not has_exit:
                    violations.append(
                        Violation(
                            violation_id=f"V-{cls.RULE_ID_REACHABILITY}-{start_line}",
                            file_id=str(parsed.file_path),
                            rule_id=cls.RULE_ID_REACHABILITY,
                            severity=SeverityLevel.HIGH,
                            status=ViolationStatus.FAIL,
                            line_start=start_line,
                            line_end=start_line,
                            message="무한 루프(while(true)/for(;;)) 내부에서 break나 return 등 탈출 제어문이 검출되지 않았습니다 (데드락 위험).",
                            snippet=l_strip,
                        )
                    )
            i += 1
        return violations




    @classmethod
    def run_ast_cfa_checks(cls, parsed: ParsedFile) -> list[Violation]:
        """
        모든 심층 AST 제어 흐름 체커를 수행하고 결과 Violation을 반환합니다.

        Args:
            parsed: 파싱된 IR

        Returns:
            검출된 Violation 목록
        """
        if parsed.parse_status.status != ParseStatusType.PARSED:
            return []

        funcs = cls._extract_function_definitions(parsed.content)

        v1 = cls._check_dp_callback_resolve(parsed, funcs)
        v2 = cls._check_callback_signature(parsed, funcs)
        v3 = cls._check_loop_reachability(parsed)

        return v1 + v2 + v3
