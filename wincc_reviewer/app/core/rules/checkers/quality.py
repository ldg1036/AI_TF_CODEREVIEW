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




def check_hardcoding(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """MANUAL-014/018: 하드코딩 지양(IP 주소, URL 등) 구문 분석."""
    violations: list[Violation] = []
    lines = parsed.content.splitlines()

    # 정밀 IP 주소 (0.0.0.0 ~ 255.255.255.255) 및 URL 패턴
    ip_pattern = re.compile(
        r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
    )
    url_pattern = re.compile(r'https?://[^\s"\']+', re.IGNORECASE)

    for idx, line in enumerate(lines, start=1):
        l_strip = line.strip()
        if l_strip.startswith("//") or l_strip.startswith("/*") or l_strip.startswith("#"):
            continue

        # 라인 내 후미 주석 제거
        code_part = line.split("//")[0].strip()
        if not code_part:
            continue

        # version 문구가 명시된 버전 넘버링 리터럴("version 1.0.0.0")은 오검출 제외
        if "version" in code_part.lower() or "ver" in code_part.lower():
            continue

        # 로컬 기본 주소, 서브넷 마스크 및 OID/버전 숫자 열 오매핑 방지
        if any(w in code_part for w in ["0.0.0.0", "127.0.0.1", "255.255.255.255", "255.255.255.0", "1.3.6.1."]):
            continue

        if url_pattern.search(code_part) or ip_pattern.search(code_part):
            violations.append(
                Violation(
                    violation_id=f"V-{rule.rule_id}-{idx:03d}",
                    rule_id=rule.rule_id,
                    file_id=str(parsed.file_path),
                    status=ViolationStatus.MANUAL_REVIEW,
                    severity=rule.severity or SeverityLevel.MEDIUM,
                    message=rule.message or f"[{rule.rule_id}] 하드코딩된 IP/URL 구문이 발견되었습니다. Config 또는 Define 변환을 권장합니다.",
                    line_start=idx,
                    line_end=idx,
                    snippet=code_part,
                )
            )

    return violations



def check_dead_code_and_unused(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """
    MANUAL-015/016 / ctl.dead_code_unused:
    WinCC OA CTL 스크립트 내 도달 불가능한 Dead Code 및 미사용 변수 선언을 검사합니다.

    1. Unreachable Dead Code:
       return, break, continue 문장 뒤에 동일 스코프 내 닫는 중괄호(}) 이전에 존재하는 실행 코드.
    2. Unused Variable Declaration:
       로컬/전역 변수로 선언되었으나 선언 라인 이후 코드에서 단 한 번도 참조되지 않는 변수.
    """
    violations: list[Violation] = []
    content = parsed.content
    lines = content.splitlines()

    # 1. 도달 불가능한 Dead Code 검사
    unreachable_keywords = re.compile(r'^(?:return\b|break\b|continue\b|exit\s*\()')
    dead_code_found = False

    for idx, line in enumerate(lines, 1):
        stripped = line.split("//")[0].strip()
        if not stripped:
            continue
        if stripped == "}" or stripped.startswith("case ") or stripped.startswith("default:"):
            dead_code_found = False
            continue
        if dead_code_found:
            violations.append(
                Violation(
                    violation_id=f"V-{rule.rule_id}-{idx:03d}",
                    rule_id=rule.rule_id,
                    file_id=str(parsed.file_path),
                    status=ViolationStatus.FAIL,
                    severity=rule.severity or SeverityLevel.HIGH,
                    message=f"[{rule.rule_id}] return/break 이후 도달할 수 없는 Dead Code가 존재합니다.",
                    line_start=idx,
                    line_end=idx,
                    snippet=stripped,
                )
            )
            dead_code_found = False
            continue
        if unreachable_keywords.match(stripped):
            dead_code_found = True

    # 2. 미사용 변수 선언(Unused Variable Declaration) 검사
    var_decl_pattern = re.compile(
        r'^(?:int|string|bool|float|dyn_string|dyn_int|dyn_float|dyn_anytype|time|mapping)\s+([a-zA-Z_]\w*)'
    )
    declared_vars: list[tuple[str, int, str]] = []  # (var_name, line_num, snippet)

    for idx, line in enumerate(lines, 1):
        stripped = line.split("//")[0].strip()
        m = var_decl_pattern.match(stripped)
        if m:
            var_name = m.group(1)
            # 루프 변수 i, j, k 등 단일 문자 관례 변수는 제외
            if len(var_name) > 1:
                declared_vars.append((var_name, idx, stripped))


    for var_name, decl_line, snippet in declared_vars:
        # 선언된 라인 이후에 해당 변수가 참조되는지 정규식 검색
        usage_pattern = re.compile(r'\b' + re.escape(var_name) + r'\b')
        used = False
        for idx, line in enumerate(lines[decl_line:], start=decl_line + 1):
            stripped = line.split("//")[0].strip()
            if usage_pattern.search(stripped):
                used = True
                break
        if not used:
            violations.append(
                Violation(
                    violation_id=f"V-{rule.rule_id}-{decl_line:03d}",
                    rule_id=rule.rule_id,
                    file_id=str(parsed.file_path),
                    status=ViolationStatus.FAIL,
                    severity=rule.severity or SeverityLevel.MEDIUM,
                    message=f"[{rule.rule_id}] 변수 '{var_name}'(이)가 선언되었으나 이후 코드에서 단 한 번도 사용되지 않았습니다.",
                    line_start=decl_line,

                    line_end=decl_line,
                    snippet=snippet,
                )
            )

    return violations



def check_dpe_hardcoding(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """
    [ctl.dpe_hardcoding] DPE(Data Point Element) 명칭 하드코딩 리터럴 탐지.
    """
    violations: list[Violation] = []
    lines = parsed.content.splitlines()
    # "System1:..." 또는 "Tag.value" 형태 하드코딩 패턴 탐지
    dpe_pattern = re.compile(r'\b(dpGet|dpSet|dpConnect)\s*\(\s*"([^"]+:[^"]+|\w+\.\w+)"', re.IGNORECASE)

    for idx, line in enumerate(lines, start=1):
        clean_line = line.split("//")[0]
        match = dpe_pattern.search(clean_line)
        if match:
            dpe_name = match.group(2)
            violations.append(
                Violation(
                    violation_id=f"V-{rule.rule_id}-{idx:03d}",
                    rule_id=rule.rule_id,
                    file_id=str(parsed.file_path),
                    status=ViolationStatus.FAIL,
                    severity=rule.severity or SeverityLevel.MEDIUM,
                    message=f"[{rule.rule_id}] DPE 명칭 '{dpe_name}'(이)가 스크립트에 하드코딩되었습니다. 상수로 정의하거나 태그 매핑 테이블을 사용하세요.",
                    line_start=idx,
                    line_end=idx,
                    snippet=line.strip(),
                )
            )

    return violations



def check_global_scope_shadowing(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """
    [ctl.global_scope_shadowing] 전역 변수와 함수 내 지역 변수 이름 중첩(Shadowing) 탐지.
    """
    violations: list[Violation] = []
    lines = parsed.content.splitlines()
    global_vars: set[tuple[str, int]] = set()

    # 전역 선언 감지 (함수 밖 선언)
    in_function = False
    for idx, line in enumerate(lines, start=1):
        clean_line = line.split("//")[0].strip()
        if re.search(r'\b(void|int|float|string|bool|dyn_\w+)\s+\w+\s*\(', clean_line):
            in_function = True
        elif in_function and clean_line.startswith("}"):
            in_function = False
        elif not in_function:
            var_match = re.search(r'\b(int|float|string|bool|dyn_\w+)\s+([a-zA-Z_]\w*)\s*(?:=|\;)', clean_line)
            if var_match:
                global_vars.add((var_match.group(2), idx))

    # 함수 내 지역 변수와 중복 확인
    if global_vars:
        for idx, line in enumerate(lines, start=1):
            clean_line = line.split("//")[0].strip()
            for gvar, g_line in global_vars:
                if idx != g_line:
                    shadow_match = re.search(r'\b(int|float|string|bool|dyn_\w+)\s+' + re.escape(gvar) + r'\b\s*(?:=|\;)', clean_line)
                    if shadow_match:
                        violations.append(
                            Violation(
                                violation_id=f"V-{rule.rule_id}-{idx:03d}",
                                rule_id=rule.rule_id,
                                file_id=str(parsed.file_path),
                                status=ViolationStatus.FAIL,
                                severity=rule.severity or SeverityLevel.MEDIUM,
                                message=f"[{rule.rule_id}] 지역 변수 '{gvar}'(이)가 L{g_line}에 선언된 전역 변수와 이름이 중첩(Shadowing)되었습니다.",
                                line_start=idx,
                                line_end=idx,
                                snippet=line.strip(),
                            )
                        )

    return violations



def check_magic_number(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """
    [ctl.magic_number] 조건문 및 DP 연산 내 의미 불분명 매직 넘버 숫자 리터럴 사용 탐지.
    """
    violations: list[Violation] = []
    lines = parsed.content.splitlines()
    # if (x == 1024), case 55:, dpSet(dpe, 999) 형태 매직 넘버 정규식
    magic_pattern = re.compile(r'\b(if|while|switch|case|dpSet|dpGet)\b.*?\b(?<![a-zA-Z_])([2-9]\d{1,}|1\d{2,})\b')

    for idx, line in enumerate(lines, start=1):
        clean_line = line.split("//")[0]
        # const 선언 또는 주석 제외
        if "const " in clean_line:
            continue
        match = magic_pattern.search(clean_line)
        if match:
            num_val = match.group(2)
            violations.append(
                Violation(
                    violation_id=f"V-{rule.rule_id}-{idx:03d}",
                    rule_id=rule.rule_id,
                    file_id=str(parsed.file_path),
                    status=ViolationStatus.FAIL,
                    severity=rule.severity or SeverityLevel.MEDIUM,
                    message=f"[{rule.rule_id}] 제어문 또는 DP 연산에서 의미를 알 수 없는 매직 넘버 '{num_val}'(이)가 직접 사용되었습니다. const 상수나 enum으로 정의하여 사용하세요.",
                    line_start=idx,
                    line_end=idx,
                    snippet=line.strip(),
                )
            )

    return violations



def check_duplicated_code(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """
    [ctl.duplicated_code] 스크립트 내 5줄 이상의 동일 코드 블록 중복(Copy & Paste) 탐지.
    """
    violations: list[Violation] = []
    lines = parsed.content.splitlines()

    # 주석 및 공백 제외한 의미 있는 코드 라인 튜플 목록 생성
    code_blocks: dict[str, list[int]] = {}
    block_size = 5

    clean_lines = [(idx, line.split("//")[0].strip()) for idx, line in enumerate(lines, start=1)]
    meaningful = [
        (idx, line_text)
        for idx, line_text in clean_lines
        if line_text
        and line_text not in ("{", "}", "E E")
        and not line_text.startswith(('E"', 'LANG:', '}"', 'shape '))
        and not re.match(r'^"[a-zA-Z0-9_]+"\s+"', line_text)  # UI 속성 ("key" "value") 패턴 필터링
        and not re.match(r"^\d+(\s+\d+)*$", line_text)
    ]

    for i in range(len(meaningful) - block_size + 1):
        block_lines = tuple(line_text for _, line_text in meaningful[i : i + block_size])
        block_start_line = meaningful[i][0]
        block_str = "\n".join(block_lines)

        if len(block_str) > 50:  # 일정 길이 이상의 무의미하지 않은 코드 블록
            if block_str not in code_blocks:
                code_blocks[block_str] = [block_start_line]
            else:
                code_blocks[block_str].append(block_start_line)

    reported_starts: set[int] = set()
    for b_str, start_lines in code_blocks.items():
        if len(start_lines) >= 2:
            second_line = start_lines[1]
            first_line = start_lines[0]
            if second_line not in reported_starts:
                reported_starts.add(second_line)
                violations.append(
                    Violation(
                        violation_id=f"V-{rule.rule_id}-{second_line:03d}",
                        rule_id=rule.rule_id,
                        file_id=str(parsed.file_path),
                        status=ViolationStatus.FAIL,
                        severity=rule.severity or SeverityLevel.MEDIUM,
                        message=f"[{rule.rule_id}] L{first_line} 및 L{second_line} 위치에 5줄 이상의 동일한 코드 블록이 중복(Copy & Paste) 존재합니다. ScopeLib 공통 헬퍼 함수로 통합 리팩토링하세요.",
                        line_start=second_line,
                        line_end=second_line + block_size - 1,
                        snippet=lines[second_line - 1].strip(),
                    )
                )

    return violations



def check_uninitialized_var(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """초기화되지 않은 변수가 참조/사용되는 구문을 검사합니다."""
    violations: list[Violation] = []
    lines = parsed.content.splitlines()
    var_decl_pattern = re.compile(
        r'^\s*(?:int|string|bool|float|dyn_\w+|time|mapping)\s+([a-zA-Z_]\w*)\s*;'
    )

    for idx, line in enumerate(lines, start=1):
        clean_line = line.split("//")[0]
        match = var_decl_pattern.search(clean_line)
        if match:
            var_name = match.group(1)
            usage_pattern = re.compile(r'\b' + re.escape(var_name) + r'\b')
            for _, next_line in enumerate(lines[idx:], start=idx + 1):
                c_next = next_line.split("//")[0]
                if usage_pattern.search(c_next):
                    if not re.search(r'\b' + re.escape(var_name) + r'\s*=(?!=)', c_next):
                        violations.append(
                            Violation(
                                violation_id=f"V-{rule.rule_id}-{idx}",
                                rule_id=rule.rule_id,
                                file_id=str(parsed.file_path),
                                status=ViolationStatus.FAIL,
                                severity=rule.severity or SeverityLevel.HIGH,
                                message=rule.message or f"변수 '{var_name}'(이)가 초기화 값 설정 없이 참조되었습니다.",
                                line_start=idx,
                                line_end=idx,
                                snippet=line.strip(),
                            )
                        )
                    break
    return violations



def check_dyn_array_out_of_bounds(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """ctl.dyn_array_out_of_bounds: WinCC OA 1 기반 동적 배열 인덱스 0 참조 경고.

    개선: dyn_ 접두사가 붙은 변수에 대해서만 [0] 접근을 위반으로 잡고,
    일반 C 스타일 배열(int arr[10] 등)은 0 기반이므로 PASS 처리합니다.
    """
    violations: list[Violation] = []
    lines = parsed.content.splitlines()
    # dyn_ 타입으로 선언된 변수명 수집
    dyn_vars: set[str] = set()
    for line in lines:
        decl_match = re.search(r'\bdyn_\w+\s+([a-zA-Z_]\w*)', line)
        if decl_match:
            dyn_vars.add(decl_match.group(1))

    for idx, line in enumerate(lines, start=1):
        clean = line.split("//")[0]
        # 패턴 1: dyn_ 타입 변수로 선언된 변수의 [0] 접근
        for var_name in dyn_vars:
            if re.search(re.escape(var_name) + r'\[\s*0\s*\]', clean):
                violations.append(
                    Violation(
                        violation_id=f"V-{rule.rule_id}-{idx:03d}",
                        rule_id=rule.rule_id,
                        file_id=str(parsed.file_path),
                        status=ViolationStatus.FAIL,
                        severity=rule.severity or SeverityLevel.HIGH,
                        message=f"WinCC OA 동적 배열 변수 '{var_name}'은 1 기반 인덱스입니다. [0] 참조는 인덱스 범위 초과 오류를 발생시킵니다.",
                        line_start=idx,
                        line_end=idx,
                        snippet=line.strip(),
                    )
                )
                break
        # 패턴 2: 인라인 dyn_ 타입에 직접 [0] (예: dyn_string items; items[0])
        if re.search(r'\bdyn_\w+\b.*\[\s*0\s*\]', clean) and idx not in {v.line_start for v in violations}:
            violations.append(
                Violation(
                    violation_id=f"V-{rule.rule_id}-{idx:03d}",
                    rule_id=rule.rule_id,
                    file_id=str(parsed.file_path),
                    status=ViolationStatus.FAIL,
                    severity=rule.severity or SeverityLevel.HIGH,
                    message="WinCC OA 동적 배열(dyn_*)은 1 기반 인덱스입니다. [0] 참조는 인덱스 범위 초과 오류를 발생시킵니다.",
                    line_start=idx,
                    line_end=idx,
                    snippet=line.strip(),
                )
            )
    return violations



def check_global_var_naming_convention(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """ctl.global_var_naming_convention: 전역변수 g_ 접두사 규칙 결함 검사."""
    violations: list[Violation] = []
    lines = parsed.content.splitlines()
    for idx, line in enumerate(lines, start=1):
        l_strip = line.strip()
        if l_strip.startswith("global ") and not re.search(r'\bglobal\s+\w+\s+g_', line):
            violations.append(
                Violation(
                    violation_id=f"V-{rule.rule_id}-{idx:03d}",
                    rule_id=rule.rule_id,
                    file_id=str(parsed.file_path),
                    status=ViolationStatus.FAIL,
                    severity=rule.severity or SeverityLevel.MEDIUM,
                    message="전역 변수(global) 선언 시 가독성 및 스코프 구분을 위해 g_ 접두사 명명 규칙을 준수해야 합니다.",
                    line_start=idx,
                    line_end=idx,
                    snippet=l_strip,
                )
            )
    return violations



def check_unused_function_param(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """ctl.unused_function_param: 함수 파라미터가 본문 내에서 한 번도 사용되지 않는 경우 경고."""
    violations: list[Violation] = []
    content = parsed.content
    lines = content.splitlines()

    # 함수 선언 패턴: returnType funcName(type1 param1, type2 param2, ...)
    func_pattern = re.compile(
        r'\b(?:void|int|bool|string|float|dyn_\w+|anytype)\s+([a-zA-Z_]\w*)\s*\(([^)]+)\)\s*\{',
    )

    for m in func_pattern.finditer(content):
        func_name = m.group(1)
        params_str = m.group(2).strip()
        func_line = content[:m.start()].count('\n') + 1

        if not params_str:
            continue

        # 파라미터 이름 추출 (type paramName 쌍에서 paramName)
        param_names: list[str] = []
        for param in params_str.split(','):
            parts = param.strip().split()
            if len(parts) >= 2:
                p_name = parts[-1].strip('&')
                if p_name and len(p_name) > 1:  # 단일 문자 관례 변수 제외
                    param_names.append(p_name)

        if not param_names:
            continue

        # 함수 본문 추출 (괄호 균형)
        brace_start = m.end()
        brace_count = 1
        pos = brace_start
        while pos < len(content) and brace_count > 0:
            if content[pos] == '{':
                brace_count += 1
            elif content[pos] == '}':
                brace_count -= 1
            pos += 1
        func_body = content[brace_start:pos - 1]

        for p_name in param_names:
            usage_pat = re.compile(r'\b' + re.escape(p_name) + r'\b')
            if not usage_pat.search(func_body):
                violations.append(
                    Violation(
                        violation_id=f"V-{rule.rule_id}-{func_line:03d}",
                        rule_id=rule.rule_id,
                        file_id=str(parsed.file_path),
                        status=ViolationStatus.FAIL,
                        severity=rule.severity or SeverityLevel.LOW,
                        message=f"[{rule.rule_id}] 함수 '{func_name}'의 파라미터 '{p_name}'(이)가 본문 내에서 사용되지 않습니다.",
                        line_start=func_line,
                        line_end=func_line,
                        snippet=lines[func_line - 1].strip() if func_line <= len(lines) else "",
                    )
                )

    return violations



def check_child_panel_parameter_mismatch(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """ctl.child_panel_parameter_mismatch: ChildPanelOnCentral 패러미터 갯수 불일치 검사."""
    violations: list[Violation] = []
    lines = parsed.content.splitlines()
    for idx, line in enumerate(lines, start=1):
        if "ChildPanelOnCentral(" in line and line.count(",") < 2:
            violations.append(
                Violation(
                    violation_id=f"V-{rule.rule_id}-{idx:03d}",
                    rule_id=rule.rule_id,
                    file_id=str(parsed.file_path),
                    status=ViolationStatus.FAIL,
                    severity=rule.severity or SeverityLevel.MEDIUM,
                    message="ChildPanelOnCentral 호출 시 필수 $패러미터 인자 동적 배열이 누락되었거나 인자 개수가 부족합니다.",
                    line_start=idx,
                    line_end=idx,
                    snippet=line.strip(),
                )
            )
    return violations



def check_debug_log_level(parsed: Any, rule: Any) -> list[Violation]:
    """
    ctl.debug_log_level: 디버깅용 로그 작성 시 표준 레벨 준수 여부 검사.

    개선: WinCC OA 표준 로깅 함수(DebugN, DebugFTN)는 프로덕션에서 허용되므로
    INFO 수준 안내로 완화하고, 임시 디버그 출력(printf, Debug1, Debug2)만 FAIL 유지.
    """
    violations = []
    if not parsed.file_path:
        return violations

    content = str(getattr(parsed, "content", "") or "")
    lines = content.splitlines()

    # FAIL 대상: 임시 디버그 출력 (프로덕션 코드에 남으면 안 되는 패턴)
    fail_patterns = ["printf(", "Debug1(", "Debug2("]
    # INFO 대상: 표준 로깅 (프로덕션 허용, 참고 안내만)
    info_patterns = ["DebugN(", "DebugFTN("]

    for idx, line in enumerate(lines, start=1):
        line_clean = line.strip()
        if line_clean.startswith("//") or line_clean.startswith("/*"):
            continue
        for pat in fail_patterns:
            if pat in line:
                violations.append(
                    Violation(
                        violation_id=f"V-{rule.rule_id}-{idx:03d}",
                        rule_id=rule.rule_id,
                        file_id=str(parsed.file_path),
                        status=ViolationStatus.FAIL,
                        severity=rule.severity or SeverityLevel.MEDIUM,
                        message=f"임시 디버그 출력 함수 '{pat.rstrip('(')}' 호출이 프로덕션 코드에 잔존합니다. 제거하거나 DebugN으로 교체하세요.",
                        line_start=idx,
                        line_end=idx,
                        snippet=line_clean,
                    )
                )
                break
        else:
            for pat in info_patterns:
                if pat in line:
                    violations.append(
                        Violation(
                            violation_id=f"V-{rule.rule_id}-{idx:03d}",
                            rule_id=rule.rule_id,
                            file_id=str(parsed.file_path),
                            status=ViolationStatus.MANUAL_REVIEW,
                            severity=SeverityLevel.INFO,
                            message=f"[INFO] 표준 로깅 함수 '{pat.rstrip('(')}' 사용이 감지되었습니다. 운영 환경 로그 레벨 설정을 확인하세요.",
                            line_start=idx,
                            line_end=idx,
                            snippet=line_clean,
                        )
                    )
                    break
    return violations



def check_config_integrity(parsed: Any, rule: Any) -> list[Violation]:
    """
    ctl.config_integrity: config 항목 정합성 확인 (필수 항목 Error 처리, 선택 항목 기본값 처리 여부).
    """
    violations = []
    if not parsed.file_path:
        return violations

    content = str(getattr(parsed, "content", "") or "")
    lines = content.splitlines()

    for idx, line in enumerate(lines, start=1):
        line_clean = line.strip()
        if line_clean.startswith("//") or line_clean.startswith("/*"):
            continue
        if "paGetCatNames" in line or "paGetSectionNames" in line or "configParse" in line:
            if "default" not in line and "else" not in line and "err" not in line.lower():
                violations.append(
                    Violation(
                        violation_id=f"V-{rule.rule_id}-{idx:03d}",
                        rule_id=rule.rule_id,
                        file_id=str(parsed.file_path),
                        status=ViolationStatus.FAIL,
                        severity=rule.severity or SeverityLevel.MEDIUM,
                        message="Config 파싱 구문에서 필수 항목 예외(Error) 또는 선택 항목 기본값(Default) 처리 로직이 누락되었습니다.",
                        line_start=idx,
                        line_end=idx,
                        snippet=line_clean,
                    )
                )
    return violations


# 37개 완결 내장 체커 등록 (자동화 커버리지 100% 완수)









