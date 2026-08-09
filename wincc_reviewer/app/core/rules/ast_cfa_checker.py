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

from app.core.models import (
    ParseStatusType,
    RuleDefinition,
    SeverityLevel,
    Violation,
    ViolationStatus,
)
from app.core.parser.base_parser import ParsedFile
from app.core.parser.tree_sitter_parser import TreeSitterASTParser

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

                    if re.search(r"\b(break|return|exit|delay|waitfor|dpwaitfor)\b", curr_line, re.IGNORECASE):
                        has_exit = True
                        break

                    # 도메인 관용구 화이트리스트 (C-2)
                    if re.search(r"\b(dpConnect|dpQueryConnectSingle|dpQueryConnectAll|startThread)\b", curr_line):
                        has_exit = True  # 이벤트 대기 루프 / 스레드 루프로 간주하여 예외 처리
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


def check_ast_bulk_dp_operations(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """CTL-PRF-002: AST 기반 이벤트 교환 횟수 최소화 (일괄 dpGet/dpSet 처리 여부 구문 분석).

    1. 함수(스코프) 단위 독립 평가 (전역 면죄부 폐지).
    2. 루프 내 통신 직격 탐지.
    3. 연속 단건 호출 클러스터링(3회 이상).
    """
    violations: list[Violation] = []
    content = parsed.content

    # 우선 빠르게 통신 함수가 없으면 스킵
    if "dpget" not in content.lower() and "dpset" not in content.lower():
        return violations

    ts_parser = TreeSitterASTParser()
    tree = ts_parser.get_raw_tree(content)

    # AST를 사용할 수 없으면 정규식 fallback으로 블록 스코프 평가를 흉내냅니다
    if not tree:
        return _fallback_bulk_dp_operations(parsed, rule)

    root = tree.root_node

    # 함수 정의 노드 수집
    def find_nodes(node, node_type, result):
        if node.type == node_type:
            result.append(node)
        for child in node.children:
            find_nodes(child, node_type, result)

    function_nodes = []
    find_nodes(root, "function_definition", function_nodes)
    if not function_nodes:
        # 패널 스크립트 등 전역 스코프이거나 C++ 파싱 불가 시 전체를 하나의 스코프로 취급
        function_nodes = [root]

    lines = content.splitlines()

    for func_node in function_nodes:
        func_text = func_node.text.decode("utf8").lower() if func_node.text else ""
        if "dpget" not in func_text and "dpset" not in func_text:
            continue

        # 1. 함수 스코프 내 배치 패턴 존재 확인 ( dynAppend + setDpValue_block )
        # 이 스코프 안에서 배치를 썼다면 이 함수는 정상적인 일괄 처리 구현체로 간주
        has_batch = False
        if "dynappend(" in func_text and ("setdpvalue_block" in func_text or "dpsettimedwait" in func_text):
            has_batch = True
        if not has_batch:
            # 다중 인자(3개 이상 콤마) 탐지 (간단히 정규식 융합 적용)
            for m in re.finditer(r'\b(dpGet|dpSet)\s*\(([^)]+)\)', func_node.text.decode("utf8")):
                if m.group(2).count(',') >= 3:
                    has_batch = True
                    break

        if has_batch:
            continue

        # 2. 루프 내 직접 호출 감지
        loop_nodes = []
        find_nodes(func_node, "for_statement", loop_nodes)
        find_nodes(func_node, "while_statement", loop_nodes)

        for loop in loop_nodes:
            call_nodes = []
            find_nodes(loop, "call_expression", call_nodes)
            for call in call_nodes:
                call_text = call.text.decode("utf8") if call.text else ""
                if re.search(r'^(dpGet|dpSet)\s*\(', call_text):
                    start_line = call.start_point[0] + 1
                    snippet = lines[start_line - 1].strip()
                    violations.append(
                        Violation(
                            violation_id=f"V-{rule.rule_id}-L{start_line}",
                            file_id=str(parsed.file_path),
                            rule_id=rule.rule_id,
                            severity=SeverityLevel.HIGH,
                            status=ViolationStatus.FAIL,
                            line_start=start_line,
                            line_end=start_line,
                            message=f"[{rule.rule_id}] 루프(for/while)문 내부에서 개별 단건 'dpGet/dpSet' 통신 연산이 호출되었습니다. Event Manager 부하 방지를 위해 루프 밖에서 일괄 처리하세요.",
                            snippet=snippet,
                        )
                    )

        # 3. compound_statement (중괄호 블록) 내부 연속 3회 이상 단건 호출 감지
        compound_nodes = []
        find_nodes(func_node, "compound_statement", compound_nodes)

        for comp in compound_nodes:
            dp_call_lines = []
            for child in comp.children:
                if child.type == "expression_statement":
                    call_nodes = []
                    find_nodes(child, "call_expression", call_nodes)
                    for call in call_nodes:
                        call_text = call.text.decode("utf8") if call.text else ""
                        if re.search(r'^(dpGet|dpSet)\s*\(', call_text):
                            dp_call_lines.append(call.start_point[0] + 1)

            # 연속 호출 카운팅 로직
            if len(dp_call_lines) >= 3:
                # 중첩 클러스터 처리
                consecutive_clusters = []
                current_cluster = [dp_call_lines[0]]
                for i in range(1, len(dp_call_lines)):
                    # 같은 형제 노드 레벨이더라도 너무 멀리 떨어져 있으면 (예: 20줄 이상) 다른 논리로 취급
                    if dp_call_lines[i] - current_cluster[-1] <= 20:
                        current_cluster.append(dp_call_lines[i])
                    else:
                        if len(current_cluster) >= 3:
                            consecutive_clusters.extend(current_cluster)
                        current_cluster = [dp_call_lines[i]]
                if len(current_cluster) >= 3:
                    consecutive_clusters.extend(current_cluster)

                for lno in consecutive_clusters:
                    snippet = lines[lno - 1].strip()
                    violations.append(
                        Violation(
                            violation_id=f"V-{rule.rule_id}-C{lno}",
                            file_id=str(parsed.file_path),
                            rule_id=rule.rule_id,
                            severity=rule.severity or SeverityLevel.MEDIUM,
                            status=ViolationStatus.MANUAL_REVIEW,
                            line_start=lno,
                            line_end=lno,
                            message=f"[{rule.rule_id}] 동일한 스코프 블록 내에 단건 dpGet/dpSet 통신 함수가 3회 이상 연속 나열되어 있습니다. dynAppend 배치를 이용한 일괄 처리를 권장합니다.",
                            snippet=snippet,
                        )
                    )

    # 중복 라인 위반 제거
    unique_violations = {v.line_start: v for v in violations}.values()
    return list(unique_violations)


def _fallback_bulk_dp_operations(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """Tree-sitter를 사용할 수 없는 환경에 대비한 구조적 텍스트 폴백 (단, 전역 면죄부는 폐지됨)."""
    violations: list[Violation] = []
    lines = parsed.content.splitlines()

    # 텍스트 기반으로 함수 블록을 나누지 못하더라도, 15라인이 아닌 5라인 초근접성에 대해서만 엄격하게 검출하여 오탐 최소화
    single_call_lines: list[tuple[int, str]] = []
    for idx, line in enumerate(lines, start=1):
        l_strip = line.strip()
        if l_strip.startswith("//") or l_strip.startswith("/*"):
            continue
        if re.search(r'\b(dpGet|dpSet)\s*\(', line):
            stmt = ""
            for j in range(idx - 1, min(idx + 3, len(lines))):
                stmt += lines[j]
                if ";" in lines[j]:
                    break
            if stmt.count(",") <= 2:
                single_call_lines.append((idx, l_strip))

    n = len(single_call_lines)
    for i in range(n - 2):
        l1, s1 = single_call_lines[i]
        l2, s2 = single_call_lines[i+1]
        l3, s3 = single_call_lines[i+2]

        # 3번의 호출이 10줄 이내에 몰려있으면
        if l3 - l1 <= 10:
            region_text = "\n".join(lines[l1-1:l3]).lower()
            if region_text.count("else") < 1 and region_text.count("case ") < 1 and region_text.count("if ") <= 1:
                violations.append(
                    Violation(
                        violation_id=f"V-{rule.rule_id}-F{l3}",
                        file_id=str(parsed.file_path),
                        rule_id=rule.rule_id,
                        severity=SeverityLevel.MEDIUM,
                        status=ViolationStatus.MANUAL_REVIEW,
                        line_start=l3,
                        line_end=l3,
                        message=f"[{rule.rule_id}] 초근접 블록(10줄 이내)에 단건 호출 연속 발생. 일괄 처리를 권장합니다.",
                        snippet=s3,
                    )
                )
    return violations
