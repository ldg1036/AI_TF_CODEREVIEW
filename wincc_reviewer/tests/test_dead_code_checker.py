"""
Phase 4 Dead Code 및 미사용 변수 선언(MANUAL-015/016) 정적 분석 룰 단위 테스트.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.core.models import (
    CheckerType,
    ParseStatus,
    ParseStatusType,
    RuleDefinition,
    SeverityLevel,
)
from app.core.parser.base_parser import ParsedFile
from app.core.rules.checker_registry import CheckerRegistry


class TestDeadCodeAndUnusedChecker:
    """MANUAL-015/016 (ctl.dead_code_unused) 체커 검증."""

    @pytest.fixture
    def rule_def(self) -> RuleDefinition:
        return RuleDefinition(
            rule_id="MANUAL-015",
            source_key="client",
            file_types=["ctl"],
            checker_type=CheckerType.BUILTIN,
            enabled=True,
            rule_version="1.0.0",
            checker_key="ctl.dead_code_unused",
            severity=SeverityLevel.HIGH,
            message="Dead Code 또는 미사용 변수가 감지되었습니다.",
        )

    def test_unreachable_dead_code_detected(self, rule_def: RuleDefinition):
        content = """
        void myFunction() {
            int val = 100;
            return;
            int dead_var = val + 1; // return 이후 도달 불가능한 Dead Code
        }
        """
        parsed = ParsedFile(
            file_path=Path("test_dead.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED),
            content=content,
        )
        checker = CheckerRegistry.get("ctl.dead_code_unused")
        assert checker is not None

        violations = checker(parsed, rule_def)
        dead_violations = [v for v in violations if "return/break 이후 도달할 수 없는 Dead Code" in v.message]
        assert len(dead_violations) == 1
        assert dead_violations[0].line_start == 5

    def test_unused_variable_declaration_detected(self, rule_def: RuleDefinition):
        content = """
        void testFunc() {
            int used_var = 10;
            string unused_message = "hello"; // 선언 이후 미사용
            DebugN(used_var);
        }
        """
        parsed = ParsedFile(
            file_path=Path("test_unused.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED),
            content=content,
        )
        checker = CheckerRegistry.get("ctl.dead_code_unused")
        assert checker is not None

        violations = checker(parsed, rule_def)
        unused_violations = [v for v in violations if "단 한 번도 사용되지 않았습니다" in v.message]
        assert len(unused_violations) == 1
        assert "unused_message" in unused_violations[0].message
        assert unused_violations[0].line_start == 4

    def test_clean_code_no_violations(self, rule_def: RuleDefinition):
        content = """
        void cleanFunc() {
            int index = 0;
            index = index + 5;
            DebugN(index);
            return;
        }
        """
        parsed = ParsedFile(
            file_path=Path("test_clean.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED),
            content=content,
        )
        checker = CheckerRegistry.get("ctl.dead_code_unused")
        assert checker is not None

        violations = checker(parsed, rule_def)
        assert len(violations) == 0
