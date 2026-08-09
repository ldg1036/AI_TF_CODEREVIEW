"""
3단계 심층 코드리뷰 기능 종합 유닛 테스트 수트.
"""

from pathlib import Path

from app.core.accepted_risk import AcceptedRiskEntry, AcceptedRiskManager
from app.core.complexity import ComplexityAnalyzer
from app.core.cross_file_analyzer import CrossFileAnalyzer
from app.core.diff_filter import GitDiffFilter
from app.core.models import RuleDefinition, SeverityLevel, ViolationStatus
from app.core.parser.base_parser import ParsedFile
from app.core.review_summary import ReviewSummaryGenerator
from app.core.rules.excel_rule_compiler import RuleCompileResult
from app.rules.check_scada_security_exec import CheckScadaSecurityExec


def test_automation_coverage_pct():
    """자동화 커버리지 비율 계산 테스트."""
    res = RuleCompileResult(
        rules=[],
        file_sha256="abc",
        profile_version="1.0.0",
        total_count=20,
        manual_review_count=14,
        automated_count=6,
    )
    assert res.automation_coverage_pct == 30.0


def test_git_diff_filter():
    """git diff 파싱 및 변경 라인 필터링 테스트."""
    sample_diff = (
        "--- a/script.ctl\n"
        "+++ b/script.ctl\n"
        "@@ -10,3 +10,4 @@\n"
        " line1\n"
        "+line2_new\n"
        " line3\n"
    )
    diff_map = GitDiffFilter.parse_unified_diff(sample_diff)
    assert "script.ctl" in diff_map
    assert 11 in diff_map["script.ctl"]


from app.core.models import ParseStatus, ParseStatusType


def test_cross_file_analyzer():
    """교차 파일 중복 스크립트 코드 탐지 테스트."""
    ps = ParseStatus(status=ParseStatusType.PARSED)
    pf1 = ParsedFile(
        file_path=Path("p1.ctl"),
        file_type="CTL",
        parse_status=ps,
        content="void test() {\n  int a = 1;\n  int b = 2;\n  int c = 3;\n  int d = 4;\n}\n",
    )
    pf2 = ParsedFile(
        file_path=Path("p2.ctl"),
        file_type="CTL",
        parse_status=ps,
        content="void test2() {\n  int a = 1;\n  int b = 2;\n  int c = 3;\n  int d = 4;\n}\n",
    )
    violations = CrossFileAnalyzer.analyze_cross_files([pf1, pf2])
    assert len(violations) >= 1
    assert violations[0].rule_id == "CROSS_FILE_DUPLICATE"


def test_accepted_risk_manager(tmp_path: Path):
    """위험 수용 이력 관리 및 승인 상태 연동 테스트."""
    mgr_path = tmp_path / "risks.json"
    mgr = AcceptedRiskManager(storage_path=mgr_path)
    entry = AcceptedRiskEntry(
        rule_id="RULE01",
        file_path="main.ctl",
        line_number=10,
        approver="홍길동",
        reason="현장 특수 구동용 안전 검증 완료",
        approved_date="2026_08_06",
    )
    mgr.add_accepted_risk(entry)

    from app.core.models import Violation
    v = Violation(
        violation_id="V01",
        rule_id="RULE01",
        file_id="main.ctl",
        status=ViolationStatus.FAIL,
        severity=SeverityLevel.HIGH,
        message="테스트",
        line_start=10,
    )
    mgr.apply_accepted_risks([v])
    assert v.status == ViolationStatus.ACCEPTED_RISK
    assert "홍길동" in v.ai_analysis


def test_complexity_analyzer():
    """순환 복잡도 및 중첩 깊이 계산 테스트."""
    code = (
        "void main() {\n"
        "  if (a > 0) {\n"
        "    while (b < 10) {\n"
        "      if (c) { d++; }\n"
        "    }\n"
        "  }\n"
        "}\n"
    )
    res = ComplexityAnalyzer.analyze(code)
    assert res["cyclomatic_complexity"] >= 4
    assert res["max_nesting_depth"] >= 3


def test_scada_security_exec_checker():
    """SCADA 보안 체커 테스트."""
    checker = CheckScadaSecurityExec()
    rule_def = RuleDefinition(
        rule_id="SCADA_SEC_001",
        source_key="cat|sub|item",
        file_types=["CTL"],
        checker_type="builtin",
        enabled=True,
        rule_version="1.0.0",
    )
    ps = ParseStatus(status=ParseStatusType.PARSED)
    pf = ParsedFile(
        file_path=Path("unsafe.ctl"),
        file_type="CTL",
        parse_status=ps,
        content="void run() {\n  system('rm -rf /');\n}\n",
    )
    violations = checker.check(pf, rule_def)
    assert len(violations) == 1
    assert violations[0].severity == SeverityLevel.CRITICAL


def test_review_summary_generator():
    """1문단 리뷰 요약문 생성 테스트."""
    from app.core.models import Violation
    v = Violation(
        violation_id="V01",
        rule_id="RULE01",
        file_id="main.ctl",
        status=ViolationStatus.FAIL,
        severity=SeverityLevel.CRITICAL,
        message="메시지",
    )
    summary = ReviewSummaryGenerator.generate_summary([v])
    assert "총 1건의 결함" in summary
    assert "Critical 1건" in summary


