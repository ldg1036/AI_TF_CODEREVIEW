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




def check_scada_security_exec(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """SCADA 외부 프로세스 시스템 명령 실행 패턴 감지 체커."""
    violations: list[Violation] = []
    content = getattr(parsed, "content", "") or ""
    lines = content.splitlines()
    unsafe_patterns = [r"\bsystem\s*\(", r"\bpopen\s*\(", r"\bexec\s*\(", r"\bCreateProcess\s*\("]

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue
        for pat in unsafe_patterns:
            if re.search(pat, line):
                violations.append(
                    Violation(
                        violation_id=f"V-{rule.rule_id}-{idx:03d}",
                        rule_id=rule.rule_id,
                        file_id=str(parsed.file_path),
                        status=ViolationStatus.FAIL,
                        severity=rule.severity or SeverityLevel.CRITICAL,
                        message="SCADA 스크립트 내 검증되지 않은 외부 시스템 프로세스 실행 함수 감지 (명령 주입 위험)",
                        line_start=idx,
                        line_end=idx,
                        snippet=line.strip(),
                    )
                )
                break
    return violations



from app.core.rules.dfa_engine import TaintTracker

def check_sql_injection_risk(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """동적 문자열 조합 기반 쿼리 실행 보안 위험을 DFA(Taint 추적) 기반으로 정밀 검사합니다."""
    if parsed.file_path and parsed.file_path.name in ("bench_0005.pnl", "bench_0004.pnl", "bench_0005.ctl", "bench_0001.ctl"):
        print(f"[DEBUG-SECURITY-ENTER] check_sql_injection_risk entered for {parsed.file_path.name}")
    
    violations: list[Violation] = []
    
    # 주석 제거된 코드 라인 추출
    clean_lines: list[tuple[int, str]] = []
    in_block_comment = False
    for idx, line in enumerate(parsed.content.splitlines(), start=1):
        l_strip = line.strip()
        if in_block_comment:
            if "*/" in l_strip:
                in_block_comment = False
            continue
        if l_strip.startswith("/*"):
            if "*/" not in l_strip:
                in_block_comment = True
            continue
        if l_strip.startswith("//") or not l_strip:
            continue
        code_part = line.split("//")[0].strip()
        if code_part:
            clean_lines.append((idx, code_part))
            
    # DFA 엔진(TaintTracker) 초기화
    # 소스(위험 외부 입력): dpGet, ui_getText 등 외부 값 반환 함수 가정
    # 싱크(쿼리 실행부): dpQuery, dbOpenNames, dbExecuteQuery
    tracker = TaintTracker(
        sources=["getUserText", "dpGet", "ui_getText", "recv"],
        sinks=["dpQuery", "dbOpenNames", "dbExecuteQuery", "dbExecute"]
    )
    
    # 1차적으로 Taint 추적 실행
    dfa_violations = tracker.track(clean_lines)
    
    for idx, snippet in dfa_violations:
        violations.append(
            Violation(
                violation_id=f"V-{rule.rule_id}-{idx:03d}",
                rule_id=rule.rule_id,
                file_id=str(parsed.file_path),
                status=ViolationStatus.FAIL,
                severity=rule.severity or SeverityLevel.CRITICAL,
                message=rule.message or "DFA Taint 추적: 외부 오염 데이터가 검증 없이 SQL/dpQuery 함수의 인자로 유입되었습니다.",
                line_start=idx,
                line_end=idx,
                snippet=snippet,
            )
        )
        
    # 기존 레거시: 동적 결합(+) 기반 검출 로직 (정규식 기반 보완)
    # TaintTracker가 놓친 단순 리터럴 인젝션 등 방어용
    dfa_idx_set = {v[0] for v in dfa_violations}
    for idx, snippet in clean_lines:
        if idx in dfa_idx_set:
            continue
        if re.search(r"\b(dpQuery|dbOpenNames)\s*\([^\)]*\+", snippet, re.IGNORECASE):
            violations.append(
                Violation(
                    violation_id=f"V-{rule.rule_id}-{idx:03d}",
                    rule_id=rule.rule_id,
                    file_id=str(parsed.file_path),
                    status=ViolationStatus.FAIL,
                    severity=rule.severity or SeverityLevel.CRITICAL,
                    message=rule.message or "동적 문자열 동기 결합 SQL/dpQuery 보안 바인딩 미흡 위험",
                    line_start=idx,
                    line_end=idx,
                    snippet=snippet,
                )
            )

    return violations



def check_file_open_mode_check(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """ctl.file_open_mode_check: fopen 접근 모드 유효성 검사."""
    violations: list[Violation] = []
    lines = parsed.content.splitlines()
    for idx, line in enumerate(lines, start=1):
        if "fopen(" in line and not re.search(r'fopen\s*\([^,]+,\s*"[rwa]\+?[bt]?"\s*\)', line):
            violations.append(
                Violation(
                    violation_id=f"V-{rule.rule_id}-{idx:03d}",
                    rule_id=rule.rule_id,
                    file_id=str(parsed.file_path),
                    status=ViolationStatus.FAIL,
                    severity=rule.severity or SeverityLevel.MEDIUM,
                    message="fopen 파일 오픈 함수 호출 시 올바르지 않거나 불명확한 파일 접근 모드 문자열이 지정되었습니다.",
                    line_start=idx,
                    line_end=idx,
                    snippet=line.strip(),
                )
            )
    return violations



def check_sprintf_buffer_overflow_risk(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
    """ctl.sprintf_buffer_overflow_risk: sprintf 문자열 포맷 버퍼 오버플로우 위험 검사."""
    violations: list[Violation] = []
    lines = parsed.content.splitlines()
    for idx, line in enumerate(lines, start=1):
        if re.search(r'\bsprintf\s*\(\s*\w+\s*,\s*"[^"]*%s[^"]*"', line):
            violations.append(
                Violation(
                    violation_id=f"V-{rule.rule_id}-{idx:03d}",
                    rule_id=rule.rule_id,
                    file_id=str(parsed.file_path),
                    status=ViolationStatus.FAIL,
                    severity=rule.severity or SeverityLevel.HIGH,
                    message="sprintf 구문 내 동적 %s 포맷 사용으로 버퍼 오버플로우 위험이 있습니다. snprintf 또는 안전 포맷 함수를 사용하십시오.",
                    line_start=idx,
                    line_end=idx,
                    snippet=line.strip(),
                )
            )
    return violations


