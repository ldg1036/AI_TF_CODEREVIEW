"""Builtin Checker Registry & Modules"""
from __future__ import annotations
import re
from typing import Any

from app.core.models import RuleDefinition, SeverityLevel, Violation, ViolationStatus
from app.core.parser.base_parser import ParsedFile


_PNL_INIT_CONTEXT_KEYWORDS = [
    "scopelib::",
    "initialize(",
    "panelonopen(",
    "event_panel",
    "panel_on_open",
    "panel_on_start",
    "initpanel(",
    "main(",
]

def _is_pnl_init_context(content: str) -> bool:
    """파일 내용이 PNL 화면 초기화 이벤트 컨텍스트인지 판정합니다."""
    content_lower = content.lower()
    return any(kw in content_lower for kw in _PNL_INIT_CONTEXT_KEYWORDS)



def check_db_query_binding(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """MANUAL-007/008/009: DB Query 바인딩 쿼리 적절성 검사.

    분석 논리:
    * 실제 DB Query 관련 함수(dbExecuteQuery, dbGetQuery, dbCommand 등) 또는 대문자 SQL 구문(SELECT, INSERT INTO, UPDATE, DELETE FROM) 존재 여부 확인
    * 주석(//, /* */) 내부 구문 및 단순 UI 텍스트("Select file:" 등) 제외
    * DB 쿼리 구문이 없거나 바인딩 쿼리/고정 쿼리 사용 시 PASS (검출 안 함)
    * SQL 쿼리 작성 시 변수 동적 결합('SELECT ... ' + var)으로 쿼리를 조립하는 미준수 구문만 FAIL/MANUAL_REVIEW 검출
    """
    violations: list[Violation] = []
    content = parsed.content

    # 1. DB 관련 함수 또는 명시적 대문자 SQL 키워드 패턴
    db_func_pattern = re.compile(r'\b(dbExecuteQuery|dbGetQuery|dbCommand|dbOpenClass|dbStartTransaction|dbBindParameter)\b')
    sql_kw_pattern = re.compile(r'\b(SELECT\s+.+?\s+FROM|INSERT\s+INTO|UPDATE\s+.+?\s+SET|DELETE\s+FROM)\b')

    # 주석 제거된 코드로 1차 검사
    clean_lines: list[tuple[int, str]] = []
    in_block_comment = False
    lines = content.splitlines()

    for idx, line in enumerate(lines, start=1):
        l_strip = line.strip()
        if in_block_comment:
            if "*/" in l_strip:
                in_block_comment = False
            continue

        if l_strip.startswith("/*"):
            if "*/" not in l_strip:
                in_block_comment = True
            continue

        if l_strip.startswith("//") or l_strip.startswith("#"):
            continue

        # 라인 내 후미 주석 제거
        code_part = line.split("//")[0].strip()
        if code_part:
            clean_lines.append((idx, code_part))

    clean_text = "\n".join([code for _, code in clean_lines])

    # DB 함수나 대문자 SQL 구문이 둘 다 없으면 PASS
    if not (db_func_pattern.search(clean_text) or sql_kw_pattern.search(clean_text)):
        return []

    # 2. 동적 결합 쿼리 패턴 정밀 검색 ("SELECT ... FROM " + var)
    unbound_concat_pattern = re.compile(
        r'["\'].*?\b(SELECT\s+.+?\s+FROM|INSERT\s+INTO|UPDATE\s+.+?\s+SET|DELETE\s+FROM)\b.*?["\']\s*\+\s*\w+',
        re.IGNORECASE
    )

    for idx, code_line in clean_lines:
        if unbound_concat_pattern.search(code_line):
            violations.append(
                Violation(
                    violation_id=f"V-{rule.rule_id}-{idx:03d}",
                    rule_id=rule.rule_id,
                    file_id=str(parsed.file_path),
                    status=ViolationStatus.MANUAL_REVIEW,
                    severity=rule.severity or SeverityLevel.MEDIUM,
                    message=rule.message or f"[{rule.rule_id}] DB Query 작성 시 바인딩 쿼리가 아닌 문자열 동적 결합(+)이 사용되었습니다.",
                    line_start=idx,
                    line_end=idx,
                    snippet=code_line,
                )
            )

    return violations




def check_try_catch_exception(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """MANUAL-012: DP 함수 호출 시 try/catch 예외 처리 여부 구문 분석 (CFA 적용)."""
    violations: list[Violation] = []
    lines = parsed.content.splitlines()
    content = parsed.content

    dp_func_pattern = re.compile(r'\b(dpSet|dpSetTimed|dpGet|dpQuery|dpQueryConnectSingle|dpConnect)\b', re.IGNORECASE)
    if not dp_func_pattern.search(content):
        return []

    # CFA AST 적용
    from app.core.parser.tree_sitter_parser import TreeSitterASTParser
    parser = TreeSitterASTParser()
    ast_nodes = parser.parse_code_to_ast(parsed.content)
    
    if parser.ts_available:
        reported_lines = set()
        for node in ast_nodes:
            if node.node_type == "call_expression":
                func_node_text = ""
                for child in node.children:
                    if child.node_type == "identifier":
                        func_node_text = child.text
                        break
                
                if dp_func_pattern.search(func_node_text):
                    in_try = False
                    has_valid_catch = False
                    curr = node.parent
                    while curr:
                        if curr.node_type == "try_statement":
                            in_try = True
                            for child in curr.children:
                                if child.node_type == "catch_clause":
                                    has_valid_catch = True
                            break
                        # 함수 정의 경계를 벗어나면 탐색 중지
                        if curr.node_type == "function_definition":
                            break
                        curr = curr.parent
                    
                    if not (in_try and has_valid_catch):
                        line_idx = node.line_start
                        if line_idx not in reported_lines:
                            violations.append(
                                Violation(
                                    violation_id=f"V-{rule.rule_id}-{line_idx:03d}",
                                    rule_id=rule.rule_id,
                                    file_id=str(parsed.file_path),
                                    status=ViolationStatus.MANUAL_REVIEW,
                                    severity=rule.severity or SeverityLevel.MEDIUM,
                                    message=rule.message or f"[{rule.rule_id}] DP 함수 호출이 유효한 catch 절을 동반한 try/catch 블록에 래핑되지 않았습니다. (AST CFA 검출)",
                                    line_start=line_idx,
                                    line_end=node.line_end,
                                    snippet=lines[line_idx - 1].strip() if line_idx <= len(lines) else "",
                                )
                            )
                            reported_lines.add(line_idx)
        return violations

    # 주석 제거 후 try/catch 키워드 검사 (Fallback)
    clean_lines: list[str] = []
    for line in lines:
        l_strip = line.strip()
        if l_strip.startswith("//") or l_strip.startswith("/*") or l_strip.startswith("#"):
            continue
        clean_lines.append(line.split("//")[0])
    clean_text = "\n".join(clean_lines)

    has_try = bool(re.search(r'\btry\s*\{', clean_text, re.IGNORECASE))
    has_catch = bool(re.search(r'\bcatch\s*\(', clean_text, re.IGNORECASE))

    if has_try and has_catch:
        return []

    # try/catch가 없는 경우: 함수 정의 탐색 (들여쓰기 및 다양한 리턴타입 지원)
    func_pattern = re.compile(
        r'^\s*(?:synchronized\s+|public\s+|private\s+)?(?:void|int|bool|string|float|dyn_\w+|mapping|anytype|unsigned)\s+(\w+)\s*\(',
        re.MULTILINE | re.IGNORECASE
    )

    for match in func_pattern.finditer(content):
        func_name = match.group(1)
        func_line = content[:match.start()].count("\n") + 1

        body_start = func_line - 1
        body_end = min(func_line + 60, len(lines))
        body_text = "\n".join(lines[body_start:body_end])

        has_error_handling = bool(
            re.search(r'\b(getlasterror|errorhandling|rtn_value_error|iserror)\b', body_text, re.IGNORECASE)
            or re.search(r'\bif\s*\([^{;]*?(?:err|res|rc|status|ret|error)\s*(?:!=|==|<|>|<=|>=)\s*[0-9]+', body_text, re.IGNORECASE)
        )
        if dp_func_pattern.search(body_text) and not re.search(r'\btry\b', body_text, re.IGNORECASE) and not has_error_handling:
            violations.append(
                Violation(
                    violation_id=f"V-{rule.rule_id}-{func_line:03d}",
                    rule_id=rule.rule_id,
                    file_id=str(parsed.file_path),
                    status=ViolationStatus.MANUAL_REVIEW,
                    severity=rule.severity or SeverityLevel.MEDIUM,
                    message=rule.message or f"[{rule.rule_id}] DP 함수를 호출하는 '{func_name}' 함수에 try/catch 예외 처리가 구현되지 않았습니다.",
                    line_start=func_line,
                    line_end=func_line,
                    snippet=lines[func_line - 1].strip() if func_line <= len(lines) else "",
                )
            )

    return violations



def check_dp_function_error_handling(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """MANUAL-013: DP 함수 예외 처리 (dpGet/dpSet 결과 반환값 검사 여부 분석)."""
    violations: list[Violation] = []
    lines = parsed.content.splitlines()
    content_lower = parsed.content.lower()

    if "dpget(" not in content_lower and "dpset(" not in content_lower:
        return []

    # 주석 제거 라인 생성
    clean_lines: list[tuple[int, str]] = []
    for idx, line in enumerate(lines, start=1):
        l_strip = line.strip()
        if l_strip.startswith("//") or l_strip.startswith("/*") or l_strip.startswith("#"):
            continue
        code_part = line.split("//")[0].strip()
        if code_part:
            clean_lines.append((idx, code_part))

    # 범용 에러 검사 패턴: getLastError(), errorHandling, if(res != 0), if(err < 0) 등
    has_global_err_check = bool(
        re.search(r'\b(getlasterror|errorhandling|rtn_value_error|iserror|errclass|errcheck|error_handler)\b', content_lower)
    )

    for idx, code_line in clean_lines:
        if re.search(r'\b(dpGet|dpSet)\s*\(', code_line):
            # 1. 반환값을 변수로 받는지 (예: err = dpGet(...), int res = dpSet(...))
            has_assignment = bool(re.search(r'\b\w+\s*=\s*dp(?:Get|Set)\s*\(', code_line))
            # 2. 직후 또는 인접 5행에 조건문/에러 체크가 있는지 확인 (오매핑 방지)
            prev_next_context = ""
            start_i = max(0, idx - 5)
            end_i = min(len(lines), idx + 5)
            for k in range(start_i, end_i):
                prev_next_context += lines[k] + "\n"

            has_local_if = bool(re.search(r'\bif\s*\(', prev_next_context, re.IGNORECASE))

            # 반환값 할당도 없고, 인접 행에 if 문/getLastError 도 없으면 위반
            if not (has_assignment or has_local_if or has_global_err_check):
                violations.append(
                    Violation(
                        violation_id=f"V-{rule.rule_id}-{idx:03d}",
                        rule_id=rule.rule_id,
                        file_id=str(parsed.file_path),
                        status=ViolationStatus.MANUAL_REVIEW,
                        severity=rule.severity or SeverityLevel.MEDIUM,
                        message=rule.message or f"[{rule.rule_id}] dpGet/dpSet 호출 결과에 대한 반환값 검사가 누락되었습니다.",
                        line_start=idx,
                        line_end=idx,
                        snippet=code_line,
                    )
                )

    return violations



def check_dp_async_handling(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """MANUAL-005: 비동기 DP 처리 함수 적절성 검사.

    분석 논리:
    * dpConnect, dpQueryConnect 등 비동기 DP 처리 함수가 콜백 함수와 함께 올바르게 사용되는지 확인
    * 콜백 함수가 정상 정의되어 있으면 PASS
    """
    violations: list[Violation] = []
    lines = parsed.content.splitlines()
    content = parsed.content

    # dpConnect 호출 시 콜백 함수명 추출
    connect_pattern = re.compile(r'dpConnect\(\s*"(\w+)"', re.MULTILINE)
    callback_names = set()
    for match in connect_pattern.finditer(content):
        callback_names.add(match.group(1))

    if not callback_names:
        # dpConnect 자체가 없으면 검사 불필요
        return []

    # 콜백 함수가 실제로 정의되어 있는지 확인
    for cb_name in callback_names:
        func_def_pattern = re.compile(rf'\b(void|int|bool|string|anytype)\s+{re.escape(cb_name)}\s*\(')
        if not func_def_pattern.search(content):
            # 콜백이 정의 안 된 경우에만 지적
            for idx, line in enumerate(lines, start=1):
                if cb_name in line and "dpConnect" in line:
                    violations.append(
                        Violation(
                            violation_id=f"V-{rule.rule_id}-{idx:03d}",
                            rule_id=rule.rule_id,
                            file_id=str(parsed.file_path),
                            status=ViolationStatus.MANUAL_REVIEW,
                            severity=rule.severity or SeverityLevel.MEDIUM,
                            message=rule.message or f"[{rule.rule_id}] dpConnect 콜백 '{cb_name}'의 함수 정의가 소스 내에서 확인되지 않습니다.",
                            line_start=idx,
                            line_end=idx,
                            snippet=line.strip(),
                        )
                    )
                    break

    return violations



def check_callback_error_handling(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """
    [ctl.callback_error_handling] 비동기 콜백 함수 내 에러 처리(getLastError/try-catch) 누락 탐지.
    괄호 균형(Brace Balancing) 알고리즘으로 중첩 블록이 있는 함수 본문도 정확히 추출합니다.
    """
    violations: list[Violation] = []
    content = parsed.content
    dp_connects = re.finditer(r'\bdpConnect\s*\(\s*"([^"]+)"', content)

    for match in dp_connects:
        cb_name = match.group(1)
        line_no = content[: match.start()].count("\n") + 1

        # 콜백 함수 헤더 탐지 후 괄호 균형으로 본문 전체 추출
        header_pat = re.search(r'\bvoid\s+' + re.escape(cb_name) + r'\s*\([^)]*\)\s*\{', content)
        if header_pat:
            body_start = header_pat.end()
            brace_count = 1
            pos = body_start
            while pos < len(content) and brace_count > 0:
                if content[pos] == '{':
                    brace_count += 1
                elif content[pos] == '}':
                    brace_count -= 1
                pos += 1
            cb_body = content[body_start:pos - 1]
            if "getlasterror" not in cb_body.lower() and "try" not in cb_body.lower():
                violations.append(
                    Violation(
                        violation_id=f"V-{rule.rule_id}-{line_no:03d}",
                        rule_id=rule.rule_id,
                        file_id=str(parsed.file_path),
                        status=ViolationStatus.FAIL,
                        severity=rule.severity or SeverityLevel.HIGH,
                        message=f"[{rule.rule_id}] 비동기 콜백 함수 '{cb_name}' 내부에 예외 처리(getLastError 또는 try-catch)가 누락되었습니다.",
                        line_start=line_no,
                        line_end=line_no,
                        snippet=match.group(0),
                    )
                )

    return violations



def check_unhandled_dp_query_error(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """ctl.unhandled_dp_query_error: dpQuery 후 반환 코드 검증 부재 검사."""
    violations: list[Violation] = []
    lines = parsed.content.splitlines()
    for idx, line in enumerate(lines, start=1):
        if "dpQuery(" in line and not any("getLastError" in line_item or "rc" in line_item or "err" in line_item for line_item in lines[max(0, idx-1):min(len(lines), idx+4)]):
            violations.append(
                Violation(
                    violation_id=f"V-{rule.rule_id}-{idx:03d}",
                    rule_id=rule.rule_id,
                    file_id=str(parsed.file_path),
                    status=ViolationStatus.FAIL,
                    severity=rule.severity or SeverityLevel.HIGH,
                    message="dpQuery 호출 직후 리턴 코드 검사 또는 getLastError() 예외 검증이 누락되었습니다.",
                    line_start=idx,
                    line_end=idx,
                    snippet=line.strip(),
                )
            )
    return violations



def check_dp_set_wait_timeout(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """ctl.dp_set_wait_timeout: dpSetWait 호출 타임아웃 지정 미비 검사."""
    violations: list[Violation] = []
    lines = parsed.content.splitlines()
    for idx, line in enumerate(lines, start=1):
        if "dpSetWait(" in line and "dpSetTimedWait" not in line:
            violations.append(
                Violation(
                    violation_id=f"V-{rule.rule_id}-{idx:03d}",
                    rule_id=rule.rule_id,
                    file_id=str(parsed.file_path),
                    status=ViolationStatus.FAIL,
                    severity=rule.severity or SeverityLevel.MEDIUM,
                    message="dpSetWait 동기성 블로킹 호출 시 무한 대기 방지를 위해 dpSetTimedWait 또는 타임아웃 처리를 권장합니다.",
                    line_start=idx,
                    line_end=idx,
                    snippet=line.strip(),
                )
            )
    return violations


