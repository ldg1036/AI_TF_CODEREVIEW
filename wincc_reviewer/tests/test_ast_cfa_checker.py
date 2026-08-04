"""
AST 기반 심층 제어 흐름 분석(Control Flow Analysis) 유닛 테스트 (test_ast_cfa_checker.py).
03_정적분석_룰카탈로그.md §13 & 05_개발로드맵 Phase 9 수용 검증.
"""

from pathlib import Path

from app.core.models import ParseStatus, ParseStatusType, SeverityLevel
from app.core.parser.base_parser import ParsedFile
from app.core.rules.ast_cfa_checker import ASTControlFlowChecker
from app.core.rules.rule_engine import RuleEngine


def _make_parsed(code: str) -> ParsedFile:
    return ParsedFile(
        file_path=Path("test.ctl"),
        file_type="ctl",
        parse_status=ParseStatus(status=ParseStatusType.PARSED),
        content=code,
    )


def test_dp_callback_resolve_missing_symbol():
    """dpConnect에 지정된 콜백이 선언되지 않았을 때 HIGH 심각도 위반 발생 검증."""
    code = """
    void main() {
        dpConnect("unresolved_cb", false, "System1:Valve.state");
    }
    """
    parsed = _make_parsed(code)
    violations = ASTControlFlowChecker.run_ast_cfa_checks(parsed)

    resolve_vs = [v for v in violations if v.rule_id == "CTL-AST-CFA-001"]
    assert len(resolve_vs) == 1
    assert resolve_vs[0].severity == SeverityLevel.HIGH
    assert "unresolved_cb" in resolve_vs[0].message


def test_callback_signature_insufficient_params():
    """콜백 함수 매개변수가 2개 미만일 때 MEDIUM 심각도 위반 발생 검증."""
    code = """
    void my_cb(string dp) {
        // 인자가 1개뿐이므로 WinCC OA 이벤트 시그니처 불일치
    }
    void main() {
        dpConnect("my_cb", false, "System1:Valve.state");
    }
    """
    parsed = _make_parsed(code)
    violations = ASTControlFlowChecker.run_ast_cfa_checks(parsed)

    sig_vs = [v for v in violations if v.rule_id == "CTL-AST-CFA-002"]
    assert len(sig_vs) == 1
    assert sig_vs[0].severity == SeverityLevel.MEDIUM
    assert "my_cb" in sig_vs[0].message
    assert "매개변수가 1개입니다" in sig_vs[0].message


def test_loop_reachability_infinite_loop_without_exit():
    """while(true) 내부에서 break/return 탈출문이 없을 때 HIGH 심각도 위반 검증."""
    code = """
    void monitor() {
        while (true) {
            dpGet("System1:Valve.state", val);
            // 탈출 조건문 break나 return이 없음 -> 데드락 위험
        }
    }
    """
    parsed = _make_parsed(code)
    violations = ASTControlFlowChecker.run_ast_cfa_checks(parsed)

    loop_vs = [v for v in violations if v.rule_id == "CTL-AST-CFA-003"]
    assert len(loop_vs) == 1
    assert loop_vs[0].severity == SeverityLevel.HIGH
    assert "무한 루프" in loop_vs[0].message


def test_loop_reachability_with_break_no_violation():
    """while(true) 내부에 break 문이 있으면 위반이 발생하지 않음 검증."""
    code = """
    void monitor() {
        while (true) {
            if (stop_flag) {
                break;
            }
        }
    }
    """
    parsed = _make_parsed(code)
    violations = ASTControlFlowChecker.run_ast_cfa_checks(parsed)

    loop_vs = [v for v in violations if v.rule_id == "CTL-AST-CFA-003"]
    assert len(loop_vs) == 0


def test_rule_engine_execute_ast_cfa_integration():
    """RuleEngine.execute_ast_cfa 통합 인터페이스 동작 검증."""
    code = """
    void main() {
        while(1) {
            // No break
        }
    }
    """
    parsed = _make_parsed(code)
    violations = RuleEngine.execute_ast_cfa(parsed)
    assert len(violations) >= 1
    assert any(v.rule_id == "CTL-AST-CFA-003" for v in violations)


def test_dp_callback_resolve_with_uses_include():
    """#uses 인클루드 파일이 있는 경우 HIGH 대신 INFO 심각도로 보정되는지 검증."""
    code = """
    #uses "std_lib.ctl"
    void main() {
        dpConnect("ext_cb", false, "System1:Valve.state");
    }
    """
    parsed = _make_parsed(code)
    violations = ASTControlFlowChecker.run_ast_cfa_checks(parsed)

    resolve_vs = [v for v in violations if v.rule_id == "CTL-AST-CFA-001"]
    assert len(resolve_vs) == 1
    assert resolve_vs[0].severity == SeverityLevel.INFO
    assert "외부 #uses 라이브러리 참조 가능성 있음" in resolve_vs[0].message


def test_rule_engine_deduplicate_violations():
    """동일 파일 동일 라인의 중복 위반 시 AST 심층 규칙 위반이 우선 병합되는지 검증."""
    from app.core.models import Violation, ViolationStatus

    v_regex = Violation(
        violation_id="V-REGEX-1",
        file_id="test.ctl",
        rule_id="CTL-REGEX-001",
        severity=SeverityLevel.HIGH,
        status=ViolationStatus.FAIL,
        line_start=10,
        line_end=10,
        message="일반 정규식 위반",
    )
    v_ast = Violation(
        violation_id="V-AST-1",
        file_id="test.ctl",
        rule_id="CTL-AST-CFA-001",
        severity=SeverityLevel.HIGH,
        status=ViolationStatus.FAIL,
        line_start=10,
        line_end=10,
        message="AST 심층 위반",
    )

    deduped = RuleEngine.deduplicate_violations([v_regex, v_ast])
    assert len(deduped) == 1
    assert deduped[0].rule_id == "CTL-AST-CFA-001"


