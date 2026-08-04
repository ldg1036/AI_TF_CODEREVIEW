"""
CTL_RES_001 PNL 화면 초기화 이벤트 컨텍스트 예외 완화 단위 테스트.

검증 항목:
1. PNL 파일 + 화면 초기화 컨텍스트(ScopeLib::, initialize 등) => INFO 등급으로 완화
2. CTL 파일에서 dpConnect without dpDisconnect => 기존 FAIL 등급 유지 (회귀)
3. PNL 파일이더라도 초기화 컨텍스트가 없으면 => FAIL 등급 유지
4. dpDisconnect가 존재하면 => 위반 없음 (PASS)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.models import RuleDefinition, CheckerType, SeverityLevel, ViolationStatus
from app.core.parser.base_parser import ParsedFile, ParseStatus, ParseStatusType
from app.core.rules.checker_registry import check_dp_connect_pair, _is_pnl_init_context


def _make_parsed(content: str, file_type: str, file_path: str = "test_file") -> ParsedFile:
    """테스트용 ParsedFile 생성 헬퍼."""
    return ParsedFile(
        file_path=Path(file_path),
        file_type=file_type,
        content=content,
        parse_status=ParseStatus(status=ParseStatusType.PARSED),
    )


def _make_rule() -> RuleDefinition:
    """CTL_RES_001 테스트용 룰 정의 생성."""
    return RuleDefinition(
        rule_id="CTL_RES_001",
        source_key="test_source",
        file_types=["CTL", "PNL"],
        checker_type=CheckerType.BUILTIN,
        enabled=True,
        rule_version="1.0.0",
        category="리소스",
        subcategory="메모리",
        check_item="dpConnect 해제 짝 확인",
        condition="dpDisconnect 미작성 금지",
        severity=SeverityLevel.MEDIUM,
        checker_key="ctl.dp_connect_pair",
        message="dpConnect 호출에 대응하는 dpDisconnect가 명시되지 않았습니다.",
    )


class TestPnlInitContextDetection:
    """_is_pnl_init_context 유틸 함수 단위 테스트."""

    def test_scopelib_keyword_detected(self):
        content = "ScopeLib::initialize() { dpConnect(\"cb\", dp); }"
        assert _is_pnl_init_context(content) is True

    def test_initialize_keyword_detected(self):
        content = "void initialize() { dpConnect(\"cb\", dp); }"
        assert _is_pnl_init_context(content) is True

    def test_main_keyword_detected(self):
        content = "void main() { dpConnect(\"cb\", dp); }"
        assert _is_pnl_init_context(content) is True

    def test_panelonopen_keyword_detected(self):
        content = "panelOnOpen() { dpConnect(\"cb\", dp); }"
        assert _is_pnl_init_context(content) is True

    def test_no_init_keyword(self):
        content = "void processData() { dpConnect(\"cb\", dp); }"
        assert _is_pnl_init_context(content) is False

    def test_case_insensitive(self):
        content = "SCOPELIB::Initialize() { dpConnect(\"cb\", dp); }"
        assert _is_pnl_init_context(content) is True


class TestCheckDpConnectPairPnlException:
    """CTL_RES_001 PNL 화면 초기화 예외 완화 통합 테스트."""

    def test_pnl_init_context_downgraded_to_info(self):
        """PNL 화면 초기화 이벤트 내 dpConnect → INFO 등급으로 완화."""
        content = """
ScopeLib::initialize()
{
  dpConnect("callbackFn", ":System.dp1");
}
"""
        parsed = _make_parsed(content, "pnl", "test_panel.pnl")
        rule = _make_rule()
        violations = check_dp_connect_pair(parsed, rule)

        assert len(violations) == 1
        v = violations[0]
        assert v.severity == SeverityLevel.INFO, (
            f"PNL 초기화 컨텍스트에서 INFO 등급이어야 하지만 {v.severity}가 반환되었습니다."
        )
        assert v.status == ViolationStatus.MANUAL_REVIEW
        assert "PNL 화면 초기화 이벤트" in v.message or "INFO" in v.message

    def test_ctl_file_remains_fail(self):
        """CTL 파일에서 dpConnect without dpDisconnect → 기존 FAIL 등급 유지 (회귀 테스트)."""
        content = """
void processLoop()
{
  while(true) {
    dpConnect("callbackFn", ":System.dp1");
    delay(1);
  }
}
"""
        parsed = _make_parsed(content, "ctl", "server_script.ctl")
        rule = _make_rule()
        violations = check_dp_connect_pair(parsed, rule)

        assert len(violations) >= 1, "CTL 파일에서 위반이 검출되어야 합니다."
        assert all(v.status == ViolationStatus.FAIL for v in violations), (
            "CTL 파일에서 모든 위반은 FAIL 상태여야 합니다."
        )

    def test_pnl_no_init_context_remains_fail(self):
        """PNL 파일이지만 초기화 컨텍스트 없으면 → FAIL 등급 유지."""
        content = """
void processData()
{
  dpConnect("cb", ":System.dp1");
}
"""
        parsed = _make_parsed(content, "pnl", "custom_panel.pnl")
        rule = _make_rule()
        violations = check_dp_connect_pair(parsed, rule)

        assert len(violations) >= 1
        assert all(v.status == ViolationStatus.FAIL for v in violations), (
            "초기화 컨텍스트가 없는 PNL 파일에서는 FAIL 등급이어야 합니다."
        )

    def test_dp_disconnect_present_no_violation(self):
        """dpDisconnect가 존재하면 위반 없음 (PASS)."""
        content = """
ScopeLib::initialize()
{
  dpConnect("callbackFn", ":System.dp1");
}

void panelOff()
{
  dpDisconnect("callbackFn", ":System.dp1");
}
"""
        parsed = _make_parsed(content, "pnl", "test_panel.pnl")
        rule = _make_rule()
        violations = check_dp_connect_pair(parsed, rule)

        assert len(violations) == 0, "dpDisconnect가 있으면 위반이 없어야 합니다."

    def test_comment_lines_excluded(self):
        """주석 내 dpConnect는 위반으로 검출하지 않음."""
        content = """
ScopeLib::initialize()
{
  // dpConnect("callbackFn", ":System.dp1"); -- 비활성화
  int x = 1;
}
"""
        parsed = _make_parsed(content, "pnl", "test_panel.pnl")
        rule = _make_rule()
        violations = check_dp_connect_pair(parsed, rule)

        assert len(violations) == 0, "주석 내 dpConnect는 위반으로 처리되지 않아야 합니다."

    def test_multiple_dp_connect_pnl_init_all_info(self):
        """PNL 초기화 컨텍스트에서 여러 dpConnect → 모두 INFO 등급."""
        content = """
ScopeLib::initialize()
{
  dpConnect("cb1", ":System.dp1");
  dpConnect("cb2", ":System.dp2");
  dpConnect("cb3", ":System.dp3");
}
"""
        parsed = _make_parsed(content, "pnl", "multi_panel.pnl")
        rule = _make_rule()
        violations = check_dp_connect_pair(parsed, rule)

        assert len(violations) == 3
        assert all(v.severity == SeverityLevel.INFO for v in violations), (
            "PNL 초기화 컨텍스트 내 모든 dpConnect 위반은 INFO 등급이어야 합니다."
        )
