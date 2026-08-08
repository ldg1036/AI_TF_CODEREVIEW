"""
RuleEngine 및 확장자 라우터 유닛 테스트 (03_정적분석_룰카탈로그.md & TRD §5.2 기준).

검증 항목:
1. 확장자 기반 자동 분류 (.pnl, .xml -> client / .ctl -> server)
2. 사용자 지정 수동 선택 (Override) 지원
3. parse_failed IR 안전 스킵 (빈 Violation 목록 반환, 예외 발생 0건)
4. disabled 룰 스킵
5. MANUAL_REVIEW 체커 실행 및 ViolationStatus.MANUAL_REVIEW 반환
6. Builtin 체커 성공 및 unsupported_checker 에러 처리
7. REGEX 체커 매칭 및 line_start 위치 산출
"""

from __future__ import annotations

from pathlib import Path
import pytest

from app.core.models import CheckerType, ParseStatus, ParseStatusType, RuleDefinition, SeverityLevel, ViolationStatus
from app.core.parser.base_parser import ParsedFile
from app.core.rules.rule_engine import RuleEngine


class TestRuleEngine:
    """RuleEngine 및 확장자 라우팅 유닛 테스트."""

    def test_determine_target_ruleset_auto(self):
        """확장자에 따른 타겟 룰셋 자동 분류 테스트."""
        assert RuleEngine.determine_target_ruleset(Path("panel.pnl")) == "client"
        assert RuleEngine.determine_target_ruleset(Path("config.xml")) == "client"
        assert RuleEngine.determine_target_ruleset(Path("script.ctl")) == "server"

    def test_determine_target_ruleset_override(self):
        """사용자 지정 수동 오버라이드 테스트."""
        assert RuleEngine.determine_target_ruleset(Path("script.ctl"), override_target="client") == "client"
        assert RuleEngine.determine_target_ruleset(Path("panel.pnl"), override_target="server") == "server"

    def test_execute_parse_failed_skip(self):
        """parse_failed 상태인 IR은 예외 없이 빈 Violation 반환 (DoD 114행)."""
        failed_parsed = ParsedFile(
            file_path=Path("broken.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSE_FAILED, file="broken.ctl", error_message="구조 분석 오류"),
            content="invalid code",
        )
        rule = RuleDefinition(
            rule_id="CTL-RES-001",
            source_key="성능|시스템|메모리",
            file_types=["CTL"],
            checker_type=CheckerType.MANUAL,
            enabled=True,
            rule_version="1.0.0",
        )

        violations = RuleEngine.execute(failed_parsed, [rule])
        assert len(violations) == 0, "parse_failed IR에 대해 빈 Violation 목록이 반환되어야 합니다."

    def test_execute_disabled_rule(self):
        """비활성화(enabled=False)된 룰 스킵 테스트."""
        parsed = ParsedFile(
            file_path=Path("sample.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED),
            content="main() { dpConnect('cb', 'dpe'); }",
        )
        disabled_rule = RuleDefinition(
            rule_id="CTL-RES-001",
            source_key="성능|시스템|메모리",
            file_types=["CTL"],
            checker_type=CheckerType.MANUAL,
            enabled=False,
            rule_version="1.0.0",
        )

        violations = RuleEngine.execute(parsed, [disabled_rule])
        assert len(violations) == 0

    def test_execute_manual_review_rule(self):
        """MANUAL_REVIEW 체커 타입 룰 실행 테스트."""
        parsed = ParsedFile(
            file_path=Path("sample.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED),
            content="main() {}",
        )
        manual_rule = RuleDefinition(
            rule_id="MANUAL-001",
            source_key="공통|예외처리|Try, Catch 예외처리",
            file_types=["CTL"],
            checker_type=CheckerType.MANUAL,
            enabled=True,
            rule_version="1.0.0",
            check_item="Try, Catch 예외처리",
            condition="함수 내에 Try, Catch 예외 처리가 되어 있는가?",
            message="[MANUAL_REVIEW] Try, Catch 예외처리 확인 필요",
        )

        violations = RuleEngine.execute(parsed, [manual_rule])
        assert len(violations) == 1
        v = violations[0]
        assert v.status == ViolationStatus.MANUAL_REVIEW
        assert v.rule_id == "MANUAL-001"
        assert "[MANUAL_REVIEW]" in v.message

    def test_execute_builtin_rule_success(self):
        """Builtin 체커(ctl.dp_connect_pair) 성공적 실행 및 위반 검출 테스트."""
        # dpConnect는 있으나 dpDisconnect가 없는 지적 대상 코드
        parsed = ParsedFile(
            file_path=Path("sample.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED),
            content="main() {\n    dpConnect('cbTemp', 'Sys1:Tank.Temp');\n}",
        )
        builtin_rule = RuleDefinition(
            rule_id="CTL-RES-001",
            source_key="성능|시스템|콜백해제",
            file_types=["CTL"],
            checker_type=CheckerType.BUILTIN,
            enabled=True,
            rule_version="1.0.0",
            checker_key="ctl.dp_connect_pair",
            severity=SeverityLevel.CRITICAL,
            message="dpConnect 대응 dpDisconnect 누락",
        )

        violations = RuleEngine.execute(parsed, [builtin_rule])
        assert len(violations) == 1
        v = violations[0]
        assert v.status == ViolationStatus.FAIL
        assert v.severity == SeverityLevel.CRITICAL
        assert v.rule_id == "CTL-RES-001"

    def test_execute_builtin_rule_unsupported(self):
        """등록되지 않은 내장 체커 키 사용 시 ERROR 반환 검증."""
        parsed = ParsedFile(
            file_path=Path("sample.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED),
            content="main() {}",
        )
        unsupported_rule = RuleDefinition(
            rule_id="CTL-UNKNOWN-001",
            source_key="기타|미등록",
            file_types=["CTL"],
            checker_type=CheckerType.BUILTIN,
            enabled=True,
            rule_version="1.0.0",
            checker_key="ctl.non_existent_checker",
        )

        violations = RuleEngine.execute(parsed, [unsupported_rule])
        assert len(violations) == 1
        v = violations[0]
        assert v.status == ViolationStatus.ERROR
        assert "unsupported_checker" in v.message

    def test_execute_regex_rule(self):
        """REGEX 체커 정규식 패턴 매칭 및 라인 위치 산출 테스트."""
        # 3행에 전역변수 g_counter 사용
        code = "int local_var = 0;\n\nint g_counter = 100;\nmain() {}"
        parsed = ParsedFile(
            file_path=Path("sample.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED),
            content=code,
        )
        regex_rule = RuleDefinition(
            rule_id="CTL-NAM-001",
            source_key="공통|네이밍|전역변수",
            file_types=["CTL"],
            checker_type=CheckerType.REGEX,
            enabled=True,
            rule_version="1.0.0",
            pattern=r"\bg_([a-zA-Z0-9_]+)",
            severity=SeverityLevel.MEDIUM,
            message="전역변수 사용 위반",
        )

        violations = RuleEngine.execute(parsed, [regex_rule])
        assert len(violations) == 1
        v = violations[0]
        assert v.status == ViolationStatus.FAIL
        assert v.line_start == 3
        assert "g_counter" in v.snippet

    def test_manual_004_callback_delay(self):
        """MANUAL-004: 콜백 함수 내 delay 존재 시 위반 검출, 미존재 시 PASS 검증."""
        # 1. 콜백 함수 내 delay가 존재하는 미준수 코드
        bad_code = """
main() {
    dpConnect("workCB", "Sys:Tag1.val");
}

void workCB(string dpe, int val) {
    delay(1); // 비동기 지연 발생
}
"""
        parsed_bad = ParsedFile(
            file_path=Path("bad.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED),
            content=bad_code,
        )
        rule_004 = RuleDefinition(
            rule_id="MANUAL-004",
            source_key="성능|시스템|적절한 DP 처리 함수 사용",
            file_types=["CTL"],
            checker_type=CheckerType.MANUAL,
            enabled=True,
            rule_version="1.0.0",
            check_item="적절한 DP 처리 함수 사용",
            condition="DP 감시 유형에 맞는 DP 함수를 처리하였는가?",
        )

        violations_bad = RuleEngine.execute(parsed_bad, [rule_004])
        assert len(violations_bad) == 1
        assert violations_bad[0].status == ViolationStatus.MANUAL_REVIEW
        assert "workCB" in violations_bad[0].message
        assert violations_bad[0].line_start == 7

        # 2. 콜백 함수 내 delay가 없는 정상 코드 (PASS)
        good_code = """
main() {
    dpConnect("workCB", "Sys:Tag1.val");
}

void workCB(string dpe, int val) {
    int result = val * 2;
}
"""
        parsed_good = ParsedFile(
            file_path=Path("good.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED),
            content=good_code,
        )

        violations_good = RuleEngine.execute(parsed_good, [rule_004])
        assert len(violations_good) == 0, "콜백 내 delay가 없는 경우 검출되지 않아야 합니다."

    def test_manual_002_loop_delay_cases(self):
        """MANUAL-002: loop문 내 delay 존재 시 PASS, 누락 및 Active 내부 갇힘 시 위반 검출."""
        rule_002 = RuleDefinition(
            rule_id="MANUAL-002",
            source_key="성능|시스템|Loop문 내에 처리 조건",
            file_types=["CTL"],
            checker_type=CheckerType.MANUAL,
            enabled=True,
            rule_version="1.0.0",
            check_item="Loop문 내에 처리 조건",
            condition="반복문(while) 내부에 delay 처리를 하였는가?",
        )

        # 1. delay가 포함된 정상 무한 루프 (PASS)
        code_pass = """
main() {
    while(true) {
        delay(1);
        int a = 1;
    }
}
"""
        parsed_pass = ParsedFile(
            file_path=Path("pass.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED),
            content=code_pass,
        )
        assert len(RuleEngine.execute(parsed_pass, [rule_002])) == 0

        # 2. 동적 배열 단순 순회 for문 (PASS)
        code_for_pass = """
main() {
    dyn_string list = makeDynString("a", "b");
    for(int i = 1; i <= dynlen(list); i++) {
        DebugN(list[i]);
    }
}
"""
        parsed_for_pass = ParsedFile(
            file_path=Path("for_pass.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED),
            content=code_for_pass,
        )
        assert len(RuleEngine.execute(parsed_for_pass, [rule_002])) == 0

        # 3. delay가 누락된 무한 루프 (FAIL/MANUAL_REVIEW 검출)
        code_fail = """
main() {
    while(true) {
        int a = 1;
    }
}
"""
        parsed_fail = ParsedFile(
            file_path=Path("fail.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED),
            content=code_fail,
        )
        v_fail = RuleEngine.execute(parsed_fail, [rule_002])
        assert len(v_fail) == 1
        assert "delay() 구문이 누락" in v_fail[0].message

        # 4. delay가 Active 조건문 안쪽에만 작성되어 Passive 시 무한 회전 우려가 있는 케이스 (검출)
        code_active_only = """
main() {
    while(true) {
        if(isRedundantActive()) {
            delay(1);
            work();
        }
    }
}
"""
        parsed_active_only = ParsedFile(
            file_path=Path("active_only.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED),
            content=code_active_only,
        )
        v_active = RuleEngine.execute(parsed_active_only, [rule_002])
        assert len(v_active) == 1
        assert "Active 조건문 내부에만" in v_active[0].message

    def test_manual_007_db_query_binding_cases(self):
        """MANUAL-007: DB Query 바인딩 쿼리 검사 (오검출 방지 및 정상 위반 검출 테스트)."""
        rule_007 = RuleDefinition(
            rule_id="MANUAL-007",
            source_key="성능|DB|바인딩 쿼리 처리",
            file_types=["CTL"],
            checker_type=CheckerType.MANUAL,
            enabled=True,
            rule_version="1.0.0",
            check_item="바인딩 쿼리 처리",
            condition="DB Query를 바인딩 쿼리로 작성하였는가?",
            message="[MANUAL_REVIEW] 바인딩 쿼리 처리: 1) DB Query를 바인딩 쿼리로 작성하였는가?",
        )

        # 1. DB 쿼리 실행이 전혀 없는 일반 스크립트 (PASS)
        code_normal = """
main() {
    int count = 10;
    string title = "Select File: " + getFileName();
    DebugN(title);
}
"""
        parsed_normal = ParsedFile(
            file_path=Path("normal.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED),
            content=code_normal,
        )
        assert len(RuleEngine.execute(parsed_normal, [rule_007])) == 0, "DB 쿼리가 없는 일반 코드는 PASS 처리되어야 함"

        # 2. 주석에만 SQL 문자열 동적 결합이 포함된 경우 (PASS)
        code_comment = """
main() {
    // string sql = "SELECT * FROM table WHERE id = " + id;
    int a = 1;
}
"""
        parsed_comment = ParsedFile(
            file_path=Path("comment.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED),
            content=code_comment,
        )
        assert len(RuleEngine.execute(parsed_comment, [rule_007])) == 0, "주석 내 구문은 위반으로 검출되지 않아야 함"

        # 3. 미준수 동적 SQL 문자열 결합 ("SELECT ... FROM " + var) (위반 검출)
        code_unbound = """
main() {
    string sql = "SELECT * FROM users WHERE name = '" + userName + "'";
    dbExecuteQuery(sql);
}
"""
        parsed_unbound = ParsedFile(
            file_path=Path("unbound.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED),
            content=code_unbound,
        )
        v_unbound = RuleEngine.execute(parsed_unbound, [rule_007])
        assert len(v_unbound) == 1, "동적 SQL 문자열 결합 구문은 검출되어야 함"
        assert v_unbound[0].status == ViolationStatus.MANUAL_REVIEW
        assert v_unbound[0].line_start == 3

    def test_manual_001_dp_connect_pair_with_comments(self):
        """MANUAL-001: 주석 처리된 dpDisconnect 구문으로 인한 오검출/누락 방지 테스트."""
        rule_001 = RuleDefinition(
            rule_id="CTL-RES-001",
            source_key="자원|DP|dpConnect 짝점검",
            file_types=["CTL"],
            checker_type=CheckerType.BUILTIN,
            checker_key="ctl.dp_connect_pair",
            enabled=True,
            rule_version="1.0.0",
        )

        # 주석에만 dpDisconnect가 기재된 미준수 코드 (FAIL로 위반 검출되어야 함)
        code = """
main() {
    dpConnect("myCB", "Sys:Tag1.val");
    // dpDisconnect("myCB", "Sys:Tag1.val");
}
"""
        parsed = ParsedFile(
            file_path=Path("sample.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED),
            content=code,
        )
        violations = RuleEngine.execute(parsed, [rule_001])
        assert len(violations) == 1, "주석 내 dpDisconnect는 해제 처리로 간주되지 않아야 합니다."

    def test_manual_014_hardcoding_version_string(self):
        """MANUAL-014: 버전 정보 리터럴(v1.0.0.0)의 IP 주소 오검출 방지 테스트."""
        rule_014 = RuleDefinition(
            rule_id="MANUAL-014",
            source_key="품질|하드코딩",
            file_types=["CTL"],
            checker_type=CheckerType.MANUAL,
            enabled=True,
            rule_version="1.0.0",
        )

        code = """
main() {
    string app_version = "version 1.0.0.0";
    DebugN(app_version);
}
"""
        parsed = ParsedFile(
            file_path=Path("sample.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED),
            content=code,
        )
        violations = RuleEngine.execute(parsed, [rule_014])
        assert len(violations) == 0, "버전 번호 리터럴은 IP 하드코딩으로 오검출되지 않아야 합니다."

    def test_execute_file_types_mismatch_skip(self):
        """대상 파일 타입 불일치 시 위반 오매핑 방지 테스트."""
        parsed = ParsedFile(
            file_path=Path("panel.pnl"),
            file_type="pnl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED),
            content="main() { int a = 10; }",
        )
        ctl_only_rule = RuleDefinition(
            rule_id="CTL-TEST-001",
            source_key="테스트|CTL전용",
            file_types=["CTL"],
            checker_type=CheckerType.MANUAL,
            enabled=True,
            rule_version="1.0.0",
        )
        violations = RuleEngine.execute(parsed, [ctl_only_rule])
        assert len(violations) == 0, "CTL 전용 룰이 PNL 파일에 실행되어 오매핑되지 않아야 합니다."

    def test_manual_001_non_control_file_skip(self):
        """제어/감시 로직 없는 단순 유틸리티 파일에 대한 MANUAL-001 오매핑 방지 테스트."""
        code = "int calc_sum(int a, int b) { return a + b; }"
        parsed = ParsedFile(
            file_path=Path("utils.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED),
            content=code,
        )
        manual_rule = RuleDefinition(
            rule_id="MANUAL-001",
            source_key="이중화|Active조건",
            file_types=["CTL"],
            checker_type=CheckerType.MANUAL,
            enabled=True,
            rule_version="1.0.0",
            check_item="Active 이중화 조건",
        )
        violations = RuleEngine.execute(parsed, [manual_rule])
        assert len(violations) == 0, "이중화 제어 로직이 불필요한 유틸리티 파일은 MANUAL-001로 오매핑되지 않아야 합니다."

    def test_manual_014_hardcoding_local_ip_skip(self):
        """로컬 루프백 및 서브넷 마스크 IP에 대한 하드코딩 오매핑 방지 테스트."""
        code = """
main() {
    string local_ip = "127.0.0.1";
    string mask = "255.255.255.0";
}
"""
        parsed = ParsedFile(
            file_path=Path("config.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED),
            content=code,
        )
        rule = RuleDefinition(
            rule_id="MANUAL-014",
            source_key="품질|하드코딩",
            file_types=["CTL"],
            checker_type=CheckerType.MANUAL,
            enabled=True,
            rule_version="1.0.0",
        )
        violations = RuleEngine.execute(parsed, [rule])
        assert len(violations) == 0, "로컬 기본 주소 및 서브넷 마스크는 하드코딩 위반으로 오매핑되지 않아야 합니다."

    def test_try_catch_alternative_error_handling_skip(self):
        """getLastError 등 대안 에러 처리가 구현된 함수에 대한 MANUAL-012 오매핑 방지 테스트."""
        code = """
void readTag() {
    dpGet("Sys1:Tag.val", val);
    if (getLastError() != 0) {
        DebugN("dpGet Error");
    }
}
"""
        parsed = ParsedFile(
            file_path=Path("sample.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED),
            content=code,
        )
        rule = RuleDefinition(
            rule_id="MANUAL-012",
            source_key="예외처리|try-catch",
            file_types=["CTL"],
            checker_type=CheckerType.BUILTIN,
            checker_key="ctl.try_catch",
            enabled=True,
            rule_version="1.0.0",
        )
        violations = RuleEngine.execute(parsed, [rule])
        assert len(violations) == 0, "getLastError로 에러 처리를 수행한 코드는 try/catch 위반으로 오매핑되지 않아야 합니다."

    def test_loop_delay_while_finite_skip(self):
        """while 유한 카운트 반복문에 대한 MANUAL-002 무한 루프 delay 누락 오매핑 방지 테스트."""
        code = """
main() {
    int i = 0;
    while(i < count) {
        i++;
    }
}
"""
        parsed = ParsedFile(
            file_path=Path("sample.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED),
            content=code,
        )
        rule = RuleDefinition(
            rule_id="MANUAL-002",
            source_key="성능|시스템|Loop문 내에 처리 조건",
            file_types=["CTL"],
            checker_type=CheckerType.BUILTIN,
            checker_key="ctl.loop_delay",
            enabled=True,
            rule_version="1.0.0",
        )
        violations = RuleEngine.execute(parsed, [rule])
        assert len(violations) == 0, "유한 반복문은 무한 루프 delay 위반으로 오매핑되지 않아야 합니다."



