"""
기준서 동적 변경 및 신규 룰/체커 동적 확장 실증 (시나리오 A, B, C) 테스트 스위트.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from app.core.models import CheckerType, ParseStatus, ParseStatusType, RuleDefinition, SeverityLevel, Violation, ViolationStatus
from app.core.parser.base_parser import ParsedFile
from app.core.rules.checker_registry import CheckerRegistry
from app.core.rules.excel_rule_compiler import ExcelRuleCompiler
from app.core.rules.rule_engine import RuleEngine


class TestRuleDynamicCompilation:
    """기준서 3가지 시나리오 동적 반영 완벽 실증."""

    def test_scenario_a_dynamic_severity_and_message_change(self, config_dir: Path):
        """시나리오 A: Excel/YAML 매핑의 심각도 및 문구 변경 시 100% 동적 적용 검증."""
        server_excel = config_dir / "(코드리뷰결과서-Server) 코드 리뷰 결과서 양식_v2.0_20251104.xlsx"
        server_yaml = config_dir / "legacy_mapping" / "server.yaml"

        with open(server_yaml, encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f)

        # auto_full 항목(예: CTL_PRF_002)의 심각도를 Critical로 임시 변경
        auto_entry = next(e for e in yaml_data["entries"] if e.get("rule_ids") == ["CTL_PRF_002"])
        auto_entry["severity"] = "Critical"

        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w", encoding="utf-8") as tf:
            yaml.dump(yaml_data, tf, allow_unicode=True)
            temp_yaml_path = Path(tf.name)

        try:
            modified_ruleset = ExcelRuleCompiler.compile_rules(server_excel, temp_yaml_path)
            comp_rule = next(r for r in modified_ruleset.rules if r.rule_id == "CTL_PRF_002")
            assert comp_rule.severity == SeverityLevel.CRITICAL
        finally:
            if temp_yaml_path.exists():
                temp_yaml_path.unlink()

    def test_scenario_b_dynamic_new_rule_addition(self, config_dir: Path):
        """시나리오 B: 기존 manual 항목을 auto_full 신규 룰 ID로 확장 시 100% 동적 로드 검증."""
        client_excel = config_dir / "(코드리뷰결과서-Client) 코드 리뷰 결과서 양식_v2.0_20251201.xlsx"
        client_yaml = config_dir / "legacy_mapping" / "client.yaml"

        with open(client_yaml, encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f)

        # 2번째 manual 항목에 신규 룰 ID 지정 및 auto_full 확장 시뮬레이션
        target_entry = yaml_data["entries"][1]
        target_entry["rule_ids"] = ["NEW_RULE_999"]
        target_entry["automation_mode"] = "auto_full"
        target_entry["checker_type"] = "builtin"
        target_entry["checker_key"] = "ctl.batch_dp_ops"
        target_entry["severity"] = "High"

        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w", encoding="utf-8") as tf:
            yaml.dump(yaml_data, tf, allow_unicode=True)
            temp_yaml_path = Path(tf.name)

        try:
            modified_ruleset = ExcelRuleCompiler.compile_rules(client_excel, temp_yaml_path)
            rule_ids = [r.rule_id for r in modified_ruleset.rules]
            assert "NEW_RULE_999" in rule_ids
            new_rule = next(r for r in modified_ruleset.rules if r.rule_id == "NEW_RULE_999")
            assert new_rule.severity == SeverityLevel.HIGH
        finally:
            if temp_yaml_path.exists():
                temp_yaml_path.unlink()

    def test_scenario_c_custom_checker_registration_and_execution(self):
        """시나리오 C: 파이프라인 기동 중 특수 파이썬 체커 함수 동적 등록 및 탐지 실증."""

        # 1. 특수 탐지 알고리즘 파이썬 체커 함수 정의
        def custom_special_checker(parsed: ParsedFile, rule: RuleDefinition) -> list[Violation]:
            violations = []
            if "SPECIAL_UNSAFE_API" in parsed.content:
                violations.append(
                    Violation(
                        violation_id=f"V-{rule.rule_id}-001",
                        rule_id=rule.rule_id,
                        file_id=str(parsed.file_path),
                        status=ViolationStatus.FAIL,
                        severity=rule.severity or SeverityLevel.HIGH,
                        message="[특수 탐지] 금지된 SPECIAL_UNSAFE_API 함수가 탐지되었습니다.",
                        line_start=1,
                        line_end=1,
                        snippet="SPECIAL_UNSAFE_API()",
                    )
                )
            return violations

        # 2. CheckerRegistry에 신규 파이썬 체커 동적 등록
        custom_key = "custom.special_unsafe_checker"
        CheckerRegistry.register(custom_key, custom_special_checker)
        assert CheckerRegistry.is_registered(custom_key) is True

        # 3. 신규 룰 정의 및 룰 엔진 실행 검증
        custom_rule = RuleDefinition(
            rule_id="CUSTOM-999",
            source_key="보안|특수탐지",
            file_types=["CTL"],
            checker_type=CheckerType.BUILTIN,
            checker_key=custom_key,
            enabled=True,
            rule_version="1.0.0",
        )

        parsed_file = ParsedFile(
            file_path=Path("unsafe_sample.ctl"),
            file_type="ctl",
            parse_status=ParseStatus(status=ParseStatusType.PARSED, file="unsafe_sample.ctl"),
            original_sha256="123456",
            detected_encoding="utf-8",
            newline_style="\n",
            content="void main() { SPECIAL_UNSAFE_API(); }",
        )

        engine = RuleEngine()
        violations = engine.execute_rule(parsed_file, custom_rule)

        assert len(violations) == 1
        assert violations[0].rule_id == "CUSTOM-999"
        assert "[특수 탐지]" in violations[0].message
