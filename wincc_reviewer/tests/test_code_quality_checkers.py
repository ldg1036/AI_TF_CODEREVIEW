"""
Phase 12 (ctl.magic_number) 및 Phase 13 (ctl.duplicated_code) 정적 체커 단위 테스트 스위트.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from app.core.models import CheckerType, ParseStatus, ParseStatusType, RuleDefinition, SeverityLevel
from app.core.parser.base_parser import ParsedFile
from app.core.rules.checker_registry import check_duplicated_code, check_magic_number


class TestCodeQualityCheckers:
    """매직 넘버 및 중복 코드 정적 체커 검증."""

    @pytest.fixture
    def mock_rule(self) -> RuleDefinition:
        return RuleDefinition(
            rule_id="QUAL-001",
            source_key="품질|고도화",
            file_types=["CTL", "PNL"],
            checker_type=CheckerType.BUILTIN,
            enabled=True,
            rule_version="1.0.0",
            severity=SeverityLevel.MEDIUM,
        )

    def test_magic_number_detection(self, mock_rule: RuleDefinition):
        code = """void main() {
    if (status == 1024) {
        dpSet("tag", 999);
    }
}
"""
        parsed = ParsedFile(
            file_path=Path("test_magic.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED, file="test_magic.ctl"),
            original_sha256="abc",
            detected_encoding="utf-8",
            newline_style="\n",
            content=code,
        )
        violations = check_magic_number(parsed, mock_rule)
        assert len(violations) >= 1
        assert "1024" in violations[0].message or "999" in violations[0].message

    def test_duplicated_code_detection(self, mock_rule: RuleDefinition):
        code = """void funcA() {
    int a = 1;
    int b = 2;
    int c = a + b;
    string msg = "hello";
    dpSet("tagA", c);
}

void funcB() {
    int a = 1;
    int b = 2;
    int c = a + b;
    string msg = "hello";
    dpSet("tagA", c);
}
"""
        parsed = ParsedFile(
            file_path=Path("test_dup.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED, file="test_dup.ctl"),
            original_sha256="abc",
            detected_encoding="utf-8",
            newline_style="\n",
            content=code,
        )
        violations = check_duplicated_code(parsed, mock_rule)
        assert len(violations) >= 1
        assert "중복" in violations[0].message
