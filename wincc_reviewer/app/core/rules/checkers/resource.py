"""Builtin Checker Registry & Modules"""
from __future__ import annotations

import re

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




def check_dp_connect_pair(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """CTL-RES-001: dpConnect 호출 시 dpDisconnect 존재 여부 검사 및 라인 번호 정밀 추출.

    PNL 화면 초기화 이벤트 컨텍스트 예외 처리:
    - PNL 파일이면서 화면 초기화 이벤트 키워드(ScopeLib::, initialize 등)가 감지되면,
      dpDisconnect가 없어도 화면 종료 시 자동 해제되므로 FAIL 대신 INFO 수준 안내로 완화합니다.
    - 실물 검증에서 77건 전부가 이 케이스로 오탐 판정되었습니다.
    """
    violations: list[Violation] = []
    content = parsed.content

    # PNL 파일 화면 초기화 이벤트 컨텍스트 판정
    file_type_lower = (parsed.file_type or "").lower().lstrip(".")
    is_pnl_file = file_type_lower in ("pnl", "xml")
    is_init_context = is_pnl_file and _is_pnl_init_context(content)

    # 주석 제거된 라인 추출
    clean_lines: list[tuple[int, str]] = []
    in_block_comment = False
    for idx, line in enumerate(content.splitlines(), start=1):
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
        code_part = line.split("//")[0].strip()
        if code_part:
            clean_lines.append((idx, code_part))

    has_disconnect = any("dpDisconnect(" in code for _, code in clean_lines)

    if not has_disconnect:
        for idx, code in clean_lines:
            if "dpConnect(" in code:
                if is_init_context:
                    # PNL 초기화 이벤트 컨텍스트: 화면 종료 시 자동 해제 — INFO 수준 안내
                    violations.append(
                        Violation(
                            violation_id=f"V-{rule.rule_id}-{idx:03d}",
                            rule_id=rule.rule_id,
                            file_id=str(parsed.file_path),
                            status=ViolationStatus.MANUAL_REVIEW,
                            severity=SeverityLevel.INFO,
                            message=(
                                f"[INFO] {rule.rule_id} — PNL 화면 초기화 이벤트 내 dpConnect 호출입니다. "
                                "화면 종료 시 자동 해제되어 메모리 누수 위험은 낮으나, "
                                "명시적 dpDisconnect 작성을 통한 자원 해제를 권장합니다."
                            ),
                            line_start=idx,
                            line_end=idx,
                            snippet=code,
                        )
                    )
                else:
                    # CTL 파일 또는 비초기화 컨텍스트: 기존 FAIL 등급 유지
                    violations.append(
                        Violation(
                            violation_id=f"V-{rule.rule_id}-{idx:03d}",
                            rule_id=rule.rule_id,
                            file_id=str(parsed.file_path),
                            status=ViolationStatus.FAIL,
                            severity=rule.severity or SeverityLevel.CRITICAL,
                            message=rule.message or "dpConnect 호출에 대응하는 dpDisconnect가 명시되지 않았습니다.",
                            line_start=idx,
                            line_end=idx,
                            snippet=code,
                        )
                    )

    return violations




def check_file_handle_leak(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """fopen 호출 시 fclose 자원 해제 누락 리크를 스코프(함수) 단위로 검사합니다.

    개선: 파일 전역이 아닌, 각 함수 블록 안에서 fopen이 있으면
    해당 블록 안에 fclose가 있는지 독립적으로 확인합니다.
    """
    violations: list[Violation] = []
    content = parsed.content
    lines = content.splitlines()

    if "fopen(" not in content.lower():
        return []

    # 함수 블록 경계를 간이 추출 (void/int/string... funcName(...) { 패턴)
    func_pattern = re.compile(
        r'\b(?:void|int|bool|string|float|dyn_\w+|anytype)\s+([a-zA-Z_]\w*)\s*\([^)]*\)\s*\{',
        re.IGNORECASE,
    )
    func_regions: list[tuple[str, int, int]] = []  # (func_name, start_line, end_line)

    for m in func_pattern.finditer(content):
        func_name = m.group(1)
        brace_start = m.end()
        start_line = content[:m.start()].count('\n') + 1
        brace_count = 1
        pos = brace_start
        while pos < len(content) and brace_count > 0:
            if content[pos] == '{':
                brace_count += 1
            elif content[pos] == '}':
                brace_count -= 1
            pos += 1
        end_line = content[:pos].count('\n') + 1
        func_regions.append((func_name, start_line, end_line))

    # 함수 영역이 없으면 전체를 하나의 스코프로 취급
    if not func_regions:
        func_regions = [("<global>", 1, len(lines))]

    for func_name, s_line, e_line in func_regions:
        region_lines = lines[s_line - 1 : e_line]
        region_text = "\n".join(region_lines).lower()
        if "fopen(" in region_text and "fclose(" not in region_text:
            for offset, line in enumerate(region_lines):
                abs_line = s_line + offset
                if "fopen(" in line.lower():
                    violations.append(
                        Violation(
                            violation_id=f"V-{rule.rule_id}-{abs_line}",
                            rule_id=rule.rule_id,
                            file_id=str(parsed.file_path),
                            status=ViolationStatus.FAIL,
                            severity=rule.severity or SeverityLevel.HIGH,
                            message=rule.message or f"함수 '{func_name}' 내 fopen() 파일 핸들 오픈 후 동일 스코프에 fclose() 누락 (자원 누수 위험)",
                            line_start=abs_line,
                            line_end=abs_line,
                            snippet=line.strip(),
                        )
                    )
    return violations



def check_pnl_scope_leak(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """PNL 패널 스코프 변수 누수 및 모듈 스코프 이탈 참조 구문을 검사합니다."""
    violations: list[Violation] = []
    lines = parsed.content.splitlines()
    scope_leak_pattern = re.compile(r'\b(global\s+dyn_\w+|global\s+mapping)\s+([a-zA-Z_]\w*)', re.IGNORECASE)

    file_type_lower = (parsed.file_type or "").lower().lstrip(".")
    if file_type_lower in ("pnl", "xml"):
        for idx, line in enumerate(lines, start=1):
            clean_line = line.split("//")[0]
            match = scope_leak_pattern.search(clean_line)
            if match:
                var_name = match.group(2)
                violations.append(
                    Violation(
                        violation_id=f"V-{rule.rule_id}-{idx}",
                        rule_id=rule.rule_id,
                        file_id=str(parsed.file_path),
                        status=ViolationStatus.FAIL,
                        severity=rule.severity or SeverityLevel.MEDIUM,
                        message=rule.message or f"PNL 패널 내 동적 스코프 전역 변수 '{var_name}' 선언으로 메모리 누수 위험이 있습니다.",
                        line_start=idx,
                        line_end=idx,
                        snippet=line.strip(),
                    )
                )
    return violations




def check_missing_panel_on_close(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """ctl.missing_panel_on_close: Panel Close 이벤트 자원 해제 루틴 부재 검사."""
    violations: list[Violation] = []
    if (parsed.file_type or "").lower().lstrip(".") in ("pnl", "xml"):
        content_lower = parsed.content.lower()
        if "dpconnect(" in content_lower and "dpdisconnect(" not in content_lower and "panelclose" not in content_lower and "scopelib" not in content_lower:
            violations.append(
                Violation(
                    violation_id=f"V-{rule.rule_id}-001",
                    rule_id=rule.rule_id,
                    file_id=str(parsed.file_path),
                    status=ViolationStatus.FAIL,
                    severity=rule.severity or SeverityLevel.MEDIUM,
                    message="Panel 스크립트 내 dpConnect 등록이 존재하나 Panel Close 시 dpDisconnect 자원 해제 루틴이 누락되었습니다.",
                    line_start=1,
                    line_end=1,
                    snippet="Panel Close Handler missing",
                )
            )
    return violations



def check_unmatched_lock_unlock(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """ctl.unmatched_lock_unlock: 정적 락 언락 대응 미비 검사."""
    violations: list[Violation] = []
    content_lower = parsed.content.lower()
    if "lock(" in content_lower and "unlock(" not in content_lower:
        violations.append(
            Violation(
                violation_id=f"V-{rule.rule_id}-001",
                rule_id=rule.rule_id,
                file_id=str(parsed.file_path),
                status=ViolationStatus.FAIL,
                severity=rule.severity or SeverityLevel.HIGH,
                message="lock() 동기화 호출에 대응하는 unlock() 자원 해제 함수가 소스 내에서 발견되지 않습니다.",
                line_start=1,
                line_end=1,
                snippet="lock() without unlock()",
            )
        )
    return violations


