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




def check_loop_delay(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """MANUAL-002 / CTL-PRF-001: while/for 루프 블록 내 delay() 배치 및 Active 조건문 관계 정밀 분석.

    분석 논리:
    * while 및 for 루프 구문 탐지
    * 단순 동적 배열/리스트 순회 for문(dynlen, len, count 등 포함)은 무한 루프가 아니므로 검사 스킵
    * 지속/작업 루프(while, for(;;))의 중괄호 바디 스코프 파싱
    * 루프 바디 내에 delay()가 존재하면 정상 (PASS)
    * delay()가 전무하면 CPU 무한 점유 위험 지적
    * delay()가 Active 조건문 안쪽에만 위치하면 Passive 상태 지연 누락 위험 지적
    """
    violations: list[Violation] = []
    lines = parsed.content.splitlines()
    content = parsed.content

    loop_pattern = re.compile(r'\b(while|for)\s*\((.*?)\)', re.DOTALL | re.IGNORECASE)

    for match in loop_pattern.finditer(content):
        loop_type = match.group(1).lower()
        loop_cond = match.group(2).strip()

        # 단순 동적 배열/리스트 순회 또는 인덱스 범위 유한 반복문(for/while)은 무한 루프 대상이 아니므로 스킵 (오매핑 방지)
        if loop_type == "for":
            # for(;;) 무한루프는 스킵 금지: 세미콜론 사이에 실질적 종료 조건이 있는지 판별
            if re.search(r'\b(dynlen|length|count|size|sizeof)\b', loop_cond, re.IGNORECASE):
                continue
            if re.search(r'\b\w+\s*<\s*\w+', loop_cond) or re.search(r'\b\w+\s*<=\s*\w+', loop_cond):
                continue
            # for(init;cond;incr) 형태에서 조건부(2번째 세그먼트)에 비교 연산자가 있으면 유한 루프
            if ";" in loop_cond:
                parts = loop_cond.split(";")
                if len(parts) >= 2:
                    cond_part = parts[1].strip()
                    if cond_part and re.search(r'[<>=!]', cond_part):
                        continue
                    # for(;;) 빈 조건부는 무한 루프이므로 스킵하지 않음
            # for(;;) 등 유한 조건 미충족 for문은 무한 루프 가능성이므로 검사 대상에 포함
        if loop_type == "while" and (
            re.search(r'\b(dynlen|length|count|size|sizeof)\b', loop_cond, re.IGNORECASE) or
            re.search(r'^[a-zA-Z0-9_]+\s*(?:<|<=|>|>=)\s*[a-zA-Z0-9_]+$', loop_cond.strip())
        ):
            continue

        start_match_pos = match.start()
        line_idx = content[:start_match_pos].count('\n') + 1

        # 루프 헤더 이후 중괄호 '{' 위치 탐색
        header_end = match.end()
        rest_content = content[header_end:]
        brace_match = re.search(r'\s*\{', rest_content)

        if not brace_match:
            continue

        start_pos = header_end + brace_match.end() - 1

        # 중괄호 스택 파싱으로 루프 바디 끝 위치 획득
        brace_count = 0
        end_pos = start_pos
        in_s_quote = False
        in_d_quote = False
        in_line_comment = False
        in_block_comment = False

        i = start_pos
        content_len = len(content)
        while i < content_len:
            ch = content[i]
            next_ch = content[i + 1] if i + 1 < content_len else ''

            if in_line_comment:
                if ch == '\n':
                    in_line_comment = False
            elif in_block_comment:
                if ch == '*' and next_ch == '/':
                    in_block_comment = False
                    i += 1
            elif in_s_quote:
                if ch == '\\':
                    i += 1
                elif ch == "'":
                    in_s_quote = False
            elif in_d_quote:
                if ch == '\\':
                    i += 1
                elif ch == '"':
                    in_d_quote = False
            else:
                if ch == '/' and next_ch == '/':
                    in_line_comment = True
                    i += 1
                elif ch == '/' and next_ch == '*':
                    in_block_comment = True
                    i += 1
                elif ch == "'":
                    in_s_quote = True
                elif ch == '"':
                    in_d_quote = True
                elif ch == '{':
                    brace_count += 1
                elif ch == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_pos = i
                        break
            i += 1

        body_content = content[start_pos + 1 : end_pos]
        body_lines = body_content.splitlines()

        has_delay = False
        active_keywords = ["isredundantactive", "scriptactive", "isactive", "activecondition"]

        for b_line in body_lines:
            l_strip = b_line.strip()
            if l_strip.startswith("//") or l_strip.startswith("/*") or l_strip.startswith("#"):
                continue

            if re.search(r'\bdelay\s*\(', b_line, re.IGNORECASE):
                has_delay = True
                break

        # delay()가 전혀 없으면 위반 검출
        if not has_delay:
            snippet_line = lines[line_idx - 1].strip() if line_idx <= len(lines) else match.group(0)
            violations.append(
                Violation(
                    violation_id=f"V-{rule.rule_id}-{line_idx:03d}",
                    rule_id=rule.rule_id,
                    file_id=str(parsed.file_path),
                    status=ViolationStatus.MANUAL_REVIEW if "MANUAL" in rule.rule_id else ViolationStatus.FAIL,
                    severity=rule.severity or SeverityLevel.MEDIUM,
                    message=rule.message or f"[{rule.rule_id}] 루프({loop_type}) 블록 내에 CPU 무한 점유 방지를 위한 delay() 구문이 누락되었습니다.",
                    line_start=line_idx,
                    line_end=line_idx,
                    snippet=snippet_line,
                )
            )
        else:
            # delay()가 존재하는 경우: Active 조건문 안쪽에만 작성되어 있는지 정밀 확인
            body_lower = body_content.lower()
            if any(ak in body_lower for ak in active_keywords):
                active_if_pattern = re.compile(
                    r'\bif\s*\([^{]*(?:isredundantactive|scriptactive|isactive|activecondition)[^{]*\)\s*\{',
                    re.IGNORECASE
                )
                active_match = active_if_pattern.search(body_content)
                if active_match:
                    a_start = active_match.end() - 1
                    a_brace = 0
                    a_end = a_start
                    j = a_start
                    while j < len(body_content):
                        c = body_content[j]
                        if c == '{':
                            a_brace += 1
                        elif c == '}':
                            a_brace -= 1
                            if a_brace == 0:
                                a_end = j
                                break
                        j += 1

                    active_body = body_content[a_start + 1 : a_end]
                    outside_body = body_content[:active_match.start()] + body_content[a_end + 1:]

                    delay_in_active = bool(re.search(r'\bdelay\s*\(', active_body, re.IGNORECASE))
                    delay_in_outside = bool(re.search(r'\bdelay\s*\(', outside_body, re.IGNORECASE))

                    if delay_in_active and not delay_in_outside:
                        snippet_line = lines[line_idx - 1].strip() if line_idx <= len(lines) else match.group(0)
                        violations.append(
                            Violation(
                                violation_id=f"V-{rule.rule_id}-{line_idx:03d}",
                                rule_id=rule.rule_id,
                                file_id=str(parsed.file_path),
                                status=ViolationStatus.MANUAL_REVIEW,
                                severity=rule.severity or SeverityLevel.MEDIUM,
                                message=rule.message or f"[{rule.rule_id}] delay() 구문이 Active 조건문 내부에만 위치하여, Passive 상태일 때 delay 없이 루프가 반복 실행되는 우려가 있습니다.",
                                line_start=line_idx,
                                line_end=line_idx,
                                snippet=snippet_line,
                            )
                        )

    return violations



def check_batch_dp_operations(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """MANUAL-003: 이벤트 교환 횟수 최소화 (일괄 dpGet/dpSet 처리 여부).
    *해당 룰은 AST 기반 스코프 체커(ast_cfa_checker.py의 check_ast_bulk_dp_operations)로 이관되었습니다.
    *여기서는 더 이상 텍스트 기반 검사를 수행하지 않고 빈 리스트를 반환합니다.
    """
    return []



def check_dp_callback_delay(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """MANUAL-004: dpConnect or dpQueryConnectSingle 콜백 함수 내 delay 유무 검사.

    분석 논리:
    * dpConnect 또는 dpQueryConnectSingle 호출 구문에서 콜백 함수명 추출
    * 콜백 함수 정의 영역 내에 delay() 구문 존재 여부 정밀 검사
    * delay() 구문이 콜백 함수 내부에 존재할 때만 비동기 이벤트 지연 위험으로 위반 생성
    * delay()가 없는 정상 비동기 처리 콜백은 검출하지 않고 PASS 처리
    """
    violations: list[Violation] = []
    lines = parsed.content.splitlines()
    content = parsed.content

    connect_pattern = re.compile(
        r'\b(?:dpConnect|dpQueryConnectSingle|dpQueryConnectAll|dpQueryConnect)\s*\(\s*"([^"]+)"',
        re.IGNORECASE
    )

    cb_info_list: list[tuple[str, int]] = []
    for match in connect_pattern.finditer(content):
        cb_name = match.group(1)
        line_no = content[:match.start()].count('\n') + 1
        cb_info_list.append((cb_name, line_no))

    if not cb_info_list:
        return []

    checked_callbacks: set[str] = set()

    for cb_name, _ in cb_info_list:
        if cb_name in checked_callbacks:
            continue
        checked_callbacks.add(cb_name)

        func_def_pattern = re.compile(
            rf'\b(?:void|int|bool|string|anytype|float|dyn_\w+)?\s*{re.escape(cb_name)}\s*\([^)]*\)\s*\{{',
            re.MULTILINE
        )
        match_def = func_def_pattern.search(content)
        if not match_def:
            continue

        start_pos = match_def.end() - 1
        start_line = content[:start_pos].count('\n') + 1

        brace_count = 0
        end_pos = start_pos
        in_s_quote = False
        in_d_quote = False
        in_line_comment = False
        in_block_comment = False

        i = start_pos
        content_len = len(content)
        while i < content_len:
            ch = content[i]
            next_ch = content[i + 1] if i + 1 < content_len else ''

            if in_line_comment:
                if ch == '\n':
                    in_line_comment = False
            elif in_block_comment:
                if ch == '*' and next_ch == '/':
                    in_block_comment = False
                    i += 1
            elif in_s_quote:
                if ch == '\\':
                    i += 1
                elif ch == "'":
                    in_s_quote = False
            elif in_d_quote:
                if ch == '\\':
                    i += 1
                elif ch == '"':
                    in_d_quote = False
            else:
                if ch == '/' and next_ch == '/':
                    in_line_comment = True
                    i += 1
                elif ch == '/' and next_ch == '*':
                    in_block_comment = True
                    i += 1
                elif ch == "'":
                    in_s_quote = True
                elif ch == '"':
                    in_d_quote = True
                elif ch == '{':
                    brace_count += 1
                elif ch == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_pos = i
                        break
            i += 1

        func_body_lines = lines[start_line - 1 : content[:end_pos].count('\n') + 1]

        for offset, b_line in enumerate(func_body_lines):
            line_idx = start_line + offset
            l_strip = b_line.strip()
            if l_strip.startswith("//") or l_strip.startswith("/*") or l_strip.startswith("#"):
                continue

            if re.search(r'\bdelay\s*\(', b_line, re.IGNORECASE):
                violations.append(
                    Violation(
                        violation_id=f"V-{rule.rule_id}-{line_idx:03d}",
                        rule_id=rule.rule_id,
                        file_id=str(parsed.file_path),
                        status=ViolationStatus.MANUAL_REVIEW,
                        severity=rule.severity or SeverityLevel.MEDIUM,
                        message=rule.message or f"[{rule.rule_id}] dpConnect/dpQueryConnectSingle 콜백 함수 '{cb_name}' 내부에 delay() 구문이 존재하여 비동기 처리 지연 위험이 있습니다.",
                        line_start=line_idx,
                        line_end=line_idx,
                        snippet=l_strip,
                    )
                )

    return violations



def check_dp_in_loop(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """
    [ctl.dp_in_loop] for/while 루프 내에서 개별 dpGet/dpSet 통신 연산 호출 탐지.
    """
    violations: list[Violation] = []
    lines = parsed.content.splitlines()
    in_loop = False
    loop_start_line = 0
    brace_depth = 0

    for idx, line in enumerate(lines, start=1):
        clean_line = line.split("//")[0]

        # 루프 시작 감지
        if not in_loop and re.search(r'\b(for|while)\s*\(', clean_line):
            in_loop = True
            loop_start_line = idx
            brace_depth = clean_line.count("{") - clean_line.count("}")
            if brace_depth <= 0 and "{" in clean_line:
                brace_depth = 1
        elif in_loop:
            brace_depth += clean_line.count("{") - clean_line.count("}")

            # 루프 블록 내 개별 dpGet / dpSet 감지 (dyn_string 배열 기반의 dpGet/dpSet 활용 권고)
            if re.search(r'\bdpGet\s*\(', clean_line):
                violations.append(
                    Violation(
                        violation_id=f"V-{rule.rule_id}-{idx:03d}",
                        rule_id=rule.rule_id,
                        file_id=str(parsed.file_path),
                        status=ViolationStatus.FAIL,
                        severity=rule.severity or SeverityLevel.HIGH,
                        message=f"[{rule.rule_id}] 루프문(L{loop_start_line}) 내부에서 개별 'dpGet' 통신 연산이 호출되었습니다. Event Manager 과부하 방지를 위해 루프 외부에서 dyn_string 배열을 구성한 후 단일 dpGet으로 일괄 처리하세요.",
                        line_start=idx,
                        line_end=idx,
                        snippet=line.strip(),
                    )
                )
            if re.search(r'\bdpSet\s*\(', clean_line):
                violations.append(
                    Violation(
                        violation_id=f"V-{rule.rule_id}-{idx:03d}",
                        rule_id=rule.rule_id,
                        file_id=str(parsed.file_path),
                        status=ViolationStatus.FAIL,
                        severity=rule.severity or SeverityLevel.HIGH,
                        message=f"[{rule.rule_id}] 루프문(L{loop_start_line}) 내부에서 개별 'dpSet' 통신 연산이 호출되었습니다. Event Manager 과부하 방지를 위해 루프 외부에서 dyn_string 배열을 구성한 후 단일 dpSet으로 일괄 처리하세요.",
                        line_start=idx,
                        line_end=idx,
                        snippet=line.strip(),
                    )
                )

            # 루프 종결 감지
            if brace_depth <= 0 and "}" in clean_line:
                in_loop = False

    return violations


