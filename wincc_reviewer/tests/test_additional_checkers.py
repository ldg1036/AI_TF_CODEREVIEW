"""
test_additional_checkers.py

신규 10대 내장 정적 체커 유닛 테스트 수트
"""

from pathlib import Path
import pytest
from app.core.models import RuleDefinition, SeverityLevel, CheckerType
from app.core.parser.ctl_parser import CTLParser
from app.core.rules.checker_registry import CheckerRegistry

class TestAdditionalCheckers:
    """신규 체커 유닛 테스트"""

    def test_dyn_array_out_of_bounds(self, tmp_path):
        fpath = tmp_path / "test_dyn.ctl"
        fpath.write_text("main() { dyn_string tags;\nstring s = tags[0]; }", encoding="utf-8")
        parsed = CTLParser().parse(fpath)
        rule = RuleDefinition(rule_id="ctl.dyn_array_out_of_bounds", source_key="R1", file_types=[".ctl"], checker_type=CheckerType.BUILTIN, rule_version="1.0", severity=SeverityLevel.HIGH, enabled=True)
        fn = CheckerRegistry.get("ctl.dyn_array_out_of_bounds")
        violations = fn(parsed, rule)
        assert len(violations) >= 1

    def test_global_var_naming_convention(self, tmp_path):
        fpath = tmp_path / "test_global.ctl"
        fpath.write_text("global int bad_global_var = 10;", encoding="utf-8")
        parsed = CTLParser().parse(fpath)
        rule = RuleDefinition(rule_id="ctl.global_var_naming_convention", source_key="R2", file_types=[".ctl"], checker_type=CheckerType.BUILTIN, rule_version="1.0", severity=SeverityLevel.MEDIUM, enabled=True)
        fn = CheckerRegistry.get("ctl.global_var_naming_convention")
        violations = fn(parsed, rule)
        assert len(violations) >= 1

    def test_sprintf_buffer_overflow_risk(self, tmp_path):
        fpath = tmp_path / "test_sprintf.ctl"
        fpath.write_text('main() { char buf[10]; sprintf(buf, "Hello %s", user_input); }', encoding="utf-8")
        parsed = CTLParser().parse(fpath)
        rule = RuleDefinition(rule_id="ctl.sprintf_buffer_overflow_risk", source_key="R3", file_types=[".ctl"], checker_type=CheckerType.BUILTIN, rule_version="1.0", severity=SeverityLevel.HIGH, enabled=True)
        fn = CheckerRegistry.get("ctl.sprintf_buffer_overflow_risk")
        violations = fn(parsed, rule)
        assert len(violations) >= 1

    def test_scada_security_exec(self, tmp_path):
        fpath = tmp_path / "test_exec.ctl"
        fpath.write_text('main() { system("ls -l /tmp"); }', encoding="utf-8")
        parsed = CTLParser().parse(fpath)
        rule = RuleDefinition(rule_id="ctl.scada_security_exec", source_key="R4", file_types=[".ctl"], checker_type=CheckerType.BUILTIN, rule_version="1.0", severity=SeverityLevel.CRITICAL, enabled=True)
        fn = CheckerRegistry.get("ctl.scada_security_exec")
        violations = fn(parsed, rule)
        assert len(violations) >= 1

    def test_magic_number(self, tmp_path):
        fpath = tmp_path / "test_magic.ctl"
        fpath.write_text("void calc() { if (x == 999) return; }", encoding="utf-8")
        parsed = CTLParser().parse(fpath)
        rule = RuleDefinition(rule_id="ctl.magic_number", source_key="R5", file_types=[".ctl"], checker_type=CheckerType.BUILTIN, rule_version="1.0", severity=SeverityLevel.MEDIUM, enabled=True)
        fn = CheckerRegistry.get("ctl.magic_number")
        violations = fn(parsed, rule)
        assert len(violations) >= 1
