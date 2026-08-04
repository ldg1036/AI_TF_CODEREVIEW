"""
고도화 정적 체커 4종 (Phase 7 ~ Phase 10) 단위 테스트 스위트.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from app.core.models import CheckerType, ParseStatus, ParseStatusType, RuleDefinition, SeverityLevel
from app.core.parser.base_parser import ParsedFile
from app.core.rules.checker_registry import (
    check_callback_error_handling,
    check_dp_in_loop,
    check_dpe_hardcoding,
    check_global_scope_shadowing,
)


class TestAdvancedCheckers:
    """고도화 정적 분석 체커 4종 검증."""

    @pytest.fixture
    def mock_rule(self) -> RuleDefinition:
        return RuleDefinition(
            rule_id="ADV-001",
            source_key="성능|고도화",
            file_types=["CTL", "PNL"],
            checker_type=CheckerType.BUILTIN,
            enabled=True,
            rule_version="1.0.0",
            severity=SeverityLevel.HIGH,
        )

    def test_dp_in_loop_detection(self, mock_rule: RuleDefinition):
        code = """void process() {
    for (int i = 0; i < 10; i++) {
        dpGet("DPE_" + i, val);
    }
}
"""
        parsed = ParsedFile(
            file_path=Path("test.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED, file="test.ctl"),
            original_sha256="abc",
            detected_encoding="utf-8",
            newline_style="\n",
            content=code,
        )
        violations = check_dp_in_loop(parsed, mock_rule)
        assert len(violations) == 1
        assert "dpGetMany" in violations[0].message

    def test_dpe_hardcoding_detection(self, mock_rule: RuleDefinition):
        code = """void init() {
    dpSet("System1:Pump01.status.value", 1);
}
"""
        parsed = ParsedFile(
            file_path=Path("test.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED, file="test.ctl"),
            original_sha256="abc",
            detected_encoding="utf-8",
            newline_style="\n",
            content=code,
        )
        violations = check_dpe_hardcoding(parsed, mock_rule)
        assert len(violations) == 1
        assert "System1:Pump01.status.value" in violations[0].message

    def test_callback_error_handling_detection(self, mock_rule: RuleDefinition):
        code = """void main() {
    dpConnect("onDataCB", "DPE1");
}

void onDataCB(string dpe, int val) {
    int x = val * 2;
}
"""
        parsed = ParsedFile(
            file_path=Path("test.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED, file="test.ctl"),
            original_sha256="abc",
            detected_encoding="utf-8",
            newline_style="\n",
            content=code,
        )
        violations = check_callback_error_handling(parsed, mock_rule)
        assert len(violations) == 1
        assert "onDataCB" in violations[0].message

    def test_global_scope_shadowing_detection(self, mock_rule: RuleDefinition):
        code = """int gCount = 100;

void run() {
    int gCount = 5;
}
"""
        parsed = ParsedFile(
            file_path=Path("test.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED, file="test.ctl"),
            original_sha256="abc",
            detected_encoding="utf-8",
            newline_style="\n",
            content=code,
        )
        violations = check_global_scope_shadowing(parsed, mock_rule)
        assert len(violations) == 1
        assert "gCount" in violations[0].message
