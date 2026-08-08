"""
Builtin Checker Registry (TRD §5.2 내장 checker registry 계약 준수).

내장 체커는 코드에 안전하게 등록된 검사 함수 목록이며,
IR(ParsedFile)과 RuleDefinition을 입력받아 list[Violation]을 반환합니다.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from app.core.models import RuleDefinition, SeverityLevel, Violation, ViolationStatus
from app.core.parser.base_parser import ParsedFile

CheckerFn = Callable[[ParsedFile, RuleDefinition], list[Violation]]


class CheckerRegistry:
    """Builtin 체커 레지스트리."""

    _registry: dict[str, CheckerFn] = {}

    @classmethod
    def register(cls, key: str, fn: CheckerFn) -> None:
        """체커 함수를 등록합니다."""
        cls._registry[key] = fn

    @classmethod
    def get(cls, key: str) -> CheckerFn | None:
        """등록된 체커 함수를 조회합니다."""
        return cls._registry.get(key)

    @classmethod
    def is_registered(cls, key: str) -> bool:
        """체커 키 존재 여부를 확인합니다."""
        return key in cls._registry

    @classmethod
    def list_registered(cls) -> list[str]:
        """등록된 전체 체커 키 목록을 반환합니다."""
        return sorted(cls._registry.keys())


# ────────────────────────────────────────────
# 내장 체커 구현 샘플 (TRD §5.2)
# ────────────────────────────────────────────



# PNL 화면 초기화 이벤트 컨텍스트 키워드 목록 (화면 종료 시 자동 해제되는 dpConnect 허용 대상)
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
    """MANUAL-003: 이벤트 교환 횟수 최소화 (일괄 dpGet/dpSet 처리 여부 구문 분석).

    분석 논리:
    - dpGet/dpSet 호출이 존재하는지 확인
    - 일괄 처리 패턴이 있으면 PASS: (1) 여러 인자를 한 번에 전달하는 dpGet(dp1,v1,dp2,v2,...) 패턴
      또는 (2) dynAppend(dpSet_dps,...) + setDpValue_block 배치 패턴
    - 인접한 15라인 이내의 코드 블록에서 단건 dpGet/dpSet만 3회 이상 연속 호출 시에만 FAIL (독립 단건 호출은 PASS)
    """
    violations: list[Violation] = []
    lines = parsed.content.splitlines()
    content_lower = parsed.content.lower()

    # dpGet/dpSet 호출이 아예 없으면 검사 불필요
    if "dpget(" not in content_lower and "dpset(" not in content_lower:
        return []

    # 일괄 처리 패턴 탐지
    has_batch_pattern = False

    # 패턴 1: dynAppend 배치 수집 + setDpValue_block 또는 dpSetTimedWait 일괄 호출
    if "dynappend(" in content_lower and ("setdpvalue_block" in content_lower or "dpsettimedwait" in content_lower):
        has_batch_pattern = True

    # 패턴 2: 다중 인자 dpGet/dpSet (한 호출에 인자 콤마 3개 이상 = 최소 2 DP 일괄)
    if not has_batch_pattern:
        for idx, line in enumerate(lines, start=1):
            l_strip = line.strip()
            if l_strip.startswith("//") or l_strip.startswith("/*"):
                continue
            if re.search(r'\bdpGet\s*\(', line) or re.search(r'\bdpSet\s*\(', line):
                stmt = ""
                for j in range(idx - 1, min(idx + 5, len(lines))):
                    stmt += lines[j]
                    if ";" in lines[j]:
                        break
                if stmt.count(",") >= 3:
                    has_batch_pattern = True
                    break

    if has_batch_pattern:
        # 일괄 처리가 잘 구현되어 있으므로 PASS (정상 준수 코드)
        return []

    # 단건 호출 라인 위치 및 내용 수집
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

    if not single_call_lines:
        return []

    # 인접 15라인 이내에 3회 이상 단건 호출이 나열된 연속 블록(클러스터) 그룹만 추출
    consecutive_clusters: set[int] = set()
    n = len(single_call_lines)
    for i in range(n):
        cluster_lines = [single_call_lines[i][0]]
        for j in range(i + 1, n):
            if single_call_lines[j][0] - cluster_lines[-1] <= 15:
                cluster_lines.append(single_call_lines[j][0])
            else:
                break
        if len(cluster_lines) >= 3:
            # cluster 내부에 if / else / case 등 조건문 분기로 나누어진 독립 호출인 경우 오매핑 제외
            start_l = max(0, cluster_lines[0] - 2)
            end_l = min(len(lines), cluster_lines[-1] + 1)
            region_text = "\n".join(lines[start_l:end_l]).lower()
            if region_text.count("else") >= 2 or region_text.count("case ") >= 2:
                continue
            for lno in cluster_lines:
                consecutive_clusters.add(lno)

    # 15라인 이내 3회 이상 연속 나열된 비효율 블록만 수동 검토 위반 지적
    for l_no, snip in single_call_lines:
        if l_no in consecutive_clusters:
            violations.append(
                Violation(
                    violation_id=f"V-{rule.rule_id}-{l_no:03d}",
                    rule_id=rule.rule_id,
                    file_id=str(parsed.file_path),
                    status=ViolationStatus.MANUAL_REVIEW,
                    severity=rule.severity or SeverityLevel.MEDIUM,
                    message=rule.message or f"[{rule.rule_id}] 인접 블록 내 단건 dpGet/dpSet 연속 3회 이상 호출로 이벤트 교환 횟수 과다. 일괄 처리(다중 인자 또는 dynAppend 배치)를 권장합니다.",
                    line_start=l_no,
                    line_end=l_no,
                    snippet=snip,
                )
            )

    return violations


def check_try_catch_exception(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """MANUAL-012: DP 함수 호출 시 try/catch 예외 처리 여부 구문 분석."""
    violations: list[Violation] = []
    lines = parsed.content.splitlines()
    content = parsed.content

    dp_func_pattern = re.compile(r'\b(dpSet|dpSetTimed|dpGet|dpQuery|dpQueryConnectSingle|dpConnect)\b', re.IGNORECASE)
    if not dp_func_pattern.search(content):
        return []

    # 주석 제거 후 try/catch 키워드 검사
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

            # 루프 블록 내 개별 dpGet / dpSet 감지 (dpGetMany, dpSetMany는 제외)
            if re.search(r'\bdpGet\s*\(', clean_line) and not re.search(r'\bdpGetMany\s*\(', clean_line):
                violations.append(
                    Violation(
                        violation_id=f"V-{rule.rule_id}-{idx:03d}",
                        rule_id=rule.rule_id,
                        file_id=str(parsed.file_path),
                        status=ViolationStatus.FAIL,
                        severity=rule.severity or SeverityLevel.HIGH,
                        message=f"[{rule.rule_id}] 루프문(L{loop_start_line}) 내부에서 개별 'dpGet' 통신 연산이 호출되었습니다. Event Manager 과부하 방지를 위해 dpGetMany 배치 연산을 사용하세요.",
                        line_start=idx,
                        line_end=idx,
                        snippet=line.strip(),
                    )
                )
            if re.search(r'\bdpSet\s*\(', clean_line) and not re.search(r'\bdpSetMany\s*\(', clean_line):
                violations.append(
                    Violation(
                        violation_id=f"V-{rule.rule_id}-{idx:03d}",
                        rule_id=rule.rule_id,
                        file_id=str(parsed.file_path),
                        status=ViolationStatus.FAIL,
                        severity=rule.severity or SeverityLevel.HIGH,
                        message=f"[{rule.rule_id}] 루프문(L{loop_start_line}) 내부에서 개별 'dpSet' 통신 연산이 호출되었습니다. Event Manager 과부하 방지를 위해 dpSetMany 배치 연산을 사용하세요.",
                        line_start=idx,
                        line_end=idx,
                        snippet=line.strip(),
                    )
                )

            # 루프 종결 감지
            if brace_depth <= 0 and "}" in clean_line:
                in_loop = False

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


def check_callback_error_handling(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """
    [ctl.callback_error_handling] 비동기 콜백 함수 내 에러 처리(getLastError/try-catch) 누락 탐지.
    """
    violations: list[Violation] = []
    content = parsed.content
    # dpConnect 사용 탐지
    dp_connects = re.finditer(r'\bdpConnect\s*\(\s*"([^"]+)"', content)

    for match in dp_connects:
        cb_name = match.group(1)
        line_no = content[: match.start()].count("\n") + 1

        # 콜백 함수 본문 탐지
        cb_func_match = re.search(r'\bvoid\s+' + re.escape(cb_name) + r'\s*\([^)]*\)\s*\{([^}]+)\}', content)
        if cb_func_match:
            cb_body = cb_func_match.group(1)
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
    meaningful = [(idx, line_text) for idx, line_text in clean_lines if line_text and line_text not in ("{", "}")]

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


def check_scada_security_exec(parsed_file: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """SCADA 외부 프로세스 시스템 명령 실행 패턴 감지 체커."""
    violations: list[Violation] = []
    lines = parsed_file.raw_content.splitlines() if parsed_file.raw_content else []
    unsafe_patterns = [r"\bsystem\s*\(", r"\bpopen\s*\(", r"\bexec\s*\(", r"\bCreateProcess\s*\("]

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue
        for pat in unsafe_patterns:
            if re.search(pat, line):
                violations.append(
                    Violation(
                        rule_id=rule.rule_id if rule else "SCADA_SEC_001",
                        file_path=str(parsed_file.file_path),
                        line_number=idx,
                        severity=SeverityLevel.CRITICAL,
                        message="SCADA 스크립트 내 검증되지 않은 외부 시스템 프로세스 실행 함수 감지 (명령 주입 위험)",
                        snippet=line.strip(),
                        status=ViolationStatus.OPEN,
                        confidence_score=0.95,
                    )
                )
                break
    return violations


def check_file_handle_leak(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """fopen 호출 시 fclose 자원 해제 누락 리크를 검사합니다."""
    violations: list[Violation] = []
    content = parsed.content
    lines = content.splitlines()

    if "fopen(" in content.lower() and "fclose(" not in content.lower():
        for idx, line in enumerate(lines, start=1):
            if "fopen(" in line.lower():
                violations.append(
                    Violation(
                        violation_id=f"V-{rule.rule_id}-{idx}",
                        rule_id=rule.rule_id,
                        file_id=str(parsed.file_path),
                        status=ViolationStatus.FAIL,
                        severity=rule.severity or SeverityLevel.HIGH,
                        message=rule.message or "fopen() 파일 핸들 오픈 후 fclose() 누락 자원 누수 위험",
                        line_start=idx,
                        line_end=idx,
                        snippet=line.strip(),
                    )
                )
    return violations


def check_sql_injection_risk(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """동적 문자열 조합 기반 쿼리 실행 보안 위험을 검사합니다."""
    violations: list[Violation] = []
    lines = parsed.content.splitlines()

    for idx, line in enumerate(lines, start=1):
        line_strip = line.strip()
        if line_strip.startswith("//") or line_strip.startswith("/*"):
            continue
        if re.search(r"\b(dpQuery|dbOpenNames)\s*\([^\)]*\+", line, re.IGNORECASE):
            violations.append(
                Violation(
                    violation_id=f"V-{rule.rule_id}-{idx}",
                    rule_id=rule.rule_id,
                    file_id=str(parsed.file_path),
                    status=ViolationStatus.FAIL,
                    severity=rule.severity or SeverityLevel.CRITICAL,
                    message=rule.message or "동적 문자열 동기 결합 SQL/dpQuery 보안 바인딩 미흡 위험",
                    line_start=idx,
                    line_end=idx,
                    snippet=line_strip,
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


# 기본 내장 체커 등록
CheckerRegistry.register("ctl.dp_connect_pair", check_dp_connect_pair)
CheckerRegistry.register("ctl.loop_delay", check_loop_delay)
CheckerRegistry.register("ctl.batch_dp_ops", check_batch_dp_operations)
CheckerRegistry.register("ctl.try_catch", check_try_catch_exception)
CheckerRegistry.register("ctl.hardcoding", check_hardcoding)
CheckerRegistry.register("ctl.dp_error_handling", check_dp_function_error_handling)
CheckerRegistry.register("ctl.dp_async", check_dp_async_handling)
CheckerRegistry.register("ctl.dp_callback_delay", check_dp_callback_delay)
CheckerRegistry.register("ctl.db_query_binding", check_db_query_binding)
CheckerRegistry.register("ctl.dead_code_unused", check_dead_code_and_unused)
CheckerRegistry.register("ctl.dp_in_loop", check_dp_in_loop)
CheckerRegistry.register("ctl.dpe_hardcoding", check_dpe_hardcoding)
CheckerRegistry.register("ctl.callback_error_handling", check_callback_error_handling)
CheckerRegistry.register("ctl.global_scope_shadowing", check_global_scope_shadowing)
CheckerRegistry.register("ctl.magic_number", check_magic_number)
CheckerRegistry.register("ctl.duplicated_code", check_duplicated_code)
CheckerRegistry.register("ctl.scada_security_exec", check_scada_security_exec)
CheckerRegistry.register("ctl.file_handle_leak", check_file_handle_leak)
CheckerRegistry.register("ctl.sql_injection_risk", check_sql_injection_risk)
CheckerRegistry.register("ctl.uninitialized_var", check_uninitialized_var)
CheckerRegistry.register("ctl.pnl_scope_leak", check_pnl_scope_leak)







